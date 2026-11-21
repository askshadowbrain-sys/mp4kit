"""Writing an MP4: the workshop. Episode 24: the zipper, a plan of which track's chunk goes next in mdat (interleave),
from each sample's decode time on the movie's timeline (timeline). Episode 26: the same drawers, built instead of
opened: each sample table written back from a track's samples (runs, stsc_rules, table_box, write_stsz, write_stbl).
Episode 27: the map room moved next to the front door (faststart, shift_chunk_offsets). Episode 28: the signs, clocks
and tray built from their fields (write_ftyp, write_mvhd, write_tkhd, write_mdhd, write_hdlr, write_media_header,
write_dinf, write_elst, write_avcc, write_avc1). Episode 29: a whole House from two piles of parcels: the sound tray's
sheet (write_esds, write_mp4a), a Track from a plain stream (video_track, audio_track), a corridor (write_trak), and
the House (mux)."""
import dataclasses
import struct
from fractions import Fraction
from itertools import accumulate

from . import audio, boxes, nal, tables


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


def shift_chunk_offsets(data, tree, delta):
    """Every chunk offset of every track (stco, co64) moved by `delta` bytes, in place in `data`, a bytearray holding
    the boxes of `tree`. phone, by its moov's 3,412: 48 → 3,460, ..., 106,571 → 109,983. An stco offset pushed past
    4 GiB no longer fits in its 4 bytes: a BoxError (it would need co64, a bigger moov, and so a bigger `delta`)."""
    for kind, fmt in (("stco", "I"), ("co64", "Q")):
        for box in boxes.find_all(tree, "moov/trak/mdia/minf/stbl/" + kind):
            offsets = tables.read_stco(data, box)
            if kind == "stco" and max(offsets, default=0) + delta > 0xFFFFFFFF:
                raise boxes.BoxError(f"stco at {box.start}: {max(offsets)} + {delta} is past 4 GiB, it needs co64")
            struct.pack_into(f">{len(offsets)}{fmt}", data, box.payload + 8, *(o + delta for o in offsets))


def faststart(data):
    """The map room moved next to the front door: the moov cut from behind the mdat and put straight after ftyp, so a
    player reading from the start meets the plans first. Everything it jumps (free, mdat) moves back by the moov's
    size, so every chunk offset grows by that size too. A file with no mdat before its moov is given back as it is.
    Refused (BoxError): no moov; fragments (moof); an mdat after the moov (its chunks would not move); saio (cenc: its
    offsets point into the moov itself, which moves by another amount)."""
    tree = boxes.walk(data)
    kinds = [b.type for b in tree]
    if "moov" not in kinds:
        raise boxes.BoxError("no moov: nothing to move")
    at = kinds.index("moov")
    if "mdat" not in kinds[:at]:
        return bytes(data)
    for bad, why in (("moof" in kinds, "fragments (moof)"), ("mdat" in kinds[at:], "an mdat after the moov"),
                     (boxes.find_all(tree, "moov/trak/mdia/minf/stbl/saio"), "saio (cenc) offsets into the moov")):
        if bad:
            raise boxes.BoxError(f"not moved: {why}")
    moov, front = tree[at], tree[0].end if kinds[0] == "ftyp" else 0
    room = bytearray(data[moov.start:moov.end])
    shift_chunk_offsets(room, boxes.walk(room), moov.size)
    return bytes(data[:front]) + bytes(room) + bytes(data[front:moov.start]) + bytes(data[moov.end:])


MATRIX = struct.pack(">9i", 0x10000, 0, 0, 0, 0x10000, 0, 0, 0, 0x40000000)   # identity: the picture as it is


def write_ftyp(major, minor, brands):
    """The front-door nameplate: major brand, minor version, compatible brands. The reverse of boxes.read_ftyp."""
    return boxes.box("ftyp", major.encode("latin-1"), struct.pack(">I", minor), *(b.encode("latin-1") for b in brands))


def write_mvhd(timescale, duration, next_track_id):
    """The wall clock (version 0, 108 bytes): created and modified at 0, its ticks and length, rate 1.0, volume 1.0,
    10 reserved bytes, the identity matrix, six zero QuickTime preview fields, the next free track_ID."""
    return boxes.full_box("mvhd", 0, 0, struct.pack(">IIIIIH", 0, 0, timescale, duration, 0x10000, 0x100), bytes(10),
                          MATRIX, bytes(24), struct.pack(">I", next_track_id))


