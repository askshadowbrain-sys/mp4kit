import unittest

from mp4kit import nal
from tests.util import data, run_cli

F1 = data("f1.mp4")


class Ep02(unittest.TestCase):
    def test_twelve_units_cover_mdat_payload(self):
        units = list(nal.iter_length_prefixed(F1, 40, 22057))
        self.assertEqual(len(units), 12)
        first_offset, first_nal = units[0]
        self.assertEqual((first_offset, len(first_nal)), (40, 5301))
        last_offset, last_nal = units[-1]
        end = last_offset + 4 + len(last_nal)
        self.assertEqual(end, 22057)

    def test_big_units_are_1_5_9(self):
        sizes = [len(u) for _, u in nal.iter_length_prefixed(F1, 40, 22057)]
        biggest_first = sorted(range(12), key=lambda i: -sizes[i])
        big = biggest_first[:3]
        self.assertEqual(sorted(i + 1 for i in big), [1, 5, 9])

    def test_cmd_nals_first_line(self):
        out = run_cli("nals", "testfiles/out/f1.mp4", "--from", "40", "--to", "22057")
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("1 40 5301"))
        self.assertEqual(len(lines), 12)


if __name__ == "__main__":
    unittest.main()
