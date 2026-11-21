"""Writing an MP4: the workshop. Episode 24: the zipper, a plan of which track's chunk goes next in mdat (interleave),
from each sample's decode time on the movie's timeline (timeline). Episode 26: the same drawers, built instead of
opened: each sample table written back from a track's samples (runs, stsc_rules, table_box, write_stsz, write_stbl)."""
import struct
from fractions import Fraction

from . import audio, boxes


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


def runs(values):
    """Runs of equal values in a row, as (count, value): how stts stores durations and ctts its slips. f1's
    durations [33] * 12 → [(12, 33)]. The reverse of unrolling them."""
    out = []
    for v in values:
        if out and out[-1][1] == v:
            out[-1][0] += 1
        else:
            out.append([1, v])
    return [tuple(run) for run in out]


def stsc_rules(chunks):
    """stsc's rules from each chunk's sample count (interleave's counts, track by track): a rule (first_chunk,
    samples_per_chunk, sample_description_index 1) starts at chunk 1 and wherever the count changes. f1: [4, 4, 2, 2]
    → [(1, 4, 1), (3, 2, 1)]. The reverse of tables.chunk_sizes."""
    return [(i, n, 1) for i, n in enumerate(chunks, 1) if i == 1 or chunks[i - 2] != n]


def table_box(kind, fmt, rows, version=0):
    """A sample table's box: the stamp (version, flags 0), entry_count, then every row packed with the struct format
    `fmt` (">II" is two 32-bit numbers a row). The reverse of tables.read_table."""
    return boxes.full_box(kind, version, 0, struct.pack(">I", len(rows)), *(struct.pack(fmt, *row) for row in rows))


def write_stsz(sizes):
    """Drawer 5: sample_size and sample_count, then a size per sample. When every sample is one size, that size and
    no list (sample_size 0 means "listed"); no samples: 0 and 0. The reverse of tables.read_stsz."""
    if sizes and len(set(sizes)) == 1:
        return boxes.full_box("stsz", 0, 0, struct.pack(">II", sizes[0], len(sizes)))
    return boxes.full_box("stsz", 0, 0, struct.pack(f">II{len(sizes)}I", 0, len(sizes), *sizes))


def write_stbl(track, stsd, chunk_offsets, chunks):
    """A track's cabinet from its samples, drawers in ffmpeg's order: the tray (stsd, as given), stts (each sample's
    duration to the next dts, the last to mdhd's duration, in runs), stss (only if some sample is not a keyframe),
    ctts (only if some cts is not its dts; version 1 if a slip is negative), stsc (`chunks`: each chunk's sample count),
    stsz, and stco (co64 if an offset needs 64 bits). Tired Sailors Carry Oars Slowly."""
    s = track.samples
    durations = [b.dts - a.dts for a, b in zip(s, s[1:])] + [track.duration - s[-1].dts] if s else []
    slips = [x.cts - x.dts for x in s]
    drawers = [stsd, table_box("stts", ">II", runs(durations))]
    if not all(x.key for x in s):
        drawers.append(table_box("stss", ">I", [(x.number,) for x in s if x.key]))
    if any(slips):
        drawers.append(table_box("ctts", ">Ii", runs(slips), int(min(slips) < 0)))
    wide = max(chunk_offsets, default=0) > 0xFFFFFFFF
    drawers += [table_box("stsc", ">III", stsc_rules(chunks)), write_stsz([x.size for x in s]),
                table_box("co64" if wide else "stco", ">Q" if wide else ">I", [(o,) for o in chunk_offsets])]
    return boxes.box("stbl", *drawers)
