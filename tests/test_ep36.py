import json
import struct
import unittest
from pathlib import Path
from mp4kit import boxes, check, tables
from tests.util import TESTFILES, data, run_cli, run_cli_code

CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep36.txt"
PHONE, STCO, NOMOOV, TS = data("phone.mp4"), data("broken-stco.mp4"), data("broken-nomoov.mp4"), data("phone.ts")
BROKEN = {"broken-stco.mp4", "broken-nomoov.mp4"}
FRAGMENTED = {"frag-cmaf.mp4", "phone-sidx.mp4"}


def tracks_of(buf):
    return tables.read_tracks(buf, boxes.walk(buf))


def patched(buf, path, at, fmt, value, n=0):
    """buf with one field of the n-th box down `path` overwritten, `at` bytes into its payload."""
    out = bytearray(buf)
    struct.pack_into(fmt, out, boxes.find_all(boxes.walk(buf), path)[n].payload + at, value)
    return bytes(out)


def levels(found):
    return [m.split(":")[0] for m in found]


class Ep36(unittest.TestCase):
    def test_problems_on_every_test_file(self):
        """The 21 committed files: errors only in the two broken ones, a note for the two fragmented files and for
        phone.ts, nothing at all for the other 16 (plan row 313: the good files give [])."""
        files = sorted(TESTFILES.glob("*.mp4")) + sorted(TESTFILES.glob("*.m4a")) + sorted(TESTFILES.glob("*.ts"))
        self.assertEqual(len(files), 21)
        for f in files:
            with self.subTest(f=f.name):
                found = check.problems(f.read_bytes())
                if f.name in BROKEN:
                    self.assertIn("error", levels(found))
                elif f.name in FRAGMENTED or f.suffix == ".ts":
                    self.assertEqual(levels(found), ["note"])
                else:
                    self.assertEqual(found, [])

    def test_every_problem_has_a_symptom_and_a_cause(self):
        for buf in (STCO, NOMOOV):
            for message in check.problems(buf):
                lines = message.splitlines()
                self.assertEqual([line.split(":")[0].strip() for line in lines[1:]], ["symptom", "cause"])

    def test_no_moov(self):
        tree = boxes.walk(NOMOOV)
        self.assertEqual([b.type for b in tree], ["ftyp", "free", "mdat"])
        found = check.no_moov(NOMOOV, tree)
        self.assertEqual(found[0].splitlines()[0],
                         "error: no moov box: the file ends at 108744, right after mdat at 40 (108704 bytes)")
        self.assertEqual(len(NOMOOV), 108744)                                       # where phone.mp4's moov starts
        self.assertEqual(boxes.find(boxes.walk(PHONE), "moov").start, 108744)
        err = (CAPS / "broken-nomoov.mp4.probe.err.txt").read_text()
        self.assertIn("moov atom not found", err)                                    # ffprobe's words, in the symptom
        self.assertIn("Invalid data found when processing input", err)
        self.assertIn("moov atom not found", found[0])
        self.assertEqual(check.problems(NOMOOV), found)

    def test_overlapping_chunks(self):
        """broken-stco's first video chunk starts 1,000 bytes late, so it runs into the next two chunks in file order
        (plan row 315 names only the first)."""
        found = check.overlapping_chunks(tracks_of(STCO))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].splitlines()[0], "error: track 1 chunk 1 (bytes 1048 to 9010) overlaps track 2 "
                                                   "chunk 1 at 8011, track 1 chunk 2 at 8249")
        video = tracks_of(STCO)[0]
        self.assertEqual(1048 + video.samples[0].size + video.samples[1].size, 9011)   # 5,824 + 2,139 = 7,963
        self.assertEqual(check.overlapping_chunks(tracks_of(PHONE)), [])

    def test_the_moved_offset_leaves_a_hole(self):
        """The other side of the same patch: mdat's first 1,000 payload bytes belong to no sample."""
        found = check.problems(STCO)
        self.assertEqual(levels(found), ["error", "warning", "error"])
        self.assertEqual(found[1].splitlines()[0], "warning: mdat bytes 48 to 1047 (1000 bytes) belong to no sample")
        self.assertEqual(tracks_of(PHONE)[0].samples[0].offset + 1000, tracks_of(STCO)[0].samples[0].offset)
        self.assertEqual(sum(a != b for a, b in zip(PHONE, STCO)), 2)                 # 48 -> 1048: two bytes of stco

    def test_outside_mdat(self):
        last = len(tables.read_stco(PHONE, boxes.find_all(boxes.walk(PHONE), "moov/trak/mdia/minf/stbl/stco")[1]))
        past = patched(PHONE, "moov/trak/mdia/minf/stbl/stco", 4 + 4 * last, ">I", len(PHONE) + 100, n=1)
        found = check.outside_mdat(tracks_of(past), boxes.walk(past), len(past))
        self.assertEqual(found[0].splitlines()[:2], [
            "error: track 2 chunk 59 (bytes 112256 to 113278) lies past the end of the file (112156)",
            "  symptom: ffmpeg says: stream 1, offset 0x1b680: partial file"])             # ffmpeg 9.0.2's line
        into = patched(PHONE, "moov/trak/mdia/minf/stbl/stco", 4 + 4 * 59, ">I", 108800)
        found = check.problems(into)
        self.assertEqual(found[0].splitlines()[0], "error: track 1 chunk 59 (bytes 108800 to 109949) lies outside "
                                                   "mdat, in moov")
        self.assertIn("Invalid NAL unit size (0 > 1146)", found[2])                      # ffmpeg 9.0.2's line
        self.assertEqual(check.outside_mdat(tracks_of(PHONE), boxes.walk(PHONE), len(PHONE)), [])

    def test_nal_lengths(self):
        """broken-stco's video samples 1 and 2 are read 1,000 bytes late: their first 4 bytes are not a length."""
        video = tracks_of(STCO)[0]
        found = check.nal_lengths(STCO, video)
        self.assertEqual(found[0].splitlines()[:2], [
            "error: track 1: a NAL length that does not fit in 2 of 60 samples; the first, sample 1 (5824 bytes at "
            "1048): length 632640939 at byte 0, 5820 bytes left",
            "  symptom: the decoder says: Invalid NAL unit size (632640939 > 5820), and drops the picture"])
        self.assertEqual(STCO[1048:1052].hex(), "25b555ab")                               # = 632,640,939
        self.assertEqual(check._overrun(STCO, video.samples[1], 4), (0, 3023811340, 2135))
        err = (CAPS / "broken-stco.mp4.probe.err.txt").read_text()
        self.assertIn("Invalid NAL unit size (632640939 > 5820).", err)                  # ffprobe's own lines,
        self.assertIn("Invalid NAL unit size (-1271155956 > 2135).", err)                # signed: 3,023,811,340 - 2**32
        self.assertEqual(3023811340 - (1 << 32), -1271155956)
        self.assertEqual([check._overrun(STCO, s, 4) is None for s in video.samples[2:]], [True] * 58)

    def test_nal_lengths_clean_and_hevc(self):
        for name in ("phone.mp4", "f1.mp4", "cenc.mp4", "hevc.mp4", "hevc-hev1.mp4", "hdr.mp4"):
            buf = data(name)
            with self.subTest(f=name):
                self.assertEqual([check.nal_lengths(buf, t) for t in tracks_of(buf)], [[]] * len(tracks_of(buf)))
        av1 = data("av1.mp4")
        self.assertEqual(check.nal_lengths(av1, tracks_of(av1)[0]), [])                   # OBUs: no length prefix

    def test_durations_agree(self):
        """phone and aac-only: every clock agrees (plan row 317); aac-only's edit plays 1,024 + 88,200 = 89,224 ticks,
        the whole media. phone's video edit plays to 1,024 + 30,720 = 31,744, past mdhd's 30,720: B-frames, so the
        last picture shown ends at 31,744, not where the last sample is decoded."""
        for name in ("phone.mp4", "aac-only.m4a", "f2.mp4", "subs.mp4", "vp9opus.mp4", "frag-cmaf.mp4"):
            with self.subTest(f=name):
                buf = data(name)
                self.assertEqual(check.durations(buf, boxes.walk(buf)), [])
        video = tracks_of(PHONE)[0]
        self.assertEqual((video.elst[0][1], video.duration), (1024, 30720))
        self.assertEqual(max(s.cts for s in video.samples) + 512, 31744)

    def test_durations_disagree(self):
        cases = [("moov/mvhd", 16, "warning: the movie: mvhd says 3.0000 s, its longest track (tkhd) 2.0000 s"),
                 ("moov/trak/tkhd", 20, "warning: the movie: mvhd says 2.0000 s, its longest track (tkhd) 3.0000 s"),
                 ("moov/trak/mdia/mdhd", 16, "warning: track 1: mdhd says 3.0000 s, its samples (stts) add up to "
                                             "2.0000 s"),
                 ("moov/trak/edts/elst", 8, "warning: track 1: tkhd says 2.0000 s, its edit list (elst) adds up to "
                                            "3.0000 s")]
        for path, at, first in cases:
            with self.subTest(box=path):
                value = 46080 if path.endswith("mdhd") else 144000                  # 3 s on each box's clock
                buf = patched(PHONE, path, at, ">I", value)
                found = check.durations(buf, boxes.walk(buf))
                self.assertTrue(found[0].startswith(first), found[0])
                self.assertEqual(set(levels(found)), {"warning"})
        buf = patched(PHONE, "moov/trak/edts/elst", 8, ">I", 144000)
        self.assertEqual(check.durations(buf, boxes.walk(buf))[1].splitlines()[0],
                         "warning: track 1: edit 1 plays the media to 3.0667 s, the media ends at 2.0667 s "
                         "(47104/15360 against 31744/15360)")

    def test_cut_short(self):
        """A recording cut inside mdat: no moov after the cut, so moov atom not found; a faststart file cut the same
        way still has its map, so ffmpeg plays up to the cut. A child too big for its parent: ffmpeg trims it."""
        moov_last = check.problems(PHONE[:50000])[0].splitlines()
        self.assertEqual(moov_last[0], "error: mdat at 40: size 108704 runs past the end (50000)")
        self.assertIn("moov atom not found", moov_last[1])
        fast = check.problems(data("phone-fast.mp4")[:50000])[0].splitlines()
        self.assertEqual(fast[0], "error: mdat at 3452: size 108704 runs past the end (50000)")
        self.assertIn("partial file", fast[1])
        udta = boxes.find(boxes.walk(PHONE), "moov/udta")
        buf = bytearray(PHONE)
        struct.pack_into(">I", buf, udta.start, udta.size + 5000)
        self.assertIn("cuts the box to fit its parent", check.problems(bytes(buf))[0])

    def test_ts_packets(self):
        """phone.ts: 679 packets of 188 bytes, each starting 0x47; phone.mp4's two streams (ffprobe: mpegts, 60 + 95
        packets). No MP4 starts with 0x47 every 188 bytes."""
        self.assertEqual((len(TS), check.ts_packets(TS)), (127652, 679))
        self.assertEqual({TS[i] for i in range(0, len(TS), 188)}, {0x47})
        self.assertEqual(check.ts_packets(PHONE), 0)
        probe = json.loads((CAPS / "phone.ts.probe.json").read_text())
        self.assertEqual(probe["format"]["format_name"], "mpegts")
        self.assertEqual([s["codec_name"] for s in probe["streams"]], ["h264", "aac"])
        self.assertEqual([sum(p["stream_index"] == i for p in probe["packets"]) for i in (0, 1)], [60, 95])
        with self.assertRaises(boxes.BoxError):
            boxes.walk(TS)                                     # 47 40 11 10 read as a box size: 1,195,381,008
        note = check.problems(TS)[0]
        self.assertTrue(note.startswith("note: not an MP4: an MPEG-TS stream, 679 packets of 188 bytes, the sync "
                                        "byte 0x47 at 0, 188, 376 ... 127464"), note)

    def test_fragments_note(self):
        found = check.problems(data("frag-cmaf.mp4"))
        self.assertEqual(found, ["note: 2 fragments (moof): their samples are listed in trun tables, which check "
                                 "does not read; only the moov and the mdat boxes were inspected"])

    def test_cmd_check(self):
        out = run_cli("check", str(TESTFILES / "broken-stco.mp4"))
        self.assertEqual(out, EXPECTED.read_text())
        self.assertEqual(out.splitlines()[-1], "2 errors, 1 warning")

    def test_cmd_check_exit_codes(self):
        """Exit 1 if any error (plan row 318), 0 for warnings and notes only."""
        for name, code, last in [("broken-stco.mp4", 1, "2 errors, 1 warning"),
                                 ("broken-nomoov.mp4", 1, "1 error, 0 warnings"),
                                 ("phone.mp4", 0, "0 errors, 0 warnings"),
                                 ("phone.ts", 0, "0 errors, 0 warnings")]:
            with self.subTest(f=name):
                got, out = run_cli_code("check", str(TESTFILES / name))
                self.assertEqual((got, out.splitlines()[-1]), (code, last))


if __name__ == "__main__":
    unittest.main()
