import os
import shutil
import subprocess
import tempfile
import unittest

from mp4kit import nal
from tests.synth import baseline_sps
from tests.test_ep04 import f1_sps_and_pps
from tests.util import data, run_cli

F1 = data("f1.mp4")
SPS, PPS = f1_sps_and_pps()
SLICES = [unit for _, unit in nal.iter_length_prefixed(F1, 40, 22057)]


def escape(payload):
    """Test helper: insert an emulation prevention 03 wherever 00 00 meets a byte <= 3."""
    out = bytearray()
    zeros = 0
    for byte in payload:
        if zeros >= 2 and byte <= 3:
            out.append(3)
            zeros = 0
        out.append(byte)
        zeros = zeros + 1 if byte == 0 else 0
    return bytes(out)


class Ep05(unittest.TestCase):
    def test_round_trip(self):
        nals = [SPS, PPS] + SLICES
        self.assertEqual(nal.split_annexb(nal.to_annexb(nals)), nals)

    def test_four_byte_start_codes(self):
        self.assertEqual(nal.to_annexb([b"\x67\xaa"]), b"\x00\x00\x00\x01\x67\xaa")

    def test_three_byte_start_codes(self):
        stream = b"\x00\x00\x01\x67\xaa\x00\x00\x01\x68\xbb"
        self.assertEqual(nal.split_annexb(stream), [b"\x67\xaa", b"\x68\xbb"])

    def test_trailing_zeros_dropped(self):
        stream = b"\x00\x00\x01\x67\xaa\x00\x00\x00\x00\x01\x68\xbb\x00\x00"
        self.assertEqual(nal.split_annexb(stream), [b"\x67\xaa", b"\x68\xbb"])

    def test_five_byte_start_code(self):
        stream = b"\x00\x00\x00\x00\x01\x67\xaa\x00\x00\x00\x00\x01\x68\xbb"
        self.assertEqual(nal.split_annexb(stream), [b"\x67\xaa", b"\x68\xbb"])

    def test_consecutive_start_codes_give_no_empty_unit(self):
        stream = b"\x00\x00\x01\x00\x00\x01\x67\xaa"
        self.assertEqual(nal.split_annexb(stream), [b"\x67\xaa"])

    def test_junk_before_first_start_code_is_dropped(self):
        stream = b"\xff\xee\x00\x00\x01\x67\xaa"
        self.assertEqual(nal.split_annexb(stream), [b"\x67\xaa"])

    def test_avcc_is_mdat_payload(self):
        self.assertEqual(nal.to_avcc(SLICES), F1[40:22057])

    def test_rbsp(self):
        self.assertEqual(nal.rbsp(b"\x00\x00\x03\x01"), b"\x00\x00\x01")
        self.assertEqual(nal.rbsp(b"\x00\x03\x01"), b"\x00\x03\x01")
        self.assertEqual(nal.parse_sps(SPS)["level_idc"], 30)

    def test_sps_with_escape_parses_the_same(self):
        raw = baseline_sps(lambda w: w.ue(2), level=0, sps_id=63)
        escaped = escape(raw)
        self.assertIn(b"\x00\x00\x03", escaped)
        s = nal.parse_sps(escaped)
        self.assertEqual((s["sps_id"], s["width_mbs"], s["height_map_units"]), (63, 40, 23))

    def test_mdat_range(self):
        self.assertEqual(nal._mdat_range_stopgap(F1), (40, 22057))
        with self.assertRaisesRegex(ValueError, "mdat size 7 is smaller than its 8-byte header"):
            nal._mdat_range_stopgap(b"\x00\x00\x00\x07mdat")

    def test_cmd_annexb_output(self):
        out = os.path.join(tempfile.mkdtemp(), "f1.h264")
        printed = run_cli("annexb", "testfiles/out/f1.mp4", "-o", out)
        with open(out, "rb") as f:
            written = f.read()
        self.assertEqual(nal.split_annexb(written), [SPS, PPS] + SLICES)
        self.assertEqual(written, nal.to_annexb([SPS, PPS] + SLICES))
        self.assertEqual(printed, "wrote 14 NAL units (SPS, PPS, 12 slices), 22056 bytes\n")

    @unittest.skipIf(shutil.which("ffprobe") is None, "ffprobe not on PATH (episodes 1-28 need no ffmpeg)")
    def test_ffprobe_reads_it(self):
        out = os.path.join(tempfile.mkdtemp(), "f1.h264")
        run_cli("annexb", "testfiles/out/f1.mp4", "-o", out)
        probe = ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height", "-of", "csv=p=0", out]
        result = subprocess.run(probe, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "h264,640,360")


if __name__ == "__main__":
    unittest.main()
