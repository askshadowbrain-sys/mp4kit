import unittest
from mp4kit import boxes
from tests.util import data, run_cli

F1, AAC = data("f1.mp4"), data("aac-only.m4a")


class Ep08(unittest.TestCase):
    def test_f1_ftyp(self):
        self.assertEqual(boxes.read_ftyp(F1, boxes.read_header(F1, 0)),
                         {"major": "isom", "minor": 512, "brands": ["isom", "iso2", "avc1", "mp41"]})

    def test_aac_ftyp(self):
        self.assertEqual(boxes.read_ftyp(AAC, boxes.read_header(AAC, 0)),
                         {"major": "M4A ", "minor": 512, "brands": ["M4A ", "isom", "iso2"]})

    def test_registry(self):
        self.assertIs(boxes.DECODERS["ftyp"], boxes.read_ftyp)
        self.assertEqual(boxes.decode(F1, boxes.read_header(F1, 32)), {})   # mdat: unknown, never an error

    def test_cmd_boxes_aac(self):
        self.assertEqual(run_cli("boxes", "testfiles/out/aac-only.m4a").splitlines(),
                         ["ftyp: M4A  512 [M4A , isom, iso2]", "free 28 8", "mdat 36 16449", "moov 16485 1078"])
