"""Time in an MP4. Episode 10: ticks and seconds. Episode 14: decode times from stts. Episode 17: composition
times, decode time plus the ctts slip (DTS → CTS → PTS: Do Cats Purr). Episode 18: presentation times, the edit
list applied. Episode 19: the sample on screen at a time, and the keyframe it is decoded from. Episode 25: the
projection booth, every sample as a player's packet, the order the reader hands them out, and how far a decoder
reorders them."""
from fractions import Fraction


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


def sample_at(pts, t_ticks):
    """The sample on screen at `t_ticks` (the track's ticks, on the presentation timeline): of the samples shown at
    or before t, the one shown last. It stays on screen until the next one shows. Samples count from 1."""
    shown = [(p, n) for n, p in enumerate(pts, 1) if p <= t_ticks]
    if not shown:
        raise ValueError(f"nothing is on screen at {t_ticks} ticks: the first picture shows at {min(pts)}")
    return max(shown)[1]


def sync_before(stss, n):
    """Where decoding sample `n` must start: the last sync sample (keyframe) at or before it. A picture can need
    earlier parcels, so walk back to the keyframe. No stss (None): every sample is a sync sample."""
    if stss is None:
        return n
    before = [k for k in stss if k <= n]
    if not before:
        raise ValueError(f"no sync sample at or before sample {n} (stss starts at {stss[0]})")
    return max(before)


def packets(tracks):
    """Every sample of every track as ffprobe's packet (-show_packets), in file order (by pos): its stream (ffprobe's
    stream_index, counted from 0), dts and pts in the track's ticks on the movie's timeline (less the first real edit's
    media_time, as mux.timeline), the same in seconds (dts_time, pts_time: ticks × time_base, 1 / timescale), its
    duration in ticks (to the next sample, the last to the track's end), size, pos (its offset) and key."""
    from . import audio
    out = []
    for stream, track in enumerate(tracks):
        shift, s = audio.priming(track.elst), track.samples
        ends = [x.dts for x in s[1:]] + [track.duration]
        for x, end in zip(s, ends):
            out.append({"stream": stream, "dts": x.dts - shift, "pts": x.cts - shift, "duration": end - x.dts,
                        "dts_time": Fraction(x.dts - shift, track.timescale),
                        "pts_time": Fraction(x.cts - shift, track.timescale),
                        "size": x.size, "pos": x.offset, "key": x.key})
    return sorted(out, key=lambda p: p["pos"])


def play_order(packets):
    """The order the reader hands packets to the decoders: merged by decode time in seconds (dts_time), a tie to the
    lower stream. Each decoder takes its own stream's packets in this order and shows them in pts order."""
    return sorted(packets, key=lambda p: (p["dts_time"], p["stream"]))


def reorder_depth(packets):
    """How many frames a decoder must hold back: the most packets decoded before one packet and shown after it (H.264's
    max_num_reorder_frames is an upper bound on it). 0: shown in decode order. One stream's packets, in decode order."""
    return max((sum(q["pts"] > p["pts"] for q in packets[:i]) for i, p in enumerate(packets)), default=0)
