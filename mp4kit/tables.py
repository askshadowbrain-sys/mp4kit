"""The map room: moov and the boxes it holds. Episode 10: mvhd, the movie's wall clock. Episode 11: tkhd.
Episode 12: mdhd and hdlr, a track's own clock and its door sign. Episode 13: stsd, the filing cabinet's top
tray, its video instruction sheets (avc1) and their avcC. Episode 14: the generic table, and drawers 1 and 2,
stts (When?) and stss (Where can I start?). Episode 15: drawers 3 to 5, stsc (Which chunk?), stco (Where does it
start?) and stsz (How big is each sample?). Episode 16: the five lookups as code, every sample of a track
from its five drawers (Sample, sample_table). Episode 17: ctts, the second-clock slip in the time drawer: each
sample's composition time, its decode time plus the slip (read_ctts). Episode 18: edts/elst, the timer at the
corridor's entrance (read_elst). Episode 21: the sound corridor's sheet, mp4a (read_audio_entry). Episode 22: the
roll slip, a sample group: its entries (sgpd) and the runs of samples it covers (sbgp). Episode 23: many tracks, each
corridor read whole (Track, read_tracks), and the signposts between corridors (read_tref)."""
import struct
from dataclasses import dataclass, field

from . import audio  # noqa: F401  (registers esds, so a sound track's entry carries it)
from . import boxes
from . import nal
from . import timing


def read_mvhd(data, box):
    """The wall clock: ticks per second (timescale), the movie's length in ticks (duration), and its other dials."""
    version = boxes.read_fullbox(data, box)[0]
    need = 120 if version == 1 else 108
    if box.size < need:
        raise boxes.BoxError(f"mvhd at {box.start}: version {version} needs {need} bytes, box has {box.size}")
    wide = 8 if version == 1 else 4
    at = box.payload + 4 + wide + wide
    timescale = boxes.u32(data, at)
    duration = boxes.u64(data, at + 4) if version == 1 else boxes.u32(data, at + 4)
    if timescale == 0:
        raise boxes.BoxError(f"mvhd at {box.start}: timescale 0, a clock that never ticks")
    at = at + 4 + wide
    return {"version": version, "timescale": timescale, "duration": duration,
            "seconds": timing.seconds(duration, timescale),
            "rate": boxes.u32(data, at) / 65536, "volume": boxes.u16(data, at + 4) / 256,
            "next_track_ID": boxes.u32(data, at + 76)}


boxes.DECODERS["mvhd"] = read_mvhd


def fixed(value, frac_bits):
    """A fixed-point number: the low `frac_bits` bits are the fraction (16.16: 640 << 16 is 640.0)."""
    return value / (1 << frac_bits)


TURNS = {(65536, 0, 0, 65536): 0, (0, -65536, 65536, 0): 90, (-65536, 0, 0, -65536): 180,
         (0, 65536, -65536, 0): 270}


def rotation(matrix):
    """Degrees the picture is turned counter-clockwise for display, read from the matrix's a, b, c, d
    (0, 90, 180 or 270); None for a matrix that is not a plain turn."""
    return TURNS.get((matrix[0], matrix[1], matrix[3], matrix[4]))


def read_tkhd(data, box):
    """The corridor's sign: flags, track_ID, the track's length on the movie clock, volume, the display matrix
    and the picture size."""
    version, flags = boxes.read_fullbox(data, box)
    need = 104 if version == 1 else 92
    if box.size < need:
        raise boxes.BoxError(f"tkhd at {box.start}: version {version} needs {need} bytes, box has {box.size}")
    wide = 8 if version == 1 else 4
    at = box.payload + 4 + wide + wide
    track_ID = boxes.u32(data, at)
    duration = boxes.u64(data, at + 8) if version == 1 else boxes.u32(data, at + 8)
    at = at + 8 + wide
    matrix = list(struct.unpack_from(">9i", data, at + 16))
    return {"version": version, "flags": flags, "track_ID": track_ID, "duration": duration,
            "volume": fixed(boxes.u16(data, at + 12), 8),
            "width": fixed(boxes.u32(data, at + 52), 16), "height": fixed(boxes.u32(data, at + 56), 16),
            "matrix": matrix, "rotation": rotation(matrix)}


