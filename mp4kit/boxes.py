"""Box reader core. Episode 1: numbers in an MP4 are big-endian."""
import struct


def u16(data, at):
    """Read an unsigned 16-bit big-endian number at byte offset `at`."""
    return struct.unpack_from(">H", data, at)[0]


def u32(data, at):
    """Read an unsigned 32-bit big-endian number at byte offset `at`."""
    return struct.unpack_from(">I", data, at)[0]


def u64(data, at):
    """Read an unsigned 64-bit big-endian number at byte offset `at`."""
    return struct.unpack_from(">Q", data, at)[0]
