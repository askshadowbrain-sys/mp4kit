import json
import struct
import unittest
from pathlib import Path
from mp4kit import boxes, nal, tables
from tests.util import TESTFILES, data, run_cli, run_cli_code

CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep35.txt"
STBL = "mdia/minf/stbl"
# testfiles/MANIFEST.md: the published TEST key and its name (make.sh -encryption_key / -encryption_kid)
KEY, KID = bytes.fromhex("00112233445566778899aabbccddeeff"), bytes.fromhex("0123456789abcdef0123456789abcdef")
CENC, PHONE = data("cenc.mp4"), data("phone.mp4")
TREE = boxes.walk(CENC)
TRAKS = boxes.find_all(TREE, "moov/trak")


def locks():
    """Each track of cenc.mp4 with its lock (sinf) and its lock log (senc entries)."""
    tracks = tables.read_tracks(CENC, TREE)
    return [(t, t.entry["sinf"], tables.read_senc(CENC, boxes.find(trak.children, STBL + "/senc"),
                                                  t.entry["sinf"]["default_Per_Sample_IV_Size"]))
            for t, trak in zip(tracks, TRAKS)]


class Ep35(unittest.TestCase):
    def test_read_sinf(self):
        video = boxes.find(TRAKS[0].children, STBL + "/stsd/encv/sinf")
        audio = boxes.find(TRAKS[1].children, STBL + "/stsd/enca/sinf")
        self.assertEqual([(b.start, b.size) for b in (video, audio)], [(109326, 80), (111868, 80)])
        common = {"scheme_type": "cenc", "scheme_version": 0x00010000, "default_isProtected": 1,
                  "default_Per_Sample_IV_Size": 8, "default_KID": KID}                   # plan rows 308-309
        self.assertEqual(tables.read_sinf(CENC, video), {"original_format": "avc1", **common})
        self.assertEqual(tables.read_sinf(CENC, audio), {"original_format": "mp4a", **common})
        self.assertEqual([c.type for c in video.children], ["frma", "schm", "schi"])       # 12 + 20 + 40 = 80 - 8

    def test_frma_is_what_ffprobe_names(self):
        streams = json.loads((CAPS / "cenc.mp4.probe.json").read_text())["streams"]
        self.assertEqual([t.entry["sinf"]["original_format"] for t, _, _ in locks()],
                         [s["codec_tag_string"] for s in streams])                       # avc1, mp4a: not encv, enca
        self.assertEqual([t.entry["type"] for t, _, _ in locks()], ["encv", "enca"])

    def test_read_tenc(self):
        tenc = boxes.find(TRAKS[0].children, STBL + "/stsd/encv/sinf/schi/tenc")
        self.assertEqual((tenc.start, tenc.size), (109374, 32))                          # 8 + 4 + 4 + 16
        self.assertEqual(tables.read_tenc(CENC, tenc), {"version": 0, "default_isProtected": 1,
                                                        "default_Per_Sample_IV_Size": 8, "default_KID": KID})

    def test_tenc_pattern_and_constant_iv(self):
        # a cbcs-style key tag: version 1, crypt 1 / skip 9, protected, IV size 0, then a 16-byte constant IV
        raw = boxes.full_box("tenc", 1, 0, bytes([0, 0x19, 1, 0]), KID, bytes([16]), bytes(range(16)))
        self.assertEqual(tables.read_tenc(raw, boxes.read_header(raw, 0)),
                         {"version": 1, "default_isProtected": 1, "default_Per_Sample_IV_Size": 0, "default_KID": KID,
                          "default_crypt_byte_block": 1, "default_skip_byte_block": 9,
                          "default_constant_IV": bytes(range(16))})
        short = boxes.full_box("tenc", 0, 0, bytes(8))
        with self.assertRaisesRegex(boxes.BoxError, "tenc at 0: needs 32 bytes, box has 20"):
            tables.read_tenc(short, boxes.read_header(short, 0))

    def test_sinf_without_frma(self):
        raw = boxes.box("sinf", boxes.box("schm", bytes(12)))
        sinf = boxes.walk(raw)[0]
        with self.assertRaisesRegex(boxes.BoxError, "sinf at 0: no frma"):
            tables.read_sinf(raw, sinf)

    def test_read_senc_video(self):
        (_, _, log), _ = locks()
        senc = boxes.find(TRAKS[0].children, STBL + "/senc")
        self.assertEqual((senc.start, senc.size, boxes.read_fullbox(CENC, senc)), (110394, 982, (0, 2)))
        self.assertEqual(len(log), 60)
        self.assertEqual(log[0], {"IV": bytes(8), "subsamples": [(5, 683), (5, 5131)]})   # plan row 310
        self.assertEqual(log[1], {"IV": (1).to_bytes(8, "big"), "subsamples": [(5, 2134)]})
        self.assertEqual([e["IV"] for e in log], [n.to_bytes(8, "big") for n in range(60)])   # +bitexact: 0, 1, 2 ...
        self.assertEqual(16 + sum(8 + 2 + 6 * len(e["subsamples"]) for e in log), senc.size)

    def test_read_senc_audio(self):
        _, (_, _, log) = locks()
        senc = boxes.find(TRAKS[1].children, STBL + "/senc")
        self.assertEqual((senc.start, senc.size, boxes.read_fullbox(CENC, senc)), (113280, 776, (0, 0)))
        self.assertEqual(log, [{"IV": n.to_bytes(8, "big"), "subsamples": []} for n in range(95)])
        self.assertEqual(senc.size, 16 + 95 * 8)                                         # IVs only

    def test_saiz_saio_index_the_log(self):
        for trak, (_, _, log) in zip(TRAKS, locks()):
            senc, saiz, saio = (boxes.find(trak.children, f"{STBL}/{kind}") for kind in ("senc", "saiz", "saio"))
            sizes, offsets = tables.read_saiz(CENC, saiz), tables.read_saio(CENC, saio)["offsets"]
            entry_sizes = [8 + (2 + 6 * len(e["subsamples"]) if e["subsamples"] else 0) for e in log]
            with self.subTest(trak.start):
                self.assertEqual(offsets, [senc.payload + 8])                               # senc's first entry
                self.assertEqual(sizes["sample_count"], len(log))
                self.assertEqual(sizes["sample_info_size"] or [sizes["default_sample_info_size"]] * len(log),
                                 entry_sizes)
        self.assertEqual(tables.read_saio(CENC, boxes.find(TRAKS[0].children, STBL + "/saio"))["offsets"], [110410])

    def test_no_pssh_and_no_key(self):
        self.assertIsNone(_anywhere(TREE, "pssh"))                                       # ffmpeg writes none
        self.assertEqual(CENC.count(KID), 2)                                              # the two key tags
        self.assertEqual(CENC.count(KEY), 0)                                              # the House never holds it

    def test_read_pssh(self):
        # W3C eme-initdata-cenc 4.2: the Common SystemID, version 1, two KIDs, no data: 68 bytes
        system = bytes.fromhex("1077efecc0b24d02ace33c1e52e2fb4b")
        raw = boxes.full_box("pssh", 1, 0, system, struct.pack(">I", 2), KID, bytes(16), struct.pack(">I", 0))
        self.assertEqual(len(raw), 68)
        self.assertEqual(tables.read_pssh(raw, boxes.read_header(raw, 0)),
                         {"version": 1, "SystemID": system, "KIDs": [KID, bytes(16)], "data": b""})
        raw = boxes.full_box("pssh", 0, 0, system, struct.pack(">I", 3), b"abc")
        self.assertEqual(tables.read_pssh(raw, boxes.read_header(raw, 0))["data"], b"abc")

    def test_saiz_saio_with_aux_type_and_64_bit(self):
        raw = boxes.full_box("saiz", 0, 1, b"cenc", bytes(4), bytes([0]), struct.pack(">I", 2), bytes([16, 22]))
        self.assertEqual(tables.read_saiz(raw, boxes.read_header(raw, 0)),
                         {"default_sample_info_size": 0, "sample_count": 2, "sample_info_size": [16, 22]})
        raw = boxes.full_box("saio", 1, 0, struct.pack(">IQ", 1, 2 ** 32 + 5))
        self.assertEqual(tables.read_saio(raw, boxes.read_header(raw, 0)), {"offsets": [2 ** 32 + 5]})

    def test_clear_ranges_sample_1(self):
        (video, _, log), (audio, _, alog) = locks()
        ranges = tables.clear_ranges(video.samples[0], log[0])
        self.assertEqual(ranges, [(0, 5, False), (5, 683, True), (688, 5, False), (693, 5131, True)])
        self.assertEqual(sum(size for _, size, _ in ranges), 5824)                        # plan row 311
        self.assertEqual(tables.clear_ranges(audio.samples[0], alog[0]), [(0, 238, True)])

    def test_clear_ranges_must_cover_the_sample(self):
        (video, _, log), _ = locks()
        with self.assertRaisesRegex(boxes.BoxError, "sample 1: its subsamples cover 2139 bytes of 5824"):
            tables.clear_ranges(video.samples[0], log[1])

    def test_clear_runs_are_length_and_header(self):
        # each subsample is one NAL: its 4-byte length and 1-byte header clear, the rest of the NAL protected
        (video, _, log), _ = locks()
        for s, entry in zip(video.samples, log):
            units = [unit for _, unit in nal.iter_length_prefixed(PHONE, s.offset, s.offset + s.size, 4)]
            with self.subTest(sample=s.number):
                self.assertEqual(entry["subsamples"], [(4 + 1, len(unit) - 1) for unit in units])
        self.assertEqual(sum(len(e["subsamples"]) for e in log), 61)                      # sample 1: SEI + IDR

    def test_same_bytes_where_clear(self):
        clear = locked = differ = 0
        for t, _, log in locks():
            for s, entry in zip(t.samples, log):
                for at, size, protected in tables.clear_ranges(s, entry):
                    a, b = CENC[s.offset + at:s.offset + at + size], PHONE[s.offset + at:s.offset + at + size]
                    if protected:
                        locked, differ = locked + size, differ + sum(x != y for x, y in zip(a, b))
                        self.assertNotEqual(a, b)
                    else:
                        clear += size
                        self.assertEqual(a, b)
        self.assertEqual((clear, locked, differ), (305, 84044 + 24347, 83728 + 24259))
        self.assertEqual(CENC[:48], PHONE[:48])                     # ftyp, free and mdat's header: the same
        self.assertEqual(len(CENC) - len(PHONE), 2052)              # moov 5,464 against 3,412: the locks and logs

    def test_cmd_cenc_check(self):
        out = run_cli("cenc-check", str(TESTFILES / "cenc.mp4"), str(TESTFILES / "phone.mp4"))
        self.assertEqual(out, EXPECTED.read_text())

    def test_cenc_check_refusals(self):
        code, out = run_cli_code("cenc-check", str(TESTFILES / "cenc.mp4"), str(TESTFILES / "cenc.mp4"))
        self.assertEqual((code, out.splitlines()[-1]), (1, "clear bytes the same, protected runs all different: no"))
        code, out = run_cli_code("cenc-check", str(TESTFILES / "phone.mp4"), str(TESTFILES / "phone.mp4"))
        self.assertEqual((code, out), (0, "track 1 avc1: not locked (no sinf or no senc)\n"
                                          "track 2 mp4a: not locked (no sinf or no senc)\n"
                                          "clear bytes the same, protected runs all different: yes\n"))
        code, out = run_cli_code("cenc-check", str(TESTFILES / "cenc.mp4"), str(TESTFILES / "f1.mp4"))
        self.assertEqual((code, out.split(":")[0]), (1, "error"))

    def test_dump_shows_the_locks(self):
        out = run_cli("dump", str(TESTFILES / "cenc.mp4"), "--find", "tenc")
        line = "version=0 default_isProtected=1 default_Per_Sample_IV_Size=8 default_KID=" + KID.hex()
        self.assertEqual(out, f"moov/trak/mdia/minf/stbl/stsd/encv/sinf/schi/tenc 109374 32 {line}\n"
                              f"moov/trak/mdia/minf/stbl/stsd/enca/sinf/schi/tenc 111916 32 {line}\n")
        out = run_cli("dump", str(TESTFILES / "cenc.mp4"), "--find", "senc")
        self.assertEqual(out, "moov/trak/mdia/minf/stbl/senc 110394 982 flags=2 sample_count=60\n"
                              "moov/trak/mdia/minf/stbl/senc 113280 776 flags=0 sample_count=95\n")
        encv = boxes.decode(CENC, boxes.find(TRAKS[0].children, STBL + "/stsd/encv"))
        self.assertEqual((encv["width"], encv["height"]), (640, 360))                    # still a picture's sheet


def _anywhere(tree, kind):
    for b in tree:
        if b.type == kind:
            return b
        found = _anywhere(b.children, kind)
        if found:
            return found
    return None


if __name__ == "__main__":
    unittest.main()
