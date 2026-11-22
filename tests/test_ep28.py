import struct
import unittest
from pathlib import Path
from mp4kit import boxes, mux, tables
from tests.util import data, run_cli, run_cli_code

OUT = Path(__file__).parents[1] / "testfiles" / "out"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep28.txt"
FILES = sorted(p.name for p in OUT.iterdir() if p.name != "broken-nomoov.mp4")
# The boxes the check finds different, and why: rotated's video tkhd has a turned matrix (write_tkhd writes the
# identity), phone-chapters' chapter track is in the movie but not enabled (tkhd flags 2, write_tkhd writes 3), and
# every libx264 avc1 carries the name "Lavc libx264" with pasp and btrt (write_avc1 writes none of them).
DIFFERENT = {"rotated.mp4": 2, "phone-chapters.mp4": 2, "phone.mp4": 1, "phone-fast.mp4": 1, "phone-large.mp4": 1,
             "broken-stco.mp4": 1, "subs.mp4": 1, "frag-cmaf.mp4": 1,
             "phone-sidx.mp4": 1, "phone-tagged.mp4": 1}   # phone-tagged: ep34


def raw(contents, box):
    return bytes(contents[box.start:box.end])


def phone():
    contents = data("phone.mp4")
    tree = boxes.walk(contents)
    return contents, tree, boxes.find_all(tree, "moov/trak")


def box_of(written):
    """The written bytes walked back into a Box (so the episode 10-13 readers can read them)."""
    return boxes.walk(written)[0]