boxes.DECODERS["tkhd"] = read_tkhd


def language(code):
    """A track's language from mdhd's 16 bits: a pad bit, then three 5-bit letters, each stored as the
    letter's code minus 0x60 (0x15C7 is "eng", 0x55C4 is "und")."""
    first = (code >> 10) & 0x1F
    second = (code >> 5) & 0x1F
    third = code & 0x1F
    return chr(first + 0x60) + chr(second + 0x60) + chr(third + 0x60)


def read_mdhd(data, box):
    """The room's clock: the track's own ticks per second (timescale), the media's length in those ticks
    (duration), and the track's language."""
    version = boxes.read_fullbox(data, box)[0]
    need = 44 if version == 1 else 32
    if box.size < need:
        raise boxes.BoxError(f"mdhd at {box.start}: version {version} needs {need} bytes, box has {box.size}")
    wide = 8 if version == 1 else 4
    at = box.payload + 4 + wide + wide
    timescale = boxes.u32(data, at)
    duration = boxes.u64(data, at + 4) if version == 1 else boxes.u32(data, at + 4)
    if timescale == 0:
        raise boxes.BoxError(f"mdhd at {box.start}: timescale 0, a clock that never ticks")
    return {"version": version, "timescale": timescale, "duration": duration,
            "seconds": timing.seconds(duration, timescale),
            "language": language(boxes.u16(data, at + 4 + wide))}


boxes.DECODERS["mdhd"] = read_mdhd


def read_hdlr(data, box):
    """The door sign: handler_type says what the track holds (vide, soun, sbtl; mdir under udta/meta), then
    a name for people, a C string ending in a zero byte."""
    if box.size < 32:
        raise boxes.BoxError(f"hdlr at {box.start}: needs 32 bytes, box has {box.size}")
    at = box.payload
    handler_type = data[at + 8:at + 12].decode("latin-1")
    name = data[at + 24:box.end].split(b"\0")[0].decode("utf-8", "replace")
    return {"handler_type": handler_type, "name": name}


boxes.DECODERS["hdlr"] = read_hdlr


def read_stsd(data, box):
    """The top tray of the filing cabinet (stbl): entry_count, then that many sample entries, one box each (avc1,
    mp4a, ...). A sample says which entry it needs by number (sample_description_index, carried by stsc)."""
    entry_count = boxes.u32(data, box.payload + 4)
    entries = boxes.walk(data, box.payload + 8, box.end)
    if len(entries) != entry_count:
        raise boxes.BoxError(f"stsd at {box.start}: entry_count {entry_count}, but it holds {len(entries)} entries")
    return entries


def read_visual_entry(data, box):
    """A video sample entry's fixed fields (avc1, hvc1, ...): 6 reserved bytes and data_reference_index, as in
    every sample entry; 16 bytes of pre_defined and reserved; width and height; two 72-dpi resolutions,
    reserved, frame_count 1; compressorname, a length byte then the name in 31 bytes; depth 0x18;
    pre_defined -1. Its own boxes (avcC, pasp, btrt, ...) start 78 bytes into the payload."""
    if box.size < 86:
        raise boxes.BoxError(f"{box.type} at {box.start}: a visual sample entry needs 86 bytes, box has {box.size}")
    at = box.payload
    name = data[at + 43:at + 43 + min(data[at + 42], 31)]
    return {"data_reference_index": boxes.u16(data, at + 6), "width": boxes.u16(data, at + 24),
            "height": boxes.u16(data, at + 26), "compressorname": name.decode("latin-1"),
            "depth": boxes.u16(data, at + 74)}