def write_tkhd(track_id, duration, width, height, volume, group=0):
    """The corridor's sign (version 0, 92 bytes): flags 3 (enabled, in the movie), track_ID, its length on the movie
    clock, layer 0, alternate group (ffmpeg writes its codec type: 0 video, 1 sound), volume (1 full, 0 for a picture)
    in 8.8, the identity matrix, width and height in 16.16."""
    return boxes.full_box("tkhd", 0, 3, struct.pack(">IIIII", 0, 0, track_id, 0, duration), bytes(8),
                          struct.pack(">hhHH", 0, group, volume << 8, 0), MATRIX,
                          struct.pack(">II", width << 16, height << 16))


def write_mdhd(timescale, duration, language="und"):
    """The room's clock (version 0, 32 bytes): its ticks and length, the language's three letters 5 bits each (each
    letter's code minus 0x60), quality 0. The reverse of tables.read_mdhd."""
    code = sum((ord(c) - 0x60) << shift for c, shift in zip(language, (10, 5, 0)))
    return boxes.full_box("mdhd", 0, 0, struct.pack(">IIIIHH", 0, 0, timescale, duration, code, 0))


def write_hdlr(handler, name):
    """The door sign: pre_defined 0, handler_type (vide, soun), 12 reserved bytes, a name ending in a zero byte."""
    return boxes.full_box("hdlr", 0, 0, bytes(4), handler.encode("latin-1"), bytes(12), name.encode() + b"\0")


def write_media_header(handler):
    """The room's own small sign: vmhd for pictures (flags 1, graphicsmode and opcolor 0: 20 bytes), smhd for sound
    (balance 0: 16 bytes)."""
    return boxes.full_box("vmhd", 0, 1, bytes(8)) if handler == "vide" else boxes.full_box("smhd", 0, 0, bytes(4))


def write_dinf():
    """Where the samples live: dinf/dref with one entry, `url ` with flags 1, "in this file" (36 bytes)."""
    return boxes.box("dinf", boxes.full_box("dref", 0, 0, struct.pack(">I", 1), boxes.full_box("url ", 0, 1)))


def write_elst(segment_duration, media_time):
    """The entrance timer (version 0, 28 bytes): one edit, play `segment_duration` (movie clock) from `media_time`
    (track clock) at rate 1.0. The caller puts it in an edts."""
    return boxes.full_box("elst", 0, 0, struct.pack(">IIiHH", 1, segment_duration, media_time, 1, 0))


def write_avcc(sps, pps):
    """The instruction sheets: version 1, the SPS's profile, compatibility and level, 0xFF (4-byte lengths), 0xE1 (one
    SPS), the SPS, one PPS; profiles but 66, 77, 88 add chroma format, bit depths and no SPS extensions."""
    tail = b""
    if sps[1] not in (66, 77, 88):
        s = nal.parse_sps(sps)
        depths = (0xF8 | s["bit_depth_luma"] - 8, 0xF8 | s["bit_depth_chroma"] - 8)
        tail = bytes([0xFC | s["chroma_format_idc"], *depths, 0])
    return boxes.box("avcC", bytes([1, *sps[1:4], 0xFF, 0xE1]), struct.pack(">H", len(sps)), sps,
                     b"\x01", struct.pack(">H", len(pps)), pps, tail)


def write_avc1(width, height, avcc):
    """The tray's sheet for H.264: 6 reserved bytes, data_reference_index 1, 16 zero bytes, width, height, 72 dpi
    twice, 0, frame_count 1, a 32-byte compressorname left empty, depth 24, pre_defined -1; then the avcC."""
    return boxes.box("avc1", bytes(6), struct.pack(">H", 1), bytes(16),
                     struct.pack(">HHIIIH", width, height, 0x480000, 0x480000, 0, 1), bytes(32),
                     struct.pack(">Hh", 0x18, -1), avcc)


def descriptor(tag, *parts):
    """One envelope (an MPEG-4 descriptor), written the way ffmpeg writes it: the tag, then the length in four bytes of
    7 bits (80 80 80 and the length; read_descriptor reads it back), then the contents. Contents up to 127 bytes."""
    body = b"".join(parts)
    return bytes([tag, 0x80, 0x80, 0x80, len(body)]) + body


