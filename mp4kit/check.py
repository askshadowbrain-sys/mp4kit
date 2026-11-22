"""The House inspector (episode 36): walk the route and check each room against the next. problems() runs every rule
on a file and gives one message per problem: what the boxes say, then the symptom a player shows and the cause.
An error means a player reads the wrong bytes or nothing at all; a warning means two numbers disagree and a player
copes; a note says what the inspector did not inspect. The inspector reads what the boxes say, not what a decoder
will do: a picture whose bytes are all in the right place can still be wrong inside."""
from fractions import Fraction
from itertools import islice, takewhile

from . import boxes, tables

TS_PACKET = 188     # MPEG-TS: fixed 188-byte packets, each starting with the sync byte 0x47


def _problem(level, finding, symptom, cause):
    """One message: the finding, then its symptom and its cause on lines of their own."""
    return f"{level}: {finding}\n  symptom: {symptom}\n  cause: {cause}"


def problems(data):
    """Every problem the inspector finds, along the route: the front door (an MPEG-TS stream has no House), the map
    room (no_moov), the chunks in the basement (overlapping_chunks, outside_mdat), the parcels (nal_lengths) and the
    clocks (durations). A file with no moov, or a box that runs past the file's end, stops the walk there."""
    if ts_packets(data):
        return [_ts_note(data)]
    try:
        tree = boxes.walk(data)
        if not boxes.find(tree, "moov"):
            return no_moov(data, tree)
        tracks = tables.read_tracks(data, tree)
    except boxes.BoxError as e:
        return [_cut_short(data, e)]
    found = overlapping_chunks(tracks) + outside_mdat(tracks, tree, len(data)) + _unclaimed(tracks, tree)
    for track in tracks:
        found += nal_lengths(data, track)
    return found + durations(data, tree) + _fragments(tree)


def _cut_short(data, error):
    """A box that runs past its parent's end. At the top level the file was cut short: with its moov before the cut
    ffmpeg plays up to it, without it there is no map. Inside a box, ffmpeg cuts the child to fit its parent."""
    seen = []
    try:
        for box in boxes.iter_boxes(data, 0, len(data)):
            seen.append(box.type)
    except boxes.BoxError:
        symptom = ("ffmpeg plays the samples before the cut, then says: partial file" if "moov" in seen else
                   "ffmpeg says: moov atom not found, then: Invalid data found when processing input")
        return _problem("error", str(error), symptom, "the file is cut short: a copy or a recording stopped early")
    return _problem("error", str(error), "ffmpeg cuts the box to fit its parent and reads on, often without a word",
                    "a size field is wrong")


def ts_packets(data):
    """How many 188-byte MPEG-TS packets the file holds, if every one starts with the sync byte 0x47; else 0."""
    n = len(data) // TS_PACKET
    if n < 2 or any(data[i * TS_PACKET] != 0x47 for i in range(n)):
        return 0
    return n


def _ts_note(data):
    """The house next door: no boxes to walk, only packets of the same size, each starting with the sync byte."""
    n = ts_packets(data)
    return (f"note: not an MP4: an MPEG-TS stream, {n} packets of {TS_PACKET} bytes, the sync byte 0x47 at 0, "
            f"{TS_PACKET}, {2 * TS_PACKET} ... {(n - 1) * TS_PACKET}\n  no House to lose: no moov; each packet names "
            "its own stream (its PID), and the tables (PAT, PMT) travel in the stream")


def no_moov(data, tree):
    """No map room. A recording that stopped before its moov was written ends after mdat (ffmpeg writes moov last)."""
    last = f"right after {tree[-1].type} at {tree[-1].start} ({tree[-1].size} bytes)" if tree else "it is empty"
    return [_problem("error", f"no moov box: the file ends at {len(data)}, {last}",
                     "ffmpeg says: moov atom not found, then: Invalid data found when processing input",
                     "the moov was never written: a recording stopped before the end, where the muxer writes it; "
                     "the samples are there, but nothing says where one ends and the next begins")]


