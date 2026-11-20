import json
import unittest
from fractions import Fraction
from pathlib import Path
from mp4kit import boxes, cli, mux, tables, timing
from tests.util import data, run_cli, run_cli_code

PHONE = data("phone.mp4")
OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep24.txt"
# Every copy of phone with the same aisle: ffmpeg wrote each from the same packets, in the same order.
COPIES = ("phone.mp4", "phone-fast.mp4", "phone-large.mp4", "rotated.mp4", "cenc.mp4", "broken-stco.mp4")


def tracks(name):
    contents = data(name)
    return tables.read_tracks(contents, boxes.walk(contents))


def stco_sorted(contents):
    """Every trak's chunk offsets (stco or co64) and samples per chunk (stsc), tagged with the track, all sorted
    together: the aisle from the drawers alone."""
    rows = []
    for n, trak in enumerate(boxes.find_all(boxes.walk(contents), "moov/trak"), 1):
        stbl = boxes.find(trak.children, "mdia/minf/stbl")
        offsets = tables.read_stco(contents, boxes.find(stbl.children, "stco") or boxes.find(stbl.children, "co64"))
        per = tables.chunk_sizes(tables.read_stsc(contents, boxes.find(stbl.children, "stsc")), len(offsets))
        firsts = [1 + sum(per[:k]) for k in range(len(per))]
        rows += zip(offsets, [n] * len(offsets), firsts, per)
    return sorted(rows)


