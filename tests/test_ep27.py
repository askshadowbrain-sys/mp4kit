import struct
import tempfile
import unittest
from pathlib import Path
from mp4kit import boxes, mux, tables
from tests.util import data, run_cli, run_cli_code

OUT = Path(__file__).parents[1] / "testfiles" / "out"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep27.txt"
# The files whose moov comes after their mdat, and that faststart moves (cenc is refused: saio).
MOVED = ["aac-only.m4a", "av1.mp4", "broken-stco.mp4", "f1.mp4", "f2.mp4", "hdr.mp4", "hevc-hev1.mp4", "hevc.mp4",
         "phone-chapters.mp4", "phone-large.mp4", "phone.mp4", "rotated.mp4", "subs.mp4"]


def layout(contents):
    return [(b.type, b.start, b.size) for b in boxes.walk(contents)]


def offsets(contents):
    """Every track's chunk offsets (stco or co64), track by track."""
    tree = boxes.walk(contents)
    stbls = boxes.find_all(tree, "moov/trak/mdia/minf/stbl")
    return [tables.read_stco(contents, boxes.find(s.children, "stco") or boxes.find(s.children, "co64")) for s in stbls]


def parcels(contents):
    """Every sample's bytes, track by track, with its times and flags: what a player gets out of the file."""
    tracks = tables.read_tracks(contents, boxes.walk(contents))
    return [[(s.dts, s.cts, s.key, bytes(contents[s.offset:s.offset + s.size])) for s in t.samples] for t in tracks]


def stco_box(contents, track=0):
    return boxes.find(boxes.find_all(boxes.walk(contents), "moov/trak")[track].children, "mdia/minf/stbl/stco")


