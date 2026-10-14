"""H.264 elementary stream. Episode 2: inside mdat, each NAL unit hides behind a length label."""


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