boxes.DECODERS["avc1"] = read_visual_entry


def read_audio_entry(data, box):
    """A sound sample entry's fixed fields (mp4a, enca, ...): 6 reserved bytes and data_reference_index, as in
    every sample entry; 8 reserved bytes; channelcount and samplesize; pre_defined and reserved; samplerate as
    16.16 fixed point. Its own boxes (esds, btrt, ...) start 28 bytes into the payload. Only a hint: the codec's
    own config (esds) is the one a decoder believes."""
    if box.size < 36:
        raise boxes.BoxError(f"{box.type} at {box.start}: a sound sample entry needs 36 bytes, box has {box.size}")
    at = box.payload
    return {"data_reference_index": boxes.u16(data, at + 6), "channelcount": boxes.u16(data, at + 16),
            "samplesize": boxes.u16(data, at + 18), "samplerate": fixed(boxes.u32(data, at + 24), 16)}


boxes.DECODERS["mp4a"] = boxes.DECODERS["enca"] = read_audio_entry


def codec_string(entry):
    """The codec string a browser is asked about (RFC 6381): "avc1." then avcC's profile, compatibility and
    level bytes as two hex digits each (100, 0x00, 30 → avc1.64001E)."""
    return (f"avc1.{entry['AVCProfileIndication']:02X}{entry['profile_compatibility']:02X}"
            f"{entry['AVCLevelIndication']:02X}")


def read_avcc(data, box):
    """The instruction sheets (AVCDecoderConfigurationRecord): version, profile, compatibility, level, the NAL
    length size minus one (low 2 bits), the SPS (count in the low 5 bits) and PPS, each with a 2-byte length;
    profiles other than Baseline, Main and Extended (66, 77, 88) add chroma_format and the bit depths after them."""
    at = box.payload
    sps, after = nal._read_param_sets(data, at + 6, data[at + 5] & 0x1F)
    pps, after = nal._read_param_sets(data, after + 1, data[after])
    if after > box.end:
        raise boxes.BoxError(f"avcC at {box.start}: the parameter sets run to {after}, past the box's end ({box.end})")
    fields = {"configurationVersion": data[at], "AVCProfileIndication": data[at + 1],
              "profile_compatibility": data[at + 2], "AVCLevelIndication": data[at + 3],
              "lengthSizeMinusOne": data[at + 4] & 3, "SPS": sps, "PPS": pps}
    if fields["AVCProfileIndication"] not in (66, 77, 88) and after + 4 <= box.end:
        fields.update(chroma_format=data[after] & 3, bit_depth_luma_minus8=data[after + 1] & 7,
                      bit_depth_chroma_minus8=data[after + 2] & 7)
    fields["codec"] = codec_string(fields)
    return fields


boxes.DECODERS["avcC"] = read_avcc


def read_table(data, box, fmt):
    """A sample table's shape: version and flags (4 bytes), entry_count (4 bytes), then entry_count rows, each
    unpacked with the struct format `fmt` (">II" is two 32-bit numbers a row)."""
    entry_count = boxes.u32(data, box.payload + 4)
    end = box.payload + 8 + entry_count * struct.calcsize(fmt)
    if end > box.end:
        raise boxes.BoxError(f"{box.type} at {box.start}: entry_count {entry_count} needs {end - box.start} bytes, "
                             f"box has {box.size}")
    return list(struct.iter_unpack(fmt, data[box.payload + 8:end]))


def read_stts(data, box):
    """Drawer 1, When?: runs of (sample_count, sample_delta), so many samples in a row that each last so many
    ticks of the track's clock (f1: [(12, 33)], twelve samples of 33 ms)."""
    return read_table(data, box, ">II")


