import json
import tempfile
import unittest
from pathlib import Path
from mp4kit import boxes, tables
from tests.util import data, run_cli, run_cli_code

PHONE, SUBS, AAC = data("phone.mp4"), data("subs.mp4"), data("aac-only.m4a")
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep12.txt"
KINDS = {"vide": "video", "soun": "audio", "sbtl": "subtitle"}          # handler_type → ffprobe's codec_type


def mdhd_v1(timescale, duration):
    """A version-1 mdhd in memory: 64-bit creation, modification and duration; 44 bytes."""
    body = bytes(16) + timescale.to_bytes(4, "big") + duration.to_bytes(8, "big") + (0x15C7).to_bytes(2, "big")
    return (44).to_bytes(4, "big") + b"mdhd" + b"\x01\x00\x00\x00" + body + bytes(2)


def probe(name):
    """ffprobe's streams for a committed file (testfiles/captures/<name>.probe.json)."""
    return json.loads((CAPS / f"{name}.probe.json").read_text())["streams"]


class Ep12(unittest.TestCase):
    def test_read_mdhd_phone(self):
        video, audio = boxes.find_all(boxes.walk(PHONE), "moov/trak/mdia/mdhd")
        self.assertEqual((video.start, video.size, audio.start, audio.size), (109004, 32, 110458, 32))
        self.assertEqual(tables.read_mdhd(PHONE, video),
                         {"version": 0, "timescale": 15360, "duration": 30720, "seconds": 2.0, "language": "und"})
        self.assertEqual(tables.read_mdhd(PHONE, audio),
                         {"version": 0, "timescale": 48000, "duration": 97024, "seconds": 97024 / 48000,
                          "language": "und"})

    def test_read_mdhd_subtitle(self):
        mdhd = boxes.find_all(boxes.walk(SUBS), "moov/trak/mdia/mdhd")[2]
        self.assertEqual(mdhd.start, 112270)
        self.assertEqual(tables.read_mdhd(SUBS, mdhd),
                         {"version": 0, "timescale": 1000000, "duration": 1900000, "seconds": 1.9,
                          "language": "eng"})

    def test_language(self):
        self.assertEqual(SUBS[112270 + 28:112270 + 30], b"\x15\xc7")        # the subtitle mdhd's language bytes
        self.assertEqual(tables.language(0x15C7), "eng")                   # 0 00101 01110 00111: 5 14 7
        self.assertEqual(tables.language(0x55C4), "und")                   # 0 10101 01110 00100: 21 14 4
        self.assertEqual(tables.language(0x15C7 | 0x8000), "eng")          # the pad bit is not a letter

    def test_two_clocks(self):
        tree = boxes.walk(PHONE)
        mvhd = tables.read_mvhd(PHONE, boxes.find(tree, "moov/mvhd"))
        tkhd = tables.read_tkhd(PHONE, boxes.find_all(tree, "moov/trak/tkhd")[1])
        mdhd = tables.read_mdhd(PHONE, boxes.find_all(tree, "moov/trak/mdia/mdhd")[1])
        self.assertEqual((mvhd["timescale"], tkhd["duration"]), (48000, 96000))   # the movie clock: 2.0 s
        self.assertEqual((mdhd["timescale"], mdhd["duration"]), (48000, 97024))   # the audio's clock: 1024 more
        self.assertEqual(mdhd["duration"] - 1024, tkhd["duration"])               # elst media_time 1024 (ep18)
        aac = tables.read_mdhd(AAC, boxes.find(boxes.walk(AAC), "moov/trak/mdia/mdhd"))
        self.assertEqual((aac["timescale"], aac["duration"]), (44100, 89224))     # mvhd 88200: 1024 more

    def test_mdhd_matches_ffprobe(self):
        for name, contents in (("phone.mp4", PHONE), ("subs.mp4", SUBS)):
            found = boxes.find_all(boxes.walk(contents), "moov/trak/mdia/mdhd")
            for mdhd, stream in zip(found, probe(name)):
                fields = tables.read_mdhd(contents, mdhd)
                self.assertEqual(f"1/{fields['timescale']}", stream["time_base"])
                self.assertEqual(fields["language"], stream["tags"]["language"])
        self.assertEqual(probe("subs.mp4")[2]["duration_ts"], 1900000)
        self.assertEqual(probe("phone.mp4")[0]["duration_ts"], 30720)
        self.assertEqual(probe("phone.mp4")[1]["duration_ts"], 96000)   # ffprobe trims the 1024 priming ticks

    def test_read_hdlr_subs(self):
        found = boxes.find_all(boxes.walk(SUBS), "moov/trak/mdia/hdlr")
        self.assertEqual([(b.start, b.size) for b in found], [(109063, 45), (110517, 45), (112302, 48)])
        self.assertEqual([tables.read_hdlr(SUBS, b) for b in found],
                         [{"handler_type": "vide", "name": "VideoHandler"},
                          {"handler_type": "soun", "name": "SoundHandler"},
                          {"handler_type": "sbtl", "name": "SubtitleHandler"}])

    def test_read_hdlr_meta(self):
        hdlr = boxes.find(boxes.walk(SUBS), "moov/udta/meta/hdlr")
        self.assertEqual((hdlr.start, hdlr.size), (112698, 33))
        self.assertEqual(tables.read_hdlr(SUBS, hdlr), {"handler_type": "mdir", "name": ""})   # name: one 00 byte

    def test_hdlr_matches_ffprobe(self):
        found = boxes.find_all(boxes.walk(SUBS), "moov/trak/mdia/hdlr")
        for hdlr, stream in zip(found, probe("subs.mp4")):
            fields = tables.read_hdlr(SUBS, hdlr)
            self.assertEqual(KINDS[fields["handler_type"]], stream["codec_type"])
            self.assertEqual(fields["name"], stream["tags"]["handler_name"])

    def test_read_mdhd_version_1(self):
        blob = mdhd_v1(90000, 2 ** 32 + 90000)
        self.assertEqual(tables.read_mdhd(blob, boxes.read_header(blob, 0)),
                         {"version": 1, "timescale": 90000, "duration": 2 ** 32 + 90000,
                          "seconds": (2 ** 32 + 90000) / 90000, "language": "eng"})

    def test_read_mdhd_short_box(self):
        blob = (24).to_bytes(4, "big") + PHONE[109004 + 4:109004 + 24]
        with self.assertRaisesRegex(boxes.BoxError, "mdhd at 0: version 0 needs 32 bytes, box has 24"):
            tables.read_mdhd(blob, boxes.read_header(blob, 0))

    def test_read_mdhd_timescale_0(self):
        blob = PHONE[109004:109004 + 20] + bytes(4) + PHONE[109004 + 24:109004 + 32]
        with self.assertRaisesRegex(boxes.BoxError, "mdhd at 0: timescale 0, a clock that never ticks"):
            tables.read_mdhd(blob, boxes.read_header(blob, 0))

    def test_read_hdlr_short_box(self):
        blob = (20).to_bytes(4, "big") + PHONE[109036 + 4:109036 + 20]
        with self.assertRaisesRegex(boxes.BoxError, "hdlr at 0: needs 32 bytes, box has 20"):
            tables.read_hdlr(blob, boxes.read_header(blob, 0))

    def test_registry(self):
        self.assertIs(boxes.DECODERS["mdhd"], tables.read_mdhd)
        self.assertIs(boxes.DECODERS["hdlr"], tables.read_hdlr)

    def test_cmd_dump_find_hdlr(self):
        printed = run_cli("dump", "testfiles/out/subs.mp4", "--find", "hdlr")
        self.assertEqual(printed, EXPECTED.read_text())

    def test_cmd_dump_bad_mdhd(self):
        blob = bytearray(PHONE)
        blob[109004 + 8] = 1                                         # version 1, but only 32 bytes
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mdhd-v1-short.mp4"
            path.write_bytes(bytes(blob))
            code, printed = run_cli_code("dump", str(path), "--find", "mdhd")
        self.assertEqual(code, 1)
        self.assertEqual(printed, "error: mdhd at 109004: version 1 needs 44 bytes, box has 32\n")
