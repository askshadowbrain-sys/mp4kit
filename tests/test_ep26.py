import struct
import unittest
from pathlib import Path
from mp4kit import boxes, mux, tables
from tests.util import data, run_cli, run_cli_code

OUT = Path(__file__).parents[1] / "testfiles" / "out"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep26.txt"
# The sample tables table_box writes, each with its row format (stts, stss, stsc, stco/co64; ctts by its version).
FORMATS = {"stts": ">II", "stss": ">I", "stsc": ">III", "stco": ">I", "co64": ">Q"}
FILES = sorted(p.name for p in OUT.iterdir() if p.name not in ("broken-nomoov.mp4", "phone.ts"))   # phone.ts: MPEG-TS


def not_written(name, track):
    """What write_stbl does not write: the roll slip (sgpd, sbgp) in every ffmpeg AAC track with samples, sdtp
    (av1, hdr, hevc, hevc-hev1) and the cenc boxes (senc, saio, saiz)."""
    left = {"sgpd", "sbgp"} if track.handler == "soun" and track.samples else set()
    left |= {"sdtp"} if name in ("av1.mp4", "hdr.mp4", "hevc.mp4", "hevc-hev1.mp4") else set()
    return left | ({"senc", "saio", "saiz"} if name == "cenc.mp4" else set())


def parsed(name):
    contents = data(name)
    tree = boxes.walk(contents)
    return contents, tables.read_tracks(contents, tree), boxes.find_all(tree, "moov/trak")


def raw(contents, box):
    return contents[box.start:box.end]


def rewrite(contents, track, trak, counts=None):
    """write_stbl from the track's samples, the file's own stsd, its chunk offsets and (unless given) its counts."""
    stbl = boxes.find(trak.children, "mdia/minf/stbl")
    chunks = tables.chunk_list([track])
    return mux.write_stbl(track, raw(contents, boxes.find(stbl.children, "stsd")), [c[0] for c in chunks],
                          [c[3] for c in chunks] if counts is None else counts), stbl


def children(contents, stbl):
    return {b.type: raw(contents, b) for b in stbl.children}


