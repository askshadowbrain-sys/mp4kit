import json
import unittest
from fractions import Fraction
from pathlib import Path
from mp4kit import boxes, cli, tables, timing
from tests.util import data, run_cli, run_cli_code

OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep25.txt"
# Every file whose samples are all ffprobe's packets (subs drops its last, empty subtitle sample; ffprobe lists no
# packets for phone-chapters' chapter track; broken-stco's first packet is not a keyframe to ffprobe's parser).
SAME = ("phone.mp4", "phone-fast.mp4", "phone-large.mp4", "rotated.mp4", "cenc.mp4", "f1.mp4", "f2.mp4",
        "aac-only.m4a", "av1.mp4", "hevc.mp4", "hevc-hev1.mp4", "hdr.mp4")


def packets(name):
    contents = data(name)
    return timing.packets(tables.read_tracks(contents, boxes.walk(contents)))


def probe(name):
    """ffprobe's packets (-show_packets, the committed capture) in mp4kit's shape; times to ffprobe's 6 decimals."""
    return [{"stream": p["stream_index"], "dts": p["dts"], "pts": p["pts"], "duration": p["duration"],
             "dts_time": p["dts_time"], "pts_time": p["pts_time"], "size": int(p["size"]), "pos": int(p["pos"]),
             "key": "K" in p["flags"]} for p in json.loads((CAPS / f"{name}.probe.json").read_text())["packets"]]


def printed_times(packets):
    return [{**p, "dts_time": f"{float(p['dts_time']):.6f}", "pts_time": f"{float(p['pts_time']):.6f}"}
            for p in packets]


class Ep25(unittest.TestCase):
    def test_packets_are_ffprobes(self):
        for name in SAME:                                                        # plan §4: = probe.json packets
            with self.subTest(name):
                self.assertEqual(printed_times(packets(name)), probe(name))

    def test_packets_phone(self):
        got = packets("phone.mp4")
        self.assertEqual(len(got), 155)
        self.assertEqual(got[0], {"stream": 0, "dts": -1024, "pts": 0, "duration": 512, "dts_time": Fraction(-1, 15),
                                  "pts_time": 0, "size": 5824, "pos": 48, "key": True})
        self.assertEqual([(p["stream"], p["dts"], p["pts"], p["pos"]) for p in got[1:4]],
                         [(0, -512, 1536, 5872), (1, -1024, -1024, 8011), (0, 0, 512, 8249)])
        self.assertEqual((got[-1]["duration"], got[-1]["dts_time"]), (768, Fraction(1984, 1000)))

    def test_play_order_is_file_order(self):
        for name in SAME:                                                        # the muxer zipped by decode time
            with self.subTest(name):
                got = packets(name)
                self.assertEqual(timing.play_order(got), got)
        got = packets("phone.mp4")
        self.assertEqual([p["stream"] for p in got[:8]], [0, 0, 1, 0, 1, 1, 0, 1])

    def test_play_order_where_the_file_is_not(self):
        got = packets("subs.mp4")
        order = timing.play_order(got)
        self.assertNotEqual(order, got)
        gap = [i for i, p in enumerate(got, 1) if p["pos"] == 63613][0]          # the empty 0.9 s subtitle sample
        self.assertEqual((gap, order.index(got[gap - 1]) + 1), (83, 76))         # written after the video at 1.0 s
        chapters = timing.play_order(packets("phone-chapters.mp4"))
        self.assertEqual([i for i, p in enumerate(chapters, 1) if p["stream"] == 2], [6, 83])  # written first, at 48

    def test_play_order_merges_by_seconds(self):
        a = {"stream": 1, "dts_time": Fraction(0), "pos": 1}
        b = {"stream": 0, "dts_time": Fraction(0), "pos": 2}
        c = {"stream": 0, "dts_time": Fraction(-1, 30), "pos": 3}
        self.assertEqual(timing.play_order([a, b, c]), [c, b, a])                 # a tie goes to the lower stream

    def test_shown_order_is_ffprobes_frames(self):
        video = [p for p in packets("phone.mp4") if p["stream"] == 0]
        # ffprobe -show_frames: the decoder's frames come out by pts; their pkt_pos in output order
        out = [48, 8249, 9796, 5872, 13285, 14852, 11208, 18145, 15997, 21488, 22903, 19279]
        self.assertEqual([p["pos"] for p in sorted(video, key=lambda p: p["pts"])][:12], out)
        f2 = sorted(packets("f2.mp4"), key=lambda p: p["pts"])
        self.assertEqual([p["pos"] for p in f2[:5]], [40, 5940, 6040, 5629, 6185])

    def test_reorder_depth(self):
        for name, depth in (("phone.mp4", 1), ("f2.mp4", 1), ("f1.mp4", 0), ("hevc.mp4", 2), ("aac-only.m4a", 0)):
            with self.subTest(name):
                video = [p for p in packets(name) if p["stream"] == 0]
                self.assertEqual(timing.reorder_depth(video), depth)
        self.assertEqual(timing.reorder_depth([]), 0)
        self.assertEqual(timing.reorder_depth([{"pts": 0}, {"pts": 3}, {"pts": 2}, {"pts": 1}]), 2)

    def test_cmd_packets(self):
        printed = run_cli("packets", str(OUT / "phone.mp4"))
        self.assertEqual(printed, EXPECTED.read_text())
        lines = printed.splitlines()
        self.assertEqual(len(lines), 160)
        self.assertEqual(lines[0], "155 packets: stream 0 vide 60 (time_base 1/15360), stream 1 soun 95 "
                                   "(time_base 1/48000)")
        self.assertEqual(lines[2:4], ["1 0 -0.066667 0.000000 -1024 0 512 5824 48 K 1",
                                      "2 0 -0.033333 0.100000 -512 1536 512 2139 5872 - 4"])
        self.assertEqual(lines[-3:], [
            "stream 0 vide: 60 packets, 2 key, reorder depth 1; the first dts is 1024 ticks = 2 x 512 before its pts",
            "stream 1 soun: 95 packets, 95 key, reorder depth 0; the first dts is 0 ticks = 0 x 1024 before its pts",
            "play order (by dts_time) is file order (by pos): yes"])

    def test_cmd_packets_other_files(self):
        self.assertTrue(run_cli("packets", str(OUT / "subs.mp4")).endswith("file order (by pos): no\n"))
        self.assertIn("reorder depth 1; the first dts is 33 ticks = 1 x 33", run_cli("packets", str(OUT / "f2.mp4")))
        for name in ("frag-cmaf.mp4", "broken-nomoov.mp4"):
            with self.subTest(name):
                code, printed = run_cli_code("packets", str(OUT / name))
                self.assertEqual(code, 1)
                self.assertTrue(printed.startswith("error: no packets"))

    def test_registry(self):
        self.assertTrue(callable(cli.cmd_packets))
        self.assertEqual([timing.packets.__name__, timing.play_order.__name__], ["packets", "play_order"])


if __name__ == "__main__":
    unittest.main()
