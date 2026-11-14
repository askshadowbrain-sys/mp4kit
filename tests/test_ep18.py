import json
import struct
import unittest
from pathlib import Path
from mp4kit import boxes, tables, timing
from tests.util import data, run_cli

F1, F2, PHONE, SUBS = data("f1.mp4"), data("f2.mp4"), data("phone.mp4"), data("subs.mp4")
OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep18.txt"


def traks(contents):
    """A file's trak boxes, in file order."""
    return boxes.find_all(boxes.walk(contents), "moov/trak")


def elst_of(contents, track=1):
    """read_elst of a track's elst box ([] when it has no edts)."""
    return tables.read_elst(contents, boxes.find(traks(contents)[track - 1].children, "edts/elst"))


def clocks(contents, track=1):
    """(media timescale, movie timescale): the track's mdhd clock and the movie's mvhd clock."""
    mdhd = boxes.find(traks(contents)[track - 1].children, "mdia/mdhd")
    mvhd = boxes.find(boxes.walk(contents), "moov/mvhd")
    return tables.read_mdhd(contents, mdhd)["timescale"], tables.read_mvhd(contents, mvhd)["timescale"]


def elst_box(version, rows):
    """A hand-packed elst box: version and flags, entry_count, then (segment_duration, media_time,
    media_rate_integer, media_rate_fraction) rows, 32-bit (version 0) or 64-bit (version 1)."""
    fmt = ">Qqhh" if version == 1 else ">Iihh"
    payload = struct.pack(">B3xI", version, len(rows)) + b"".join(struct.pack(fmt, *row) for row in rows)
    return struct.pack(">I4s", 8 + len(payload), b"elst") + payload


def times(contents, track=1):
    """A track's (dts, pts) lists in its own ticks, the edit list applied to both clocks."""
    samples = tables.sample_table(contents, traks(contents)[track - 1])
    edit = (elst_of(contents, track), *clocks(contents, track))
    return (timing.presentation_times([s.dts for s in samples], *edit),
            timing.presentation_times([s.cts for s in samples], *edit))


