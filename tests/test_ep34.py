import json
import struct
import unittest
from pathlib import Path
from mp4kit import boxes, tables
from tests.util import TESTFILES, data, run_cli

CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep34.txt"
HVC1 = "moov/trak/mdia/minf/stbl/stsd/hvc1"
# ffprobe's names for the H.273 code points in these files (libavutil/pixfmt.h: AVCOL_PRI_BT2020 9,
# AVCOL_TRC_SMPTE2084 16, AVCOL_SPC_BT2020_NCL 9); full_range_flag 0 is "tv" (limited range), 1 "pc"
PRIMARIES, TRANSFER, MATRIX, RANGE = {9: "bt2020"}, {16: "smpte2084"}, {9: "bt2020nc"}, {0: "tv", 1: "pc"}


def chart(name, kind):
    """The decoded paint-chart box `kind` of a file's (first) hvc1 sample entry, and the box."""
    contents = data(name)
    box = boxes.find(boxes.walk(contents), f"{HVC1}/{kind}")
    return boxes.decode(contents, box), box


def probe(name):
    return json.loads((CAPS / f"{name}.probe.json").read_text())


def side_data(name, kind):
    return next(d for d in probe(name)["streams"][0]["side_data_list"] if d["side_data_type"] == kind)


def ratio(text):
    top, bottom = text.split("/")
    return int(top), int(bottom)


