"""The mp4kit command line: one cmd_* per subcommand."""
import argparse
from pathlib import Path
from typing import Optional


def hexdump(data, start, length):
    """Hex bytes from `start`, 16 per line, lowercase pairs, no offset column."""
    chunk = data[start:start + length]
    rows = [chunk[i:i + 16] for i in range(0, len(chunk), 16)]
    return "\n".join(" ".join(f"{b:02x}" for b in row) for row in rows)


def cmd_hex(args):
    """`hex FILE [--at N] [--len N]`: print bytes of the file as hex."""
    with open(args.file, "rb") as f:
        print(hexdump(f.read(), args.at, args.len))
    return 0


def cmd_nals(args):
    """`nals FILE --from N --to N`: list the length-prefixed NAL units in that byte range."""
    from . import nal
    with open(args.file, "rb") as f:
        contents = f.read()
    units = nal.iter_length_prefixed(contents, args.start, args.end)
    for index, (offset, unit) in enumerate(units, 1):
        unit_type = nal.nal_header(unit[0])[2]
        name = nal.NAL_TYPES.get(unit_type, "?")
        print(index, offset, len(unit), unit_type, name)
    return 0


def cmd_sps(args):
    """`sps FILE`: print the profile, level, picture size and entropy coder from the SPS and PPS, read from the
    first video track's avcC (moov/trak/mdia/minf/stbl/stsd/avc1/avcC)."""
    from . import boxes, nal, tables
    data = boxes.read_mp4(args.file)
    avcc = boxes.find(boxes.walk(data), "moov/trak/mdia/minf/stbl/stsd/avc1/avcC")
    if avcc is None:
        print("error: no moov/trak/mdia/minf/stbl/stsd/avc1/avcC box")
        return 1
    config = tables.read_avcc(data, avcc)
    sps = nal.parse_sps(config["SPS"][0])
    pps = nal.parse_pps(config["PPS"][0])
    width, height = nal.picture_size(sps)
    coder = "CABAC" if pps["entropy_coding_mode_flag"] == 1 else "CAVLC"
    print(f"profile {sps['profile_idc']} level {sps['level_idc']} {width}x{height} {coder}")
    return 0


def cmd_annexb(args):
    """`annexb FILE -o OUT`: write SPS, PPS and the slices as an Annex B .h264 file."""
    from . import nal
    with open(args.file, "rb") as f:
        contents = f.read()
    sps, pps = nal._avcc_params_stopgap(contents)
    start, end = nal._mdat_range_stopgap(contents)  # a stopgap until cmd_annexb is next extended
    slices = [unit for _, unit in nal.iter_length_prefixed(contents, start, end)]
    stream = nal.to_annexb([sps, pps] + slices)
    with open(args.out, "wb") as f:
        f.write(stream)
    print(f"wrote {len(slices) + 2} NAL units (SPS, PPS, {len(slices)} slices), {len(stream)} bytes")
    return 0


def cmd_boxes(args):
    """`boxes FILE`: print each top-level box (type, start, size, any header not 8 bytes); ftyp prints its brands."""
    from . import boxes
    with open(args.file, "rb") as f:
        contents = f.read()
    try:
        for box in boxes.iter_boxes(contents, 0, len(contents)):
            if box.type == "ftyp":
                f = boxes.decode(contents, box)
                print(f"ftyp: {f['major']} {f['minor']} [{', '.join(f['brands'])}]")
            else:
                print(f"{box.type} {box.start} {box.size}" + ("" if box.header == 8 else f" (header {box.header})"))
    except boxes.BoxError as e:
        print(f"error: {e}")
        return 1
    return 0


