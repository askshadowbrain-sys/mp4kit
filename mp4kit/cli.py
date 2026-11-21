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
    and each sample's place in display order. (`--rewrite-check` runs cmd_rewrite_check instead, episode 26.)"""
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


def cmd_rewrite_check(args):
    """`samples FILE --rewrite-check`: the workshop's test. Each track's stbl written back from its samples
    (_rewrite_track), then compared with the file's box by box (_compare_stbl). Last, whether every table written is
    the file's, byte for byte."""
    from . import boxes, tables
    data = boxes.read_mp4(args.file)
    try:
        tree = boxes.walk(data)
        tracks = tables.read_tracks(data, tree)
        if not tracks:
            raise boxes.BoxError("no tracks: the file has no moov/trak to write back")
    except boxes.BoxError as e:
        print(f"error: {e}")
        return 1
    print("each track's stbl written back from its samples (mux.write_stbl), box by box\nbox bytes written same")
    same = [_rewrite_track(data, n, track, trak)
            for n, (track, trak) in enumerate(zip(tracks, boxes.find_all(tree, "moov/trak")), 1)]
    print(f"every table written is the file's, byte for byte: {'yes' if all(same) else 'no'}")
    return 0


def _rewrite_track(data, n, track, trak):
    """One track's stbl, written by mux.write_stbl from its samples, the file's own stsd (copied) and its chunks
    (tables.chunk_list: each chunk's offset and sample count), then compared (_compare_stbl)."""
    from . import boxes, mux, tables
    stbl = boxes.find(trak.children, "mdia/minf/stbl")
    chunks = tables.chunk_list([track])
    counts = [c[3] for c in chunks]
    print(f"track {n} {track.handler}: {len(track.samples)} samples in {len(chunks)} chunks, "
          f"{len(mux.stsc_rules(counts))} stsc rules")
    stsd = boxes.find(stbl.children, "stsd")
    written = mux.write_stbl(track, data[stsd.start:stsd.end], [c[0] for c in chunks], counts)
    return _compare_stbl({b.type: bytes(data[b.start:b.end]) for b in stbl.children},
                         {b.type: written[b.start:b.end] for b in boxes.walk(written)[0].children})


def _compare_stbl(old, new):
    """One track's rows: each box of the file's stbl (`old`, type → bytes) against the written stbl's (`new`): its
    bytes, the bytes written, and the same or not ("copied": the stsd went in as it was; "not written": a box
    write_stbl does not make: sgpd, sbgp, sdtp, senc, or a co64 whose offsets fit in stco). Then the stbl: if it
    differs, is it the same boxes without the ones not written, or in another order? True if every table written is
    the file's."""
    from . import boxes
    for kind in [*old, *(k for k in new if k not in old)]:
        a, b = old.get(kind), new.get(kind)
        same = ("copied" if kind == "stsd" else "yes" if a == b else "not written" if b is None
                else "not in the file" if a is None else "no")
        print(kind, len(a) if a else "-", len(b) if b else "-", same)
    whole, written = boxes.box("stbl", *old.values()), boxes.box("stbl", *new.values())
    left_out, moved = " ".join(k for k in old if k not in new), [k for k in old if k in new] != list(new)
    kept = boxes.box("stbl", *(old.get(k, b"") for k in new))   # the file's boxes that were written, in write order
    same = ("yes" if whole == written else "no" if kept != written else "the same boxes"
            + (f" without {left_out}" if left_out else "") + (" in another order" if moved else ""))
    print("stbl", len(whole), len(written), same)
    return all(old.get(k) == new[k] for k in new)


