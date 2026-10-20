"""Time in an MP4. Episode 10: ticks and seconds."""


def seconds(ticks, timescale):
    """Ticks to seconds: a clock that ticks `timescale` times a second has counted `ticks`."""
    return ticks / timescale