class Ep34(unittest.TestCase):
    def test_read_colr_hdr(self):
        fields, box = chart("hdr.mp4", "colr")
        self.assertEqual((box.start, box.size), (30785, 19))                         # 8 + 4 (nclx) + 3 x 2 + 1
        self.assertEqual(fields, {"colour_type": "nclx", "colour_primaries": 9, "transfer_characteristics": 16,
                                  "matrix_coefficients": 9, "full_range_flag": 0})   # plan row 305

    def test_colr_matches_ffprobe(self):
        fields, _ = chart("hdr.mp4", "colr")
        stream = probe("hdr.mp4")["streams"][0]
        self.assertEqual(PRIMARIES[fields["colour_primaries"]], stream["color_primaries"])
        self.assertEqual(TRANSFER[fields["transfer_characteristics"]], stream["color_transfer"])
        self.assertEqual(MATRIX[fields["matrix_coefficients"]], stream["color_space"])
        self.assertEqual(RANGE[fields["full_range_flag"]], stream["color_range"])

    def test_read_mdcv_hdr(self):
        fields, box = chart("hdr.mp4", "mdcv")
        self.assertEqual((box.start, box.size), (30816, 32))
        self.assertEqual(fields, {"display_primaries": [(13250, 34500), (7500, 3000), (34000, 16000)],
                                  "white_point": (15635, 16450), "max_display_mastering_luminance": 10000000,
                                  "min_display_mastering_luminance": 1})            # plan row 306

    def test_mdcv_matches_ffprobe(self):
        # stored green, blue, red; ffprobe (mov.c mov_read_mdcv's mapping {1, 2, 0}) names them
        fields, _ = chart("hdr.mp4", "mdcv")
        side = side_data("hdr.mp4", "Mastering display metadata")
        (gx, gy), (bx, by), (rx, ry) = fields["display_primaries"]
        for value, key in ((gx, "green_x"), (gy, "green_y"), (bx, "blue_x"), (by, "blue_y"), (rx, "red_x"),
                           (ry, "red_y"), (fields["white_point"][0], "white_point_x"),
                           (fields["white_point"][1], "white_point_y")):
            self.assertEqual(ratio(side[key]), (value, 50000), key)
        self.assertEqual(ratio(side["max_luminance"]), (fields["max_display_mastering_luminance"], 10000))
        self.assertEqual(ratio(side["min_luminance"]), (fields["min_display_mastering_luminance"], 10000))

    def test_mdcv_arithmetic(self):
        fields, _ = chart("hdr.mp4", "mdcv")
        self.assertEqual([(x / 50000, y / 50000) for x, y in fields["display_primaries"]],
                         [(0.265, 0.69), (0.15, 0.06), (0.68, 0.32)])               # P3's, not BT.2020's
        self.assertEqual(tuple(v / 50000 for v in fields["white_point"]), (0.3127, 0.329))   # D65
        self.assertEqual(fields["max_display_mastering_luminance"] / 10000, 1000)           # cd/m2
        self.assertEqual(fields["min_display_mastering_luminance"] / 10000, 0.0001)

    def test_read_clli_hdr(self):
        fields, box = chart("hdr.mp4", "clli")
        self.assertEqual((box.start, box.size), (30804, 12))
        self.assertEqual(fields, {"max_content_light_level": 1000, "max_pic_average_light_level": 400})  # row 307
        side = side_data("hdr.mp4", "Content light level metadata")
        self.assertEqual((side["max_content"], side["max_average"]), (1000, 400))

    def test_paint_chart_beside_the_sheet(self):
        contents = data("hdr.mp4")
        entry = boxes.find(boxes.walk(contents), HVC1)
        self.assertEqual([b.type for b in entry.children], ["hvcC", "fiel", "colr", "clli", "mdcv", "pasp", "btrt"])

    def test_only_hdr_has_a_chart(self):
        for path in sorted(TESTFILES.glob("*.mp4")) + sorted(TESTFILES.glob("*.m4a")):
            tree = boxes.walk(data(path.name))
            found = {kind for kind in ("colr", "mdcv", "clli") if _anywhere(tree, kind)}
            with self.subTest(path.name):
                self.assertEqual(found, {"colr", "mdcv", "clli"} if path.name == "hdr.mp4" else set())

    def test_phone_says_nothing_about_colour(self):
        self.assertEqual(run_cli("dump", str(TESTFILES / "phone.mp4"), "--find", "colr"), "no colr box\n")
        stream = probe("phone.mp4")["streams"][0]
        self.assertEqual([stream.get(k, "unknown") for k in ("color_primaries", "color_transfer", "color_space",
                                                            "color_range")], ["unknown"] * 4)

    def test_colr_nclc_and_prof(self):
        nclc = boxes.box("colr", b"nclc", struct.pack(">3H", 1, 1, 1))              # QuickTime: no range byte
        self.assertEqual(tables.read_colr(nclc, boxes.read_header(nclc, 0)),
                         {"colour_type": "nclc", "colour_primaries": 1, "transfer_characteristics": 1,
                          "matrix_coefficients": 1})
        prof = boxes.box("colr", b"prof", bytes(100))
        self.assertEqual(tables.read_colr(prof, boxes.read_header(prof, 0)),
                         {"colour_type": "prof", "ICC_profile_size": 100})
        full = boxes.box("colr", b"nclx", struct.pack(">3HB", 1, 13, 1, 0x80))      # sRGB transfer, full range
        self.assertEqual(tables.read_colr(full, boxes.read_header(full, 0))["full_range_flag"], 1)

    def test_short_boxes(self):
        for kind, payload, message in (("colr", b"nclx" + bytes(6), "colr at 0: nclx needs 19 bytes, box has 18"),
                                       ("mdcv", bytes(20), "mdcv at 0: needs 32 bytes, box has 28"),
                                       ("clli", bytes(2), "clli at 0: needs 12 bytes, box has 10")):
            raw = boxes.box(kind, payload)
            with self.subTest(kind), self.assertRaisesRegex(boxes.BoxError, message):
                boxes.decode(raw, boxes.read_header(raw, 0))

    def test_visitors_book(self):
        contents = data("phone-tagged.mp4")
        ilst = boxes.find(boxes.walk(contents), "moov/udta/meta/ilst")
        self.assertEqual((ilst.start, ilst.size), (112148, 84))
        self.assertEqual(tables.read_ilst(contents, ilst),
                         {"tags": {"©nam": "Test pattern", "©ART": "MP4 from Scratch"}})
        tags = probe("phone-tagged.mp4")["format"]["tags"]
        self.assertEqual((tags["title"], tags["artist"]), ("Test pattern", "MP4 from Scratch"))
        self.assertEqual(contents[ilst.start + 12:ilst.start + 16], b"\xa9nam")       # the key's first byte

    def test_empty_book_and_the_same_parcels(self):
        phone, tagged = data("phone.mp4"), data("phone-tagged.mp4")
        ilst = boxes.find(boxes.walk(phone), "moov/udta/meta/ilst")
        self.assertEqual((ilst.size, tables.read_ilst(phone, ilst)), (8, {"tags": {}}))
        self.assertEqual(len(tagged) - len(phone), 76)                                 # the two items
        self.assertEqual(tagged[:108704 + 40], phone[:108704 + 40])                   # ftyp, free, mdat unchanged
        handler = boxes.find(boxes.walk(tagged), "moov/udta/meta/hdlr")
        self.assertEqual(boxes.decode(tagged, handler)["handler_type"], "mdir")

    def test_ilst_other_values(self):
        number = boxes.box("tmpo", boxes.box("data", struct.pack(">II", 21, 0), b"\x00\x78"))   # type 21: integer
        raw = boxes.box("ilst", number)
        self.assertEqual(tables.read_ilst(raw, boxes.read_header(raw, 0)), {"tags": {"tmpo": b"\x00\x78"}})
        raw = boxes.box("ilst", boxes.box("©nam", boxes.box("free")))
        with self.assertRaisesRegex(boxes.BoxError, "©nam at 8: holds free, not a data box"):
            tables.read_ilst(raw, boxes.read_header(raw, 0))

    def test_cmd_dump_find_mdcv(self):
        self.assertEqual(run_cli("dump", str(TESTFILES / "hdr.mp4"), "--find", "mdcv"), EXPECTED.read_text())

    def test_dump_shows_tags(self):
        out = run_cli("dump", str(TESTFILES / "phone-tagged.mp4"), "--find", "ilst")
        self.assertEqual(out, "moov/udta/meta/ilst 112148 84 tags={'©nam': 'Test pattern', "
                              "'©ART': 'MP4 from Scratch'}\n")


def _anywhere(tree, kind):
    return any(b.type == kind or _anywhere(b.children, kind) for b in tree)


if __name__ == "__main__":
    unittest.main()