def cmd_header_check(args):
    """`dump FILE --rewrite-check`: the workshop's second test (episode 28). ftyp, mvhd and each track's header boxes,
    written back from the fields mp4kit reads (mux.write_*) and compared with the file's, box by box. Last, how many
    boxes were written and how many of them are the file's, byte for byte."""
    from . import boxes
    data = boxes.read_mp4(args.file)
    try:
        tree = boxes.walk(data)
        rows = _rewrite_movie(data, tree)
    except boxes.BoxError as e:
        print(f"error: {e}")
        return 1
    for n, trak in enumerate(boxes.find_all(tree, "moov/trak"), 1):
        rows += _rewrite_track_headers(data, n, trak)
    written = [r for r in rows if r not in ("not written", "none in the file")]
    print(f"boxes written {len(written)}, the file's byte for byte {written.count('yes')}")
    return 0


def _rewrite_movie(data, tree):
    """The nameplate (ftyp) and the wall clock (mvhd), written from their fields and compared; a BoxError if the file
    has neither."""
    from . import boxes, mux, tables
    ftyp, mvhd = boxes.find(tree, "ftyp"), boxes.find(tree, "moov/mvhd")
    if ftyp is None or mvhd is None:
        raise boxes.BoxError("no ftyp or no moov/mvhd: no headers to write back")
    print("each header box written back from its fields (mux.write_*), box by box\nbox bytes written same")
    m = tables.read_mvhd(data, mvhd)
    return [_compare_box(data, "ftyp", ftyp, mux.write_ftyp(**boxes.read_ftyp(data, ftyp))),
            _compare_box(data, "mvhd", mvhd, mux.write_mvhd(m["timescale"], m["duration"], m["next_track_ID"]))]


def _rewrite_track_headers(data, n, trak):
    """One track's header boxes, each written from the fields its reader gives, then compared (_compare_box). tkhd's
    alternate group is read where it sits, 50 bytes before the box's end. vmhd and smhd are the only media headers
    written (subs' nmhd and the chapter track's gmhd are not)."""
    from . import boxes, mux, tables
    c = trak.children
    tkhd, mdhd, hdlr = boxes.find(c, "tkhd"), boxes.find(c, "mdia/mdhd"), boxes.find(c, "mdia/hdlr")
    k, d, h = tables.read_tkhd(data, tkhd), tables.read_mdhd(data, mdhd), tables.read_hdlr(data, hdlr)
    elst, minf, kind = boxes.find(c, "edts/elst"), boxes.find(c, "mdia/minf"), h["handler_type"]
    edits, media, group = tables.read_elst(data, elst), minf.children[0], boxes.u16(data, tkhd.end - 50)
    print(f"track {n} {kind}")
    return [_compare_box(data, "tkhd", tkhd, mux.write_tkhd(k["track_ID"], k["duration"], int(k["width"]),
                                                            int(k["height"]), int(k["volume"]), group)),
            _compare_box(data, "elst", elst, mux.write_elst(*edits[0][:2]) if len(edits) == 1 else None),
            _compare_box(data, "mdhd", mdhd, mux.write_mdhd(d["timescale"], d["duration"], d["language"])),
            _compare_box(data, "hdlr", hdlr, mux.write_hdlr(kind, h["name"])),
            _compare_box(data, media.type, media, mux.write_media_header(kind) if kind in ("vide", "soun") else None),
            _compare_box(data, "dinf", boxes.find(minf.children, "dinf"), mux.write_dinf()),
            *_rewrite_entry(data, minf)]


def _rewrite_entry(data, minf):
    """The tray's first sheet: an avc1 and its avcC written from their fields and compared; any other sample entry
    (mp4a comes in episode 29) is not written."""
    from . import boxes, mux, tables
    entry = tables.read_stsd(data, boxes.find(minf.children, "stbl/stsd"))[0]
    if entry.type != "avc1":
        return [_compare_box(data, entry.type, entry, None)]
    avcc = boxes.find(entry.children, "avcC")
    a, v = tables.read_avcc(data, avcc), tables.read_visual_entry(data, entry)
    written = mux.write_avcc(a["SPS"][0], a["PPS"][0])
    return [_compare_box(data, "avcC", avcc, written),
            _compare_box(data, "avc1", entry, mux.write_avc1(v["width"], v["height"], written))]