def read_stss(data, box):
    """Drawer 2, Where can I start?: the sync samples (keyframes) by sample_number, counted from 1. No stss box
    means every sample is a sync sample, so this gives None."""
    if box is None:
        return None
    return [row[0] for row in read_table(data, box, ">I")]


boxes.DECODERS["stts"] = lambda data, box: {"entries": read_stts(data, box)}
boxes.DECODERS["stss"] = lambda data, box: {"sample_number": read_stss(data, box)}


def read_stsc(data, box):
    """Drawer 3, Which chunk?: rules of (first_chunk, samples_per_chunk, sample_description_index). Chunks count
    from 1, and a rule holds from its first_chunk until the next rule's (f1: [(1, 4, 1), (3, 2, 1)])."""
    return read_table(data, box, ">III")


def read_stco(data, box):
    """Drawer 4, Where does it start?: each chunk's byte offset in the file, one entry per chunk. co64 is the same
    table with 64-bit offsets (f1: [40, 6598, 14356, 21149])."""
    fmt = ">Q" if box.type == "co64" else ">I"
    return [row[0] for row in read_table(data, box, fmt)]


def read_stsz(data, box):
    """Drawer 5, How big is each sample?: every sample's size in bytes. Not read_table's shape: sample_size and
    sample_count come first, and the entries are there only when sample_size is 0 (else every sample is that size)."""
    sample_size = boxes.u32(data, box.payload + 4)
    sample_count = boxes.u32(data, box.payload + 8)
    if sample_size != 0:
        return [sample_size] * sample_count
    end = box.payload + 12 + sample_count * 4
    if end > box.end:
        raise boxes.BoxError(f"stsz at {box.start}: sample_count {sample_count} needs {end - box.start} bytes, "
                             f"box has {box.size}")
    return [row[0] for row in struct.iter_unpack(">I", data[box.payload + 12:end])]


def chunk_sizes(stsc, n_chunks):
    """stsc's rules unrolled: how many samples each of the `n_chunks` chunks holds. Each rule runs until the next
    rule's first_chunk; the last one runs to the final chunk (f1: [4, 4, 2, 2])."""
    ends = [row[0] for row in stsc[1:]] + [n_chunks + 1]
    sizes = []
    for (first_chunk, samples_per_chunk, _), end in zip(stsc, ends):
        sizes.extend([samples_per_chunk] * (end - first_chunk))
    return sizes


def _stsc_fields(data, box):
    """dump's stsc fields: the rules, and the samples in each chunk. stsc does not say how many chunks there are;
    that is the number of entries in the stco (or co64) of the same stbl."""
    stsc = read_stsc(data, box)
    stbl = [s for s in boxes.find_all(boxes.walk(data), "moov/trak/mdia/minf/stbl") if s.start < box.start < s.end][0]
    offsets = boxes.find(stbl.children, "stco") or boxes.find(stbl.children, "co64")
    return {"entries": stsc, "chunk_sizes": chunk_sizes(stsc, len(read_stco(data, offsets)))}


boxes.DECODERS["stsc"] = _stsc_fields
boxes.DECODERS["stco"] = boxes.DECODERS["co64"] = lambda data, box: {"chunk_offset": read_stco(data, box)}
boxes.DECODERS["stsz"] = lambda data, box: {"entry_size": read_stsz(data, box)}


def read_ctts(data, box):
    """The second-clock slip in drawer 1: runs of (sample_count, sample_offset), so many samples in a row whose
    composition time is their decode time plus sample_offset ticks. It stores only the difference. Version 0
    reads it unsigned, version 1 signed (it can be negative). No ctts box: no slips, so this gives []."""
    if box is None:
        return []
    signed = boxes.read_fullbox(data, box)[0] == 1
    return read_table(data, box, ">Ii" if signed else ">II")


boxes.DECODERS["ctts"] = lambda data, box: {"version": boxes.read_fullbox(data, box)[0],
                                            "entries": read_ctts(data, box)}


