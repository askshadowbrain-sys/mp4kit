"""Sound. Episode 20: PCM arithmetic (how many bytes raw sound takes), AAC's frame of 1,024 samples, and ADTS,
the 7-byte header that lets AAC frames travel without an MP4 around them. Episode 21: esds, the sheet in the
sound corridor's tray, in nested envelopes (descriptors), and the AudioSpecificConfig inside the last one. Episode
22: priming, the encoder's warm-up that the entrance timer (elst) skips, and asc_bytes, parse_asc backwards."""
from . import boxes
from . import timing

# AAC's sample rates, by the 4-bit index that ADTS and the AudioSpecificConfig store (3 is 48,000, 4 is 44,100)
SAMPLE_RATES = [96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350]


def pcm_bytes(seconds, sample_rate, channels, bits):
    """Raw sound's size: `sample_rate` numbers a second for each of `channels`, each `bits` wide
    (2.0 s x 48,000 x 2 channels x 16 bits = 384,000 bytes)."""
    return round(seconds * sample_rate) * channels * bits // 8


def frame_seconds(sample_rate, frame_length=1024):
    """How long one AAC frame plays: its `frame_length` samples at `sample_rate` (1,024 / 44,100 = 23.2 ms)."""
    return frame_length / sample_rate


def adts_header(asc, payload_size):
    """The 7-byte ADTS header for one AAC frame of `payload_size` bytes: sync word FFF, MPEG-4, no CRC, the
    profile (object type - 1), the sample-rate index and the channels from `asc`, then the frame's length with
    the header included, and buffer fullness 7FF (variable bitrate)."""
    v = (0xFFF << 44 | 1 << 40 | (asc["audioObjectType"] - 1) << 38 | asc["samplingFrequencyIndex"] << 34
         | asc["channelConfiguration"] << 30 | (7 + payload_size) << 13 | 0x7FF << 2)
    return v.to_bytes(7, "big")


def split_adts(stream):
    """An ADTS stream back into (the first header's fields, each frame's payload). Each header says how long its
    frame is, so the next sync word is found by jumping, not searching; a header with a CRC is 9 bytes, not 7."""
    fields, payloads, at = None, [], 0
    while at < len(stream):
        v = int.from_bytes(stream[at:at + 7], "big")
        if v >> 44 != 0xFFF:
            raise ValueError(f"no ADTS sync word at byte {at}")
        if fields is None:
            fields = {"audioObjectType": (v >> 38 & 3) + 1, "samplingFrequencyIndex": v >> 34 & 15,
                      "channelConfiguration": v >> 30 & 7}
        header, length = 7 if v >> 40 & 1 else 9, v >> 13 & 0x1FFF
        payloads.append(bytes(stream[at + header:at + length]))
        at = at + length
    return fields, payloads


def read_descriptor(data, at):
    """One envelope's label (an MPEG-4 descriptor): a tag byte, then its length in 1 to 4 bytes of 7 bits each,
    the top bit saying another byte follows (ffmpeg writes 80 80 80 25 for 37). Returns (tag, length, where the
    contents start)."""
    tag, length = data[at], 0
    for i in range(1, 5):
        length = length << 7 | data[at + i] & 0x7F
        if not data[at + i] & 0x80:
            return tag, length, at + i + 1
    raise boxes.BoxError(f"descriptor at {at}: its length runs past 4 bytes")


def _open(data, at, tag, end):
    """Open the envelope at `at`, which must be a `tag` descriptor that ends inside `end`; return (contents, its end)."""
    found, length, inside = read_descriptor(data, at)
    if found != tag or inside + length > end:
        raise boxes.BoxError(f"descriptor at {at}: expected tag {tag:#04x} inside {end}, found {found:#04x} "
                             f"of {length} bytes")
    return inside, inside + length


