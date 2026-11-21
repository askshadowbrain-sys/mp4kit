"""The terrace: fragmented MP4. Episode 30: the moov's map room keeps the corridors and their sheets but no parcels;
each moof is a pocket map room for the parcels beside it, one traf (track fragment) per corridor. A track's samples
come from three places: trex (in the moov's mvex: the track's defaults), tfhd (this traf's defaults, and where its
offsets count from), and trun (the run itself: a table with a column for each field it carries); tfdt says when
the traf's first sample is decoded. Episode 31: every sample of every track, moof by moof (fragment_samples), and
the two indexes that find a fragment by time without reading the file through: the block directory (sidx, before
the fragments: each one's byte range and duration) and the back-gate index (mfra at the end, found from its last 4
bytes (mfro): each random access point's time and moof, per track in a tfra)."""
import bisect
import dataclasses
import struct

from . import boxes
from .tables import Sample

DEFAULTS = ("sample_description_index", "default_sample_duration", "default_sample_size", "default_sample_flags")
TFHD_FIELDS = ((0x01, "base_data_offset", ">Q"), (0x02, DEFAULTS[0], ">I"), (0x08, DEFAULTS[1], ">I"),
               (0x10, DEFAULTS[2], ">I"), (0x20, DEFAULTS[3], ">I"))
TRUN_COLUMNS = ((0x100, "sample_duration"), (0x200, "sample_size"), (0x400, "sample_flags"),
                (0x800, "sample_composition_time_offset"))
NON_SYNC = 0x00010000                    # sample_is_non_sync_sample, bit 16 of the sample flags
DEFAULT_BASE_IS_MOOF = 0x020000


def read_trex(data, box):
    """mvex/trex, one per track: the defaults every fragment of the track starts from (frag-cmaf: track 1 and
    track 2, sample description 1, every other default 0)."""
    track_ID, *defaults = struct.unpack_from(">5I", data, box.payload + 4)
    return {"track_ID": track_ID, **dict(zip(DEFAULTS, defaults))}


def read_tfhd(data, box):
    """The traf's header: its track_ID, then only the fields its flags say are there, in a fixed order. Flag
    0x020000, default-base-is-moof: offsets count from the start of the moof, not the file."""
    flags, at = boxes.read_fullbox(data, box)[1], box.payload + 8
    fields = {"flags": flags, "track_ID": boxes.u32(data, box.payload + 4)}
    for bit, name, fmt in TFHD_FIELDS:
        if flags & bit:
            fields[name] = struct.unpack_from(fmt, data, at)[0]
            at = at + struct.calcsize(fmt)
    return fields


def read_tfdt(data, box):
    """baseMediaDecodeTime: the decode time of the traf's first sample on the track's clock, so a reader need not
    add up every earlier fragment. Version 1 is 64-bit, version 0 32-bit."""
    version = boxes.read_fullbox(data, box)[0]
    return boxes.u64(data, box.payload + 4) if version == 1 else boxes.u32(data, box.payload + 4)


def read_trun(data, box):
    """The pocket map's one table: sample_count, then data_offset (flag 0x1) and first_sample_flags (0x4) if
    present, then a row per sample with only the columns its flags carry: duration (0x100), size (0x200), flags
    (0x400), composition time offset (0x800; signed in version 1)."""
    version, flags = boxes.read_fullbox(data, box)
    fields, at = {"version": version, "flags": flags, "sample_count": boxes.u32(data, box.payload + 4)}, box.payload + 8
    if flags & 0x1:
        fields["data_offset"], at = struct.unpack_from(">i", data, at)[0], at + 4
    if flags & 0x4:
        fields["first_sample_flags"], at = boxes.u32(data, at), at + 4
    names = [name for bit, name in TRUN_COLUMNS if flags & bit]
    fmt = ">" + "".join("i" if name.endswith("offset") and version == 1 else "I" for name in names)
    rows = list(struct.iter_unpack(fmt, data[at:at + fields["sample_count"] * 4 * len(names)])) if names else []
    fields.update({name: [row[i] for row in rows] for i, name in enumerate(names)})
    return fields


def column(run, name, i, default):
    """Row `i` of the trun's column `name`, or `default` when the trun has no such column."""
    return run[name][i] if name in run else default


def traf_samples(data, moof, traf, trex, implicit):
    """One traf's samples, each field from the nearest place that has it: the trun's column (or its
    first_sample_flags, for a run's first sample), else the tfhd's default, else the trex's. Times start at tfdt;
    offsets at the tfhd's base (its base_data_offset; with default-base-is-moof the moof's start; else `implicit`,
    where the last traf's data ended) plus each run's data_offset (none: right after the last run). Gives
    tables.Sample rows, numbered from 1 in the traf, cts = dts + the composition time offset."""
    tfhd = read_tfhd(data, boxes.find(traf.children, "tfhd"))
    duration, size, flags = (tfhd.get(name, trex[name]) for name in DEFAULTS[1:])
    base = tfhd.get("base_data_offset", moof.start if tfhd["flags"] & DEFAULT_BASE_IS_MOOF else implicit)
    dts, offset, samples = read_tfdt(data, boxes.find(traf.children, "tfdt")), base, []
    for run in (read_trun(data, b) for b in traf.children if b.type == "trun"):
        offset = base + run["data_offset"] if "data_offset" in run else offset
        for i in range(run["sample_count"]):
            first = run.get("first_sample_flags", flags) if i == 0 else flags
            nbytes, cto = column(run, "sample_size", i, size), column(run, "sample_composition_time_offset", i, 0)
            key = not column(run, "sample_flags", i, first) & NON_SYNC
            samples.append(Sample(len(samples) + 1, dts, dts + cto, nbytes, offset, key))
            dts, offset = dts + column(run, "sample_duration", i, duration), offset + nbytes
    return samples


