"""Time in an MP4. Episode 10: ticks and seconds. Episode 14: decode times from stts. Episode 17: composition
times, decode time plus the ctts slip (DTS → CTS → PTS: Do Cats Purr). Episode 18: presentation times, the edit
list applied."""


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


def composition_times(dts, ctts):
    """Each sample's composition time in ticks: its decode time plus its slip from ctts's runs of (sample_count,
    sample_offset). CT = DT + offset. No ctts (an empty list): every slip is 0, so CT = DT."""
    offsets = [sample_offset for sample_count, sample_offset in ctts for _ in range(sample_count)]
    return [t + offset for t, offset in zip(dts, offsets or [0] * len(dts))]


def presentation_times(cts, elst, media_timescale, movie_timescale):
    """Each sample's presentation time in the track's ticks: the edit list applied to its composition time. Empty
    edits (media_time -1) push the track later by their segment_duration, which counts in the movie's clock, so it
    is converted to the track's first. The first real edit says where the track starts: PTS = CTS - media_time +
    the empty time before it. No edit list: PTS = CTS. Later edits and media_rate are not applied."""
    start = 0
    for segment_duration, media_time, *_ in elst:
        if media_time != -1:
            return [t - media_time + start for t in cts]
        start = start + segment_duration * media_timescale // movie_timescale
    return [t + start for t in cts]