class Ep24(unittest.TestCase):
    def test_chunk_list_phone(self):
        chunks = tables.chunk_list(tracks("phone.mp4"))
        self.assertEqual(len(chunks), 118)                                       # plan §4: 118 chunks
        self.assertEqual(chunks[:4], [(48, 1, 1, 2), (8011, 2, 1, 1), (8249, 1, 3, 1), (9289, 2, 2, 2)])
        self.assertEqual(chunks[-1], (107721, 2, 92, 4))
        self.assertEqual([sum(c[1] == n for c in chunks) for n in (1, 2)], [59, 59])
        self.assertEqual([c[1] for c in chunks], [1, 2] * 59)                     # the chunks alternate, every one

    def test_chunk_list_is_the_sorted_offsets(self):
        for name in COPIES + ("subs.mp4", "phone-chapters.mp4", "f1.mp4", "aac-only.m4a"):
            with self.subTest(name):
                self.assertEqual(tables.chunk_list(tracks(name)), stco_sorted(data(name)))

    def test_sample_chunk(self):
        video, sound = tracks("phone.mp4")
        self.assertEqual([s.chunk for s in video.samples[:4]], [1, 1, 2, 3])
        self.assertEqual([s.chunk for s in sound.samples[:6]], [1, 2, 2, 3, 3, 4])
        self.assertEqual([s.chunk for s in sound.samples[-4:]], [59] * 4)
        self.assertEqual([s.chunk for s in tracks("f1.mp4")[0].samples], [1] * 4 + [2] * 4 + [3] * 2 + [4] * 2)
        moved = tables.Sample(1, 0, 1024, 5824, 48, True, chunk=7)
        self.assertEqual(moved, video.samples[0])                                 # where it lies is not the sample

    def test_aisle_has_no_gaps(self):
        for name in ("phone.mp4", "phone-fast.mp4", "phone-large.mp4"):
            with self.subTest(name):
                contents, ts = data(name), tracks(name)
                mdat = boxes.find(boxes.walk(contents), "mdat")
                at = mdat.payload
                for offset, n, first, count in tables.chunk_list(ts):
                    self.assertEqual(offset, at)
                    at += sum(s.size for s in ts[n - 1].samples[first - 1:first - 1 + count])
                self.assertEqual(at, mdat.end)

    def test_chunks_match_ffprobe_packets(self):
        packets = json.loads((CAPS / "phone.mp4.probe.json").read_text())["packets"]
        runs = []
        for p in sorted(packets, key=lambda p: int(p["pos"])):
            pos, n, size = int(p["pos"]), p["stream_index"] + 1, int(p["size"])
            if runs and runs[-1][1] == n and runs[-1][4] == pos:
                runs[-1][3:] = [runs[-1][3] + 1, pos + size]
            else:
                runs.append([pos, n, None, 1, pos + size])
        chunks = tables.chunk_list(tracks("phone.mp4"))
        self.assertEqual([(r[0], r[1], r[3]) for r in runs], [(c[0], c[1], c[3]) for c in chunks])

    def test_timeline(self):
        video, sound = tracks("phone.mp4")
        self.assertEqual(mux.timeline(video)[:3], [Fraction(-1, 15), Fraction(-1, 30), 0])
        self.assertEqual(mux.timeline(sound)[:2], [Fraction(-8, 375), 0])
        packets = json.loads((CAPS / "phone.mp4.probe.json").read_text())["packets"]
        line = {(n, s.offset): t for n, tr in enumerate((video, sound)) for s, t in zip(tr.samples, mux.timeline(tr))}
        for p in packets:                                                         # ffprobe's dts_time, 6 decimals
            self.assertAlmostEqual(float(line[(p["stream_index"], int(p["pos"]))]), float(p["dts_time"]), places=6)

    def test_interleave_is_ffmpegs_order(self):
        for name in COPIES:
            with self.subTest(name):
                ts = tracks(name)
                self.assertEqual(mux.interleave(ts), [c[1:] for c in tables.chunk_list(ts)])

    def test_interleave_covers_every_sample_once(self):
        for name in COPIES + ("subs.mp4", "phone-chapters.mp4", "aac-only.m4a", "f1.mp4", "f2.mp4"):
            with self.subTest(name):
                ts = tracks(name)
                plan = mux.interleave(ts)
                got = sorted((n, first + i) for n, first, count in plan for i in range(count))
                self.assertEqual(got, [(n, s.number) for n, t in enumerate(ts, 1) for s in t.samples])
                starts = [mux.timeline(ts[n - 1])[first - 1] for n, first, _ in plan]
                self.assertEqual(starts, sorted(starts))                          # never goes backwards

    def test_interleave_chunk_seconds(self):
        ts = tracks("phone.mp4")
        self.assertEqual(len(mux.interleave(ts, 0)), 155)                         # one sample a chunk
        self.assertEqual(len(mux.interleave(ts, 0.03)), 120)                      # splits video 1-2, 1/30 s apart
        self.assertEqual(mux.interleave(ts, 1), mux.interleave(ts))               # runs end at the other track
        alone = tracks("aac-only.m4a")
        # 22 frames of 1,024 / 44,100 s = 0.51 s: the 23rd starts 0.5 s or more after a chunk's first
        self.assertEqual(mux.interleave(alone), [(1, 1, 22), (1, 23, 22), (1, 45, 22), (1, 67, 22)])
        self.assertEqual(mux.interleave(alone, 3), [(1, 1, 88)])                  # = the file's one chunk

    def test_seeking_lands_on_keyframes_not_chunks(self):
        video = tracks("phone.mp4")[0]
        starts = [first for _, n, first, _ in tables.chunk_list([video])]
        keys = [s.number for s in video.samples if s.key]
        self.assertEqual((len(starts), keys), (59, [1, 31]))
        self.assertIn(46, starts)                                                # 1.5 s: a chunk of its own
        self.assertEqual(timing.sync_before(keys, 46), 31)                        # decoding starts 15 samples back

    def test_cmd_chunks(self):
        printed = run_cli("chunks", str(OUT / "phone.mp4"))
        self.assertEqual(printed, EXPECTED.read_text())
        lines = printed.splitlines()
        self.assertEqual(lines[0], "118 chunks in file order: track 1 vide 59, track 2 soun 59")
        self.assertEqual(lines[2:4], ["1 48 1 1 2 7963 -0.0667 0.0667", "2 8011 2 1 1 238 -0.0213 0.0213"])
        self.assertEqual(lines[-3:], ["track 1 vide: 59 chunks, 60 samples, 84349 bytes, 1 to 2 samples a chunk",
                                      "track 2 soun: 59 chunks, 95 samples, 24347 bytes, 1 to 4 samples a chunk",
                                      "interleave (0.5 s chunks): the same order"])

    def test_cmd_chunks_other_files(self):
        self.assertIn("interleave (0.5 s chunks): a different order", run_cli("chunks", str(OUT / "aac-only.m4a")))
        self.assertTrue(run_cli("chunks", str(OUT / "phone-chapters.mp4")).splitlines()[2].startswith("1 48 3 1 2 34"))
        for name in ("frag-cmaf.mp4", "broken-nomoov.mp4"):
            with self.subTest(name):
                code, printed = run_cli_code("chunks", str(OUT / name))
                self.assertEqual(code, 1)
                self.assertTrue(printed.startswith("error: no chunks"))

    def test_registry(self):
        self.assertTrue(callable(cli.cmd_chunks))
        self.assertEqual([tables.chunk_list.__name__, mux.interleave.__name__], ["chunk_list", "interleave"])


if __name__ == "__main__":
    unittest.main()
