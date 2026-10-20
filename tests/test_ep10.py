import json
import tempfile
import unittest
from pathlib import Path
from mp4kit import boxes, tables, timing
from tests.util import data, run_cli, run_cli_code

PHONE, F1, FAST = data("phone.mp4"), data("f1.mp4"), data("phone-fast.mp4")
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep10.txt"
PHONE_MVHD = {"version": 0, "timescale": 48000, "duration": 96000, "seconds": 2.0, "rate": 1.0, "volume": 1.0,
              "next_track_ID": 3}


def mvhd_v1(timescale, duration):
    """A version-1 mvhd in memory: 64-bit creation, modification and duration; 120 bytes."""
    body = bytes(16) + timescale.to_bytes(4, "big") + duration.to_bytes(8, "big")
    body += (0x10000).to_bytes(4, "big") + (0x100).to_bytes(2, "big") + bytes(10) + bytes(36) + bytes(24)
    body += (2).to_bytes(4, "big")
    return (120).to_bytes(4, "big") + b"mvhd" + b"\x01\x00\x00\x00" + body


class Ep10(unittest.TestCase):
    def test_find_moov_mvhd(self):
        mvhd = boxes.find(boxes.walk(PHONE), "moov/mvhd")
        self.assertEqual((mvhd.type, mvhd.start, mvhd.size), ("mvhd", 108752, 108))

    def test_find_path_from_the_top(self):
        tree = boxes.walk(PHONE)
        self.assertIsNone(boxes.find(tree, "mvhd"))           # a path starts at the top level
        self.assertIsNone(boxes.find(tree, "moov/nope"))
        self.assertEqual(boxes.find(tree, "moov").start, 108744)

    def test_find_tries_the_next_trak(self):
        smhd = boxes.find(boxes.walk(PHONE), "moov/trak/mdia/minf/smhd")   # only the second trak (audio) has one
        self.assertEqual((smhd.start, smhd.size), (110543, 16))

    def test_read_mvhd_phone(self):
        mvhd = boxes.find(boxes.walk(PHONE), "moov/mvhd")
        self.assertEqual(tables.read_mvhd(PHONE, mvhd), PHONE_MVHD)

    def test_read_mvhd_f1(self):
        mvhd = boxes.find(boxes.walk(F1), "moov/mvhd")
        self.assertEqual(mvhd.start, 22065)
        self.assertEqual(tables.read_mvhd(F1, mvhd),
                         {"version": 0, "timescale": 1000, "duration": 396, "seconds": 0.396, "rate": 1.0,
                          "volume": 1.0, "next_track_ID": 2})

    def test_moov_first_same_clock(self):
        mvhd = boxes.find(boxes.walk(FAST), "moov/mvhd")
        self.assertEqual(mvhd.start, 40)                      # moov at 32, before mdat
        self.assertEqual(tables.read_mvhd(FAST, mvhd), PHONE_MVHD)

    def test_seconds_matches_ffprobe(self):
        self.assertEqual(timing.seconds(96000, 48000), 2.0)
        for name, ticks, scale in (("phone.mp4", 96000, 48000), ("f1.mp4", 396, 1000)):
            probe = json.loads((CAPS / f"{name}.probe.json").read_text())
            self.assertEqual(f"{timing.seconds(ticks, scale):.6f}", probe["format"]["duration"])

    def test_read_mvhd_version_1(self):
        blob = mvhd_v1(90000, 2 ** 32 + 90000)               # a duration too long for 32 bits
        got = tables.read_mvhd(blob, boxes.read_header(blob, 0))
        self.assertEqual(got, {"version": 1, "timescale": 90000, "duration": 2 ** 32 + 90000,
                               "seconds": (2 ** 32 + 90000) / 90000, "rate": 1.0, "volume": 1.0,
                               "next_track_ID": 2})

    def test_read_mvhd_short_box(self):
        blob = PHONE[108752:108752 + 60]
        blob = (60).to_bytes(4, "big") + blob[4:]
        with self.assertRaisesRegex(boxes.BoxError, "mvhd at 0: version 0 needs 108 bytes, box has 60"):
            tables.read_mvhd(blob, boxes.read_header(blob, 0))

    def test_read_mvhd_timescale_zero(self):
        blob = bytearray(PHONE)
        blob[108752 + 20:108752 + 24] = bytes(4)             # timescale at payload + 4 + 4 + 4
        with self.assertRaisesRegex(boxes.BoxError, "mvhd at 108752: timescale 0, a clock that never ticks"):
            tables.read_mvhd(bytes(blob), boxes.read_header(bytes(blob), 108752))

    def test_registry(self):
        self.assertIs(boxes.DECODERS["mvhd"], tables.read_mvhd)

    def test_cmd_dump_find(self):
        printed = run_cli("dump", "testfiles/out/phone.mp4", "--find", "mvhd")
        self.assertEqual(printed, EXPECTED.read_text())

    def test_cmd_dump_find_many(self):
        lines = run_cli("dump", "testfiles/out/phone.mp4", "--find", "stco").splitlines()
        self.assertEqual(lines, ["moov/trak/mdia/minf/stbl/stco 110062 252",
                                 "moov/trak/mdia/minf/stbl/stco 111789 252"])

    def test_cmd_dump_find_none(self):
        code, printed = run_cli_code("dump", "testfiles/out/broken-nomoov.mp4", "--find", "mvhd")
        self.assertEqual(code, 0)
        self.assertEqual(printed.splitlines(), ["no mvhd box", "no moov box"])

    def test_cmd_dump_bad_mvhd(self):
        blob = bytearray(PHONE)
        blob[108752 + 20:108752 + 24] = bytes(4)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "timescale0.mp4"
            path.write_bytes(bytes(blob))
            code, printed = run_cli_code("dump", str(path), "--find", "mvhd")
        self.assertEqual(code, 1)
        self.assertEqual(printed, "error: mvhd at 108752: timescale 0, a clock that never ticks\n")