def _compare_box(data, kind, box, new):
    """One row: the file's box against the one written (`new`; None: not written). Its bytes, the bytes written, and
    the same or not: an avc1 that differs is checked again as _bare_avc1; any other box of the same length that
    differs shows the first and last of its bytes that differ."""
    old = bytes(data[box.start:box.end]) if box else None
    same = "no"
    if old is None or new is None:
        same = "not written" if old else "none in the file"
    elif old == new:
        same = "yes"
    elif kind == "avc1" and _bare_avc1(data, box) == new:
        same = "the same without " + ", ".join(["its compressorname"] + [b.type for b in box.children
                                                                         if b.type != "avcC"])
    elif len(old) == len(new):
        at = [i for i, (x, y) in enumerate(zip(old, new)) if x != y]
        same = f"no (bytes {at[0]} to {at[-1]} differ)"
    print(kind, len(old) if old else "-", len(new) if new else "-", same)
    return same


def _bare_avc1(data, box):
    """The file's avc1 as write_avc1 would write it: its compressorname blanked (32 zero bytes) and only its avcC kept
    (no pasp, btrt)."""
    from . import boxes
    sheet = bytearray(data[box.payload:box.payload + 78])
    sheet[42:74] = bytes(32)
    avcc = boxes.find(box.children, "avcC")
    return boxes.box(box.type, sheet, data[avcc.start:avcc.end])


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


def cmd_extract(args):
    """`extract FILE --track N -o OUT`: list the corridors, then copy one track's parcels out of the House into a plain
    stream, without decoding them: H.264 (avc1) as Annex B, AAC (mp4a) as ADTS, text (tx3g, text) as SRT. Tracks
    count from 1 in file order; a signpost (tref) names tracks by track_ID."""
    from . import boxes, tables
    data = boxes.read_mp4(args.file)
    tracks = tables.read_tracks(data, boxes.walk(data))
    for n, t in enumerate(tracks, 1):
        signs = "".join(f", {kind} -> track_ID {ids}" for kind, ids in t.tref.items())
        print(f"track {n}: track_ID {t.id} {t.handler} {t.entry['type']}, {len(t.samples)} samples{signs}")
    try:
        track, form, stream = _plain_stream(data, tracks, args.track)
    except ValueError as e:
        print(f"error: {e}")
        return 1
    Path(args.out).write_bytes(stream)
    print(f"wrote track {args.track} as {form}: {len(track.samples)} samples ({sum(s.size for s in track.samples)} "
          f"bytes) -> {len(stream)} bytes")
    return 0


def _plain_stream(data, tracks, n):
    """Track n (from 1), the stream's form and its bytes, written by the WRITERS entry for its sample entry's type."""
    if not 1 <= n <= len(tracks):
        raise ValueError(f"no track {n}, the file has {len(tracks)}")
    track = tracks[n - 1]
    if track.entry["type"] not in WRITERS or not track.samples:
        raise ValueError(f"track {n} ({track.entry['type']}, {len(track.samples)} samples): no plain stream for it")
    form, write = WRITERS[track.entry["type"]]
    return track, form, write(data, track)


def _annexb_track(data, track):
    """Every sample's NAL units, length labels swapped for start codes, avcC's SPS and PPS before each keyframe."""
    from . import nal
    config = track.entry["avcC"]
    size, params = config["lengthSizeMinusOne"] + 1, config["SPS"] + config["PPS"]
    units = lambda s: [u for _, u in nal.iter_length_prefixed(data, s.offset, s.offset + s.size, size)]
    return b"".join(nal.annexb_sample(units(s), params) for s in track.samples)


def _adts_track(data, track):
    """Every AAC frame behind its 7-byte ADTS header, built from the esds AudioSpecificConfig (episodes 20, 21)."""
    from . import audio
    asc = audio.parse_asc(track.entry["esds"]["ASC"])
    return b"".join(audio.adts_header(asc, s.size) + data[s.offset:s.offset + s.size] for s in track.samples)


