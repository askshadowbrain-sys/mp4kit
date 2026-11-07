"""Time in an MP4. Episode 10: ticks and seconds. Episode 14: decode times from stts."""


def seconds(ticks, timescale):
    """Ticks to seconds: a clock that ticks `timescale` times a second has counted `ticks`."""
    return ticks / timescale


def decode_times(stts):
    """Each sample's decode time in ticks, from stts's runs: the first is 0, and each sample starts where the one
    before it ends (its start + its sample_delta)."""
    times = []
    t = 0
    for sample_count, sample_delta in stts:
        for _ in range(sample_count):
            times.append(t)
            t = t + sample_delta
    return times
