import contextlib
import io
import unittest

from mp4kit import boxes, cli
from tests.util import data, run_cli

F1 = data("f1.mp4")


class Ep01(unittest.TestCase):
    def test_u32_ftyp_size(self):
        self.assertEqual(boxes.u32(F1, 0), 32)
        self.assertEqual(F1[4:8], b"ftyp")

    def test_u16_u64(self):
        self.assertEqual(boxes.u16(b"\x01\x02", 0), 0x0102)
        self.assertEqual(boxes.u64(b"\x00\x00\x00\x01\x00\x00\x00\x02", 0), (1 << 32) | 2)

    def test_hexdump_first_line(self):
        self.assertEqual(cli.hexdump(F1, 0, 8), "00 00 00 20 66 74 79 70")

    def test_cmd_hex(self):
        self.assertEqual(
            run_cli("hex", "testfiles/out/f1.mp4", "--at", "0", "--len", "8").strip(),
            "00 00 00 20 66 74 79 70",
        )
        with contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["hex", "testfiles/out/f1.mp4", "--at", "0", "--len", "8"])
        self.assertEqual(code, 0)
