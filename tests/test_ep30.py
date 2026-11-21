import json
import shutil
import struct
import subprocess
import unittest
from pathlib import Path
from mp4kit import boxes, frag, tables
from mp4kit.boxes import box, full_box
from tests.util import data, run_cli

OUT = Path(__file__).parents[1] / "testfiles" / "out"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep30.txt"


def cmaf():
    contents = data("frag-cmaf.mp4")
    return contents, boxes.walk(contents)


def every_traf(contents, tree):
    """(track_ID, samples) for every traf of every moof, in file order, as dump --find trun lists them."""
    trex = {t["track_ID"]: t for t in (frag.read_trex(contents, b) for b in boxes.find_all(tree, "moov/mvex/trex"))}
    found = []
    for moof in (b for b in tree if b.type == "moof"):
        implicit = moof.start
        for traf in boxes.find_all(moof.children, "traf"):
            track = frag.read_tfhd(contents, boxes.find(traf.children, "tfhd"))["track_ID"]
            samples = frag.traf_samples(contents, moof, traf, trex[track], implicit)
            found.append((track, samples))
            implicit = samples[-1].offset + samples[-1].size
    return found


def trex(track, duration=0, size=0, flags=0):
    return full_box("trex", 0, 0, struct.pack(">5I", track, 1, duration, size, flags))


def tfhd(flags, track, *fields):
    """fields: (format, value) pairs, in the order the flags put them."""
    return full_box("tfhd", 0, flags, struct.pack(">I", track), *(struct.pack(f, v) for f, v in fields))


def trun(version, flags, count, *words, fmt=None):
    return full_box("trun", version, flags, struct.pack(">I", count), struct.pack(fmt or f">{len(words)}I", *words))


def tiny(*trafs):
    """A made-up file: an 8-byte ftyp-like box, then moov (mvex/trex for tracks 1 and 2: duration 100, size 7, flags
    non-sync), then one moof holding `trafs`, then an mdat of 64 bytes. Returns (bytes, tree, moof, trexes)."""
    moov = box("moov", box("mvex", trex(1, 100, 7, frag.NON_SYNC), trex(2, 100, 7, frag.NON_SYNC)))
    head = box("free") + moov
    moof = box("moof", full_box("mfhd", 0, 0, struct.pack(">I", 1)), *trafs)
    contents = head + moof + box("mdat", bytes(64))
    tree = boxes.walk(contents)
    trexes = {t["track_ID"]: t for t in (frag.read_trex(contents, b) for b in boxes.find_all(tree, "moov/mvex/trex"))}
    return contents, tree, boxes.find(tree, "moof"), trexes


