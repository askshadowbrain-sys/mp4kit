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


def read_header(data, at):
    """Read the 8-byte box header at offset `at`: 4 bytes of size, 4 letters of type."""
    size = u32(data, at)
    box_type = data[at + 4:at + 8].decode("latin-1")
    if size < 8:
        raise ValueError(f"{box_type} at {at}: size {size} is smaller than its 8-byte header")
    if at + size > len(data):
        raise ValueError(f"{box_type} at {at}: size {size} runs past the end ({len(data)})")
    return Box(box_type, at, size, 8, [])


def iter_boxes(data, start, end):
    """Yield the boxes from `start` to `end`, one after another."""
    at = start
    while at < end:
        box = read_header(data, at)
        yield box
        at = box.end