def read_elst(data, box):
    """The timer at the corridor's entrance (edts/elst): edits of (segment_duration, media_time,
    media_rate_integer, media_rate_fraction): skip to media_time, then play for segment_duration. Its length counts
    in the movie's clock (mvhd timescale), its start in the track's (mdhd timescale). media_time -1 is an empty
    edit: nothing of the track plays for that long. Version 0 is 32-bit, version 1 64-bit. No edts gives []."""
    if box is None:
        return []
    wide = boxes.read_fullbox(data, box)[0] == 1
    return read_table(data, box, ">Qqhh" if wide else ">Iihh")


boxes.DECODERS["elst"] = lambda data, box: {"version": boxes.read_fullbox(data, box)[0],
                                            "entries": read_elst(data, box)}


def read_sgpd(data, box):
    """The roll slip (sgpd, a sample group's descriptions): its grouping_type, then entries. Version 1 says how long
    each entry is (default_length); a roll entry is one signed 16-bit roll_distance, -1 = start decoding one sample
    earlier and throw that sample's sound away. Version 0 or 2, or entries of their own lengths: not read."""
    version, at = boxes.read_fullbox(data, box)[0], box.payload + 8
    kind = data[box.payload + 4:at].decode("latin-1")
    length = boxes.u32(data, at) if version == 1 else 0
    if length == 0:
        return {"version": version, "grouping_type": kind}
    count, at = boxes.u32(data, at + 4), at + 8
    if at + count * length > box.end:
        raise boxes.BoxError(f"sgpd at {box.start}: {count} entries of {length} bytes run past the box")
    entries = [bytes(data[e:e + length]) for e in range(at, at + count * length, length)]
    if kind in ("roll", "prol"):
        entries = [int.from_bytes(e, "big", signed=True) for e in entries]
    return {"version": version, "grouping_type": kind, "default_length": length, "entries": entries}


def read_sbgp(data, box):
    """Which samples carry which slip (sbgp): its grouping_type (and in version 1 a parameter), then runs of
    (sample_count, group_description_index): so many samples in a row that use sgpd's entry n (from 1; 0 = none).
    aac-only: [(88, 1)], every sample."""
    version = boxes.read_fullbox(data, box)[0]
    at = box.payload + 8 + 4 * (version == 1)
    count = boxes.u32(data, at)
    if at + 4 + 8 * count > box.end:
        raise boxes.BoxError(f"sbgp at {box.start}: entry_count {count} runs past the box")
    return {"version": version, "grouping_type": data[box.payload + 4:box.payload + 8].decode("latin-1"),
            "entries": list(struct.iter_unpack(">II", data[at + 4:at + 4 + 8 * count]))}


boxes.DECODERS["sgpd"], boxes.DECODERS["sbgp"] = read_sgpd, read_sbgp


@dataclass
class Sample:
    """One sample, as the five drawers give it: its number (from 1), its decode time (dts) and composition time
    (cts) in the track's ticks, its size in bytes, its byte offset in the file, and whether it is a keyframe."""
    number: int
    dts: int
    cts: int
    size: int
    offset: int
    key: bool


def _check_counts(stbl, stts_count, stsc_count, stsz_count):
    """The drawers must agree on how many samples the track has (stts's runs, stsc unrolled over stco, stsz)."""
    if not stts_count == stsc_count == stsz_count:
        raise boxes.BoxError(f"stbl at {stbl.start}: stts has {stts_count} samples, stsc {stsc_count}, "
                             f"stsz {stsz_count}")


def _clocks(data, stbl):
    """Drawer 1 and its slip: each sample's decode time (stts), and its composition time (stts + ctts). Do Cats
    Purr: DTS, then CTS. A ctts that covers a different number of samples than stts raises BoxError."""
    dts = timing.decode_times(read_stts(data, boxes.find(stbl.children, "stts")))
    ctts_box = boxes.find(stbl.children, "ctts")
    ctts = read_ctts(data, ctts_box)
    count = sum(sample_count for sample_count, _ in ctts)
    if ctts and count != len(dts):
        raise boxes.BoxError(f"ctts at {ctts_box.start}: ctts has {count} samples, stts {len(dts)}")
    return dts, timing.composition_times(dts, ctts)