def cmd_dump(args):
    """`dump FILE [--find TYPE] [--pcm]`: print the box tree, indented by depth, or only the boxes of one type by
    their path, each with any decoded fields; or, with --pcm, each sound track's PCM arithmetic."""
    from . import boxes
    from . import audio, tables  # noqa: F401  (importing them registers their readers in boxes.DECODERS)
    data = boxes.read_mp4(args.file)
    try:
        tree = boxes.walk(data)
        _dump_view(data, tree, args)
    except ValueError as e:         # a BoxError, or an edit list with no edit that plays (episode 22)
        print(f"error: {e}")
        return 1
    if not any(b.type == "moov" for b in tree):
        print("no moov box")
    return 0


def _dump_view(data, tree, args):
    """What dump prints: the box tree, the boxes of one type (--find; elst adds each sound track's priming), or the
    sound arithmetic (--pcm)."""
    if args.pcm:
        _print_pcm(data, tree)
    elif args.find is None:
        _print_tree(data, tree, 0)
    elif _print_found(data, tree, args.find, "") == 0:
        print(f"no {args.find} box")
    elif args.find == "elst":
        _print_priming(data, tree)


def _print_pcm(data, tree):
    """--pcm, five lines a sound track: its sample rate, channels and bits; its AAC frames of 1,024 samples; what
    its length would weigh as raw PCM; what its AAC frames weigh (stsz); and the same sums for one second."""
    from . import audio
    tracks = _sound_tracks(data, tree)
    for number, entry, rate, channels, bits, seconds, sizes, _ in tracks:
        pcm, aac = audio.pcm_bytes(seconds, rate, channels, bits), sum(sizes)
        second, aac_second = audio.pcm_bytes(1, rate, channels, bits), round(aac / seconds)
        print(f"track {number} soun {entry}: {rate} samples/s (mdhd), channelcount {channels}, samplesize {bits}")
        print(f"{len(sizes)} AAC frames (stsz) of 1024 samples, each {audio.frame_seconds(rate) * 1000:.1f} ms")
        print(f"raw PCM: {seconds:g} s (tkhd) x {rate} x {channels} channel{'s' * (channels != 1)} x {bits // 8} bytes"
              f" = {pcm} bytes")
        print(f"AAC in the file: {aac} bytes (stsz), {pcm / aac:.1f} times smaller")
        print(f"one second: {second} bytes of PCM, {aac_second} of AAC; AAC saves {second - aac_second} bytes")
    if not tracks:
        print("no sound track with samples")


def _sound_tracks(data, tree):
    """Each sound track (hdlr soun) with samples in its stsz: its number (from 1, in file order), its sample entry's
    type, the sample rate (its mdhd clock), channelcount and samplesize (read_audio_entry), its length in seconds
    (tkhd, on the movie's clock), its sample sizes and its trak box."""
    from . import boxes, tables, timing
    found = []
    for number, trak in enumerate(boxes.find_all(tree, "moov/trak"), 1):
        if tables.read_hdlr(data, boxes.find(trak.children, "mdia/hdlr"))["handler_type"] != "soun":
            continue
        entry = boxes.find(trak.children, "mdia/minf/stbl/stsd").children[0]
        sizes = tables.read_stsz(data, boxes.find(trak.children, "mdia/minf/stbl/stsz"))
        rate = tables.read_mdhd(data, boxes.find(trak.children, "mdia/mdhd"))["timescale"]
        length = tables.read_tkhd(data, boxes.find(trak.children, "tkhd"))["duration"]
        movie = tables.read_mvhd(data, boxes.find(tree, "moov/mvhd"))["timescale"]
        if sizes:
            fields = tables.read_audio_entry(data, entry)
            found.append((number, entry.type, rate, fields["channelcount"], fields["samplesize"],
                          timing.seconds(length, movie), sizes, trak))
    return found


