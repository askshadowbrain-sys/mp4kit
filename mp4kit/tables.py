"""The map room: moov and the boxes it holds. Episode 10: mvhd, the movie's wall clock. Episode 11: tkhd.
Episode 12: mdhd and hdlr, a track's own clock and its door sign. Episode 13: stsd, the filing cabinet's top
tray, its video instruction sheets (avc1) and their avcC. Episode 14: the generic table, and drawers 1 and 2,
stts (When?) and stss (Where can I start?)."""
import struct

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