class Ep27(unittest.TestCase):
    def test_faststart_phone_is_phone_fast(self):
        self.assertEqual(mux.faststart(data("phone.mp4")), data("phone-fast.mp4"))           # plan §4: byte for byte

    def test_layout(self):
        fast = mux.faststart(data("phone.mp4"))
        self.assertEqual(layout(data("phone.mp4")), [("ftyp", 0, 32), ("free", 32, 8), ("mdat", 40, 108704),
                                                     ("moov", 108744, 3412)])
        self.assertEqual(layout(fast), [("ftyp", 0, 32), ("moov", 32, 3412), ("free", 3444, 8), ("mdat", 3452, 108704)])
        self.assertEqual(len(fast), len(data("phone.mp4")))                                  # nothing added or lost

    def test_shift_chunk_offsets_phone(self):
        contents = data("phone.mp4")
        moov = boxes.find(boxes.walk(contents), "moov")
        room = bytearray(contents[moov.start:moov.end])
        mux.shift_chunk_offsets(room, boxes.walk(room), 3412)                                # plan §4: + 3,412
        self.assertEqual(offsets(room), [[o + 3412 for o in t] for t in offsets(contents)])
        self.assertEqual(offsets(room), offsets(data("phone-fast.mp4")))
        self.assertEqual((offsets(contents)[0][0], offsets(room)[0][0]), (48, 3460))
        self.assertEqual((offsets(contents)[0][-1], offsets(room)[0][-1]), (106571, 109983))
        self.assertEqual(len(room), 3412)                                                    # the same size: patched

    def test_shift_is_the_moov_size(self):
        for name in MOVED:
            with self.subTest(name):
                contents = data(name)
                fast = mux.faststart(contents)
                moov = boxes.find(boxes.walk(contents), "moov")
                self.assertEqual(offsets(fast), [[o + moov.size for o in t] for t in offsets(contents)])
                self.assertEqual(boxes.find(boxes.walk(fast), "moov").start, boxes.walk(contents)[0].end)
                self.assertEqual(len(fast), len(contents))

    def test_every_moved_file_keeps_its_samples(self):
        for name in MOVED:
            with self.subTest(name):
                self.assertEqual(parcels(mux.faststart(data(name))), parcels(data(name)))

    def test_co64(self):
        contents = data("phone-large.mp4")                                                 # co64 and a trailing uuid
        fast = mux.faststart(contents)
        self.assertEqual([t for t, _, _ in layout(fast)], ["ftyp", "moov", "mdat", "uuid"])
        self.assertEqual(offsets(fast)[0][:1], [48 + 3884])
        self.assertEqual(layout(fast)[-1], layout(contents)[-1])                            # after the moov: stays put

    def test_co64_past_4_gib(self):
        contents = data("phone-large.mp4")
        moov = boxes.find(boxes.walk(contents), "moov")
        room = bytearray(contents[moov.start:moov.end])
        mux.shift_chunk_offsets(room, boxes.walk(room), 0xFFFFFFFF)
        self.assertEqual(offsets(room)[0][0], 48 + 0xFFFFFFFF)                             # 8 bytes hold it

    def test_stco_past_4_gib_refused(self):
        contents = bytearray(data("phone.mp4"))
        box = stco_box(contents)
        struct.pack_into(">I", contents, box.end - 4, 0xFFFFFFFF - 3411)                   # the last video chunk
        with self.assertRaisesRegex(boxes.BoxError, r"4294963884 \+ 3412 is past 4 GiB, it needs co64"):
            mux.faststart(contents)                                                          # one byte too far
        moov = boxes.find(boxes.walk(contents), "moov")
        room = bytearray(contents[moov.start:moov.end])
        mux.shift_chunk_offsets(room, boxes.walk(room), 3411)                              # 0xFFFFFFFF still fits
        self.assertEqual(offsets(room)[0][-1], 0xFFFFFFFF)

    def test_already_faststart(self):
        for name in ("phone-fast.mp4", "frag-cmaf.mp4"):
            with self.subTest(name):
                self.assertEqual(mux.faststart(data(name)), data(name))
        once = mux.faststart(data("f1.mp4"))
        self.assertEqual(mux.faststart(once), once)                                          # twice = once

    def test_two_mdats_before_the_moov(self):
        contents = data("f1.mp4")                                                          # ftyp 32, mdat, moov
        moov = boxes.find(boxes.walk(contents), "moov")
        room = bytearray(contents[moov.start:moov.end])
        mux.shift_chunk_offsets(room, boxes.walk(room), 8)
        two = contents[:32] + boxes.box("mdat") + contents[32:moov.start] + bytes(room)   # an empty mdat first
        fast = mux.faststart(two)
        self.assertEqual([t for t, _, _ in layout(fast)], ["ftyp", "moov", "mdat", "mdat"])
        self.assertEqual(parcels(fast), parcels(contents))

    def test_refused(self):
        f1 = data("f1.mp4")
        cases = {"no moov: nothing to move": data("broken-nomoov.mp4"),
                 "saio": data("cenc.mp4"),
                 "an mdat after the moov": f1 + boxes.box("mdat", b"late"),
                 "fragments": f1[:32] + boxes.box("mdat") + f1[32:] + boxes.box("moof")}
        for why, contents in cases.items():
            with self.subTest(why):
                with self.assertRaisesRegex(boxes.BoxError, why):
                    mux.faststart(contents)

    def test_cmd_faststart(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_cli("faststart", str(OUT / "phone.mp4"), "-o", f"{tmp}/fast.mp4")
            self.assertEqual(out, EXPECTED.read_text())
            self.assertEqual(Path(f"{tmp}/fast.mp4").read_bytes(), data("phone-fast.mp4"))

    def test_cmd_faststart_unchanged_and_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_cli("faststart", str(OUT / "phone-fast.mp4"), "-o", f"{tmp}/x.mp4")
            self.assertIn("no mdat before the moov: unchanged", out)
            self.assertIn("first 3460 -> 3460", out)
            code, out = run_cli_code("faststart", str(OUT / "cenc.mp4"), "-o", f"{tmp}/y.mp4")
            self.assertEqual((code, out), (1, "error: not moved: saio (cenc) offsets into the moov\n"))
            self.assertFalse(Path(f"{tmp}/y.mp4").exists())


if __name__ == "__main__":
    unittest.main()