def write_esds(asc, avg_bitrate, es_id=0):
    """The sound tray's sheet (esds): ES_Descriptor (ES_ID, flags 0) holding the DecoderConfigDescriptor (0x40 MPEG-4
    audio, 0x15 = stream type 5 sound, bufferSizeDB 0, max and average bitrate) holding the AudioSpecificConfig,
    then an SLConfigDescriptor (predefined 2). ffmpeg's ES_ID is the track_ID. The reverse of audio.read_esds."""
    config = descriptor(0x04, bytes([0x40, 0x15]), bytes(3), struct.pack(">II", avg_bitrate, avg_bitrate),
                        descriptor(0x05, asc))
    return boxes.full_box("esds", 0, 0, descriptor(0x03, struct.pack(">HB", es_id, 0), config,
                                                   descriptor(0x06, b"\x02")))


def write_mp4a(channels, sample_rate, esds):
    """The tray's sheet for AAC: 6 reserved bytes, data_reference_index 1, 8 reserved, channelcount, samplesize 16,
    pre_defined and reserved 0, samplerate in 16.16; then the esds. The reverse of tables.read_audio_entry."""
    return boxes.box("mp4a", bytes(6), struct.pack(">H", 1), bytes(8),
                     struct.pack(">HHII", channels, 16, 0, sample_rate << 16), esds)


def video_clock(fps):
    """A video track's clock, as ffmpeg's movenc picks it: the frame rate, doubled until it reaches 10,000 ticks a
    second (30 -> 15,360, 25 -> 12,800), so every frame lasts a whole number of ticks."""
    timescale = fps
    while timescale < 10000:
        timescale *= 2
    return timescale


def display_order(units, sps, pps):
    """Each access unit's slot in display order (from 0): sorted by picture order count (the slice header's
    pic_order_cnt_lsb, episode 17), which restarts at each IDR, so first by how many IDRs came before. A stream with
    no pic_order_cnt_lsb (POC type 1 or 2) is shown in decode order. Only the lsb is read: no wrap within a GOP."""
    s, p = nal.parse_sps(sps), nal.parse_pps(pps)
    slices = [next(u for u in au if u[0] & 31 in (1, 5)) for au in units]
    gop = list(accumulate(x[0] & 31 == 5 for x in slices))
    poc = [nal.read_slice_header(x, s, p).get("pic_order_cnt_lsb", i) for i, x in enumerate(slices)]
    slots = [0] * len(units)
    for slot, i in enumerate(sorted(range(len(units)), key=lambda i: (gop[i], poc[i]))):
        slots[i] = slot
    return slots


def video_track(annexb, fps, timescale=None):
    """A Track from an Annex B H.264 stream: one sample per access unit (its NAL units but SPS and PPS, which go to
    avcC, behind 4-byte lengths), a frame every timescale / fps ticks in decode order (the clock: video_clock).
    Each cts is the picture's display slot plus the least shift that keeps every cts at or after its dts; the
    entrance timer starts at that shift, so the first picture shows at 0 (phone: 512, one frame)."""
    timescale = timescale or video_clock(fps)
    units = nal.access_units(nal.split_annexb(annexb))
    sps, pps = (next((u for au in units for u in au if u[0] & 31 == t), None) for t in (7, 8))
    if sps is None or pps is None or timescale % fps:
        raise ValueError(f"needs an SPS and a PPS, and a clock ({timescale}) that counts whole ticks a frame")
    display, delta = display_order(units, sps, pps), timescale // fps
    shift = max(i - slot for i, slot in enumerate(display))
    payloads = [nal.to_avcc([u for u in au if u[0] & 31 not in (7, 8)]) for au in units]
    samples = [tables.Sample(i + 1, i * delta, (slot + shift) * delta, len(b), 0, any(u[0] & 31 == 5 for u in au))
               for i, (slot, b, au) in enumerate(zip(display, payloads, units))]
    width, height = nal.picture_size(nal.parse_sps(sps))
    entry = {"type": "avc1", "width": width, "height": height, "avcC": {"SPS": [sps], "PPS": [pps]}}
    return tables.Track(1, "vide", timescale, entry, samples, [(len(units) * delta, shift * delta, 1, 0)],
                        duration=len(units) * delta, payloads=payloads)


