"""Sound. Episode 20: PCM arithmetic (how many bytes raw sound takes), AAC's frame of 1,024 samples, and ADTS,
the 7-byte header that lets AAC frames travel without an MP4 around them."""

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
