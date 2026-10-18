"""Box reader core: big-endian numbers and box headers."""
import struct
from dataclasses import dataclass, field


def u16(data, at):
    """Read an unsigned 16-bit big-endian number at byte offset `at`."""
    return struct.unpack_from(">H", data, at)[0]


def u32(data, at):
    """Read an unsigned 32-bit big-endian number at byte offset `at`."""
    return struct.unpack_from(">I", data, at)[0]


def u64(data, at):
    """Read an unsigned 64-bit big-endian number at byte offset `at`."""
    return struct.unpack_from(">Q", data, at)[0]


@dataclass
class Box:
    """One box: its type, where it starts, its size and its header size."""
    type: str
    start: int
    size: int
    header: int
    children: list = field(default_factory=list)

    @property
    def payload(self):
        """Offset of the first byte after the header."""
        return self.start + self.header

    @property
    def end(self):
        """Offset of the first byte after the box."""
        return self.start + self.size


class BoxError(ValueError):
    """A box header that cannot be right: too short, or running past its parent."""


def read_header(data, at, end=None):
    """Read a box header at `at`: size, type, then a 64-bit size (size 1) or a uuid's 16 bytes."""
    end = len(data) if end is None else end
    if at + 8 > end:
        raise BoxError(f"box at {at}: only {end - at} bytes left, a header needs 8")
    size, box_type, header = u32(data, at), data[at + 4:at + 8].decode("latin-1"), 8
    if size == 1 and at + 16 <= end:
        size, header = u64(data, at + 8), 16
    elif size == 0:
        size = end - at
    if box_type == "uuid":
        header += 16
    if size < header:
        raise BoxError(f"{box_type} at {at}: size {size} is smaller than its {header}-byte header")
    if at + size > end:
        raise BoxError(f"{box_type} at {at}: size {size} runs past the end ({end})")
    return Box(box_type, at, size, header, [])


def iter_boxes(data, start, end):
    """Yield the boxes from `start` to `end` (the parent's end), one after another."""
    at = start
    while at < end:
        box = read_header(data, at, end)
        yield box
        at = box.end


def read_fullbox(data, box):
    """A full box's stamp: version (1 byte) and flags (3 bytes) at the start of its payload."""
    word = u32(data, box.payload)
    return word >> 24, word & 0xFFFFFF