class Ep28(unittest.TestCase):
    def test_write_ftyp(self):
        contents, tree, _ = phone()
        ftyp = boxes.find(tree, "ftyp")
        written = mux.write_ftyp(**boxes.read_ftyp(contents, ftyp))
        self.assertEqual(len(written), 32)                                               # plan §4: phone's 32 bytes
        self.assertEqual(written, raw(contents, ftyp))
        self.assertEqual(written[8:], b"isom" + struct.pack(">I", 512) + b"isomiso2avc1mp41")

    def test_write_mvhd(self):
        contents, tree, _ = phone()
        written = mux.write_mvhd(48000, 96000, 3)
        m = tables.read_mvhd(written, box_of(written))
        self.assertEqual((m["timescale"], m["duration"], m["rate"], m["volume"], m["next_track_ID"]),
                         (48000, 96000, 1.0, 1.0, 3))                                  # plan §4
        self.assertEqual(written[44:80], mux.MATRIX)                                    # the identity matrix
        self.assertEqual(written, raw(contents, boxes.find(tree, "moov/mvhd")))       # phone's 108 bytes

    def test_write_tkhd(self):
        contents, _, (video, sound) = phone()
        written = mux.write_tkhd(1, 96000, 640, 360, 0)
        t = tables.read_tkhd(written, box_of(written))
        self.assertEqual((t["flags"], t["track_ID"], t["duration"], t["width"], t["height"], t["rotation"]),
                         (3, 1, 96000, 640, 360, 0))                                   # plan §4
        self.assertEqual(written, raw(contents, boxes.find(video.children, "tkhd")))   # phone's 92 bytes
        self.assertEqual(mux.write_tkhd(2, 96000, 0, 0, 1, group=1), raw(contents, boxes.find(sound.children, "tkhd")))
        self.assertNotEqual(mux.write_tkhd(2, 96000, 0, 0, 1), raw(contents, boxes.find(sound.children, "tkhd")))

    def test_tkhd_matrix_not_kept(self):
        contents = data("rotated.mp4")
        tkhd = boxes.find(boxes.walk(contents), "moov/trak/tkhd")
        t = tables.read_tkhd(contents, tkhd)
        written, old = mux.write_tkhd(1, t["duration"], 640, 360, 0), raw(contents, tkhd)
        self.assertEqual(t["rotation"], 90)
        self.assertEqual([i for i in range(92) if written[i] != old[i]], [49, 52, 53, 61, 65])   # matrix a b c d
        self.assertEqual(written[:48] + written[84:], old[:48] + old[84:])

    def test_write_mdhd(self):
        contents, _, (video, sound) = phone()
        self.assertEqual(mux.write_mdhd(15360, 30720), raw(contents, boxes.find(video.children, "mdia/mdhd")))
        self.assertEqual(mux.write_mdhd(48000, 97024), raw(contents, boxes.find(sound.children, "mdia/mdhd")))
        self.assertEqual(mux.write_mdhd(15360, 30720)[28:30], bytes.fromhex("55c4"))   # "und"
        eng = mux.write_mdhd(1000, 1, "eng")
        self.assertEqual(eng[28:30], bytes.fromhex("15c7"))
        self.assertEqual(tables.read_mdhd(eng, box_of(eng))["language"], "eng")

    def test_write_hdlr(self):
        contents, _, (video, sound) = phone()
        written = mux.write_hdlr("vide", "VideoHandler")
        self.assertEqual(len(written), 45)                                               # plan §4
        self.assertEqual(written, raw(contents, boxes.find(video.children, "mdia/hdlr")))
        self.assertEqual(mux.write_hdlr("soun", "SoundHandler"), raw(contents, boxes.find(sound.children, "mdia/hdlr")))
        self.assertEqual(tables.read_hdlr(written, box_of(written)), {"handler_type": "vide", "name": "VideoHandler"})

    def test_write_media_header(self):
        contents, _, (video, sound) = phone()
        vmhd, smhd = mux.write_media_header("vide"), mux.write_media_header("soun")
        self.assertEqual((vmhd[4:8], len(vmhd), boxes.read_fullbox(vmhd, box_of(vmhd))), (b"vmhd", 20, (0, 1)))
        self.assertEqual((smhd[4:8], len(smhd), boxes.read_fullbox(smhd, box_of(smhd))), (b"smhd", 16, (0, 0)))
        self.assertEqual(vmhd, raw(contents, boxes.find(video.children, "mdia/minf/vmhd")))
        self.assertEqual(smhd, raw(contents, boxes.find(sound.children, "mdia/minf/smhd")))

    def test_write_dinf(self):
        contents, _, (video, _) = phone()
        written = mux.write_dinf()
        dinf = box_of(written)
        dref, url = dinf.children[0], dinf.children[0].children[0]
        self.assertEqual((dinf.size, dref.size, url.type, url.size), (36, 28, "url ", 12))   # plan §4: dref 28 B
        self.assertEqual(boxes.read_fullbox(written, url), (0, 1))                     # flags 1: in this file
        self.assertEqual(written, raw(contents, boxes.find(video.children, "mdia/minf/dinf")))

    def test_write_elst(self):
        contents, _, (video, sound) = phone()
        written = mux.write_elst(96000, 1024)
        self.assertEqual(len(written), 28)
        self.assertEqual(written, raw(contents, boxes.find(video.children, "edts/elst")))   # the B-frame delay
        self.assertEqual(written, raw(contents, boxes.find(sound.children, "edts/elst")))   # the priming
        self.assertEqual(tables.read_elst(written, box_of(written)), [(96000, 1024, 1, 0)])
        f2 = data("f2.mp4")
        self.assertEqual(mux.write_elst(396, 33), raw(f2, boxes.find(boxes.walk(f2), "moov/trak/edts/elst")))

    def test_write_avcc(self):
        contents, _, (video, _) = phone()
        avcc = boxes.find(video.children, "mdia/minf/stbl/stsd/avc1/avcC")
        a = tables.read_avcc(contents, avcc)
        written = mux.write_avcc(a["SPS"][0], a["PPS"][0])
        self.assertEqual(len(written), 8 + 6 + 2 + 26 + 1 + 2 + 6 + 4)                # plan §4: 55 bytes
        self.assertEqual(written, raw(contents, avcc))
        self.assertEqual(written[-4:], bytes.fromhex("fd f8 f8 00"))                    # 4:2:0, 8-bit, no SPS ext
        baseline = mux.write_avcc(bytes([0x67, 66, 0xC0, 30, 0xAB]), bytes([0x68, 0xCE]))
        self.assertEqual(baseline, boxes.box("avcC", bytes([1, 66, 0xC0, 30, 0xFF, 0xE1, 0, 5, 0x67, 66, 0xC0, 30,
                                                            0xAB, 1, 0, 2, 0x68, 0xCE])))   # no tail for 66

    def test_write_avc1(self):
        contents, _, (video, _) = phone()
        avc1 = boxes.find(video.children, "mdia/minf/stbl/stsd/avc1")
        avcc = boxes.find(avc1.children, "avcC")
        written = mux.write_avc1(640, 360, raw(contents, avcc))
        entry = box_of(written)
        self.assertEqual(tables.read_visual_entry(written, entry),
                         {"data_reference_index": 1, "width": 640, "height": 360, "compressorname": "", "depth": 24})
        self.assertEqual([b.type for b in entry.children], ["avcC"])
        self.assertEqual(entry.children[0].start - entry.payload, 78)                  # plan §4: 78 bytes of fields
        self.assertEqual((len(written), avc1.size), (141, 177))                         # no pasp (16), btrt (20)
        old = bytearray(raw(contents, avc1))
        self.assertEqual(old[50:63], b"\x0cLavc libx264")                               # the name ffmpeg writes
        old[50:82] = bytes(32)
        self.assertEqual(written, boxes.box("avc1", old[8:86], raw(contents, avcc)))   # the rest is phone's
        for name in ("f1.mp4", "f2.mp4"):                                                # minimux: no name, no extras
            f = data(name)
            box = boxes.find(boxes.walk(f), "moov/trak/mdia/minf/stbl/stsd/avc1")
            self.assertEqual(mux.write_avc1(640, 360, raw(f, boxes.find(box.children, "avcC"))), raw(f, box))

    def test_cmd_rewrite_check(self):
        out = run_cli("dump", str(OUT / "phone.mp4"), "--rewrite-check")
        self.assertEqual(out, EXPECTED.read_text())
        self.assertEqual(len(out.splitlines()), 22)
        self.assertIn("avc1 177 141 the same without its compressorname, pasp, btrt\n", out)
        self.assertIn("mp4a 110 - not written\n", out)
        self.assertTrue(out.endswith("boxes written 16, the file's byte for byte 15\n"))

    def test_cmd_rewrite_check_other_files(self):
        for name in FILES:
            with self.subTest(name):
                code, out = run_cli_code("dump", str(OUT / name), "--rewrite-check")
                self.assertEqual(code, 0)
                rows = [line.split(" ", 3) for line in out.splitlines()[2:-1] if not line.startswith("track ")]
                odd = [r for r in rows if r[3] not in ("yes", "not written", "none in the file")]
                self.assertEqual(len(odd), DIFFERENT.get(name, 0))
        rotated = run_cli("dump", str(OUT / "rotated.mp4"), "--rewrite-check")
        self.assertIn("tkhd 92 92 no (bytes 49 to 65 differ)\n", rotated)
        chapters = run_cli("dump", str(OUT / "phone-chapters.mp4"), "--rewrite-check")
        self.assertIn("tkhd 92 92 no (bytes 11 to 11 differ)\n", chapters)               # flags 2: not enabled
        self.assertIn("gmhd 76 - not written\n", chapters)
        self.assertIn("elst - - none in the file\n", run_cli("dump", str(OUT / "f1.mp4"), "--rewrite-check"))
        code, out = run_cli_code("dump", str(OUT / "broken-nomoov.mp4"), "--rewrite-check")
        self.assertEqual((code, out), (1, "error: no ftyp or no moov/mvhd: no headers to write back\n"))

    def test_dump_unchanged(self):
        self.assertTrue(run_cli("dump", str(OUT / "phone.mp4")).startswith("ftyp 0 32 major=isom"))

if __name__ == "__main__":
    unittest.main()