def read_esds(data, box):
    """The sheet in the tray (esds, a FullBox): an ES_Descriptor (0x03) holding a DecoderConfigDescriptor (0x04: the
    object type, 0x40 for MPEG-4 audio, stream type 5 for sound, buffer size and bitrates) holding the
    DecoderSpecificInfo (0x05), the AudioSpecificConfig; an SLConfigDescriptor (0x06) closes the ES_Descriptor."""
    at, es_end = _open(data, box.payload + 4, 0x03, box.end)
    flags = data[at + 2]          # dependsOn_ES_ID, URL and OCR_ES_Id follow when their flag bits are set
    after = at + 3 + 2 * (flags >> 7)
    after = after + (1 + data[after] if flags & 0x40 else 0) + 2 * (flags >> 5 & 1)
    dc, dc_end = _open(data, after, 0x04, es_end)
    asc, asc_end = _open(data, dc + 13, 0x05, dc_end)
    fields = {"ES_ID": boxes.u16(data, at), "objectTypeIndication": data[dc], "streamType": data[dc + 1] >> 2,
              "bufferSizeDB": int.from_bytes(data[dc + 2:dc + 5], "big"), "maxBitrate": boxes.u32(data, dc + 5),
              "avgBitrate": boxes.u32(data, dc + 9), "ASC": bytes(data[asc:asc_end])}
    fields.update(parse_asc(fields["ASC"]))
    sl, _ = _open(data, dc_end, 0x06, es_end)
    fields.update(sample_rate=SAMPLE_RATES[fields["samplingFrequencyIndex"]], SLConfig_predefined=data[sl],
                  codec=f"mp4a.{fields['objectTypeIndication']:02x}.{fields['audioObjectType']}")
    return fields


boxes.DECODERS["esds"] = read_esds


def parse_asc(asc):
    """The AudioSpecificConfig's first 13 bits: audioObjectType (5 bits, 2 = AAC LC), samplingFrequencyIndex (4
    bits, into SAMPLE_RATES) and channelConfiguration (4 bits): 12 08 = 00010 0100 0001 = AAC LC, 44,100 Hz, 1
    channel. The same three fields an ADTS header carries."""
    bits = int.from_bytes(asc[:2], "big")
    fields = {"audioObjectType": bits >> 11, "samplingFrequencyIndex": bits >> 7 & 15,
              "channelConfiguration": bits >> 3 & 15}
    if len(asc) < 2 or fields["audioObjectType"] == 31 or fields["samplingFrequencyIndex"] > 12:
        raise ValueError(f"AudioSpecificConfig {bytes(asc).hex(' ')}: escaped object type or rate not read")
    return fields


def priming(elst):
    """How many samples of warm-up the entrance timer skips: the first real edit's media_time. A sound track's clock
    (mdhd) ticks once a sample, so its ticks are samples: ffmpeg's AAC encoder primes 1,024 (one frame). Empty edits
    (-1) are skipped; no edit list gives 0, and a player cannot tell priming from sound."""
    return next((media_time for _, media_time, *_ in elst if media_time != -1), 0)


def edit_window(elst, media_timescale, movie_timescale):
    """The first real edit as (where it starts in the track, how long it plays), in seconds: its media_time on the
    track's clock, its segment_duration on the movie's. aac-only: (1,024 / 44,100, 88,200 / 44,100) = (0.023, 2.0),
    out of the track's 89,224 ticks."""
    for segment_duration, media_time, *_ in elst:
        if media_time != -1:
            return timing.seconds(media_time, media_timescale), timing.seconds(segment_duration, movie_timescale)
    raise ValueError("no edit plays the track (no edit list, or only empty edits)")


def asc_bytes(asc):
    """parse_asc backwards: the three fields an ADTS header carries, packed into a 2-byte AudioSpecificConfig (5 + 4
    + 4 bits, then three flags of 0): AAC LC, index 4, 1 channel = 12 08. ADTS gives these back; it has no field
    for the priming, which lives in the edit list, so stripping the boxes loses it."""
    aot, index, channels = asc["audioObjectType"], asc["samplingFrequencyIndex"], asc["channelConfiguration"]
    if not (0 < aot < 31 and index <= 12 and channels < 16):
        raise ValueError(f"AudioSpecificConfig fields {asc}: out of the 2-byte form's range")
    return (aot << 11 | index << 7 | channels << 3).to_bytes(2, "big")