def _srt_track(data, track):
    """Text samples as SRT cues: a sample is a 2-byte length, then that many bytes of text (an empty one is a gap,
    and gets no cue); a cue lasts until the next sample starts, the last one until the track ends (mdhd)."""
    from . import boxes
    ends, cues = [s.dts for s in track.samples[1:]] + [track.duration], []
    for s, end in zip(track.samples, ends):
        text = bytes(data[s.offset + 2:s.offset + 2 + boxes.u16(data, s.offset)]) if s.size >= 2 else b""
        if text:
            cues.append(f"{len(cues) + 1}\n{_srt_time(s.dts, track.timescale)} --> "
                        f"{_srt_time(end, track.timescale)}\n{text.decode('utf-8')}\n\n")
    return "".join(cues).encode("utf-8")


def _srt_time(ticks, timescale):
    """Ticks on a track's clock as SRT's hours:minutes:seconds,milliseconds (900,000 at 1,000,000/s = 00:00:00,900)."""
    ms = ticks * 1000 // timescale
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


WRITERS = {"avc1": ("Annex B", _annexb_track), "mp4a": ("ADTS", _adts_track), "tx3g": ("SRT", _srt_track),
           "text": ("SRT", _srt_track)}


def cmd_chunks(args):
    """`chunks FILE`: the basement aisle, drawn. Every chunk in mdat in file order: its offset (stco), track, first
    sample and sample count (stsc), bytes (stsz), and its start and length in seconds on the movie's timeline (stts,
    less the edit list's media_time); then each track's totals, and whether mux.interleave's zipper (0.5 s chunks)
    plans the same order. Tracks count from 1 in file order, chunks and samples from 1."""
    from . import boxes, mux, tables
    data = boxes.read_mp4(args.file)
    try:
        tracks = tables.read_tracks(data, boxes.walk(data))
    except boxes.BoxError as e:
        print(f"error: {e}")
        return 1
    chunks = tables.chunk_list(tracks)
    if not chunks:
        print(f"error: no chunks: the moov's tables list no samples ({len(tracks)} tracks)")
        return 1
    _print_chunks(tracks, chunks)
    same = mux.interleave(tracks) == [c[1:] for c in chunks]
    print(f"interleave (0.5 s chunks): {'the same' if same else 'a different'} order")
    return 0


def _print_chunks(tracks, chunks):
    """The map, one chunk a line; then each track's chunks, samples and bytes, and the fewest and most samples it puts
    in a chunk."""
    rows = [(offset, n, first, count, *_chunk_columns(tracks[n - 1], first, count))
            for offset, n, first, count in chunks]
    print(f"{len(chunks)} chunks in file order: "
          + ", ".join(f"track {n} {t.handler} {sum(c[1] == n for c in chunks)}" for n, t in enumerate(tracks, 1)))
    print("chunk offset track first samples bytes start lasts")
    for i, row in enumerate(rows, 1):
        print(i, *row[:5], f"{row[5]:.4f}", f"{row[6]:.4f}")
    for n, t in enumerate(tracks, 1):
        counts = [r[3] for r in rows if r[1] == n]
        print(f"track {n} {t.handler}: {len(counts)} chunks, {len(t.samples)} samples, "
              f"{sum(r[4] for r in rows if r[1] == n)} bytes, {min(counts, default=0)} to {max(counts, default=0)} "
              f"samples a chunk")


def _chunk_columns(track, first, count):
    """A chunk's bytes, its start on the movie's timeline in seconds (mux.timeline) and how long its samples last:
    from its first sample's decode time to the next sample's, or to the track's end (mdhd) after the last sample."""
    from . import mux
    samples = track.samples[first - 1:first - 1 + count]
    end = track.samples[first - 1 + count].dts if first - 1 + count < len(track.samples) else track.duration
    return sum(s.size for s in samples), float(mux.timeline(track)[first - 1]), (end - samples[0].dts) / track.timescale