def _chunks(tracks):
    """Every chunk in file order as (start, end, track_ID, chunk number): from its stco offset to the end of its
    last sample."""
    spans = {}
    for track in tracks:
        for s in track.samples:
            spans[track.id, s.chunk] = (spans.get((track.id, s.chunk), (s.offset,))[0], s.offset + s.size)
    return sorted((start, end, n, c) for (n, c), (start, end) in spans.items())


def overlapping_chunks(tracks):
    """Each chunk against the ones after it in file order: no two chunks may claim the same bytes."""
    chunks, found = _chunks(tracks), []
    for i, (start, end, n, c) in enumerate(chunks):
        hits = takewhile(lambda later: later[0] < end, islice(chunks, i + 1, None))
        names = [f"track {m} chunk {d} at {s}" for s, _, m, d in hits]
        if names:
            found.append(_problem("error", f"track {n} chunk {c} (bytes {start} to {end - 1}) overlaps "
                                  + ", ".join(names),
                                  "a decoder is handed another chunk's bytes as this track's samples",
                                  "a chunk offset (stco or co64) is wrong: two chunks cannot hold the same bytes"))
    return found


def outside_mdat(tracks, tree, size):
    """Each chunk against the mdat boxes: it must lie inside one, not in another box or past the file's end."""
    mdats, found = [(b.payload, b.end) for b in tree if b.type == "mdat"], []
    stream = {track.id: i for i, track in enumerate(tracks)}            # ffmpeg's stream index: the trak's place
    for start, end, n, c in _chunks(tracks):
        if any(a <= start and end <= b for a, b in mdats):
            continue
        where = (f"past the end of the file ({size})" if end > size else
                 "outside mdat, in " + next(b.type for b in tree if b.start <= start < b.end))
        symptom = (f"ffmpeg says: stream {stream[n]}, offset 0x{start:x}: partial file" if start >= size else
                   "a decoder is handed bytes that are not samples, or samples cut short")
        found.append(_problem("error", f"track {n} chunk {c} (bytes {start} to {end - 1}) lies {where}", symptom,
                              "its chunk offset (stco or co64) is wrong, or the file is cut short"))
    return found


def _unclaimed(tracks, tree):
    """The other way round: every mdat byte should belong to a chunk (a warning if not). A fragmented file lists its
    samples in trun, not in the moov's tables: not checked."""
    if boxes.find(tree, "moof"):
        return []
    return [_problem("warning", f"mdat bytes {a} to {b - 1} ({b - a} bytes) belong to no sample",
                     "none: nothing reads them", "padding, or the bytes a wrong chunk offset should point to")
            for a, b in _gaps(_chunks(tracks), [(b.payload, b.end) for b in tree if b.type == "mdat"])]


def _gaps(chunks, mdats):
    """The (start, end) runs of each mdat's payload that no chunk covers."""
    gaps = []
    for a, b in mdats:
        at = a
        for start, end, _, _ in chunks:
            if start < b and end > a:
                gaps += [(at, start)] if start > at else []
                at = max(at, end)
        gaps += [(at, b)] if at < b else []
    return gaps


def nal_lengths(data, track):
    """Each sample of an H.264 or HEVC track, length prefix by length prefix (avcC's or hvcC's lengthSizeMinusOne +
    1 bytes): every NAL length must be more than 0 and fit in what is left of the sample."""
    config = track.entry.get("avcC") or track.entry.get("hvcC")
    if not config:
        return []
    size = config["lengthSizeMinusOne"] + 1
    bad = [(s, found) for s in track.samples if s.offset + s.size <= len(data) and (found := _overrun(data, s, size))]
    if not bad:
        return []
    s, (at, length, left) = bad[0]
    signed = length - (1 << 32) if length >= 1 << 31 else length       # ffmpeg prints the length as a signed int
    return [_problem("error", f"track {track.id}: a NAL length that does not fit in {len(bad)} of {len(track.samples)} "
                     f"samples; the first, sample {s.number} ({s.size} bytes at {s.offset}): length {length} at byte "
                     f"{at}, {left} bytes left",
                     f"the decoder says: Invalid NAL unit size ({signed} > {left}), and drops the picture",
                     "the sample is read from the wrong bytes (its chunk offset is wrong), or its bytes are damaged")]


