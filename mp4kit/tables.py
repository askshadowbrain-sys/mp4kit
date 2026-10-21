"""The map room: moov and the boxes it holds. Episode 10: mvhd, the movie's wall clock. Episode 11: tkhd.
Episode 12: mdhd and hdlr, a track's own clock and its door sign."""
import struct

from . import boxes
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