def cmd_packets(args):
    """`packets FILE`: the projection booth's first belt. Every sample as a player's packet, in the order the reader
    hands them to the decoders (timing.play_order: by dts_time), in ffprobe's vocabulary (-show_packets): stream,
    dts_time, pts_time, dts, pts, duration, size, pos, key; and where each is shown in its stream (by pts). Then
    whether that order is the file's (by pos), and per stream how far its decoder reorders (timing.reorder_depth)."""
    from . import boxes, tables, timing
    data = boxes.read_mp4(args.file)
    try:
        tracks = tables.read_tracks(data, boxes.walk(data))
    except boxes.BoxError as e:
        print(f"error: {e}")
        return 1
    packets = timing.packets(tracks)
    if not packets:
        print(f"error: no packets: the moov's tables list no samples ({len(tracks)} tracks)")
        return 1
    order = timing.play_order(packets)
    _print_packets(tracks, packets, order)
    print(f"play order (by dts_time) is file order (by pos): {'yes' if order == packets else 'no'}")
    return 0


def _print_packets(tracks, packets, order):
    """The belt, one packet a line in play order, with its place in its own stream's pts order (shown); then each
    stream's totals (_print_streams)."""
    shown = {}
    for n in range(len(tracks)):
        mine = sorted((p for p in packets if p["stream"] == n), key=lambda p: p["pts"])
        shown.update({p["pos"]: place for place, p in enumerate(mine, 1)})
    print(f"{len(packets)} packets: " + ", ".join(f"stream {n} {t.handler} {sum(p['stream'] == n for p in packets)} "
                                              f"(time_base 1/{t.timescale})" for n, t in enumerate(tracks)))
    print("packet stream dts_time pts_time dts pts duration size pos key shown")
    for i, p in enumerate(order, 1):
        print(i, p["stream"], f"{float(p['dts_time']):.6f}", f"{float(p['pts_time']):.6f}", p["dts"], p["pts"],
              p["duration"], p["size"], p["pos"], "K" if p["key"] else "-", shown[p["pos"]])
    _print_streams(tracks, order)


def _print_streams(tracks, order):
    """Each stream's packets, keyframes and reorder depth, and how far its first dts runs before its first pts: the
    decoder's delay, which an ffmpeg file stores as the edit list's media_time."""
    from . import timing
    for n, t in enumerate(tracks):
        mine = [p for p in order if p["stream"] == n]
        if mine:
            early = mine[0]["pts"] - mine[0]["dts"]
            print(f"stream {n} {t.handler}: {len(mine)} packets, {sum(p['key'] for p in mine)} key, reorder depth "
                  f"{timing.reorder_depth(mine)}; the first dts is {early} ticks = {early // mine[0]['duration']} x "
                  f"{mine[0]['duration']} before its pts")

def cmd_faststart(args):
    """`faststart FILE -o OUT`: move the map room next to the front door (mux.faststart). Prints the top-level boxes
    before and after (type, start, size), the shift, and each track's first and last chunk offsets before and after;
    then writes OUT. A file with no mdat before its moov is written unchanged."""
    from . import boxes, mux
    data = boxes.read_mp4(args.file)
    try:
        out = mux.faststart(data)
    except boxes.BoxError as e:
        print(f"error: {e}")
        return 1
    _print_move(data, out)
    Path(args.out).write_bytes(out)
    print(f"wrote {len(out)} bytes")
    return 0