def _print_priming(data, tree):
    """After --find elst, three lines a sound track: the warm-up its entrance timer skips (priming, in samples and
    ms), what the edit plays out of the track (edit_window, mdhd), and its roll slip (sgpd) with the samples it
    covers (sbgp)."""
    from . import audio, boxes, tables
    movie = tables.read_mvhd(data, boxes.find(tree, "moov/mvhd"))["timescale"]
    for number, entry, rate, *_, sizes, trak in _sound_tracks(data, tree):
        elst = tables.read_elst(data, boxes.find(trak.children, "edts/elst"))
        stbl = boxes.find(trak.children, "mdia/minf/stbl").children
        sgpd, sbgp = (boxes.decode(data, b) if b else {} for b in (boxes.find(stbl, "sgpd"), boxes.find(stbl, "sbgp")))
        skip, track = audio.priming(elst), tables.read_mdhd(data, boxes.find(trak.children, "mdia/mdhd"))["seconds"]
        print(f"track {number} soun: priming {skip} samples (elst media_time), {skip / rate * 1000:.1f} ms at {rate}/s")
        if elst:
            start, length = audio.edit_window(elst, rate, movie)
            print(f"track {number} soun: plays {length:.3f} s from {start:.3f} s, of {track:.3f} s in the track (mdhd)")
        covered = sum(n for n, index in sbgp.get("entries", []) if index)
        print(f"track {number} soun: {sgpd.get('grouping_type', 'no')} slip {sgpd.get('entries', [])} (sgpd) on "
              f"{covered} of {len(sizes)} samples (sbgp)")


def cmd_samples(args):
    """`samples FILE [--track N] [--pts]`: print a track's sample table, one sample a line, its columns in lookup
    order: decode time (stts), keyframe (stss), offset (stsc + stco), size (stsz). Tracks count from 1 in file order.
    `--pts` prints dts and pts on the movie's timeline (ctts and the edit list applied, as ffprobe prints them)
    and each sample's place in display order."""
    from . import boxes, tables
    data = boxes.read_mp4(args.file)
    traks = boxes.find_all(boxes.walk(data), "moov/trak")
    if not 1 <= args.track <= len(traks):
        print(f"error: no track {args.track}, the file has {len(traks)}")
        return 1
    trak = traks[args.track - 1]
    handler = tables.read_hdlr(data, boxes.find(trak.children, "mdia/hdlr"))["handler_type"]
    timescale = tables.read_mdhd(data, boxes.find(trak.children, "mdia/mdhd"))["timescale"]
    samples = tables.sample_table(data, trak)
    print(f"track {args.track} {handler}, timescale {timescale}, {len(samples)} samples")
    print("sample dts pts display key offset size" if args.pts else "sample dts key offset size")
    for s, times in zip(samples, _time_columns(data, trak, samples, args.pts)):
        print(s.number, *times, "K" if s.key else "-", s.offset, s.size)
    return 0


def _time_columns(data, trak, samples, pts):
    """Each sample's time columns: its dts; with `--pts` its dts and pts with the edit list applied to both (Do Cats
    Purr: DTS, CTS, PTS), and its place in display order (by cts)."""
    if not pts:
        return [(s.dts,) for s in samples]
    from . import boxes, tables, timing
    elst = tables.read_elst(data, boxes.find(trak.children, "edts/elst"))
    clocks = (tables.read_mdhd(data, boxes.find(trak.children, "mdia/mdhd"))["timescale"],
              tables.read_mvhd(data, boxes.find(boxes.walk(data), "moov/mvhd"))["timescale"])
    dts = timing.presentation_times([s.dts for s in samples], elst, *clocks)
    pts = timing.presentation_times([s.cts for s in samples], elst, *clocks)
    shown = {s.number: place for place, s in enumerate(sorted(samples, key=lambda s: s.cts), 1)}
    return [(d, p, shown[s.number]) for s, d, p in zip(samples, dts, pts)]


