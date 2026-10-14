import unittest

from mp4kit import nal
from tests.synth import baseline_sps, high_sps
from tests.util import data, run_cli

F1 = data("f1.mp4")


def f1_sps_and_pps():
    """f1's first SPS and PPS, found by the avcC byte search."""
    return nal._avcc_params_stopgap(F1)


class Ep04(unittest.TestCase):
    def test_sps(self):
        sps_bytes, _ = f1_sps_and_pps()
        s = nal.parse_sps(sps_bytes)
        self.assertEqual((s["profile_idc"], s["level_idc"], s["pic_order_cnt_type"]), (100, 30, 2))
        self.assertEqual((s["width_mbs"], s["height_map_units"], s["frame_mbs_only"]), (40, 23, 1))
        self.assertEqual(s["crop"], (0, 0, 0, 4))

    def test_picture_size(self):
        sps_bytes, _ = f1_sps_and_pps()
        sps = nal.parse_sps(sps_bytes)
        self.assertEqual(nal.picture_size(sps), (640, 360))

    def test_pps(self):
        _, pps_bytes = f1_sps_and_pps()
        pps = nal.parse_pps(pps_bytes)
        self.assertEqual(pps["entropy_coding_mode_flag"], 1)

    def test_slice_headers(self):
        sps_bytes, pps_bytes = f1_sps_and_pps()
        sps = nal.parse_sps(sps_bytes)
        pps = nal.parse_pps(pps_bytes)
        units = nal.iter_length_prefixed(F1, 40, 22057)
        headers = [nal.read_slice_header(unit, sps, pps) for _, unit in units]
        slice_types = [h["slice_type"] % 5 for h in headers]
        self.assertEqual(slice_types, [2, 0, 0, 0] * 3)  # I P P P
        self.assertEqual([h["frame_num"] for h in headers], [0, 1, 2, 3] * 3)
        idr_ids = [h["idr_pic_id"] for h in headers if "idr_pic_id" in h]
        self.assertEqual(idr_ids, [0, 1, 0])

    def test_cmd_sps(self):
        out = run_cli("sps", "testfiles/out/f1.mp4")
        self.assertEqual(out.strip(), "profile 100 level 30 640x360 CABAC")

    def test_sps_poc_type_0(self):
        s = nal.parse_sps(baseline_sps(lambda w: w.ue(0).ue(2)))
        self.assertEqual((s["pic_order_cnt_type"], s["log2_max_poc_lsb"]), (0, 6))
        self.assertEqual((s["max_num_ref_frames"], s["width_mbs"]), (1, 40))

    def test_sps_poc_type_1(self):
        s = nal.parse_sps(baseline_sps(lambda w: w.ue(1).u(1, 0).se(-1).se(2).ue(2).se(3).se(-4)))
        self.assertEqual(s["pic_order_cnt_type"], 1)
        self.assertEqual((s["max_num_ref_frames"], s["width_mbs"], s["height_map_units"]), (1, 40, 23))

    def test_scaling_lists_refused(self):
        with self.assertRaisesRegex(ValueError, "scaling lists not taught"):
            nal.parse_sps(high_sps(1, scaling_matrix=1))

    def test_separate_colour_planes_refused(self):
        sps = nal.parse_sps(high_sps(3))
        self.assertIs(sps["separate_colour_plane"], True)
        _, pps_bytes = f1_sps_and_pps()
        first_slice = next(nal.iter_length_prefixed(F1, 40, 22057))[1]
        with self.assertRaisesRegex(ValueError, "separate colour planes not taught"):
            nal.read_slice_header(first_slice, sps, nal.parse_pps(pps_bytes))
        with self.assertRaisesRegex(ValueError, "only 4:2:0 taught here"):
            nal.picture_size(sps)

    def test_field_coding_refused_first(self):
        sps = nal.parse_sps(high_sps(1, frame_mbs_only=0))
        _, pps_bytes = f1_sps_and_pps()
        with self.assertRaisesRegex(ValueError, "field coding not taught"):
            nal.read_slice_header(b"\x65", sps, nal.parse_pps(pps_bytes))


if __name__ == "__main__":
    unittest.main()
