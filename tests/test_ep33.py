import json
import unittest
from pathlib import Path
from mp4kit import boxes, nal, tables
from tests.util import data, run_cli, run_cli_code

CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep33.txt"
STSD = "moov/trak/mdia/minf/stbl/stsd"


def track(name, n=1):
    contents = data(name)
    return contents, tables.read_tracks(contents, boxes.walk(contents))[n - 1]


def hevc_units(contents, sample):
    """(nal_unit_type, size) of each NAL of an HEVC sample (4-byte lengths in every test file)."""
    return [(nal.hevc_nal_header(u[0], u[1])[0], len(u))
            for _, u in nal.iter_length_prefixed(contents, sample.offset, sample.offset + sample.size)]


def stream(name, index=0):
    """ffprobe's stream line for one stream (captures/<name>.probe.json)."""
    return json.loads((CAPS / f"{name}.probe.json").read_text())["streams"][index]


class Ep33(unittest.TestCase):
    def test_hevc_nal_header(self):
        self.assertEqual(nal.hevc_nal_header(0x40, 0x01), (32, 0, 0))     # VPS
        self.assertEqual(nal.hevc_nal_header(0x28, 0x01), (20, 0, 0))     # IDR_N_LP
        self.assertEqual(nal.hevc_nal_header(0x2A, 0x01), (21, 0, 0))     # CRA_NUT
        self.assertEqual(nal.hevc_nal_header(0x41, 0x0B), (32, 33, 2))    # layer 0b100001, nuh_temporal_id_plus1 3
        self.assertEqual(nal.hevc_nal_header(0x7E, 0x01), (63, 0, 0))     # forbidden bit stays out of the type

    def test_hev1_sample_1(self):
        contents, video = track("hevc-hev1.mp4")
        self.assertEqual(video.entry["type"], "hev1")
        self.assertEqual(hevc_units(contents, video.samples[0]),          # plan row 300; check table line 212
                         [(32, 24), (33, 43), (34, 7), (39, 2329), (20, 2518)])
        self.assertEqual(video.samples[0].size, 5 * 4 + 24 + 43 + 7 + 2329 + 2518)

    def test_hvc1_sample_1_is_one_idr(self):
        contents, video = track("hevc.mp4")
        self.assertEqual(video.entry["type"], "hvc1")
        self.assertEqual(hevc_units(contents, video.samples[0]), [(20, 2518)])
        self.assertEqual(video.samples[0].size, 2522)

    def test_keyframe_28_is_a_cra(self):
        for name, first in (("hevc.mp4", []), ("hevc-hev1.mp4", [32, 33, 34, 39])):
            contents, video = track(name)
            with self.subTest(name=name):
                self.assertEqual([s.number for s in video.samples if s.key], [1, 28])
                self.assertEqual([t for t, _ in hevc_units(contents, video.samples[27])], first + [21])
                self.assertEqual([hevc_units(contents, video.samples[n])[0][0] for n in (28, 29, 30)], [9, 8, 8])

    def test_leb128(self):
        self.assertEqual(nal.leb128(b"\x0b", 0), (11, 1))
        self.assertEqual(nal.leb128(b"\xf0\x17", 0), (3056, 2))                     # av1.mp4 sample 1's OBU_FRAME
        self.assertEqual(nal.leb128(b"\x00\x80\x01", 1), (128, 3))
        self.assertEqual(nal.leb128(b"\x8b\x80\x80\x00", 0), (11, 4))              # padded: still 11
        with self.assertRaisesRegex(ValueError, "leb128 at 0: more than 8 bytes"):
            nal.leb128(b"\x80" * 9, 0)

    def test_iter_obus_av1_sample_1(self):
        contents, video = track("av1.mp4")
        first = video.samples[0]
        self.assertEqual((first.offset, first.size), (48, 3072))                   # plan row 302
        self.assertEqual(list(nal.iter_obus(contents, 48, 48 + 3072)), [(48, 1, 2, 11), (61, 6, 3, 3056)])

    def test_iter_obus_every_av1_sample(self):
        contents, video = track("av1.mp4")
        counts = {}
        for s in video.samples:
            obus = list(nal.iter_obus(contents, s.offset, s.offset + s.size))
            self.assertEqual(sum(head + size for _, _, head, size in obus), s.size)
            self.assertEqual(obus[0][1] == 1, s.key)                   # a sequence header opens each sync sample
            for _, t, _, _ in obus:
                counts[t] = counts.get(t, 0) + 1
        self.assertEqual(counts, {1: 2, 6: 60, 3: 28})                            # no temporal delimiter
        self.assertEqual([s.number for s in video.samples if s.key], [1, 31])

    def test_iter_obus_in_memory(self):
        unsized = bytes([6 << 3]) + b"abc"                                        # OBU_FRAME, no size field
        self.assertEqual(list(nal.iter_obus(unsized, 0, 4)), [(0, 6, 1, 3)])
        extended = bytes([1 << 3 | 4 | 2, 0x08, 2]) + b"xy" + bytes([2 << 3 | 2, 0])
        self.assertEqual(list(nal.iter_obus(extended, 0, 7)), [(0, 1, 3, 2), (5, 2, 2, 0)])
        with self.assertRaisesRegex(ValueError, "OBU at 0: obu_size 9 runs past 4"):
            list(nal.iter_obus(bytes([6 << 3 | 2, 9, 0, 0]), 0, 4))

    def test_read_hvcc_hvc1(self):
        contents = data("hevc.mp4")
        h = tables.read_hvcc(contents, boxes.find(boxes.walk(contents), STSD + "/hvc1/hvcC"))
        self.assertEqual((h["configurationVersion"], h["general_profile_idc"], h["general_level_idc"]), (1, 1, 60))
        self.assertEqual((h["general_profile_space"], h["general_tier_flag"]), (0, 0))
        self.assertEqual(h["general_profile_compatibility_flags"].hex(), "60000000")
        self.assertEqual((h["chromaFormat"], h["bitDepthLumaMinus8"], h["bitDepthChromaMinus8"]), (1, 0, 0))
        self.assertEqual((h["lengthSizeMinusOne"], h["numTemporalLayers"], h["temporalIdNested"]), (3, 1, 1))
        self.assertEqual([(full, kind, [len(n) for n in nalus]) for full, kind, nalus in h["arrays"]],
                         [(1, 32, [24]), (1, 33, [43]), (1, 34, [7]), (0, 39, [2332])])

    def test_read_hvcc_hev1_and_in_band_sets(self):
        contents, video = track("hevc-hev1.mp4")
        h = video.entry["hvcC"]
        self.assertEqual([(full, kind, sizes) for full, kind, sizes in h["arrays"]],
                         [(0, 32, [24]), (0, 33, [43]), (0, 34, [7]), (0, 39, [2329])])   # hev1: completeness 0
        sheets = tables.read_hvcc(contents, boxes.find(boxes.walk(contents), STSD + "/hev1/hvcC"))["arrays"]
        in_band = [u for _, u in nal.iter_length_prefixed(contents, video.samples[0].offset,
                                                           video.samples[0].offset + video.samples[0].size)]
        self.assertEqual([nalus[0] for _, _, nalus in sheets], in_band[:4])         # the same bytes, twice
        other = data("hevc.mp4")
        hvc1 = tables.read_hvcc(other, boxes.find(boxes.walk(other), STSD + "/hvc1/hvcC"))["arrays"]
        self.assertEqual([n for _, _, n in hvc1[:3]], [n for _, _, n in sheets[:3]])  # same VPS, SPS, PPS

    def test_read_hvcc_hdr(self):
        contents = data("hdr.mp4")
        h = tables.read_hvcc(contents, boxes.find(boxes.walk(contents), STSD + "/hvc1/hvcC"))
        self.assertEqual((h["general_profile_idc"], h["bitDepthLumaMinus8"], h["bitDepthChromaMinus8"]), (2, 2, 2))
        self.assertEqual([len(n) for n in h["arrays"][3][2]], [9, 30, 2442])        # three SEI in one array

    def test_read_hvcc_runs_past(self):
        contents = data("hevc.mp4")
        box = boxes.find(boxes.walk(contents), STSD + "/hvc1/hvcC")
        short = boxes.Box("hvcC", box.start, 100, 8)
        message = r"hvcC at 29795: the arrays run to 32252, past the box's end \(29895\)"
        with self.assertRaisesRegex(boxes.BoxError, message):
            tables.read_hvcc(contents, short)

    def test_hvcc_matches_ffprobe(self):
        for name, profile, tag in (("hevc.mp4", "Main", "hvc1"), ("hevc-hev1.mp4", "Main", "hev1"),
                                   ("hdr.mp4", "Main 10", "hvc1")):
            contents, video = track(name)
            with self.subTest(name=name):
                self.assertEqual((stream(name)["profile"], stream(name)["level"], stream(name)["codec_tag_string"]),
                                 (profile, video.entry["hvcC"]["general_level_idc"], tag))

    def test_read_av1c(self):
        contents, video = track("av1.mp4")
        a = video.entry["av1C"]
        self.assertEqual((a["version"], a["seq_profile"], a["seq_level_idx_0"], a["seq_tier_0"]), (1, 0, 0, 0))
        self.assertEqual((a["high_bitdepth"], a["twelve_bit"], a["monochrome"]), (0, 0, 0))
        self.assertEqual((a["chroma_subsampling_x"], a["chroma_subsampling_y"], a["chroma_sample_position"]), (1, 1, 0))
        self.assertEqual(a["initial_presentation_delay_present"], 0)
        self.assertEqual(list(nal.iter_obus(a["configOBUs"], 0, len(a["configOBUs"]))), [(0, 1, 2, 11)])
        self.assertEqual((stream("av1.mp4")["profile"], stream("av1.mp4")["level"]), ("Main", 0))
        sample = contents[video.samples[0].offset:video.samples[0].offset + 13]
        self.assertEqual(sample[:9], a["configOBUs"][:9])                           # the same sequence header ...
        self.assertNotEqual(sample, a["configOBUs"])                                # ... but not the same bytes

    def test_read_av1c_marker(self):
        blob = boxes.box("av1C", b"\x01\x00\x0c\x00")
        with self.assertRaisesRegex(boxes.BoxError, "av1C at 0: marker and version 01, expected 81"):
            tables.read_av1c(blob, boxes.read_header(blob, 0))

    def test_registry(self):
        self.assertIs(boxes.DECODERS["av1C"], tables.read_av1c)
        self.assertIs(boxes.DECODERS["hvcC"], tables._hvcc_fields)
        printed = run_cli("dump", "testfiles/out/hevc.mp4", "--find", "hvcC")
        self.assertTrue(printed.rstrip().endswith("arrays=[(1, 32, [24]), (1, 33, [43]), (1, 34, [7]), (0, 39, "
                                                  "[2332])]"))
        printed = run_cli("dump", "testfiles/out/av1.mp4", "--find", "av1C")
        self.assertTrue(printed.rstrip().endswith("configOBUs=0a0b0200000561e7f66017c002"))

    def test_web_codec_sheets_walked(self):
        tree = boxes.walk(data("vp9opus.mp4"))
        self.assertEqual([b.type for b in boxes.find(tree, STSD + "/vp09").children],
                         ["vpcC", "fiel", "pasp", "btrt"])
        self.assertEqual([b.type for b in boxes.find(tree, STSD + "/Opus").children], ["dOps", "btrt"])

    def test_cmd_nals_sample(self):
        printed = run_cli("nals", "testfiles/out/hevc-hev1.mp4", "--sample", "1")
        self.assertEqual(printed, EXPECTED.read_text())
        self.assertEqual([line.split()[3] for line in printed.splitlines()[1:]], ["32", "33", "34", "39", "20"])

    def test_cmd_nals_av1(self):
        self.assertEqual(run_cli("nals", "testfiles/out/av1.mp4", "--sample", "1").splitlines(), [
            "track 1 (av01) sample 1: 3072 bytes at 48, first bytes 0a 0b 02 00 00 05 61 e7",
            "1 48 13 1 OBU_SEQUENCE_HEADER header 2 obu_size 11",
            "2 61 3059 6 OBU_FRAME header 3 obu_size 3056"])
        self.assertEqual(run_cli("nals", "testfiles/out/av1.mp4", "--sample", "3").splitlines(), [
            "track 1 (av01) sample 3: 3 bytes at 9425, first bytes 1a 01 e8",
            "1 9425 3 3 OBU_FRAME_HEADER header 2 obu_size 1"])

    def test_cmd_nals_h264_by_sample(self):
        self.assertEqual(run_cli("nals", "testfiles/out/phone.mp4", "--sample", "1").splitlines()[1:],
                         ["1 48 684 6 SEI", "2 736 5132 5 IDR slice"])
        whole = run_cli("nals", "testfiles/out/f1.mp4", "--from", "40", "--to", "22057").splitlines()
        self.assertEqual(run_cli("nals", "testfiles/out/f1.mp4", "--sample", "1").splitlines()[1], whole[0])

    def test_first_bytes_tell_the_codec(self):
        # (file, track): the sample entry, and sample 1's first bytes as `nals --sample 1` prints them
        for name, n, kind, first in (("phone.mp4", 1, "avc1", "00 00 02 ac 06 05 ff ff"),
                                     ("hevc.mp4", 1, "hvc1", "00 00 09 d6 28 01 af 0c"),
                                     ("hevc-hev1.mp4", 1, "hev1", "00 00 00 18 40 01 0c 01"),
                                     ("av1.mp4", 1, "av01", "0a 0b 02 00 00 05 61 e7"),
                                     ("vp9opus.mp4", 1, "vp09", "82 49 83 42 00 13 f0 0b"),
                                     ("vp9opus.mp4", 2, "Opus", "f8 72 49 47 27 10 e4 c8"),
                                     ("phone.mp4", 2, "mp4a", "21 2a 0f ff ff ff e0 04")):
            with self.subTest(name=name, track=n):
                head = run_cli("nals", f"testfiles/out/{name}", "--track", str(n), "--sample", "1").splitlines()[0]
                self.assertTrue(head.startswith(f"track {n} ({kind}) sample 1: "))
                self.assertTrue(head.endswith(f"first bytes {first}"))
        self.assertEqual(run_cli("nals", "testfiles/out/vp9opus.mp4", "--sample", "1").splitlines()[1],
                         "vp09: not NAL units or OBUs")

    def test_cmd_nals_errors(self):
        for argv, line in ((("phone.mp4", "--track", "3", "--sample", "1"), "error: no track 3, the file has 2"),
                           (("phone.mp4", "--sample", "61"), "error: no sample 61, track 1 has 60"),
                           (("frag-cmaf.mp4", "--sample", "1"), "error: no sample 1, track 1 has 0"),
                           (("f1.mp4",), "error: give --from and --to, or --sample")):
            with self.subTest(argv=argv):
                self.assertEqual(run_cli_code("nals", f"testfiles/out/{argv[0]}", *argv[1:]), (1, line + "\n"))


if __name__ == "__main__":
    unittest.main()
