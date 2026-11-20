"""Writing an MP4: the workshop. Episode 24: the zipper, a plan of which track's chunk goes next in mdat (interleave),
from each sample's decode time on the movie's timeline (timeline)."""
from fractions import Fraction

from . import audio


def timeline(track):
    """Each sample's decode time in seconds on the movie's timeline, as a Fraction: its dts less the entrance timer's
    first real media_time (audio.priming, episode 22: the sound's priming, the video's B-frame delay), over the
    track's clock. phone: video from -1,024 / 15,360 = -0.0667 s, sound from -1,024 / 48,000 = -0.0213 s."""
    shift = audio.priming(track.elst)
    return [Fraction(s.dts - shift, track.timescale) for s in track.samples]


def interleave(tracks, chunk_seconds=0.5):
    """The zipper: every sample of every track in decode order on the movie's timeline (a tie goes to the earlier
    track), cut into chunks. A chunk is a run of one track's samples; it ends where another track's sample comes
    next, or before a sample that starts `chunk_seconds` or more after the chunk's first. Gives (track, first
    sample, sample count) for each chunk in mdat order; tracks and samples count from 1."""
    teeth = sorted((t, n, s) for n, track in enumerate(tracks, 1) for s, t in enumerate(timeline(track), 1))
    plan = []
    for t, n, s in teeth:
        if plan and plan[-1][0] == n and t - plan[-1][3] < chunk_seconds:
            plan[-1][2] += 1
        else:
            plan.append([n, s, 1, t])
    return [(n, first, count) for n, first, count, _ in plan]
