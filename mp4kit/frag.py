"""The terrace: fragmented MP4. Episode 30: the moov's map room keeps the corridors and their sheets but no parcels;
each moof is a pocket map room for the parcels beside it, one traf (track fragment) per corridor. A track's samples
come from three places: trex (in the moov's mvex: the track's defaults), tfhd (this traf's defaults, and where its
offsets count from), and trun (the run itself: a table with a column for each field it carries); tfdt says when
the traf's first sample is decoded."""
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
