"""The mp4kit command line: one cmd_* per subcommand."""
import argparse
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
    """`dump FILE [--find TYPE]`: print the box tree, indented by depth, or only the boxes of one type by their
    path; each with any decoded fields."""
    from . import boxes
    from . import tables  # noqa: F401  (importing it registers its readers in boxes.DECODERS)
    data = boxes.read_mp4(args.file)
    try:
        tree = boxes.walk(data)
        if args.find is None:
            _print_tree(data, tree, 0)
        elif _print_found(data, tree, args.find, "") == 0:
            print(f"no {args.find} box")
    except boxes.BoxError as e:
        print(f"error: {e}")
        return 1
    if not any(b.type == "moov" for b in tree):
        print("no moov box")
    return 0


def cmd_samples(args):
    """`samples FILE [--track N] [--pts]`: print a track's sample table, one sample a line, its columns in lookup
    order: decode time (stts), keyframe (stss), offset (stsc + stco), size (stsz). Tracks count from 1 in file order.
    `--pts` adds, after dts, the composition time (stts + ctts) and each sample's place in display order."""
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
    print("sample dts cts display key offset size" if args.pts else "sample dts key offset size")
    for s, times in zip(samples, _time_columns(samples, args.pts)):
        print(s.number, *times, "K" if s.key else "-", s.offset, s.size)
    return 0


def _time_columns(samples, pts):
    """Each sample's time columns: its dts; with `--pts` also its cts and its place in display order (by cts)."""
    shown = {s.number: place for place, s in enumerate(sorted(samples, key=lambda s: s.cts), 1)}
    return [(s.dts, s.cts, shown[s.number]) if pts else (s.dts,) for s in samples]


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
    d.set_defaults(func=cmd_dump)


def _add_samples(sub):
    """Register the `samples` command."""
    s = sub.add_parser("samples", help="print a track's sample table")
    s.add_argument("file", help="the MP4 file to read")
    s.add_argument("--track", type=int, default=1, help="which track, counted from 1 in file order (default 1)")
    s.add_argument("--pts", action="store_true", help="add the composition time (cts) and the display order")
    s.set_defaults(func=cmd_samples)


def main(argv: Optional[list] = None) -> int:
    """Parse the command line and run the chosen subcommand."""
    p = argparse.ArgumentParser(prog="mp4kit")
    sub = p.add_subparsers(dest="cmd", required=True)
    for add in (_add_hex, _add_nals, _add_sps, _add_annexb, _add_boxes, _add_dump, _add_samples):
        add(sub)
    args = p.parse_args(argv)
    return args.func(args)
