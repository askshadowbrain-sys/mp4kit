"""H.264 elementary stream. Episode 2: length labels in mdat. Episode 3: NAL header, types, bit reader."""


def iter_length_prefixed(data, start, end, length_size=4):
    """Yield (offset of the length field, NAL bytes) for each unit in data[start:end]."""
    at = start
    while at < end:
        length_field = data[at:at + length_size]
        size = int.from_bytes(length_field, "big")
        first = at + length_size
        nal_bytes = bytes(data[first:first + size])
        yield at, nal_bytes
        at = first + size


NAL_TYPES = {1: "non-IDR slice", 5: "IDR slice", 6: "SEI", 7: "SPS", 8: "PPS", 9: "AUD"}


def nal_header(first_byte):
    """Split a NAL's first byte into (forbidden_zero_bit, nal_ref_idc, nal_unit_type)."""
    forbidden_zero_bit = first_byte >> 7
    nal_ref_idc = (first_byte >> 5) & 3
    nal_unit_type = first_byte & 31
    return forbidden_zero_bit, nal_ref_idc, nal_unit_type


class BitReader:
    """Reads a byte string one bit at a time, most significant bit first."""

    def __init__(self, data):
        self.data = bytes(data)
        self.pos = 0

    def u(self, n):
        """Read n bits as an unsigned number."""
        value = 0
        for _ in range(n):
            byte = self.data[self.pos >> 3]
            bit = (byte >> (7 - (self.pos & 7))) & 1
            value = (value << 1) | bit
            self.pos += 1
        return value

    def ue(self):
        """Read an unsigned Exp-Golomb number."""
        zeros = 0
        while self.u(1) == 0:
            zeros += 1
        return (1 << zeros) - 1 + self.u(zeros)

    def se(self):
        """Read a signed Exp-Golomb number."""
        k = self.ue()
        if k & 1:
            return (k + 1) // 2
        return -(k // 2)