def fragment_samples(data, tree):
    """Every track's samples, listed from the moofs alone: each traf of each moof in file order (traf_samples),
    numbered from 1 per track. A sample's chunk is the fragment it came from (1 = the first moof)."""
    trex = {t["track_ID"]: t for t in (read_trex(data, b) for b in boxes.find_all(tree, "moov/mvex/trex"))}
    tracks = {track_ID: [] for track_ID in trex}
    for fragment, moof in enumerate((b for b in tree if b.type == "moof"), 1):
        implicit = moof.start
        for traf in boxes.find_all(moof.children, "traf"):
            track_ID = read_tfhd(data, boxes.find(traf.children, "tfhd"))["track_ID"]
            for s in traf_samples(data, moof, traf, trex[track_ID], implicit):
                tracks[track_ID].append(dataclasses.replace(s, number=len(tracks[track_ID]) + 1, chunk=fragment))
                implicit = s.offset + s.size
    return tracks


def read_sidx(data, box):
    """The block directory: for one track (reference_ID) on its own clock (timescale), the presentation time the
    first reference starts at, and where it starts (first_offset bytes after this box's end); then one row per
    reference: (reference_type (1 = another sidx), referenced_size, subsegment_duration, starts_with_SAP, SAP_type,
    SAP_delta_time). `ranges` adds them up: (start time, first byte, end byte) of each reference."""
    version = boxes.read_fullbox(data, box)[0]
    reference_ID, timescale = struct.unpack_from(">II", data, box.payload + 4)
    wide = ">QQ" if version == 1 else ">II"
    time, first_offset = struct.unpack_from(wide, data, box.payload + 12)
    at = box.payload + 12 + struct.calcsize(wide) + 2                        # + 2 reserved bytes
    rows = [(size >> 31, size & 0x7FFFFFFF, duration, sap >> 31, sap >> 28 & 7, sap & 0x0FFFFFFF)
            for size, duration, sap in struct.iter_unpack(">III", data[at + 2:at + 2 + 12 * boxes.u16(data, at)])]
    fields = {"version": version, "reference_ID": reference_ID, "timescale": timescale,
              "earliest_presentation_time": time, "first_offset": first_offset, "references": rows, "ranges": []}
    start = box.end + first_offset
    for _, size, duration, *_ in rows:
        fields["ranges"].append((time, start, start + size))
        time, start = time + duration, start + size
    return fields


def read_tfra(data, box):
    """The back-gate index for one track: for each random access point its presentation time and the moof that holds
    it, then which traf, trun and sample in that moof (each number 1 to 4 bytes long, as length_size_of_traf_num,
    _trun_num and _sample_num say, less one). Rows (time, moof_offset, traf, trun, sample)."""
    version = boxes.read_fullbox(data, box)[0]
    track_ID, lengths, count = struct.unpack_from(">III", data, box.payload + 4)
    widths, at, entries = [(lengths >> shift & 3) + 1 for shift in (4, 2, 0)], box.payload + 16, []
    for _ in range(count):
        row = list(struct.unpack_from(">QQ" if version == 1 else ">II", data, at))
        at = at + (16 if version == 1 else 8)
        for width in widths:
            row.append(int.from_bytes(data[at:at + width], "big"))
            at = at + width
        entries.append(tuple(row))
    return {"version": version, "track_ID": track_ID, "entries": entries}


def read_mfro(data, box):
    """mfra's last box: the size of the whole mfra, so the file's last 4 bytes say how far back the index starts."""
    return boxes.u32(data, box.payload + 4)


def back_gate(data):
    """The mfra, found from the back of the file as a reader does (mov.c mov_read_mfra): the last 4 bytes are mfro's
    copy of mfra's size; step back that far and an mfra of that size must start there. None if not."""
    size = boxes.u32(data, len(data) - 4) if len(data) >= 16 else 0
    if not 16 <= size <= len(data):
        return None
    try:
        mfra = boxes.walk(data, len(data) - size)[0]
    except boxes.BoxError:
        return None
    return mfra if mfra.type == "mfra" and mfra.size == size else None


def fragment_at(index, t):
    """The row of an index (rows sorted by start time, first) whose start is the last at or before time `t`; the
    first row for a `t` before it (mov.c search_frag_timestamp and mov_seek_fragment do the same)."""
    return index[max(bisect.bisect_right([row[0] for row in index], t) - 1, 0)]


def in_hex(fields):
    """dump's view of a fragment box: its flag words in hex (flags=0x000a05), as the specification writes them."""
    return {k: f"0x{v:0{6 if k == 'flags' else 8}x}" if k.endswith("flags") and isinstance(v, int) else v
            for k, v in fields.items()}


boxes.DECODERS["trex"] = lambda data, box: in_hex(read_trex(data, box))
boxes.DECODERS["mfhd"] = lambda data, box: {"sequence_number": boxes.u32(data, box.payload + 4)}
boxes.DECODERS["tfhd"] = lambda data, box: in_hex(read_tfhd(data, box))
boxes.DECODERS["tfdt"] = lambda data, box: {"version": boxes.read_fullbox(data, box)[0],
                                            "baseMediaDecodeTime": read_tfdt(data, box)}
boxes.DECODERS["trun"] = lambda data, box: in_hex(read_trun(data, box))
boxes.DECODERS["sidx"] = read_sidx
boxes.DECODERS["tfra"] = read_tfra
boxes.DECODERS["mfro"] = lambda data, box: {"mfra_size": read_mfro(data, box)}