def _print_move(data, out):
    """The top-level boxes before and after, where the moov went, and each track's chunk-offset table (stco or co64):
    how many offsets, and the first and last, before -> after."""
    from . import boxes, tables
    before, after, path = boxes.walk(data), boxes.walk(out), "mdia/minf/stbl/"
    for name, tree in (("before", before), ("after", after)):
        print(f"{name}: " + ", ".join(f"{b.type} {b.start} {b.size}" for b in tree))
    old, new = boxes.find(before, "moov"), boxes.find(after, "moov")
    print(f"moov {old.start} -> {new.start}: every chunk offset + {new.size}, the moov's size" if old.start != new.start
          else "no mdat before the moov: unchanged")
    for n, (a, b) in enumerate(zip(boxes.find_all(before, "moov/trak"), boxes.find_all(after, "moov/trak")), 1):
        box = boxes.find(a.children, path + "stco") or boxes.find(a.children, path + "co64")
        if box:
            o, m = tables.read_stco(data, box), tables.read_stco(out, boxes.find(b.children, path + box.type))
            print(f"track {n} {box.type}: {len(o)} offsets" + (f", first {o[0]} -> {m[0]}, last {o[-1]} -> {m[-1]}"
                                                                if o else ""))


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
    d.add_argument("--rewrite-check", dest="func", action="store_const", const=cmd_header_check,
                   help="write ftyp, mvhd and each track's header boxes back from their fields and compare them")
    d.set_defaults(func=cmd_dump)


def _add_samples(sub):
    """Register the `samples` command."""
    s = sub.add_parser("samples", help="print a track's sample table")
    s.add_argument("file", help="the MP4 file to read")
    s.add_argument("--track", type=int, default=1, help="which track, counted from 1 in file order (default 1)")
    s.add_argument("--pts", action="store_true", help="dts and pts with the edit list applied, and the display order")
    s.add_argument("--rewrite-check", dest="func", action="store_const", const=cmd_rewrite_check,
                   help="write every track's sample tables back from its samples and compare them with the file's")
    s.set_defaults(func=cmd_samples)


def _add_frame(sub):
    """Register the `frame` command."""
    f = sub.add_parser("frame", help="find the frame on screen at a time, and extract it")
    f.add_argument("file", help="the MP4 file to read")
    f.add_argument("--at", type=int, required=True, help="the time, in milliseconds from the start of the movie")
    f.add_argument("--out", help="write the keyframe-to-frame samples here as an Annex B .h264 stream")
    f.set_defaults(func=cmd_frame)


def _add_extract(sub):
    """Register the `extract` command."""
    e = sub.add_parser("extract", help="copy one track's samples out into a plain stream (.h264, .aac, .srt)")
    e.add_argument("file", help="the MP4 file to read")
    e.add_argument("--track", type=int, required=True, help="which track, counted from 1 in file order")
    e.add_argument("-o", dest="out", required=True, help="the file to write")
    e.set_defaults(func=cmd_extract)


def _add_chunks(sub):
    """Register the `chunks` command."""
    c = sub.add_parser("chunks", help="draw the chunk map: which track's chunk comes next in mdat")
    c.add_argument("file", help="the MP4 file to read")
    c.set_defaults(func=cmd_chunks)


def _add_faststart(sub):
    """Register the `faststart` command."""
    f = sub.add_parser("faststart", help="move the moov to the front, so a player reads it first")
    f.add_argument("file", help="the MP4 file to read")
    f.add_argument("-o", dest="out", required=True, help="the file to write")
    f.set_defaults(func=cmd_faststart)


def _add_packets(sub):
    """Register the `packets` command."""
    c = sub.add_parser("packets", help="list every packet in the order a player decodes them")
    c.add_argument("file", help="the MP4 file to read")
    c.set_defaults(func=cmd_packets)


def main(argv: Optional[list] = None) -> int:
    """Parse the command line and run the chosen subcommand."""
    p = argparse.ArgumentParser(prog="mp4kit")
    sub = p.add_subparsers(dest="cmd", required=True)
    for add in (_add_hex, _add_nals, _add_sps, _add_annexb, _add_boxes, _add_dump, _add_samples,
                _add_frame, _add_extract, _add_chunks, _add_packets, _add_faststart):
        add(sub)
    args = p.parse_args(argv)
    return args.func(args)