class Ep26(unittest.TestCase):
    def test_box(self):
        self.assertEqual(boxes.box("free"), bytes.fromhex("00 00 00 08 66 72 65 65"))      # plan §4: the empty crate
        self.assertEqual(boxes.box("free", b"ab", b"c"), b"\x00\x00\x00\x0bfreeabc")       # the lid counts itself
        self.assertEqual(boxes.read_header(boxes.box("mdat", bytes(5)), 0).size, 13)

    def test_full_box_rebuilds_f1_stts(self):
        contents, _, (trak,) = parsed("f1.mp4")
        stts = boxes.find(trak.children, "mdia/minf/stbl/stts")
        written = boxes.full_box("stts", 0, 0, struct.pack(">III", 1, 12, 33))
        self.assertEqual(len(written), 24)                                               # plan §4: f1's 24-byte stts
        self.assertEqual(written, raw(contents, stts))
        self.assertEqual(boxes.read_fullbox(boxes.full_box("ctts", 1, 0x000203), boxes.read_header(
            boxes.full_box("ctts", 1, 0x000203), 0)), (1, 0x000203))

    def test_runs(self):
        self.assertEqual(mux.runs([33] * 12), [(12, 33)])                                  # plan §4
        self.assertEqual(mux.runs([]), [])
        self.assertEqual(mux.runs([1, 1, 2, 1]), [(2, 1), (1, 2), (1, 1)])  # a value seen again starts a new run

    def test_stsc_rules(self):
        self.assertEqual(mux.stsc_rules([4, 4, 2, 2]), [(1, 4, 1), (3, 2, 1)])             # plan §4, f1
        self.assertEqual(mux.stsc_rules([]), [])
        contents, (video, sound), traks = parsed("phone.mp4")
        for track, trak, rules in ((video, traks[0], 2), (sound, traks[1], 51)):
            counts = [c[3] for c in tables.chunk_list([track])]
            self.assertEqual(len(counts), 59)
            stsc = tables.read_stsc(contents, boxes.find(trak.children, "mdia/minf/stbl/stsc"))
            self.assertEqual(mux.stsc_rules(counts), stsc)
            self.assertEqual(len(stsc), rules)
            self.assertEqual(tables.chunk_sizes(mux.stsc_rules(counts), len(counts)), counts)   # and back

    def test_stsc_worked_example(self):
        """phone's sound: the first chunks' counts and the rules they compress to."""
        _, (_, sound), _ = parsed("phone.mp4")
        counts = [c[3] for c in tables.chunk_list([sound])]
        self.assertEqual(counts[:8], [1, 2, 2, 1, 2, 1, 2, 1])
        self.assertEqual(mux.stsc_rules(counts)[:5], [(1, 1, 1), (2, 2, 1), (4, 1, 1), (5, 2, 1), (6, 1, 1)])
        self.assertEqual(counts[-3:], [2, 2, 4])                                          # the last chunk holds 4
        self.assertEqual(mux.stsc_rules(counts)[-2:], [(57, 2, 1), (59, 4, 1)])
        self.assertEqual(sum(counts), 95)

    def test_table_box_from_rows_every_file(self):
        """plan §4: stts, ctts, stss, stsc and stco written from their parsed rows = the original boxes."""
        for name in FILES:
            contents = data(name)
            for stbl in boxes.find_all(boxes.walk(contents), "moov/trak/mdia/minf/stbl"):
                for box in stbl.children:
                    with self.subTest(name, box=box.type):
                        if box.type in FORMATS:
                            rows = tables.read_table(contents, box, FORMATS[box.type])
                            self.assertEqual(mux.table_box(box.type, FORMATS[box.type], rows), raw(contents, box))
                        elif box.type == "ctts":
                            version = boxes.read_fullbox(contents, box)[0]
                            rows = tables.read_ctts(contents, box)
                            self.assertEqual(mux.table_box("ctts", ">Ii", rows, version), raw(contents, box))

    def test_write_stsz(self):
        contents, _, traks = parsed("phone.mp4")
        for trak, size in zip(traks, (260, 400)):
            stsz = boxes.find(trak.children, "mdia/minf/stbl/stsz")
            written = mux.write_stsz(tables.read_stsz(contents, stsz))
            self.assertEqual(len(written), size)
            self.assertEqual(written, raw(contents, stsz))                                  # plan §4: phone's two stsz
        self.assertEqual(mux.write_stsz([17, 17]), bytes.fromhex("00000014 7374737a 00000000 00000011 00000002"))
        self.assertEqual(mux.write_stsz([]), bytes.fromhex("00000014 7374737a 00000000 00000000 00000000"))

    def test_write_stsz_one_size(self):
        """phone-chapters' chapter track: two 17-byte samples, so sample_size 17 and no list (20 bytes)."""
        contents, tracks, traks = parsed("phone-chapters.mp4")
        stsz = boxes.find(traks[2].children, "mdia/minf/stbl/stsz")
        self.assertEqual([s.size for s in tracks[2].samples], [17, 17])
        self.assertEqual(mux.write_stsz([17, 17]), raw(contents, stsz))

    def test_write_stbl_f1(self):
        """plan §4: sample_table of the written stbl = the input samples; f1's whole stbl, byte for byte."""
        contents, (track,), (trak,) = parsed("f1.mp4")
        written, stbl = rewrite(contents, track, trak)
        self.assertEqual(written, raw(contents, stbl))
        self.assertEqual(len(written), 356)
        fake_trak = boxes.Box("trak", 0, 0, 0, [boxes.Box("mdia", 0, 0, 0, [boxes.Box("minf", 0, 0, 0,
                                                                                         boxes.walk(written))])])
        self.assertEqual(tables.sample_table(written, fake_trak), track.samples)

    def test_write_stbl_phone(self):
        contents, (video, sound), traks = parsed("phone.mp4")
        written, stbl = rewrite(contents, video, traks[0])
        self.assertEqual(written, raw(contents, stbl))                                    # all 1,169 bytes
        written, stbl = rewrite(contents, sound, traks[1])
        old = children(contents, stbl)
        self.assertEqual(list(old), ["stsd", "stts", "stsc", "stsz", "stco", "sgpd", "sbgp"])
        self.assertEqual(written, boxes.box("stbl", *(old[k] for k in ("stsd", "stts", "stsc", "stsz", "stco"))))
        self.assertEqual((len(raw(contents, stbl)), len(written)), (1500, 1446))          # less sgpd 26 + sbgp 28

    def test_write_stbl_f2_order(self):
        """f2 (minimux) puts ctts before stss; write_stbl keeps ffmpeg's order: the same boxes, moved."""
        contents, (track,), (trak,) = parsed("f2.mp4")
        written, stbl = rewrite(contents, track, trak)
        old = children(contents, stbl)
        self.assertEqual(list(old), ["stsd", "stts", "ctts", "stss", "stsc", "stsz", "stco"])
        self.assertNotEqual(written, raw(contents, stbl))
        self.assertEqual(written, boxes.box("stbl", *(old[k] for k in ("stsd", "stts", "stss", "ctts", "stsc",
                                                                         "stsz", "stco"))))

    def test_write_stbl_every_file(self):
        """Every table write_stbl writes is the file's own, byte for byte, in every track of every file but
        phone-large (its co64 holds offsets that fit in 32 bits, so write_stbl writes stco); only the boxes of
        not_written are missing."""
        for name in FILES:
            contents, tracks, traks = parsed(name)
            for track, trak in zip(tracks, traks):
                with self.subTest(name, track=track.id):
                    written, stbl = rewrite(contents, track, trak)
                    old, new = children(contents, stbl), children(written, boxes.walk(written)[0])
                    if name == "phone-large.mp4":
                        self.assertEqual((set(old) - set(new), set(new) - set(old)),
                                         ({"co64"} | not_written(name, track), {"stco"}))
                        continue
                    self.assertEqual({k: v for k, v in old.items() if k in new}, new)
                    self.assertEqual(set(old) - set(new), not_written(name, track))

    def test_phone_large_co64(self):
        """phone-large's co64 (patch_stco.py --large) holds phone's own offsets, each in 8 bytes; written as stco
        they are phone's stco, byte for byte. write_stbl writes co64 only for an offset past 4 GiB."""
        contents, tracks, traks = parsed("phone-large.mp4")
        phone, _, phone_traks = parsed("phone.mp4")
        for track, trak, ptrak in zip(tracks, traks, phone_traks):
            co64 = boxes.find(trak.children, "mdia/minf/stbl/co64")
            offsets = tables.read_stco(contents, co64)
            self.assertLess(max(offsets), 2 ** 32)
            self.assertEqual(mux.table_box("co64", ">Q", [(o,) for o in offsets]), raw(contents, co64))
            self.assertEqual(len(raw(contents, co64)), 488)
            stco = boxes.find(ptrak.children, "mdia/minf/stbl/stco")
            self.assertEqual(offsets, tables.read_stco(phone, stco))                          # mdat did not move
            self.assertEqual(mux.table_box("stco", ">I", [(o,) for o in offsets]), raw(phone, stco))
        self.assertEqual(len(mux.table_box("co64", ">Q", [(2 ** 32,)])), 24)
        big = tables.Track(1, "vide", 1, {}, [], [])
        self.assertIn(b"co64", mux.write_stbl(big, b"", [2 ** 32], [0]))

    def test_stsc_from_interleave(self):
        """ep24's zipper plans phone's chunks; its sample counts, track by track, are stsc_rules' input, and
        write_stbl from them is phone's stbl again (episode 29 builds on this)."""
        contents, tracks, traks = parsed("phone.mp4")
        plan = mux.interleave(tracks)
        for n, (track, trak) in enumerate(zip(tracks, traks), 1):
            counts = [count for t, _, count in plan if t == n]
            written, stbl = rewrite(contents, track, trak, counts)
            old = children(contents, stbl)
            self.assertEqual(written, boxes.box("stbl", *(v for k, v in old.items() if k not in ("sgpd", "sbgp"))))

    def test_cmd_rewrite_check(self):
        out = run_cli("samples", str(OUT / "phone.mp4"), "--rewrite-check")
        self.assertEqual(out, EXPECTED.read_text())
        self.assertEqual(len(out.splitlines()), 21)
        self.assertIn("stbl 1500 1446 the same boxes without sgpd sbgp\n", out)
        self.assertTrue(out.endswith("every table written is the file's, byte for byte: yes\n"))

    def test_cmd_rewrite_check_other_files(self):
        for name in FILES:
            with self.subTest(name):
                code, out = run_cli_code("samples", str(OUT / name), "--rewrite-check")
                self.assertEqual(code, 0)
                verdict = "no" if name == "phone-large.mp4" else "yes"
                self.assertTrue(out.endswith(f"byte for byte: {verdict}\n"))
        f2 = run_cli("samples", str(OUT / "f2.mp4"), "--rewrite-check")
        self.assertIn("stbl 444 444 the same boxes in another order\n", f2)
        code, out = run_cli_code("samples", str(OUT / "broken-nomoov.mp4"), "--rewrite-check")
        self.assertEqual((code, out), (1, "error: no tracks: the file has no moov/trak to write back\n"))

    def test_samples_unchanged(self):
        self.assertEqual(run_cli("samples", str(OUT / "phone.mp4"), "--track", "1"),
                         (Path(__file__).parents[1] / "expected" / "ep16.txt").read_text())


if __name__ == "__main__":
    unittest.main()
