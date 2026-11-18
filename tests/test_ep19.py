import mmap
import tempfile
import unittest
from pathlib import Path
from mp4kit import boxes, nal, tables, timing
from tests.util import data, run_cli, run_cli_code

F1, F2, PHONE = data("f1.mp4"), data("f2.mp4"), data("phone.mp4")
OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep19.txt"


def video(contents):
    """The first trak and its samples."""
    trak = boxes.find(boxes.walk(contents), "moov/trak")
    return trak, tables.sample_table(contents, trak)


def pts_of(contents):
    """The first track's presentation times in its ticks (ep18: the edit list applied to cts)."""
    tree = boxes.walk(contents)
    trak, samples = video(contents)
    elst = tables.read_elst(contents, boxes.find(trak.children, "edts/elst"))
    clocks = (tables.read_mdhd(contents, boxes.find(trak.children, "mdia/mdhd"))["timescale"],
              tables.read_mvhd(contents, boxes.find(tree, "moov/mvhd"))["timescale"])
    return timing.presentation_times([s.cts for s in samples], elst, *clocks)


def frame(*argv):
    """Run `mp4kit frame` with --out to a temporary file: (exit code, printed, the bytes written)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "frame.h264"
        code, printed = run_cli_code("frame", *argv, "--out", str(out))
        return code, printed, out.read_bytes() if out.exists() else None


class Ep19(unittest.TestCase):
    def test_sample_at_f2(self):
        pts = pts_of(F2)
        self.assertEqual(pts, [0, 99, 33, 66, 132, 231, 165, 198, 264, 363, 297, 330])
        self.assertEqual(timing.sample_at(pts, 198), 8)              # shown 7th: f2's "frame 7"
        self.assertEqual(timing.sample_at(pts, 197), 7)              # sample 7 is on screen from 165 to 197
        self.assertEqual(timing.sample_at(pts, 231), 6)              # decoded 6th, shown 8th
        self.assertEqual(timing.sample_at(pts, 0), 1)
        self.assertEqual(timing.sample_at(pts, 395), 10)             # the last picture shown (pts 363)
        with self.assertRaisesRegex(ValueError, "nothing is on screen at -1 ticks: the first picture shows at 0"):
            timing.sample_at(pts, -1)

    def test_sample_at_needs_pts(self):
        _, samples = video(F2)
        self.assertEqual(timing.sample_at([s.cts for s in samples], 198), 7)    # CTS, no edit list: one too early
        self.assertEqual(timing.sample_at([s.dts for s in samples], 198), 7)    # decode order: not what is shown
        self.assertEqual(timing.sample_at(pts_of(F2), 198), 8)                   # PTS: what ffprobe shows at 198

    def test_sample_at_phone(self):
        pts = pts_of(PHONE)                                                       # timescale 15,360
        self.assertEqual(timing.sample_at(pts, 1000 * 15360 // 1000), 31)        # 1,000 ms = 15,360 ticks
        self.assertEqual(timing.sample_at(pts, 7680), 17)
        self.assertEqual(timing.sample_at(pts, 0), 1)

    def test_sync_before(self):
        self.assertEqual(timing.sync_before([1, 31], 40), 31)                   # phone
        self.assertEqual(timing.sync_before([1, 31], 31), 31)                   # a keyframe needs nothing earlier
        self.assertEqual(timing.sync_before([1, 5, 9], 7), 5)                   # f1
        self.assertEqual(timing.sync_before([1, 5, 9], 8), 5)                   # f2's sample 8
        self.assertEqual(timing.sync_before(None, 7), 7)                        # no stss: every sample is sync
        with self.assertRaisesRegex(ValueError, "no sync sample at or before sample 3 \\(stss starts at 5\\)"):
            timing.sync_before([5, 9], 3)

    def test_frame_7_by_hand(self):
        _, samples = video(F2)
        # sample 8 is in chunk 2 (chunks hold 4, 4, 2, 2), which starts at 6185 (stco); before it in that chunk
        # are samples 5, 6 and 7 (stsz 6562, 379, 171)
        offset = 6185 + 6562 + 379 + 171
        self.assertEqual((samples[7].offset, samples[7].size), (offset, 180))   # 13297, 180 bytes
        self.assertEqual(F2[13297:13301].hex(), "000000b0")                     # one NAL of 176 bytes
        self.assertEqual(nal.nal_header(F2[13301])[2], 1)                        # a non-IDR slice
        self.assertEqual((samples[7].dts, samples[7].cts), (231, 231))          # ctts slip 0; PTS 231 - 33 = 198

    def test_cmd_frame_f2(self):
        code, printed, stream = frame("testfiles/out/f2.mp4", "--at", "198")
        self.assertEqual(code, 0)
        self.assertEqual(printed, EXPECTED.read_text())
        self.assertEqual(printed.splitlines()[0],
                         "198 ms = 198 ticks: on screen is sample 8 (pts 198, offset 13297, 180 bytes)")
        trak, samples = video(F2)
        config = tables.read_avcc(F2, boxes.find(trak.children, "mdia/minf/stbl/stsd/avc1/avcC"))
        units = [u for s in samples[4:8] for _, u in nal.iter_length_prefixed(F2, s.offset, s.offset + s.size)]
        self.assertEqual(nal.split_annexb(stream), config["SPS"] + config["PPS"] + units)
        self.assertEqual([nal.nal_header(u[0])[2] for u in nal.split_annexb(stream)], [7, 8, 5, 1, 1, 1])
        self.assertEqual(stream[:5].hex(), "0000000167")                         # a start code, then the SPS
        self.assertEqual(len(stream), 4 + 25 + 4 + 6 + 4 * 4 + 6558 + 375 + 167 + 176)   # 7,331 bytes

    def test_cmd_frame_without_out(self):
        printed = run_cli("frame", "testfiles/out/f2.mp4", "--at", "198")
        self.assertEqual(printed, "".join(EXPECTED.read_text().splitlines(keepends=True)[:2]))

    def test_cmd_frame_phone(self):
        code, printed, stream = frame("testfiles/out/phone.mp4", "--at", "1000")
        self.assertEqual(printed.splitlines()[:2],
                         ["1000 ms = 15360 ticks: on screen is sample 31 (pts 15360, offset 53206, 6517 bytes)",
                          "walk back to keyframe 31: decode samples 31 to 31; "
                          "sample 31 is picture 1 of 1 in display order"])
        self.assertEqual([nal.nal_header(u[0])[2] for u in nal.split_annexb(stream)], [7, 8, 5])     # SPS, PPS, IDR
        printed = run_cli("frame", "testfiles/out/phone.mp4", "--at", "1300")
        self.assertIn("walk back to keyframe 31: decode samples 31 to 41; sample 41 is picture 10 of 11", printed)

    def test_cmd_frame_errors(self):
        code, printed, stream = frame("testfiles/out/broken-nomoov.mp4", "--at", "0")
        self.assertEqual((code, printed, stream),
                         (1, "error: no moov box (moov atom not found): the file is truncated\n", None))
        self.assertIn("moov atom not found", (CAPS / "broken-nomoov.mp4.probe.err.txt").read_text())  # ffprobe's words
        self.assertEqual(run_cli_code("frame", "testfiles/out/f2.mp4", "--at", "396"),
                         (1, "error: --at 396 ms is outside the movie, which lasts 396 ms\n"))
        self.assertEqual(frame("testfiles/out/hevc.mp4", "--at", "0")[:2],
                         (1, "error: --out writes H.264 only, and this track has no avc1/avcC\n"))
        self.assertEqual(run_cli_code("frame", "testfiles/out/aac-only.m4a", "--at", "0"),
                         (1, "error: no video track\n"))

    def test_read_mp4_maps_the_file(self):
        mapped = boxes.read_mp4(OUT / "f2.mp4")
        self.assertIsInstance(mapped, mmap.mmap)
        self.assertEqual((len(mapped), mapped[:8], mapped[4:8].decode()), (21663, F2[:8], "ftyp"))
        self.assertEqual(boxes.walk(mapped)[2].type, "moov")                     # readers take it as they took bytes
        with tempfile.NamedTemporaryFile() as empty:
            self.assertEqual(boxes.read_mp4(empty.name), b"")                     # an empty file cannot be mapped


if __name__ == "__main__":
    unittest.main()
