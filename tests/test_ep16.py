import dataclasses
import json
import unittest
from pathlib import Path
from mp4kit import boxes, tables, timing
from tests.util import data, run_cli, run_cli_code

F1, PHONE, LARGE = data("f1.mp4"), data("phone.mp4"), data("phone-large.mp4")
OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep16.txt"
STBL = "moov/trak/mdia/minf/stbl"


def probe(name):
    """ffprobe's packets and streams for a committed file (testfiles/captures/<name>.probe.json)."""
    return json.loads((CAPS / f"{name}.probe.json").read_text())


def tables_of(contents):
    """sample_table of every track of a file, in file order."""
    return [tables.sample_table(contents, trak) for trak in boxes.find_all(boxes.walk(contents), "moov/trak")]


class Ep16(unittest.TestCase):
    def test_sample_fields(self):
        self.assertEqual([f.name for f in dataclasses.fields(tables.Sample)],
                         ["number", "dts", "cts", "size", "offset", "key"])

    def test_sample_table_f1(self):
        samples = tables_of(F1)[0]
        self.assertEqual([s.number for s in samples], list(range(1, 13)))
        self.assertEqual([s.dts for s in samples], timing.decode_times([(12, 33)]))            # drawer 1, stts
        self.assertEqual([s.number for s in samples if s.key], [1, 5, 9])                    # drawer 2, stss
        self.assertEqual([s.offset for s in samples], [40, 5345, 5707, 6139, 6598, 12808, 13307, 13817,
                                                       14356, 20712, 21149, 21638])          # drawers 3 and 4
        self.assertEqual([s.size for s in samples], [5305, 362, 432, 459, 6210, 499, 510, 539, 6356, 437, 489,
                                                     419])                                   # drawer 5, stsz
        self.assertEqual(samples[6], tables.Sample(7, 198, 198, 510, 13307, False))          # ep15's worked answer
        self.assertEqual(F1[13307:13312].hex(), "000001fa41")                                # 506 = 510 - 4

    def test_sample_table_phone(self):
        video, audio = tables_of(PHONE)
        self.assertEqual((len(video), len(audio)), (60, 95))
        self.assertEqual(video[0], tables.Sample(1, 0, 0, 5824, 48, True))
        self.assertEqual(video[1], tables.Sample(2, 512, 512, 2139, 5872, False))              # 48 + 5824
        self.assertEqual(video[2].offset, 8249)                                              # chunk 2: stco
        self.assertEqual([s.number for s in video if s.key], [1, 31])
        self.assertEqual((audio[0].offset, audio[0].size, audio[0].dts), (8011, 238, 0))
        self.assertTrue(all(s.key for s in audio))                                           # no stss in audio
        self.assertTrue(all(s.cts == s.dts for s in video + audio))                          # ctts is episode 17

    def test_matches_ffprobe(self):
        for f in sorted(OUT.glob("*.mp4")) + sorted(OUT.glob("*.m4a")):
            if f.name in ("broken-nomoov.mp4", "frag-cmaf.mp4"):                              # no moov; samples in moof
                continue
            captured = probe(f.name)
            for index, samples in enumerate(tables_of(f.read_bytes())):
                packets = [p for p in captured["packets"] if p["stream_index"] == index]
                with self.subTest(f=f.name, track=index + 1):
                    self.assertEqual(len(samples), int(captured["streams"][index]["nb_frames"]))
                    samples = samples[:len(packets)]                                         # subs: 3 of 4 listed
                    self.assertEqual([int(p["pos"]) for p in packets], [s.offset for s in samples])
                    self.assertEqual([int(p["size"]) for p in packets], [s.size for s in samples])
                    self.assertEqual([p["dts"] - packets[0]["dts"] for p in packets],
                                     [s.dts for s in samples])                               # ffprobe adds elst
                    keys = [p["flags"].startswith("K") for p in packets]
                    if (f.name, index) == ("broken-stco.mp4", 0):    # stss says 1 and 31; ffprobe's parser reads
                        self.assertEqual((keys[0], samples[0].key), (False, True))   # junk at 1,048 and drops K
                        keys[0] = True
                    self.assertEqual(keys, [s.key for s in samples])

    def test_phone_all_155(self):
        packets = sorted((int(p["pos"]), int(p["size"])) for p in probe("phone.mp4")["packets"])
        mine = sorted((s.offset, s.size) for track in tables_of(PHONE) for s in track)
        self.assertEqual((len(mine), mine), (155, packets))

    def test_phone_large_co64(self):
        self.assertEqual(tables_of(LARGE), tables_of(PHONE))                                 # same offsets in co64

    def test_broken_stco(self):
        video = tables_of(data("broken-stco.mp4"))[0]
        self.assertEqual((video[0].offset, video[0].size), (1048, 5824))                     # MANIFEST: stco patched

    def test_frag_cmaf_empty(self):
        self.assertEqual(tables_of(data("frag-cmaf.mp4")), [[], []])                         # samples live in moof

    def test_counts_disagree(self):
        blob = bytearray(F1)
        self.assertEqual(blob[22602:22606].hex(), "0000000c")                                # stts sample_count 12
        blob[22605] = 11
        trak = boxes.find(boxes.walk(bytes(blob)), "moov/trak")
        with self.assertRaisesRegex(boxes.BoxError, "stbl at 22422: stts has 11 samples, stsc 12, stsz 12"):
            tables.sample_table(bytes(blob), trak)

    def test_cmd_samples_phone(self):
        printed = run_cli("samples", "testfiles/out/phone.mp4", "--track", "1")
        self.assertEqual(printed, EXPECTED.read_text())
        lines = printed.splitlines()
        self.assertEqual(lines[:3], ["track 1 vide, timescale 15360, 60 samples", "sample dts key offset size",
                                     "1 0 K 48 5824"])
        self.assertEqual((len(lines), lines[32]), (62, "31 15360 K 53206 6517"))

    def test_cmd_samples_f1_default_track(self):
        lines = run_cli("samples", "testfiles/out/f1.mp4").splitlines()
        self.assertEqual((lines[0], lines[8]), ("track 1 vide, timescale 1000, 12 samples", "7 198 - 13307 510"))

    def test_cmd_samples_no_track(self):
        self.assertEqual(run_cli_code("samples", "testfiles/out/phone.mp4", "--track", "3"),
                         (1, "error: no track 3, the file has 2\n"))
        self.assertEqual(run_cli_code("samples", "testfiles/out/broken-nomoov.mp4"),
                         (1, "error: no track 1, the file has 0\n"))