class Ep30(unittest.TestCase):
    def test_read_trex(self):
        contents, tree = cmaf()
        found = [frag.read_trex(contents, b) for b in boxes.find_all(tree, "moov/mvex/trex")]
        self.assertEqual(found, [{"track_ID": t, "sample_description_index": 1, "default_sample_duration": 0,
                                  "default_sample_size": 0, "default_sample_flags": 0} for t in (1, 2)])
        # plan §4 says "every default 0": all but sample_description_index, which ffmpeg writes as 1 (movenc 4482)

    def test_read_tfhd(self):
        contents, tree = cmaf()
        found = [frag.read_tfhd(contents, b) for b in boxes.find_all(tree, "moof/traf/tfhd")]
        self.assertEqual(found[0], {"flags": 0x02003A, "track_ID": 1, "sample_description_index": 1,
                                    "default_sample_duration": 512, "default_sample_size": 5824,
                                    "default_sample_flags": 0x01010000})
        self.assertEqual(found[1], {"flags": 0x02003A, "track_ID": 2, "sample_description_index": 1,
                                    "default_sample_duration": 1024, "default_sample_size": 238,
                                    "default_sample_flags": 0x02000000})
        self.assertEqual([f["track_ID"] for f in found], [1, 2, 1, 2])
        self.assertTrue(all(f["flags"] & frag.DEFAULT_BASE_IS_MOOF and "base_data_offset" not in f for f in found))

    def test_read_tfhd_optional_fields(self):
        made = tfhd(0x01 | 0x10, 9, (">Q", 5000), (">I", 33))        # base_data_offset, then default size
        contents = box("moof", box("traf", made))
        got = frag.read_tfhd(contents, boxes.find(boxes.walk(contents), "moof/traf/tfhd"))
        self.assertEqual(got, {"flags": 0x11, "track_ID": 9, "base_data_offset": 5000, "default_sample_size": 33})

    def test_read_tfdt(self):
        contents, tree = cmaf()
        found = boxes.find_all(tree, "moof/traf/tfdt")
        self.assertEqual([frag.read_tfdt(contents, b) for b in found], [0, 0, 15360, 46080])   # plan §4
        self.assertEqual({boxes.read_fullbox(contents, b)[0] for b in found}, {1})                # version 1, 64-bit
        v0 = full_box("tfdt", 0, 0, struct.pack(">I", 777))
        self.assertEqual(frag.read_tfdt(v0, boxes.walk(v0)[0]), 777)

    def test_read_trun(self):
        contents, tree = cmaf()
        runs = [frag.read_trun(contents, b) for b in boxes.find_all(tree, "moof/traf/trun")]
        self.assertEqual([(r["flags"], r["sample_count"], r["data_offset"]) for r in runs],
                         [(0xA05, 30, 616), (0x201, 45, 42253), (0xA05, 30, 836), (0x301, 50, 43548)])
        video = runs[0]
        self.assertEqual(video["first_sample_flags"], 0x02000000)
        self.assertEqual(video["sample_size"][:3], [5824, 2139, 1040])
        self.assertEqual(video["sample_composition_time_offset"][:3], [0, 1024, -512])       # version 1: signed
        self.assertNotIn("sample_duration", video)
        self.assertNotIn("sample_flags", video)
        self.assertEqual(set(runs[1]) - {"version", "flags", "sample_count", "data_offset"}, {"sample_size"})
        self.assertEqual(runs[3]["sample_duration"][-1], 768)                               # the short last frame
        self.assertEqual(set(runs[3]["sample_duration"][:-1]), {1024})

    def test_trun_version_0_is_unsigned(self):
        made = trun(0, 0x800, 1, 0xFFFFFE00)
        self.assertEqual(frag.read_trun(made, boxes.walk(made)[0])["sample_composition_time_offset"], [0xFFFFFE00])
        made = trun(1, 0x800, 1, 0xFFFFFE00)
        self.assertEqual(frag.read_trun(made, boxes.walk(made)[0])["sample_composition_time_offset"], [-512])

    def test_one_trun_per_traf_here(self):
        _, tree = cmaf()
        trafs = boxes.find_all(tree, "moof/traf")
        self.assertEqual([sum(b.type == "trun" for b in t.children) for t in trafs], [1, 1, 1, 1])

    def test_offsets_fill_each_mdat(self):
        contents, tree = cmaf()
        found = every_traf(contents, tree)
        self.assertEqual([len(s) for _, s in found], [30, 45, 30, 50])
        self.assertEqual([s[0].offset for _, s in found], [1858, 43495, 55852, 98564])     # moof + data_offset
        mdats = [b for b in tree if b.type == "mdat"]
        for mdat, (_, video), (_, sound) in zip(mdats, found[0::2], found[1::2]):
            self.assertEqual(video[0].offset, mdat.payload)
            self.assertEqual(video[-1].offset + video[-1].size, sound[0].offset)
            self.assertEqual(sound[-1].offset + sound[-1].size, mdat.end)

    def test_phone_samples(self):
        contents, tree = cmaf()
        phone = data("phone.mp4")
        video, sound = tables.read_tracks(phone, boxes.walk(phone))
        found = every_traf(contents, tree)
        ours = {t: [s for track, samples in found if track == t for s in samples] for t in (1, 2)}
        self.assertEqual([(s.size, s.key) for s in ours[1]], [(s.size, s.key) for s in video.samples])
        self.assertEqual([(s.size, s.key, s.dts, s.cts) for s in ours[2]],
                         [(s.size, s.key, s.dts, s.cts) for s in sound.samples])
        self.assertEqual([s.dts for s in ours[1]], [s.dts for s in video.samples])
        self.assertEqual([s.cts for s in ours[1]], [s.cts - 1024 for s in video.samples])   # no elst: shifted
        self.assertEqual([i for i, s in enumerate(ours[1], 1) if s.key], [1, 31])

    def test_against_ffprobe(self):
        if not shutil.which("ffprobe"):
            self.fail("ffprobe required from ep29")
        contents, tree = cmaf()
        out = subprocess.run(["ffprobe", "-v", "error", "-show_packets", "-of", "json", str(OUT / "frag-cmaf.mp4")],
                             capture_output=True, text=True, check=True).stdout
        packets = json.loads(out)["packets"]
        found = every_traf(contents, tree)
        for track in (1, 2):
            ours = [s for t, samples in found if t == track for s in samples]
            theirs = [p for p in packets if p["stream_index"] == track - 1]
            shift = max(0, *(s.dts - s.cts for s in ours))       # mov.c's dts_shift: 512 for video, 0 for sound
            self.assertEqual([(s.offset, s.size, s.dts, s.cts + shift, s.key) for s in ours],
                             [(int(p["pos"]), int(p["size"]), p["dts"], p["pts"], p["flags"][0] == "K") for p in theirs])

    def test_defaults_chain(self):
        # track 1: tfhd gives only a default duration (50); size and flags fall back to trex (7, non-sync).
        # run 1: data_offset, first_sample_flags 0 (a sync sample), 2 samples. run 2: no data_offset, one size column.
        traf1 = box("traf", tfhd(0x020008, 1, (">I", 50)), full_box("tfdt", 1, 0, struct.pack(">Q", 1000)),
                    trun(0, 0x005, 2, 0, 0, fmt=">iI"), trun(0, 0x200, 2, 3, 4))
        # track 2: no base flags, so its base is where track 1's data ended; trun columns for everything.
        traf2 = box("traf", tfhd(0, 2), full_box("tfdt", 0, 0, struct.pack(">I", 0)),
                    trun(1, 0xF00, 1, 9, 5, frag.NON_SYNC, -3, fmt=">IIIi"))
        contents, tree, moof, trexes = tiny(traf1, traf2)
        traf1_box, traf2_box = boxes.find_all(moof.children, "traf")
        first = frag.traf_samples(contents, moof, traf1_box, trexes[1], moof.start)
        self.assertEqual([(s.dts, s.size, s.offset, s.key) for s in first],
                         [(1000, 7, moof.start, True), (1050, 7, moof.start + 7, False),
                          (1100, 3, moof.start + 14, False), (1150, 4, moof.start + 17, False)])
        second = frag.traf_samples(contents, moof, traf2_box, trexes[2], first[-1].offset + first[-1].size)
        self.assertEqual([(s.dts, s.cts, s.size, s.offset, s.key) for s in second], [(0, -3, 5, moof.start + 21, False)])

    def test_base_data_offset(self):
        traf = box("traf", tfhd(0x01 | 0x020000, 1, (">Q", 40)), full_box("tfdt", 1, 0, struct.pack(">Q", 0)),
                   trun(0, 0x201, 1, 8, 2, fmt=">iI"))
        contents, tree, moof, trexes = tiny(traf)
        samples = frag.traf_samples(contents, moof, boxes.find(moof.children, "traf"), trexes[1], moof.start)
        self.assertEqual((samples[0].offset, samples[0].size), (48, 2))   # base_data_offset wins over the moof

    def test_dump_boxes(self):
        printed = run_cli("dump", str(OUT / "frag-cmaf.mp4")).splitlines()
        self.assertIn("  mfhd 1250 16 sequence_number=1", printed)
        self.assertIn("  mfhd 55024 16 sequence_number=2", printed)
        self.assertIn("    tfdt 55080 20 version=1 baseMediaDecodeTime=15360", printed)
        self.assertIn("    trex 1117 32 track_ID=1 sample_description_index=1 default_sample_duration=0 "
                      "default_sample_size=0 default_sample_flags=0x00000000", printed)

    def test_cli(self):
        printed = run_cli("dump", str(OUT / "frag-cmaf.mp4"), "--find", "trun")
        self.assertEqual(printed, EXPECTED.read_text())
        lines = printed.splitlines()
        self.assertEqual(lines[4], "moof 1242 traf 1266: track 1, 1 trun, 30 samples, tfdt 0; duration 512 from tfhd; "
                                   "size from trun; flags first_sample_flags from trun, then 0x01010000 from tfhd; "
                                   "cto from trun")
        self.assertEqual(lines[6], "1 0 0 5824 1858 K")
        self.assertEqual(len(lines), 4 + 4 * 2 + 155)
        self.assertEqual(run_cli("dump", str(OUT / "phone.mp4"), "--find", "trun"), "no trun box\n")


if __name__ == "__main__":
    unittest.main()
