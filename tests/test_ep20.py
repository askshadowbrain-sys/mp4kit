import hashlib
import json
import unittest
from pathlib import Path
from mp4kit import audio, boxes, tables
from tests.util import data, run_cli, run_cli_code

PHONE, AAC_ONLY = data("phone.mp4"), data("aac-only.m4a")
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep20.txt"
# The AudioSpecificConfig's first fields, as episode 21 will read them out of esds (phone: 11 90, aac-only: 12 08)
PHONE_ASC = {"audioObjectType": 2, "samplingFrequencyIndex": 3, "channelConfiguration": 2}
AAC_ONLY_ASC = {"audioObjectType": 2, "samplingFrequencyIndex": 4, "channelConfiguration": 1}


def sound(contents):
    """The sound track (hdlr soun) and its samples."""
    for trak in boxes.find_all(boxes.walk(contents), "moov/trak"):
        if tables.read_hdlr(contents, boxes.find(trak.children, "mdia/hdlr"))["handler_type"] == "soun":
            return trak, tables.sample_table(contents, trak)


def payloads(contents):
    """Each AAC frame's bytes, the sound track's samples in order."""
    return [bytes(contents[s.offset:s.offset + s.size]) for s in sound(contents)[1]]


def adts(contents, asc):
    """The sound track as an ADTS stream: each frame behind its own 7-byte header."""
    return b"".join(audio.adts_header(asc, len(p)) + p for p in payloads(contents))


def probe_audio(name):
    """ffprobe's audio stream for a committed file (captures/<name>.probe.json)."""
    streams = json.loads((CAPS / f"{name}.probe.json").read_text())["streams"]
    return next(s for s in streams if s["codec_type"] == "audio")


