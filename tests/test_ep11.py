import json
import tempfile
import unittest
from pathlib import Path
from mp4kit import boxes, tables
from tests.util import data, run_cli, run_cli_code

PHONE, ROTATED, SUBS = data("phone.mp4"), data("rotated.mp4"), data("subs.mp4")
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep11.txt"
IDENTITY = [65536, 0, 0, 0, 65536, 0, 0, 0, 1073741824]
TURNED = [0, -65536, 0, 65536, 0, 0, 0, 0, 1073741824]
PHONE_VIDEO = {"version": 0, "flags": 3, "track_ID": 1, "duration": 96000, "volume": 0.0, "width": 640.0,
               "height": 360.0, "matrix": IDENTITY, "rotation": 0}


def tkhd_v1(track_id, duration, width, height):
    """A version-1 tkhd in memory: 64-bit creation, modification and duration; 104 bytes."""
    body = bytes(16) + track_id.to_bytes(4, "big") + bytes(4) + duration.to_bytes(8, "big") + bytes(8)
    body += bytes(4) + (0x100).to_bytes(2, "big") + bytes(2)
    body += b"".join(v.to_bytes(4, "big", signed=True) for v in TURNED)
    body += (width << 16).to_bytes(4, "big") + (height << 16).to_bytes(4, "big")
    return (104).to_bytes(4, "big") + b"tkhd" + b"\x01\x00\x00\x03" + body


class Ep11(unittest.TestCase):
    def test_find_all_three_traks(self):
        traks = boxes.find_all(boxes.walk(SUBS), "moov/trak")
        self.assertEqual([(b.type, b.start, b.size) for b in traks],
                         [("trak", 108887, 1454), ("trak", 110341, 1785), ("trak", 112126, 552)])

    def test_find_all_down_every_trak(self):
        tree = boxes.walk(SUBS)
        self.assertEqual([b.start for b in boxes.find_all(tree, "moov/trak/tkhd")], [108895, 110349, 112134])
        self.assertEqual(boxes.find_all(tree, "moov/trak")[0], boxes.find(tree, "moov/trak"))  # find = the first
        self.assertEqual(boxes.find_all(tree, "trak"), [])                                     # from the top
        self.assertEqual(boxes.find_all(tree, "moov/nope"), [])

    def test_read_tkhd_phone_video(self):
        tkhd = boxes.find(boxes.walk(PHONE), "moov/trak/tkhd")
        self.assertEqual((tkhd.start, tkhd.size), (108868, 92))
        self.assertEqual(tables.read_tkhd(PHONE, tkhd), PHONE_VIDEO)

    def test_read_tkhd_phone_audio(self):
        tkhd = boxes.find_all(boxes.walk(PHONE), "moov/trak/tkhd")[1]
        self.assertEqual(tkhd.start, 110322)
        self.assertEqual(tables.read_tkhd(PHONE, tkhd),
                         {"version": 0, "flags": 3, "track_ID": 2, "duration": 96000, "volume": 1.0, "width": 0.0,
                          "height": 0.0, "matrix": IDENTITY, "rotation": 0})

    def test_size_matches_ffprobe(self):
        probe = json.loads((CAPS / "phone.mp4.probe.json").read_text())
        video = probe["streams"][0]
        tkhd = tables.read_tkhd(PHONE, boxes.find(boxes.walk(PHONE), "moov/trak/tkhd"))
        self.assertEqual((tkhd["width"], tkhd["height"]), (video["width"], video["height"]))

    def test_fixed(self):
        self.assertEqual(tables.fixed(640 << 16, 16), 640.0)
        self.assertEqual(tables.fixed(0x01680000, 16), 360.0)        # tkhd height at 108956
        self.assertEqual(tables.fixed(0x0100, 8), 1.0)               # audio volume, 8.8
        self.assertEqual(tables.fixed(0x40000000, 30), 1.0)          # the matrix's w, 2.30

    def test_rotation(self):
        self.assertEqual(tables.rotation(TURNED), 90)
        self.assertEqual(tables.rotation(IDENTITY), 0)
        self.assertEqual(tables.rotation([-65536, 0, 0, 0, -65536, 0, 0, 0, 1073741824]), 180)
        self.assertEqual(tables.rotation([0, 65536, 0, -65536, 0, 0, 0, 0, 1073741824]), 270)
        self.assertIsNone(tables.rotation([131072, 0, 0, 0, 131072, 0, 0, 0, 1073741824]))   # scaled, no turn

    def test_rotated_matches_ffprobe(self):
        tkhd = tables.read_tkhd(ROTATED, boxes.find(boxes.walk(ROTATED), "moov/trak/tkhd"))
        self.assertEqual((tkhd["matrix"], tkhd["rotation"]), (TURNED, 90))
        probe = json.loads((CAPS / "rotated.mp4.probe.json").read_text())
        self.assertEqual(probe["streams"][0]["side_data_list"][0]["rotation"], tkhd["rotation"])

    def test_five_bytes_turn_it(self):
        changed = [at for at in range(108868, 108960) if PHONE[at] != ROTATED[at]]
        self.assertEqual(changed, [108917, 108920, 108921, 108929, 108933])   # all inside the matrix, 108916..108951

    def test_read_tkhd_version_1(self):
        blob = tkhd_v1(7, 2 ** 32 + 5, 1920, 1080)
        self.assertEqual(tables.read_tkhd(blob, boxes.read_header(blob, 0)),
                         {"version": 1, "flags": 3, "track_ID": 7, "duration": 2 ** 32 + 5, "volume": 1.0,
                          "width": 1920.0, "height": 1080.0, "matrix": TURNED, "rotation": 90})

    def test_read_tkhd_short_box(self):
        blob = (60).to_bytes(4, "big") + PHONE[108868 + 4:108868 + 60]
        with self.assertRaisesRegex(boxes.BoxError, "tkhd at 0: version 0 needs 92 bytes, box has 60"):
            tables.read_tkhd(blob, boxes.read_header(blob, 0))

    def test_registry(self):
        self.assertIs(boxes.DECODERS["tkhd"], tables.read_tkhd)

    def test_cmd_dump_find_tkhd(self):
        printed = run_cli("dump", "testfiles/out/rotated.mp4", "--find", "tkhd")
        self.assertEqual(printed, EXPECTED.read_text())

    def test_cmd_dump_bad_tkhd(self):
        blob = bytearray(PHONE)
        blob[108868 + 8] = 1                                         # version 1, but only 92 bytes
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tkhd-v1-short.mp4"
            path.write_bytes(bytes(blob))
            code, printed = run_cli_code("dump", str(path), "--find", "tkhd")
        self.assertEqual(code, 1)
        self.assertEqual(printed, "error: tkhd at 108868: version 1 needs 104 bytes, box has 92\n")
