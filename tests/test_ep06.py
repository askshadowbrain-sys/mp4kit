import os
import tempfile
import unittest

from mp4kit import boxes
from tests.util import data, run_cli, run_cli_code

F1 = data("f1.mp4")
PHONE = data("phone.mp4")
NOMOOV = data("broken-nomoov.mp4")


class Ep06(unittest.TestCase):
    def test_f1_top_level(self):
        got = [(b.type, b.start, b.size) for b in boxes.iter_boxes(F1, 0, len(F1))]
        self.assertEqual(got, [("ftyp", 0, 32), ("mdat", 32, 22025), ("moov", 22057, 721)])

    def test_read_header(self):
        ftyp = boxes.read_header(F1, 0)
        self.assertEqual(ftyp, boxes.Box("ftyp", 0, 32, 8, []))
        self.assertEqual((ftyp.payload, ftyp.end), (8, 32))

    def test_phone_top_level(self):
        got = [(b.type, b.start, b.size) for b in boxes.iter_boxes(PHONE, 0, len(PHONE))]
        self.assertEqual(got, [("ftyp", 0, 32), ("free", 32, 8), ("mdat", 40, 108704), ("moov", 108744, 3412)])

    def test_box_running_past_end_raises(self):
        blob = PHONE[:50]  # the mdat header at 40 claims far more than the 10 bytes left
        with self.assertRaisesRegex(ValueError, "mdat at 40: size 108704 runs past the end"):
            list(boxes.iter_boxes(blob, 0, len(blob)))

    def test_size_smaller_than_header_raises(self):
        blob = b"\x00\x00\x00\x07free"
        with self.assertRaisesRegex(ValueError, "free at 0: size 7 is smaller than its 8-byte header"):
            boxes.read_header(blob, 0)

    def test_cut_at_boundary_lists_cleanly(self):
        got = [b.type for b in boxes.iter_boxes(NOMOOV, 0, len(NOMOOV))]
        self.assertEqual(got, ["ftyp", "free", "mdat"])  # no moov: diagnosing that is ep36's job

    def test_cmd_boxes(self):
        printed = run_cli("boxes", "testfiles/out/f1.mp4")
        # ep08 decodes ftyp; tag ep06 keeps its own test
        self.assertEqual(printed.splitlines(),
                         ["ftyp: isom 512 [isom, iso2, avc1, mp41]", "mdat 32 22025", "moov 22057 721"])

    def test_cmd_boxes_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "cut.mp4")
            with open(path, "wb") as f:
                f.write(PHONE[:50])
            code, printed = run_cli_code("boxes", path)
        self.assertEqual(code, 1)
        # ep08 decodes ftyp; tag ep06 keeps its own test
        self.assertEqual(printed, "ftyp: isom 512 [isom, iso2, avc1, mp41]\nfree 32 8\n"
                                  "error: mdat at 40: size 108704 runs past the end (50)\n")

    def test_too_few_bytes_for_a_header(self):
        blob = b"\x00\x00\x00\x08free\x00\x00"  # an 8-byte free box, then 2 stray bytes
        listed = []
        with self.assertRaisesRegex(ValueError, "box at 8: only 2 bytes left, a header needs 8"):
            for box in boxes.iter_boxes(blob, 0, len(blob)):
                listed.append((box.type, box.start, box.size))
        self.assertEqual(listed, [("free", 0, 8)])

    def test_cmd_boxes_trailing_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "junk.mp4")
            with open(path, "wb") as f:
                f.write(b"\x00\x00\x00\x08free\x00\x00")
            code, printed = run_cli_code("boxes", path)
        self.assertEqual(code, 1)
        self.assertEqual(printed, "free 0 8\nerror: box at 8: only 2 bytes left, a header needs 8\n")


if __name__ == "__main__":
    unittest.main()
