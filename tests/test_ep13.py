import json
import tempfile
import unittest
from pathlib import Path
from mp4kit import boxes, nal, tables
from tests.util import data, run_cli, run_cli_code

PHONE, F1 = data("phone.mp4"), data("f1.mp4")
OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep13.txt"
STSD = "moov/trak/mdia/minf/stbl/stsd"
PHONE_SPS = bytes.fromhex("6764001eacd940a02ff970110000030001000003003c0f162d96")
F1_SPS = bytes.fromhex("6764001eacb201405ff2c2000003000200000300781e2c5c90")


def probe(name):
    """ffprobe's streams for a committed file (testfiles/captures/<name>.probe.json)."""
    return json.loads((CAPS / f"{name}.probe.json").read_text())["streams"]


class Ep13(unittest.TestCase):
    def test_trains_make_many_stops(self):
        tree = boxes.walk(PHONE)
        path = ""
        found = []
        for kind in ("moov", "trak", "mdia", "minf", "stbl", "stsd"):
            path = path + kind
            box = boxes.find(tree, path)
            found.append((box.type, box.start, box.size))
            path = path + "/"
        self.assertEqual(found, [("moov", 108744, 3412), ("trak", 108860, 1454), ("mdia", 108996, 1318),
                                 ("minf", 109081, 1233), ("stbl", 109145, 1169), ("stsd", 109153, 193)])

    def test_read_stsd_phone(self):
        video, audio = boxes.find_all(boxes.walk(PHONE), STSD)
        self.assertEqual(PHONE[109153:109169].hex(), "000000c1737473640000000000000001")   # size, stsd, v/f, 1
        self.assertEqual([(e.type, e.start, e.size) for e in tables.read_stsd(PHONE, video)], [("avc1", 109169, 177)])
        self.assertEqual([(e.type, e.start, e.size) for e in tables.read_stsd(PHONE, audio)], [("mp4a", 110619, 110)])

    def test_every_stsd_holds_one_entry(self):
        kinds = set()
        for f in sorted(OUT.glob("*.mp4")) + sorted(OUT.glob("*.m4a")):
            if f.name == "broken-nomoov.mp4":
                continue
            contents = f.read_bytes()
            for stsd in boxes.find_all(boxes.walk(contents), STSD):
                with self.subTest(f=f.name, at=stsd.start):
                    self.assertEqual(boxes.u32(contents, stsd.payload + 4), 1)
                    entries = tables.read_stsd(contents, stsd)
                    self.assertEqual(len(entries), 1)
                    kinds.add(entries[0].type)
        self.assertEqual(kinds, {"avc1", "encv", "hvc1", "hev1", "av01", "mp4a", "enca", "tx3g"})

    def test_read_stsd_count_mismatch(self):
        blob = bytearray(PHONE[109153:109153 + 193])
        blob[15] = 2                                          # entry_count 2, one entry
        with self.assertRaisesRegex(boxes.BoxError, "stsd at 0: entry_count 2, but it holds 1 entries"):
            tables.read_stsd(bytes(blob), boxes.read_header(bytes(blob), 0))

    def test_read_visual_entry_phone(self):
        avc1 = boxes.find(boxes.walk(PHONE), STSD + "/avc1")
        self.assertEqual(tables.read_visual_entry(PHONE, avc1),
                         {"data_reference_index": 1, "width": 640, "height": 360, "compressorname": "Lavc libx264",
                          "depth": 24})
        at = avc1.payload
        self.assertEqual(PHONE[at:at + 6], bytes(6))                                     # reserved
        self.assertEqual(PHONE[at + 28:at + 36].hex(), "0048000000480000")              # 72 dpi, 16.16
        self.assertEqual(boxes.u16(PHONE, at + 40), 1)                                   # frame_count
        self.assertEqual(PHONE[at + 42:at + 55], b"\x0cLavc libx264")                    # length 12, the name
        self.assertEqual(PHONE[at + 55:at + 74], bytes(19))                              # padding to 32 bytes
        self.assertEqual(PHONE[at + 74:at + 78].hex(), "0018ffff")                       # depth, pre_defined -1
        self.assertEqual([(c.type, c.start) for c in avc1.children],
                         [("avcC", at + 78), ("pasp", 109310), ("btrt", 109326)])

    def test_read_visual_entry_f1(self):
        avc1 = boxes.find(boxes.walk(F1), STSD + "/avc1")
        self.assertEqual((avc1.start, avc1.size), (22446, 140))
        self.assertEqual(tables.read_visual_entry(F1, avc1),
                         {"data_reference_index": 1, "width": 640, "height": 360, "compressorname": "",
                          "depth": 24})
        self.assertEqual([c.type for c in avc1.children], ["avcC"])                     # no pasp, no btrt

    def test_visual_entry_matches_ffprobe(self):
        for name in ("phone.mp4", "f1.mp4", "av1.mp4", "hevc.mp4", "hevc-hev1.mp4", "hdr.mp4", "cenc.mp4"):
            contents = data(name)
            entry = tables.read_stsd(contents, boxes.find(boxes.walk(contents), STSD))[0]
            fields = tables.read_visual_entry(contents, entry)
            stream = probe(name)[0]
            with self.subTest(name=name):
                self.assertEqual((fields["width"], fields["height"]), (stream["width"], stream["height"]))

    def test_read_visual_entry_short_box(self):
        blob = (80).to_bytes(4, "big") + PHONE[109169 + 4:109169 + 80]
        with self.assertRaisesRegex(boxes.BoxError, "avc1 at 0: a visual sample entry needs 86 bytes, box has 80"):
            tables.read_visual_entry(blob, boxes.read_header(blob, 0))

    def test_read_avcc_phone(self):
        avcc = boxes.find(boxes.walk(PHONE), STSD + "/avc1/avcC")
        self.assertEqual((avcc.start, avcc.size), (109255, 55))
        self.assertEqual(PHONE[109263:109269].hex(), "0164001effe1")     # version, 100, 0x00, 30, 0xFF, 0xE1
        self.assertEqual(tables.read_avcc(PHONE, avcc),
                         {"configurationVersion": 1, "AVCProfileIndication": 100, "profile_compatibility": 0,
                          "AVCLevelIndication": 30, "lengthSizeMinusOne": 3, "SPS": [PHONE_SPS],
                          "PPS": [bytes.fromhex("68ebe112c8b0")], "chroma_format": 1, "bit_depth_luma_minus8": 0,
                          "bit_depth_chroma_minus8": 0, "codec": "avc1.64001E"})
        self.assertEqual((len(PHONE_SPS), boxes.u16(PHONE, 109269)), (26, 26))
        self.assertEqual(PHONE[109306:109310].hex(), "fdf8f800")          # the High tail: 1, 0, 0, no SPS ext
        self.assertEqual(6 + 2 + 26 + 1 + 2 + 6 + 4, avcc.size - 8)          # every byte accounted for

    def test_read_avcc_f1(self):
        avcc = boxes.find(boxes.walk(F1), STSD + "/avc1/avcC")
        fields = tables.read_avcc(F1, avcc)
        self.assertEqual((avcc.start, avcc.size), (22532, 54))
        self.assertEqual((fields["SPS"], len(fields["SPS"][0])), ([F1_SPS], 25))
        self.assertEqual(fields["PPS"], [bytes.fromhex("68ebc084b22c")])
        self.assertEqual((fields["lengthSizeMinusOne"] + 1, fields["chroma_format"], fields["codec"]),
                         (4, 1, "avc1.64001E"))

    def test_read_avcc_same_as_the_stopgap(self):
        for contents in (PHONE, F1):
            fields = tables.read_avcc(contents, boxes.find(boxes.walk(contents), STSD + "/avc1/avcC"))
            self.assertEqual((fields["SPS"][0], fields["PPS"][0]), nal._avcc_params_stopgap(contents))

    def test_avcc_matches_ffprobe(self):
        for name in ("phone.mp4", "f1.mp4", "f2.mp4", "subs.mp4", "rotated.mp4", "phone-fast.mp4", "cenc.mp4"):
            contents = data(name)
            avcc = boxes.find_all(boxes.walk(contents), "moov/trak/mdia/minf/stbl/stsd")[0].children[0].children[0]
            fields = tables.read_avcc(contents, avcc)
            stream = probe(name)[0]
            with self.subTest(name=name):
                self.assertEqual(avcc.type, "avcC")
                self.assertEqual((fields["AVCProfileIndication"], stream["profile"]), (100, "High"))
                self.assertEqual(fields["AVCLevelIndication"], stream["level"])
                self.assertEqual(str(fields["lengthSizeMinusOne"] + 1), stream["nal_length_size"])   # JSON: "4"
                self.assertEqual(avcc.size - 8, stream["extradata_size"])
                self.assertEqual(fields["codec"].lower(), stream["mime_codec_string"])     # ffprobe: avc1.64001e

    def test_read_avcc_overrun(self):
        blob = bytearray(PHONE[109255:109255 + 55])
        blob[14:16] = (60).to_bytes(2, "big")         # an SPS of 60 bytes in a 55-byte box: to 76, a PPS count 0
        message = "avcC at 0: the parameter sets run to 77, past the box's end \\(55\\)"
        with self.assertRaisesRegex(boxes.BoxError, message):
            tables.read_avcc(bytes(blob) + bytes(80), boxes.read_header(bytes(blob), 0))

    def test_read_avcc_baseline_has_no_tail(self):
        blob = bytes.fromhex("0000001a61766343" "0142c01effe1000567") + bytes(4) + bytes.fromhex("010002" "68ce")
        fields = tables.read_avcc(blob, boxes.read_header(blob, 0))
        self.assertEqual((fields["AVCProfileIndication"], fields["codec"]), (66, "avc1.42C01E"))
        self.assertNotIn("chroma_format", fields)

    def test_codec_string(self):
        self.assertEqual(tables.codec_string({"AVCProfileIndication": 100, "profile_compatibility": 0x00,
                                              "AVCLevelIndication": 30}), "avc1.64001E")
        self.assertEqual(f"{100:02X} {0:02X} {30:02X}", "64 00 1E")            # 0x1E = 30: level 3.0

    def test_registry(self):
        self.assertIs(boxes.DECODERS["avc1"], tables.read_visual_entry)
        self.assertIs(boxes.DECODERS["avcC"], tables.read_avcc)

    def test_cmd_dump_find_avcc(self):
        printed = run_cli("dump", "testfiles/out/phone.mp4", "--find", "avcC")
        self.assertEqual(printed, EXPECTED.read_text())
        self.assertTrue(printed.rstrip().endswith("codec=avc1.64001E"))

    def test_cmd_dump_find_avcc_none(self):
        for name in ("hevc.mp4", "hevc-hev1.mp4", "hdr.mp4", "av1.mp4", "aac-only.m4a"):
            with self.subTest(name=name):
                self.assertEqual(run_cli_code("dump", f"testfiles/out/{name}", "--find", "avcC"), (0, "no avcC box\n"))

    def test_cmd_sps_reads_avcc(self):
        self.assertEqual(run_cli("sps", "testfiles/out/f1.mp4"), "profile 100 level 30 640x360 CABAC\n")
        self.assertEqual(run_cli("sps", "testfiles/out/phone.mp4"), "profile 100 level 30 640x360 CABAC\n")
        with tempfile.TemporaryDirectory() as folder:      # the bytes "avcC" in mdat no longer fool it
            path = Path(folder) / "avcc-in-mdat.mp4"
            blob = bytearray(F1)
            blob[44:48] = b"avcC"                            # inside f1's first NAL unit (mdat payload 40-22057)
            path.write_bytes(bytes(blob))
            self.assertEqual(run_cli("sps", str(path)), "profile 100 level 30 640x360 CABAC\n")
        with self.assertRaises(IndexError):                  # the ep04 byte search reads slice bytes as an avcC
            nal._avcc_params_stopgap(bytes(blob))

    def test_cmd_sps_no_avcc(self):
        self.assertEqual(run_cli_code("sps", "testfiles/out/hevc.mp4"),
                         (1, "error: no moov/trak/mdia/minf/stbl/stsd/avc1/avcC box\n"))
