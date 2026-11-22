import json
import struct
import unittest
from pathlib import Path
from mp4kit import boxes, cli, frag, tables
from mp4kit.boxes import box, full_box
from tests.util import data, run_cli, run_cli_code

OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep31.txt"


def opened(name):
    contents = data(name)
    return contents, boxes.walk(contents)


def packets(name, stream):
    """ffprobe's packets of one stream (captures/<name>.probe.json): (pos, size, dts, pts, key)."""
    probe = json.loads((CAPS / f"{name}.probe.json").read_text())
    return [(int(p["pos"]), int(p["size"]), p["dts"], p["pts"], p["flags"].startswith("K"))
            for p in probe["packets"] if p["stream_index"] == stream]


class Ep31(unittest.TestCase):
    def test_fragment_samples_cmaf(self):
        contents, tree = opened("frag-cmaf.mp4")
        tracks = frag.fragment_samples(contents, tree)
        self.assertEqual(sorted(tracks), [1, 2])
        video, sound = tracks[1], tracks[2]
        self.assertEqual([len(video), len(sound)], [60, 95])                          # plan §4: phone's 60 + 95
        self.assertEqual([s.number for s in sound], list(range(1, 96)))               # numbered per track
        self.assertEqual([sum(s.chunk == n for s in video) for n in (1, 2)], [30, 30])
        self.assertEqual([sum(s.chunk == n for s in sound) for n in (1, 2)], [45, 50])   # ep30: 45 then 50 frames
        phone = data("phone.mp4")
        pv, pa = tables.read_tracks(phone, boxes.walk(phone))[:2]
        self.assertEqual([s.size for s in video], [s.size for s in pv.samples])
        self.assertEqual([s.size for s in sound], [s.size for s in pa.samples])
        for track, stream, shift in ((video, 0, 512), (sound, 1, 0)):                 # mov.c's dts_shift: ep30
            ours = [(s.offset, s.size, s.dts, s.cts + shift, s.key) for s in track]
            self.assertEqual(ours, packets("frag-cmaf.mp4", stream))

    def test_fragment_samples_sidx_file(self):
        contents, tree = opened("phone-sidx.mp4")
        tracks = frag.fragment_samples(contents, tree)
        for track, stream in ((tracks[1], 0), (tracks[2], 1)):                         # no negative cto: no shift
            ours = [(s.offset, s.size, s.dts, s.cts, s.key) for s in track]
            self.assertEqual(ours, packets("phone-sidx.mp4", stream))
        self.assertEqual(tracks[1][0].cts, 1024)                                       # no +cmaf: cto from 1,024
        self.assertEqual(tracks[2][1].dts, 3200)                                       # its first sound frame: 3,200

    def test_trex_still_says_description_1(self):
        contents, tree = opened("frag-cmaf.mp4")
        found = [frag.read_trex(contents, b) for b in boxes.find_all(tree, "moov/mvex/trex")]
        self.assertEqual([t["sample_description_index"] for t in found], [1, 1])      # ep30's correction holds

    def test_read_tfra(self):
        contents, tree = opened("frag-cmaf.mp4")
        found = [frag.read_tfra(contents, b) for b in boxes.find_all(tree, "mfra/tfra")]
        self.assertEqual(found, [  # plan §4: track 1 [(0, 1242), (15360, 55016)], track 2 [(0, 1242), (45056, 55016)]
            {"version": 1, "track_ID": 1, "entries": [(0, 1242, 1, 1, 1), (15360, 55016, 1, 1, 1)]},
            {"version": 1, "track_ID": 2, "entries": [(0, 1242, 1, 1, 1), (45056, 55016, 1, 1, 1)]}])
        self.assertEqual([b.start for b in tree if b.type == "moof"], [1242, 55016])  # each entry names a moof
        tfdt = [frag.read_tfdt(contents, b) for b in boxes.find_all(tree, "moof/traf/tfdt")]
        self.assertEqual(tfdt[3] - found[1]["entries"][1][0], 1024)                    # sound: the priming, not tfdt
        contents, tree = opened("phone-sidx.mp4")
        found = [frag.read_tfra(contents, b)["entries"] for b in boxes.find_all(tree, "mfra/tfra")]
        self.assertEqual(found, [[(1024, 1370, 1, 1, 1), (16384, 55316, 1, 1, 1)],
                                 [(0, 1370, 1, 1, 1), (48256, 55316, 1, 1, 1)]])

    def test_tfra_number_lengths(self):
        # version 0, lengths 0x1b: traf number 2 bytes, trun 3, sample 4 (each field's 2 bits + 1)
        made = full_box("tfra", 0, 0, struct.pack(">III", 7, 0x1B, 2), struct.pack(">II", 100, 5000),
                        b"\x00\x01" b"\x00\x00\x02" b"\x00\x00\x00\x03", struct.pack(">II", 200, 9000),
                        b"\x00\x02" b"\x00\x00\x01" b"\x00\x00\x01\x00")
        self.assertEqual(frag.read_tfra(made, boxes.walk(made)[0]),
                         {"version": 0, "track_ID": 7, "entries": [(100, 5000, 1, 2, 3), (200, 9000, 2, 1, 256)]})

    def test_read_mfro_and_back_gate(self):
        for name, start in (("frag-cmaf.mp4", 111390), ("phone-sidx.mp4", 111682)):
            contents, tree = opened(name)
            mfra = frag.back_gate(contents)
            self.assertEqual((mfra.start, mfra.size, mfra.end), (start, 148, len(contents)))   # plan §4: 148
            self.assertEqual(frag.read_mfro(contents, boxes.find(mfra.children, "mfro")), 148)
            self.assertEqual(boxes.u32(contents, len(contents) - 4), 148)
            self.assertEqual([b.type for b in mfra.children], ["tfra", "tfra", "mfro"])
        skip = ("frag-cmaf.mp4", "phone-sidx.mp4", "phone.ts")            # phone.ts (episode 36): MPEG-TS
        for name in sorted(p.name for p in OUT.iterdir() if p.name not in skip):
            with self.subTest(name):
                self.assertIsNone(frag.back_gate(data(name)))       # phone-fast and broken-nomoov end in 896: no mfra
        self.assertIsNone(frag.back_gate(b""))

    def test_read_sidx(self):
        contents, tree = opened("phone-sidx.mp4")
        found = [frag.read_sidx(contents, b) for b in boxes.find_all(tree, "sidx")]
        self.assertEqual([(b.start, b.size) for b in boxes.find_all(tree, "sidx")], [(1242, 64), (1306, 64)])
        self.assertEqual([(f["reference_ID"], f["timescale"], f["earliest_presentation_time"], f["first_offset"])
                          for f in found], [(1, 15360, 1024, 64), (2, 48000, 0, 0)])  # one sidx per track
        self.assertEqual(found[0]["references"], [(0, 53946, 15360, 1, 0, 0), (0, 56366, 15360, 1, 0, 0)])
        self.assertEqual(found[1]["references"], [(0, 53946, 48256, 1, 0, 0), (0, 56366, 50944, 1, 0, 0)])
        self.assertEqual(found[0]["ranges"], [(1024, 1370, 55316), (16384, 55316, 111682)])
        self.assertEqual(found[1]["ranges"], [(0, 1370, 55316), (48256, 55316, 111682)])
        moofs, mdats = [b for b in tree if b.type == "moof"], [b for b in tree if b.type == "mdat"]
        self.assertEqual([(m.start, d.end) for m, d in zip(moofs, mdats)], [(r[1], r[2]) for r in found[0]["ranges"]])
        probe = json.loads((CAPS / "phone-sidx.mp4.probe.json").read_text())["streams"]
        self.assertEqual([int(s["duration_ts"]) for s in probe], [1024 + 15360 * 2, 48256 + 50944])  # mov.c: from sidx
        self.assertEqual(boxes.find_all(boxes.walk(data("frag-cmaf.mp4")), "sidx"), [])

    def test_sidx_version_0_in_memory(self):
        made = full_box("sidx", 0, 0, struct.pack(">IIIIHH", 3, 1000, 40, 8, 0, 2),
                        struct.pack(">III", (1 << 31) | 500, 2000, (1 << 31) | (2 << 28) | 7),
                        struct.pack(">III", 600, 1000, 0))
        got = frag.read_sidx(made, boxes.walk(made)[0])
        self.assertEqual(got["references"], [(1, 500, 2000, 1, 2, 7), (0, 600, 1000, 0, 0, 0)])
        end = len(made)                                                                 # first_offset 8 after it
        self.assertEqual(got["ranges"], [(40, end + 8, end + 508), (2040, end + 508, end + 1108)])

    def test_fragment_at(self):
        index = [(0, 1242), (15360, 55016)]
        self.assertEqual([frag.fragment_at(index, t)[1] for t in (0, 15359, 15360, 99999)], [1242, 1242, 55016, 55016])
        self.assertEqual(frag.fragment_at([(1024, 1370), (16384, 55316)], 0), (1024, 1370))   # before it: the first

    def test_cmd_samples(self):
        out = run_cli("samples", str(OUT / "frag-cmaf.mp4"))
        self.assertEqual(out, EXPECTED.read_text())
        lines = out.splitlines()
        self.assertEqual(len(lines), 62)
        self.assertEqual(lines[:3], ["track 1 vide, timescale 15360, 60 samples in 2 fragments (moof 1242, 55016)",
                                     "sample dts key offset size fragment", "1 0 K 1858 5824 1"])
        self.assertEqual(lines[32], "31 15360 K 55852 6517 2")
        self.assertEqual(run_cli("samples", str(OUT / "phone.mp4")).splitlines()[:2],
                         ["track 1 vide, timescale 15360, 60 samples", "sample dts key offset size"])   # unchanged

    def test_cmd_samples_at(self):
        self.assertEqual(run_cli("samples", str(OUT / "phone-sidx.mp4"), "--at", "1500").splitlines()[1:], [
            "at 23040 ticks",
            "sidx: ranges start at [1024, 16384]: 16384, bytes 55316 to 111682",
            "mfra 111682 (the last 4 bytes: 148): tfra times [1024, 16384]: 16384, moof 55316",
            "moofs: fragment 2, moof 55316, earliest cts 16384: samples 31 to 60, from byte 56144"])
        # the sound tfra of frag-cmaf runs 1,024 ticks early: at 0.95 s it names fragment 2, the moofs say 1
        out = run_cli("samples", str(OUT / "frag-cmaf.mp4"), "--track", "2", "--at", "950").splitlines()
        self.assertEqual(out[2:], ["mfra 111390 (the last 4 bytes: 148): tfra times [0, 45056]: 45056, moof 55016",
                                   "moofs: fragment 1, moof 1242, earliest cts 0: samples 1 to 45, from byte 43495"])
        code, out = run_cli_code("samples", str(OUT / "frag-cmaf.mp4"), "--at", "1000")
        self.assertEqual((code, out.splitlines()[-1]),
                         (0, "moofs: fragment 2, moof 55016, earliest cts 15360: samples 31 to 60, from byte 55852"))

    def test_source_says_when_only_some_runs_carry_a_column(self):
        tfhd, trex = {"default_sample_size": 6517, "default_sample_duration": 512}, {"default_sample_flags": 0}
        runs = [{"sample_size": [1]}, {}, {"sample_size": [2], "first_sample_flags": 5}]
        self.assertEqual(cli._source("size", "default_sample_size", tfhd, trex, runs),
                         "size from trun (2 of 3 runs), else 6517 from tfhd")
        self.assertEqual(cli._source("duration", "default_sample_duration", tfhd, trex, runs), "duration 512 from tfhd")
        self.assertEqual(cli._source("flags", "default_sample_flags", tfhd, trex, runs),
                         "flags first_sample_flags from trun (1 of 3 runs), then 0x00000000 from trex")
        self.assertEqual(cli._source("size", "default_sample_size", tfhd, trex, runs[:1]), "size from trun")
        self.assertEqual(cli._from_runs("sample_composition_time_offset", runs, "0"), "0")


if __name__ == "__main__":
    unittest.main()