def cmd_frame(args):
    """`frame FILE --at MS [--out FRAME.h264]`: the whole route, front door to parcel. In the first video track,
    find the sample on screen at --at milliseconds (sample_at, on the presentation timeline), walk back to the
    keyframe it is decoded from (sync_before), and with --out write SPS + PPS + the samples from that keyframe to
    it, in decode order, as an Annex B stream a decoder can play."""
    from . import boxes, timing
    data = boxes.read_mp4(args.file)
    try:
        trak, samples, pts, t = _frame_route(data, args.at)
        n = timing.sample_at(pts, t)
        key = timing.sync_before([s.number for s in samples if s.key], n)
        stream = _annexb_samples(data, trak, samples[key - 1:n]) if args.out else b""
    except (boxes.BoxError, ValueError) as e:
        print(f"error: {e}")
        return 1
    _print_route(args.at, t, samples, pts, key, n)
    if args.out:
        Path(args.out).write_bytes(stream)
        print(f"wrote SPS, PPS and samples {key} to {n} as Annex B, {len(stream)} bytes")
    return 0


def _print_route(at_ms, t, samples, pts, key, n):
    """The route as two lines: the sample on screen at the time, where it lies, and the walk back to its keyframe;
    the decoder shows the pictures in display order, so say which of them the target is."""
    s, shown = samples[n - 1], sum(p <= pts[n - 1] for p in pts[key - 1:n])
    print(f"{at_ms} ms = {t} ticks: on screen is sample {n} (pts {pts[n - 1]}, offset {s.offset}, {s.size} bytes)")
    print(f"walk back to keyframe {key}: decode samples {key} to {n}; sample {n} is picture {shown} of "
          f"{n - key + 1} in display order")


def _frame_route(data, at_ms):
    """Front door to time drawer: the first video track, its samples, their presentation times (the edit list
    applied), and --at in the track's ticks. No moov: the file was cut before it was written."""
    from . import boxes, tables
    tree = boxes.walk(data)
    if boxes.find(tree, "moov") is None:
        raise ValueError("no moov box (moov atom not found): the file is truncated")
    video = [t for t in boxes.find_all(tree, "moov/trak")
             if tables.read_hdlr(data, boxes.find(t.children, "mdia/hdlr"))["handler_type"] == "vide"]
    if not video:
        raise ValueError("no video track")
    mvhd = tables.read_mvhd(data, boxes.find(tree, "moov/mvhd"))
    if not 0 <= at_ms * mvhd["timescale"] < mvhd["duration"] * 1000:
        raise ValueError(f"--at {at_ms} ms is outside the movie, which lasts {mvhd['seconds'] * 1000:g} ms")
    samples = tables.sample_table(data, video[0])
    pts = [p for _, p, _ in _time_columns(data, video[0], samples, True)]
    timescale = tables.read_mdhd(data, boxes.find(video[0].children, "mdia/mdhd"))["timescale"]
    return video[0], samples, pts, at_ms * timescale // 1000


def _annexb_samples(data, trak, samples):
    """The parcels as a decoder wants them: SPS and PPS from avcC, then each sample's NAL units with their length
    labels swapped for start codes (Annex B, episode 5)."""
    from . import boxes, nal, tables
    avcc = boxes.find(trak.children, "mdia/minf/stbl/stsd/avc1/avcC")
    if avcc is None:
        raise ValueError("--out writes H.264 only, and this track has no avc1/avcC")
    config = tables.read_avcc(data, avcc)
    size = config["lengthSizeMinusOne"] + 1
    units = [u for s in samples for _, u in nal.iter_length_prefixed(data, s.offset, s.offset + s.size, size)]
    return nal.to_annexb(config["SPS"] + config["PPS"] + units)


def _show(value):
    """A field as dump prints it: bytes as hex digits (in a list too), anything else as Python prints it."""
    if isinstance(value, list):
        return [_show(v) for v in value]
    return value.hex() if isinstance(value, bytes) else value


def _print_tree(data, tree, depth):
    """Print each box of `tree` at `depth` (two spaces a level), then its children one level deeper."""
    from . import boxes
    for b in tree:
        fields = "".join(f" {k}={_show(v)}" for k, v in boxes.decode(data, b).items())
        print(f"{'  ' * depth}{b.type} {b.start} {b.size}{fields}")
        _print_tree(data, b.children, depth + 1)