class Ep18(unittest.TestCase):
    def test_read_elst_f2(self):
        box = boxes.find(traks(F2)[0].children, "edts/elst")
        self.assertEqual((box.start, box.size, boxes.read_fullbox(F2, box)), (21042, 28, (0, 0)))  # version 0
        self.assertEqual(elst_of(F2), [(396, 33, 1, 0)])                                       # play 396, skip 33
        self.assertEqual(clocks(F2), (1000, 1000))                                             # one clock for both

    def test_read_elst_phone(self):
        self.assertEqual(elst_of(PHONE, 1), [(96000, 1024, 1, 0)])                            # video: B-frame delay
        self.assertEqual(elst_of(PHONE, 2), [(96000, 1024, 1, 0)])                            # audio: priming
        self.assertEqual(clocks(PHONE, 1), (15360, 48000))                                     # two clocks
        self.assertEqual(elst_of(F1), [])                                                      # no edts

    def test_read_elst_version1(self):
        rows = [(96000, 1024, 1, 0)]                          # no committed file has version 1 (all are 0)
        v1 = elst_box(1, rows)
        self.assertEqual(len(v1), 36)                                                          # 28 + 2 × 4 wider
        self.assertEqual(tables.read_elst(v1, boxes.read_header(v1, 0)), rows)
        v0 = v1[:8] + b"\x00" + v1[9:]                        # stamped version 0: rows read 12 bytes, not 20
        self.assertEqual(tables.read_elst(v0, boxes.read_header(v0, 0)), [(0, 96000, 0, 0)])  # the high halves

    def test_presentation_times_phone(self):
        captured = json.loads((CAPS / "phone.mp4.probe.json").read_text())
        packets = [p for p in captured["packets"] if p["stream_index"] == 0]
        dts, pts = times(PHONE, 1)
        self.assertEqual((dts[0], pts[0]), (-1024, 0))           # decoded at -1,024 ticks, shown at 0
        self.assertEqual(pts, [p["pts"] for p in packets])                                     # all 60
        self.assertEqual(dts, [p["dts"] for p in packets])
        samples = tables.sample_table(PHONE, traks(PHONE)[0])
        self.assertEqual((samples[0].dts, samples[0].cts), (0, 1024))                         # DTS 0, CTS 1024

    def test_pts_matches_ffprobe(self):
        for f in sorted(OUT.glob("*.mp4")) + sorted(OUT.glob("*.m4a")):
            if f.name in ("broken-nomoov.mp4", "frag-cmaf.mp4"):                              # no moov; samples in moof
                continue
            contents = f.read_bytes()
            captured = json.loads((CAPS / f"{f.name}.probe.json").read_text())
            for index in range(len(traks(contents))):
                packets = [p for p in captured["packets"] if p["stream_index"] == index]
                dts, pts = times(contents, index + 1)
                with self.subTest(f=f.name, track=index + 1):
                    self.assertEqual([p["pts"] for p in packets], pts[:len(packets)])        # exact: no shift
                    self.assertEqual([p["dts"] for p in packets], dts[:len(packets)])
                    self.assertEqual(len(packets), len(pts) - (f.name == "subs.mp4" and index == 2))

    def test_edit_length_in_movie_ticks_subs(self):
        self.assertEqual(elst_of(SUBS, 3), [(91200, 0, 1, 0)])
        self.assertEqual(clocks(SUBS, 3), (1000000, 48000))
        end = 91200 * 1000000 // 48000                           # play this long: 1.9 s in the track's ticks
        self.assertEqual(times(SUBS, 3)[1], [0, 900000, 1000000, end])  # the 4th starts where the edit ends
        self.assertNotEqual(91200, end)                          # read in the track's clock it would be 0.0912 s

    def test_empty_edit_in_memory(self):
        # no committed file has an empty edit; these are the elst bytes of phone.mp4 re-muxed with -itsoffset 0.25
        box = bytes.fromhex("00000028656c7374000000000000000200017700ffffffff00010000000bb80000000400" "00010000")
        rows = tables.read_elst(box, boxes.read_header(box, 0))
        self.assertEqual(rows, [(96000, -1, 1, 0), (768000, 1024, 1, 0)])                     # empty, then media
        self.assertEqual(timing.presentation_times([1024, 2560], rows, 15360, 384000), [3840, 5376])  # 0.25 s later
        self.assertEqual(timing.presentation_times([1024], [(96000, -1, 1, 0)], 15360, 384000), [4864])  # no media

    def test_media_rate_and_later_edits_in_memory(self):
        dwell = elst_box(0, [(48000, 1024, 0, 0)])           # media_rate 0: hold one picture (no committed file)
        self.assertEqual(tables.read_elst(dwell, boxes.read_header(dwell, 0)), [(48000, 1024, 0, 0)])
        two = [(48000, 1024, 1, 0), (48000, 0, 1, 0)]          # only the first real edit moves the track
        self.assertEqual(timing.presentation_times([1024, 2560], two, 15360, 48000), [0, 1536])

    def test_no_edit_list(self):
        self.assertEqual(timing.presentation_times([0, 33, 66], [], 1000, 1000), [0, 33, 66])      # PTS = CTS
        dts, pts = times(F1)
        self.assertEqual(dts, pts)                                                             # f1: no B-frames

    def test_elst_count_error(self):
        blob = bytearray(F2)
        self.assertEqual(blob[21054:21058].hex(), "00000001")                               # entry_count 1
        blob[21057] = 2
        with self.assertRaisesRegex(boxes.BoxError, "elst at 21042: entry_count 2 needs 40 bytes, box has 28"):
            elst_of(bytes(blob))

    def test_dump_elst(self):
        self.assertEqual(run_cli("dump", "testfiles/out/phone.mp4", "--find", "elst"),
                         "moov/trak/edts/elst 108968 28 version=0 entries=[(96000, 1024, 1, 0)]\n"
                         "moov/trak/edts/elst 110422 28 version=0 entries=[(96000, 1024, 1, 0)]\n")

    def test_cmd_samples_phone_pts(self):
        printed = run_cli("samples", "testfiles/out/phone.mp4", "--track", "1", "--pts")
        self.assertEqual(printed, EXPECTED.read_text())
        self.assertEqual(printed.splitlines()[:3], ["track 1 vide, timescale 15360, 60 samples",
                                                    "sample dts pts display key offset size",
                                                    "1 -1024 0 1 K 48 5824"])
        without = run_cli("samples", "testfiles/out/phone.mp4", "--track", "1")
        self.assertEqual(without, (EXPECTED.parent / "ep16.txt").read_text())                 # no --pts: ep16's
