import unittest
from mp4kit import boxes
from tests.util import data, run_cli

F1, PHONE, LARGE = data("f1.mp4"), data("phone.mp4"), data("phone-large.mp4")


class Ep07(unittest.TestCase):
    def test_largesize_mdat(self):
        mdat = boxes.read_header(LARGE, 32)
        self.assertEqual((mdat.type, mdat.size, mdat.header, mdat.payload), ("mdat", 108712, 16, 48))

    def test_top_level_uuid(self):
        got = [(b.type, b.start, b.size, b.header) for b in boxes.iter_boxes(LARGE, 0, len(LARGE))]
        self.assertEqual(got, [("ftyp", 0, 32, 8), ("mdat", 32, 108712, 16), ("moov", 108744, 3884, 8),
                               ("uuid", 112628, 28, 24)])

    def test_size_zero_runs_to_end(self):
        blob = b"\x00\x00\x00\x00mdat" + b"x" * 10
        self.assertEqual(boxes.read_header(blob, 0).size, 18)

    def test_size_zero_runs_to_parent_end(self):
        blob = b"\x00\x00\x00\x00free" + b"x" * 10
        self.assertEqual(boxes.read_header(blob, 0, end=12).size, 12)

    def test_overrun_is_checked_against_the_parent(self):
        with self.assertRaisesRegex(boxes.BoxError, "mvhd at 22065: size 108 runs past the end \\(22100\\)"):
            boxes.read_header(F1, 22065, end=22100)

    def test_largesize_cut_short(self):
        blob = b"\x00\x00\x00\x01mdat\x00\x00"   # size 1, but no room for the 64-bit size
        with self.assertRaisesRegex(boxes.BoxError, "mdat at 0: size 1 is smaller than its 8-byte header"):
            boxes.read_header(blob, 0)

    def test_boxerror_is_a_valueerror(self):
        self.assertTrue(issubclass(boxes.BoxError, ValueError))

    def test_fullbox(self):
        self.assertEqual(boxes.read_fullbox(F1, boxes.read_header(F1, 22065)), (0, 0))   # mvhd
        self.assertEqual(boxes.read_fullbox(F1, boxes.read_header(F1, 22181)), (0, 3))   # tkhd: enabled + in movie

    def test_cmd_boxes_large(self):
        # ep08 decodes ftyp; tag ep07 keeps its own test
        self.assertEqual(run_cli("boxes", "testfiles/out/phone-large.mp4").splitlines(),
                         ["ftyp: isom 512 [isom, iso2, avc1, mp41]", "mdat 32 108712 (header 16)", "moov 108744 3884",
                          "uuid 112628 28 (header 24)"])