def _print_found(data, tree, box_type, parent):
    """Print every box of `box_type` anywhere in `tree` as `path start size` and its fields; return how many."""
    from . import boxes
    count = 0
    for b in tree:
        path = parent + b.type
        if b.type == box_type:
            fields = "".join(f" {k}={_show(v)}" for k, v in boxes.decode(data, b).items())
            print(f"{path} {b.start} {b.size}{fields}")
            count = count + 1
        count = count + _print_found(data, b.children, box_type, path + "/")
    return count


def _add_hex(sub):
    """Register the `hex` command."""
    h = sub.add_parser("hex", help="print bytes as hex")
    h.add_argument("file")
    h.add_argument("--at", type=int, default=0, help="byte offset to start at (default 0)")
    h.add_argument("--len", type=int, default=64, help="how many bytes to show (default 64)")
    h.set_defaults(func=cmd_hex)


def _add_nals(sub):
    """Register the `nals` command."""
    n = sub.add_parser("nals", help="list length-prefixed NAL units in a byte range")
    n.add_argument("file", help="the MP4 file to read")
    n.add_argument("--from", dest="start", type=int, required=True, help="byte offset where the units start")
    n.add_argument("--to", dest="end", type=int, required=True, help="byte offset where the units end")
    n.set_defaults(func=cmd_nals)


def _add_sps(sub):
    """Register the `sps` command."""
    s = sub.add_parser("sps", help="show the picture size and settings from the SPS and PPS")
    s.add_argument("file", help="the MP4 file to read")
    s.set_defaults(func=cmd_sps)


def _add_annexb(sub):
    """Register the `annexb` command."""
    a = sub.add_parser("annexb", help="write the video as an Annex B .h264 file")
    a.add_argument("file", help="the MP4 file to read")
    a.add_argument("-o", dest="out", required=True, help="the .h264 file to write")
    a.set_defaults(func=cmd_annexb)


def _add_boxes(sub):
    """Register the `boxes` command."""
    b = sub.add_parser("boxes", help="list the top-level boxes")
    b.add_argument("file", help="the MP4 file to read")
    b.set_defaults(func=cmd_boxes)


def _add_dump(sub):
    """Register the `dump` command."""
    d = sub.add_parser("dump", help="print the box tree")
    d.add_argument("file", help="the MP4 file to read")
    d.add_argument("--find", metavar="TYPE", help="print only the boxes of this type, by their path")
    d.add_argument("--pcm", action="store_true", help="each sound track's size as raw PCM against its AAC frames")
    d.set_defaults(func=cmd_dump)


def _add_samples(sub):
    """Register the `samples` command."""
    s = sub.add_parser("samples", help="print a track's sample table")
    s.add_argument("file", help="the MP4 file to read")
    s.add_argument("--track", type=int, default=1, help="which track, counted from 1 in file order (default 1)")
    s.add_argument("--pts", action="store_true", help="dts and pts with the edit list applied, and the display order")
    s.set_defaults(func=cmd_samples)


def _add_frame(sub):
    """Register the `frame` command."""
    f = sub.add_parser("frame", help="find the frame on screen at a time, and extract it")
    f.add_argument("file", help="the MP4 file to read")
    f.add_argument("--at", type=int, required=True, help="the time, in milliseconds from the start of the movie")
    f.add_argument("--out", help="write the keyframe-to-frame samples here as an Annex B .h264 stream")
    f.set_defaults(func=cmd_frame)


def main(argv: Optional[list] = None) -> int:
    """Parse the command line and run the chosen subcommand."""
    p = argparse.ArgumentParser(prog="mp4kit")
    sub = p.add_subparsers(dest="cmd", required=True)
    for add in (_add_hex, _add_nals, _add_sps, _add_annexb, _add_boxes, _add_dump, _add_samples,
                _add_frame):
        add(sub)
    args = p.parse_args(argv)
    return args.func(args)