def _overrun(data, s, size):
    """The first length prefix in sample s that does not fit, as (its byte in the sample, the length, the bytes left
    after the prefix); None if they all fit."""
    at = 0
    while at < s.size:
        left = s.size - at - size
        length = int.from_bytes(data[s.offset + at:s.offset + at + size], "big")
        if not 0 < length <= left:
            return at, length, left
        at += size + length
    return None


def durations(data, tree):
    """The clocks against each other, in seconds, each pair allowed one tick of the coarser clock: mvhd against the
    longest tkhd; each tkhd against its edits (elst), or its media (mdhd) when it has none; mdhd against its samples
    (the sum of stts); and each edit against the media it plays (to the end of the last picture shown)."""
    mvhd = tables.read_mvhd(data, boxes.find(tree, "moov/mvhd"))
    traks, mv, found = boxes.find_all(tree, "moov/trak"), mvhd["timescale"], []
    tkhds = [tables.read_tkhd(data, boxes.find(t.children, "tkhd"))["duration"] for t in traks]
    if tkhds and not _close(mvhd["duration"], mv, max(tkhds), mv):
        found.append(_clock("the movie", "mvhd says", mvhd["duration"], mv, "its longest track (tkhd)", max(tkhds),
                            mv))
    for trak, track, tkhd in zip(traks, tables.read_tracks(data, tree), tkhds):
        stts = sum(count * delta for count, delta in tables.read_stts(data, boxes.find(trak.children,
                                                                                       "mdia/minf/stbl/stts")))
        found += _track_clocks(track, tkhd, mv, stts)
    return found


def _track_clocks(track, tkhd, mv, stts):
    """One track's clocks, in order: tkhd against its edits or its media, mdhd against stts, each edit's end against
    the media's last composition time plus that sample's delta (B-frames: the last picture shown is not the last
    decoded)."""
    ts, name, found = track.timescale, f"track {track.id}", []
    length, scale, other = ((sum(e[0] for e in track.elst), mv, "its edit list (elst) adds up to") if track.elst
                            else (track.duration, ts, "its media (mdhd)"))
    if not _close(tkhd, mv, length, scale):
        found.append(_clock(name, "tkhd says", tkhd, mv, other, length, scale))
    if track.duration != stts:
        found.append(_clock(name, "mdhd says", track.duration, ts, "its samples (stts) add up to", stts, ts))
    ends = [s.dts for s in track.samples[1:]] + [stts]
    shown = max((s.cts + end - s.dts for s, end in zip(track.samples, ends)), default=0)
    for k, (segment, media_time, *_) in enumerate(track.elst, 1):
        if media_time >= 0 and Fraction(media_time, ts) + Fraction(segment, mv) > Fraction(shown + 1, ts):
            found.append(_clock(name, f"edit {k} plays the media to", media_time + Fraction(segment * ts, mv), ts,
                                "the media ends at", shown, ts))
    return found


def _close(a, a_scale, b, b_scale):
    """Two durations in ticks of two clocks are the same length, to within one tick of the coarser clock."""
    return abs(Fraction(a, a_scale) - Fraction(b, b_scale)) <= Fraction(1, min(a_scale, b_scale))


def _clock(name, what, a, a_scale, other, b, b_scale):
    """A warning that two clocks disagree: both lengths in seconds, then the ticks and clocks they came from."""
    return _problem("warning", f"{name}: {what} {a / a_scale:.4f} s, {other} {b / b_scale:.4f} s "
                    f"({a}/{a_scale} against {b}/{b_scale})",
                    "none in ffmpeg: it ignores the tkhd and mvhd durations and plays the shortest of mdhd, stts and "
                    "the edits; a player that trusts this box may show another length",
                    "a muxer or an editor updated one box and not the other")


def _fragments(tree):
    """A note when the file is fragmented: the moof boxes' trun tables hold the samples, and they are not checked."""
    moofs = boxes.find_all(tree, "moof")
    if not moofs:
        return []
    return [f"note: {len(moofs)} fragments (moof): their samples are listed in trun tables, which check does not "
            "read; only the moov and the mdat boxes were inspected"]
