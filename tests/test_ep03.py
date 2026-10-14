import unittest

from mp4kit import nal
from tests.util import data, run_cli

F1 = data("f1.mp4")


class Ep03(unittest.TestCase):
    def test_bitreader_u(self):
        r = nal.BitReader(bytes([0x65]))
        self.assertEqual((r.u(1), r.u(2), r.u(5)), (0, 3, 5))

    def test_bitreader_ue(self):
        self.assertEqual(nal.BitReader(bytes([0b10000000])).ue(), 0)
        self.assertEqual(nal.BitReader(bytes([0b01000000])).ue(), 1)
        self.assertEqual(nal.BitReader(bytes([0b01100000])).ue(), 2)

    def test_bitreader_se(self):
        values = [nal.BitReader(bytes([b])).se() for b in (0b01000000, 0b01100000)]
        self.assertEqual(values, [1, -1])

    def test_nal_header(self):
        self.assertEqual(nal.nal_header(0x65), (0, 3, 5))

    def test_f1_types(self):
        units = nal.iter_length_prefixed(F1, 40, 22057)
        types = [nal.nal_header(unit[0])[2] for _, unit in units]
        self.assertEqual(types, [5, 1, 1, 1] * 3)

    def test_names(self):
        names = {k: nal.NAL_TYPES[k] for k in (1, 5, 7, 8)}
        self.assertEqual(names, {1: "non-IDR slice", 5: "IDR slice", 7: "SPS", 8: "PPS"})

    def test_cmd_nals_type_column(self):
        out = run_cli("nals", "testfiles/out/f1.mp4", "--from", "40", "--to", "22057")
        self.assertEqual(out.splitlines()[0], "1 40 5301 5 IDR slice")


if __name__ == "__main__":
    unittest.main()