def sample_table(data, trak):
    """Every sample of a track, each drawer of its stbl unrolled once, in lookup order: stts (When?), stss (Where
    can I start?), stsc (Which chunk?), stco (Where does it start?), stsz (How big?). Tired Sailors Carry Oars
    Slowly. A sample's offset is its chunk's offset plus the sizes of the samples before it in that chunk. Its cts
    is its dts plus its ctts slip (episode 17); a track with no ctts has cts = dts."""
    stbl = boxes.find(trak.children, "mdia/minf/stbl")
    times, cts = _clocks(data, stbl)
    sync = read_stss(data, boxes.find(stbl.children, "stss"))
    stsc = read_stsc(data, boxes.find(stbl.children, "stsc"))
    offsets = read_stco(data, boxes.find(stbl.children, "stco") or boxes.find(stbl.children, "co64"))
    sizes = read_stsz(data, boxes.find(stbl.children, "stsz"))
    per_chunk = chunk_sizes(stsc, len(offsets))
    _check_counts(stbl, len(times), sum(per_chunk), len(sizes))
    samples = []
    for offset, count in zip(offsets, per_chunk):
        for _ in range(count):
            n = len(samples) + 1
            samples.append(Sample(n, times[n - 1], cts[n - 1], sizes[n - 1], offset, sync is None or n in sync))
            offset = offset + sizes[n - 1]
    return samples


def read_tref(data, box):
    """The signposts (tref): one box per reference type (chap, subt, hint, ...), each a list of track_IDs, the tracks
    this one points at. A signpost points one way: the track it names holds no sign back."""
    return {ref.type: [boxes.u32(data, at) for at in range(ref.payload, ref.end, 4)] for ref in box.children}


boxes.DECODERS["tref"] = read_tref


@dataclass
class Track:
    """One corridor, read whole: its track_ID (tkhd), what it holds (hdlr), its clock (mdhd timescale), its tray's
    first sheet as a dict (the sample entry's type and fields, and each box inside it: avcC, esds), every sample
    (sample_table), its entrance timer (elst), its signposts (tref) and its length on its own clock (mdhd)."""
    id: int
    handler: str
    timescale: int
    entry: dict
    samples: list
    elst: list
    tref: dict = field(default_factory=dict)
    duration: int = 0


def _entry(data, stsd):
    """The tray's first sheet as a dict: {"type": "avc1", its fields, "avcC": {...}, ...}; a type with no reader
    (tx3g, text) gives only its type."""
    box = read_stsd(data, stsd)[0]
    entry = {"type": box.type, **boxes.decode(data, box)}
    entry.update({child.type: boxes.decode(data, child) for child in box.children})
    return entry


def read_tracks(data, tree):
    """Every corridor in the map room, in file order, each a Track. Trains Make Many Stops: trak, mdia, minf, stbl."""
    tracks = []
    for trak in boxes.find_all(tree, "moov/trak"):
        mdhd, tref = read_mdhd(data, boxes.find(trak.children, "mdia/mdhd")), boxes.find(trak.children, "tref")
        tracks.append(Track(read_tkhd(data, boxes.find(trak.children, "tkhd"))["track_ID"],
                            read_hdlr(data, boxes.find(trak.children, "mdia/hdlr"))["handler_type"],
                            mdhd["timescale"], _entry(data, boxes.find(trak.children, "mdia/minf/stbl/stsd")),
                            sample_table(data, trak), read_elst(data, boxes.find(trak.children, "edts/elst")),
                            read_tref(data, tref) if tref else {}, mdhd["duration"]))
    return tracks