def audio_track(adts, priming=0):
    """A Track from an ADTS AAC stream: one sample per frame, 1,024 ticks each on a clock of the sample rate, all of
    them sync samples. ADTS has no field for the priming, so it is given: the entrance timer skips that many. The
    average bitrate is the frames' bits over their length, as ffmpeg's movenc computes it."""
    asc, frames = audio.split_adts(adts)
    rate, duration = audio.SAMPLE_RATES[asc["samplingFrequencyIndex"]], 1024 * len(frames)
    samples = [tables.Sample(i + 1, i * 1024, i * 1024, len(f), 0, True) for i, f in enumerate(frames)]
    esds = {"ASC": audio.asc_bytes(asc), "avgBitrate": sum(map(len, frames)) * 8 * rate // duration}
    entry = {"type": "mp4a", "channelcount": asc["channelConfiguration"], "samplerate": rate, "esds": esds}
    return tables.Track(2, "soun", rate, entry, samples, [(duration - priming, priming, 1, 0)], duration=duration,
                        payloads=frames)


def write_stsd(track):
    """The tray (stsd): entry_count 1, then the track's one sheet, avc1 + avcC or mp4a + esds."""
    e = track.entry
    if e["type"] == "avc1":
        sheet = write_avc1(e["width"], e["height"], write_avcc(e["avcC"]["SPS"][0], e["avcC"]["PPS"][0]))
    else:
        sheet = write_mp4a(e["channelcount"], e["samplerate"], write_esds(e["esds"]["ASC"], e["esds"]["avgBitrate"],
                                                                          track.id))
    return boxes.full_box("stsd", 0, 0, struct.pack(">I", 1), sheet)


def write_trak(track, stsd, chunk_offsets, chunks, movie_timescale):
    """One corridor: tkhd (sound: volume 1, alternate group 1), edts/elst, then mdia: mdhd, hdlr, minf (media header,
    dinf, stbl). A built track's edit counts on its own clock; here it goes on the movie's, as tkhd's length."""
    length, media_time = track.elst[0][0] * movie_timescale // track.timescale, track.elst[0][1]
    vide, e = track.handler == "vide", track.entry
    tkhd = write_tkhd(track.id, length, e.get("width", 0), e.get("height", 0), int(not vide), int(not vide))
    minf = boxes.box("minf", write_media_header(track.handler), write_dinf(),
                     write_stbl(track, stsd, chunk_offsets, chunks))
    mdia = boxes.box("mdia", write_mdhd(track.timescale, track.duration),
                     write_hdlr(track.handler, "VideoHandler" if vide else "SoundHandler"), minf)
    return boxes.box("trak", tkhd, boxes.box("edts", write_elst(length, media_time)), mdia)


def mux(tracks, fast=False):
    """The House: ftyp, free (ffmpeg's 8 bytes kept for a largesize mdat), mdat (every chunk, in interleave's order),
    then moov: mvhd on the finest track clock (the largest timescale), a trak each. Tracks are numbered 1, 2, ... in
    order. fast=True: the moov moved to the front by faststart (episode 27). 32-bit sizes only."""
    tracks = [dataclasses.replace(t, id=n) for n, t in enumerate(tracks, 1)]
    movie, head = max(t.timescale for t in tracks), write_ftyp("isom", 512, ["isom", "iso2", "avc1", "mp41"])
    head, parcels, offsets, counts = head + boxes.box("free"), [], [[] for _ in tracks], [[] for _ in tracks]
    at = len(head) + 8
    for n, first, count in interleave(tracks):
        chunk = tracks[n - 1].payloads[first - 1:first - 1 + count]
        offsets[n - 1].append(at)
        counts[n - 1].append(count)
        parcels += chunk
        at += sum(map(len, chunk))
    traks = [write_trak(t, write_stsd(t), offsets[i], counts[i], movie) for i, t in enumerate(tracks)]
    length = max(t.elst[0][0] * movie // t.timescale for t in tracks)
    data = head + boxes.box("mdat", *parcels) + boxes.box("moov", write_mvhd(movie, length, len(tracks) + 1), *traks)
    return faststart(data) if fast else data