class Ep20(unittest.TestCase):
    def test_sample_rates(self):
        self.assertEqual(len(audio.SAMPLE_RATES), 13)
        self.assertEqual((audio.SAMPLE_RATES[3], audio.SAMPLE_RATES[4]), (48000, 44100))
        self.assertEqual((audio.SAMPLE_RATES[0], audio.SAMPLE_RATES[12]), (96000, 7350))

    def test_pcm_bytes(self):
        # ffmpeg decodes each file's sound to 16-bit PCM in exactly these many bytes:
        # ffmpeg -i phone.mp4 -map 0:a -f s16le - | wc -c → 384000; aac-only.m4a → 176400 (captures ep20)
        self.assertEqual(audio.pcm_bytes(2.0, 48000, 2, 16), 384000)
        self.assertEqual(audio.pcm_bytes(2.0, 44100, 1, 16), 176400)
        self.assertEqual(audio.pcm_bytes(1, 48000, 2, 16), 192000)             # one second of phone's sound
        self.assertEqual(audio.pcm_bytes(1, 44100, 2, 16), 176400)             # a CD's second
        self.assertEqual(audio.pcm_bytes(0.5, 44100, 1, 24), 66150)            # 22,050 samples of 3 bytes

    def test_frame_seconds(self):
        self.assertAlmostEqual(audio.frame_seconds(44100) * 1000, 23.22, places=2)   # 1,024 / 44,100
        self.assertAlmostEqual(audio.frame_seconds(48000) * 1000, 21.33, places=2)
        self.assertEqual(audio.frame_seconds(48000, 960), 0.02)                      # a 960-sample frame: 20 ms

    def test_the_sound_corridor(self):
        for contents, rate, channels, frames, total in ((PHONE, 48000, 2, 95, 24347), (AAC_ONLY, 44100, 1, 88, 16441)):
            trak, samples = sound(contents)
            mdhd = tables.read_mdhd(contents, boxes.find(trak.children, "mdia/mdhd"))
            entry = boxes.find(trak.children, "mdia/minf/stbl/stsd/mp4a")
            self.assertEqual(mdhd["timescale"], rate)                          # the corridor's clock is the sample rate
            self.assertEqual((boxes.u16(contents, entry.payload + 16), boxes.u16(contents, entry.payload + 18)),
                             (channels, 16))                                   # channelcount, samplesize
            self.assertEqual((len(samples), sum(s.size for s in samples)), (frames, total))
        stts = tables.read_stts(PHONE, boxes.find(sound(PHONE)[0].children, "mdia/minf/stbl/stts"))
        self.assertEqual(stts, [(94, 1024), (1, 768)])                         # 1,024 samples a parcel
        self.assertEqual(94 * 1024 + 768, 96000 + 1024)                        # the mdhd duration, 97,024

    def test_agrees_with_ffprobe(self):
        for name, contents, rate, channels in (("phone.mp4", PHONE, 48000, 2), ("aac-only.m4a", AAC_ONLY, 44100, 1)):
            probed = probe_audio(name)
            self.assertEqual((int(probed["sample_rate"]), probed["channels"]), (rate, channels))
            self.assertEqual(int(probed["nb_frames"]), len(sound(contents)[1]))
            self.assertEqual(probed["duration_ts"], 2 * rate)                  # 2 s presented: tkhd's length

    def test_adts_header(self):
        header = audio.adts_header(PHONE_ASC, 238)
        self.assertEqual(header.hex(), "fff14c801ebffc")                       # ffmpeg's first header for phone
        self.assertEqual(len(header), 7)
        self.assertEqual(int.from_bytes(header, "big") >> 13 & 0x1FFF, 7 + 238)   # frame length counts the header
        self.assertEqual(len(payloads(PHONE)[0]), 238)
        self.assertEqual(audio.adts_header(AAC_ONLY_ASC, len(payloads(AAC_ONLY)[0])).hex(), "fff1504021fffc")

    def test_adts_matches_ffmpeg(self):
        # ffmpeg -i FILE -map 0:a -c:a copy -f adts OUT: 25,012 and 17,057 bytes, with these SHA-256 (captures ep20)
        stream = adts(PHONE, PHONE_ASC)
        self.assertEqual(len(stream), 24347 + 95 * 7)
        self.assertEqual(hashlib.sha256(stream).hexdigest(),
                         "2da8e41153b728ca73e57418e1f082245369c3588e8ca63586c0f23856e6aef0")
        stream = adts(AAC_ONLY, AAC_ONLY_ASC)
        self.assertEqual(len(stream), 16441 + 88 * 7)
        self.assertEqual(hashlib.sha256(stream).hexdigest(),
                         "796e0e97ee8a05838a43e7464e99853818ce0ce75deb8db375945ecf908a7041")

    def test_split_adts_round_trip(self):
        fields, back = audio.split_adts(adts(PHONE, PHONE_ASC))
        self.assertEqual((fields, back), (PHONE_ASC, payloads(PHONE)))         # the same 95 payloads, same fields
        self.assertEqual(len(back), 95)
        fields, back = audio.split_adts(adts(AAC_ONLY, AAC_ONLY_ASC))
        self.assertEqual((fields, len(back)), (AAC_ONLY_ASC, 88))

    def test_split_adts_crc_and_errors(self):
        # protection_absent 0: a 2-byte CRC follows the 7 bytes, and the frame length counts it
        crc = bytearray(audio.adts_header(PHONE_ASC, 2 + 3))
        crc[1] = crc[1] & 0xFE
        fields, back = audio.split_adts(bytes(crc) + b"\x12\x34" + b"abc")
        self.assertEqual((fields, back), (PHONE_ASC, [b"abc"]))
        self.assertEqual(audio.split_adts(b""), (None, []))
        with self.assertRaisesRegex(ValueError, "no ADTS sync word at byte 10"):
            audio.split_adts(audio.adts_header(PHONE_ASC, 3) + b"abc" + b"\x00" * 7)

    def test_cmd_dump_pcm(self):
        printed = run_cli("dump", "testfiles/out/phone.mp4", "--pcm")
        self.assertEqual(printed, EXPECTED.read_text())
        self.assertEqual(len(printed.splitlines()), 5)
        self.assertIn("= 384000 bytes", printed)
        self.assertIn("AAC in the file: 24347 bytes (stsz), 15.8 times smaller", printed)

    def test_cmd_dump_pcm_aac_only(self):
        self.assertEqual(run_cli("dump", "testfiles/out/aac-only.m4a", "--pcm").splitlines(), [
            "track 1 soun mp4a: 44100 samples/s (mdhd), channelcount 1, samplesize 16",
            "88 AAC frames (stsz) of 1024 samples, each 23.2 ms",
            "raw PCM: 2 s (tkhd) x 44100 x 1 channel x 2 bytes = 176400 bytes",
            "AAC in the file: 16441 bytes (stsz), 10.7 times smaller",
            "one second: 88200 bytes of PCM, 8220 of AAC; AAC saves 79980 bytes"])

    def test_cmd_dump_pcm_no_sound(self):
        self.assertEqual(run_cli_code("dump", "testfiles/out/f1.mp4", "--pcm"), (0, "no sound track with samples\n"))
        self.assertEqual(run_cli_code("dump", "testfiles/out/broken-nomoov.mp4", "--pcm"),
                         (0, "no sound track with samples\nno moov box\n"))
        self.assertEqual(run_cli("dump", "testfiles/out/frag-cmaf.mp4", "--pcm"),
                         "no sound track with samples\n")                      # its samples are in moofs (ep30)


if __name__ == "__main__":
    unittest.main()
