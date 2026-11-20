import json
import unittest
from pathlib import Path
from mp4kit import audio, boxes, tables
from tests.util import data, run_cli, run_cli_code

PHONE, AAC_ONLY = data("phone.mp4"), data("aac-only.m4a")
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep21.txt"
STSD = "moov/trak/mdia/minf/stbl/stsd"
# aac-only's esds (54 bytes at 16942): the FullBox header, then four envelopes, each length in ffmpeg's 4-byte form
AAC_ONLY_ESDS = bytes.fromhex("00000036 65736473 00000000" "0380808025 000100" "0480808017 40 15 000000 0000fdf1 0000fdf1"
                              "0580808005 120856e500" "0680808001 02")


def probe_audio(name):
    """ffprobe's audio stream for a committed file (captures/<name>.probe.json)."""
    streams = json.loads((CAPS / f"{name}.probe.json").read_text())["streams"]
    return next(s for s in streams if s["codec_type"] == "audio")


def esds_of(contents):
    """The first esds box (in the first mp4a) of a file."""
    return boxes.find(boxes.walk(contents), STSD + "/mp4a/esds")


def read(blob):
    """read_esds on an esds box held alone in `blob`."""
    return audio.read_esds(blob, boxes.read_header(blob, 0))


class Ep21(unittest.TestCase):
    def test_read_audio_entry(self):
        # phone: 8 + 28 + esds 54 + btrt 20 = 110; aac-only has no btrt: 8 + 28 + 54 = 90
        for contents, start, size, channels, rate, inside in ((PHONE, 110619, 110, 2, 48000, ["esds", "btrt"]),
                                                              (AAC_ONLY, 16906, 90, 1, 44100, ["esds"])):
            mp4a = boxes.find(boxes.walk(contents), STSD + "/mp4a")
            with self.subTest(start=start):
                self.assertEqual((mp4a.start, mp4a.size), (start, size))
                self.assertEqual(tables.read_audio_entry(contents, mp4a),
                                 {"data_reference_index": 1, "channelcount": channels, "samplesize": 16,
                                  "samplerate": rate})
                self.assertEqual(boxes.u32(contents, mp4a.payload + 24), rate << 16)    # 16.16: 0xbb80_0000
                self.assertEqual([b.type for b in mp4a.children], inside)
                self.assertEqual(mp4a.children[0].start, mp4a.payload + 28)               # 28 bytes of fields

    def test_audio_entry_matches_ffprobe(self):
        for contents, name in ((PHONE, "phone.mp4"), (AAC_ONLY, "aac-only.m4a")):
            fields = tables.read_audio_entry(contents, boxes.find(boxes.walk(contents), STSD + "/mp4a"))
            stream = probe_audio(name)
            with self.subTest(name=name):
                self.assertEqual((fields["channelcount"], fields["samplerate"]),
                                 (stream["channels"], int(stream["sample_rate"])))
                self.assertEqual(stream["codec_tag_string"], "mp4a")

    def test_read_audio_entry_short_box(self):
        blob = (32).to_bytes(4, "big") + AAC_ONLY[16906 + 4:16906 + 32]
        with self.assertRaisesRegex(boxes.BoxError, "mp4a at 0: a sound sample entry needs 36 bytes, box has 32"):
            tables.read_audio_entry(blob, boxes.read_header(blob, 0))

    def test_read_descriptor(self):
        # aac-only: ES_Descriptor at 16954, DecoderConfigDescriptor at 16962, DecoderSpecificInfo at 16980, SL at 16990
        self.assertEqual(audio.read_descriptor(AAC_ONLY, 16954), (0x03, 37, 16959))
        self.assertEqual(audio.read_descriptor(AAC_ONLY, 16962), (0x04, 23, 16967))
        self.assertEqual(audio.read_descriptor(AAC_ONLY, 16980), (0x05, 5, 16985))
        self.assertEqual(audio.read_descriptor(AAC_ONLY, 16990), (0x06, 1, 16995))
        self.assertEqual(16959 + 37, esds_of(AAC_ONLY).end)          # the outer envelope fills the box

    def test_read_descriptor_size_code(self):
        self.assertEqual(audio.read_descriptor(bytes.fromhex("0525"), 0), (5, 37, 2))         # one byte: 37
        self.assertEqual(audio.read_descriptor(bytes.fromhex("038025"), 0), (3, 37, 3))       # 37 again, padded
        self.assertEqual(audio.read_descriptor(bytes.fromhex("048148"), 0), (4, 200, 3))      # 1 x 128 + 72
        self.assertEqual(audio.read_descriptor(bytes.fromhex("03ffffff7f"), 0), (3, (1 << 28) - 1, 5))
        with self.assertRaisesRegex(boxes.BoxError, "descriptor at 0: its length runs past 4 bytes"):
            audio.read_descriptor(bytes.fromhex("0380808080 01"), 0)

    def test_read_esds_aac_only(self):
        esds = esds_of(AAC_ONLY)
        self.assertEqual((esds.start, esds.size), (16942, 54))
        self.assertEqual(bytes(AAC_ONLY[esds.start:esds.end]), AAC_ONLY_ESDS)
        self.assertEqual(audio.read_esds(AAC_ONLY, esds),
                         {"ES_ID": 1, "objectTypeIndication": 0x40, "streamType": 5, "bufferSizeDB": 0,
                          "maxBitrate": 65009, "avgBitrate": 65009, "ASC": bytes.fromhex("120856e500"),
                          "audioObjectType": 2, "samplingFrequencyIndex": 4, "channelConfiguration": 1,
                          "sample_rate": 44100, "SLConfig_predefined": 2, "codec": "mp4a.40.2"})

    def test_read_esds_phone(self):
        fields = audio.read_esds(PHONE, esds_of(PHONE))
        self.assertEqual((fields["ES_ID"], fields["avgBitrate"], fields["ASC"]), (2, 96360, bytes.fromhex("119056e500")))
        self.assertEqual((fields["samplingFrequencyIndex"], fields["sample_rate"], fields["channelConfiguration"]),
                         (3, 48000, 2))

    def test_esds_matches_ffprobe(self):
        for contents, name in ((PHONE, "phone.mp4"), (AAC_ONLY, "aac-only.m4a")):
            fields, stream = audio.read_esds(contents, esds_of(contents)), probe_audio(name)
            with self.subTest(name=name):
                self.assertEqual((fields["sample_rate"], fields["channelConfiguration"], fields["avgBitrate"]),
                                 (int(stream["sample_rate"]), stream["channels"], int(stream["bit_rate"])))
                self.assertEqual((fields["codec"], stream["profile"], len(fields["ASC"])),
                                 (stream["mime_codec_string"], "LC", stream["extradata_size"]))

    def test_entry_and_esds_agree(self):
        for contents in (PHONE, AAC_ONLY, data("cenc.mp4"), data("frag-cmaf.mp4")):
            tree = boxes.walk(contents)
            entry = boxes.find(tree, STSD + "/mp4a") or boxes.find(tree, STSD + "/enca")
            hint, sheet = tables.read_audio_entry(contents, entry), audio.read_esds(contents, entry.children[0])
            self.assertEqual((hint["samplerate"], hint["channelcount"]),
                             (sheet["sample_rate"], sheet["channelConfiguration"]))

    def test_read_esds_es_flags(self):
        # streamDependence (+2), URL (+1 + its length) and OCR (+2): the DecoderConfigDescriptor moves along
        es = bytes.fromhex("0001" "e0" "0007" "03" "616263" "0009")
        rest = AAC_ONLY_ESDS[20:]           # from the DecoderConfigDescriptor on
        blob = (12 + 2 + len(es) + len(rest)).to_bytes(4, "big") + b"esds" + bytes(4) + bytes(
            [3, len(es) + len(rest)]) + es + rest
        fields = read(blob)
        self.assertEqual((fields["ES_ID"], fields["sample_rate"], fields["SLConfig_predefined"]), (1, 44100, 2))

    def test_read_esds_envelope_checks(self):
        blob = bytearray(AAC_ONLY_ESDS)
        blob[42] = 6                       # DecoderSpecificInfo of 6 bytes: past its DecoderConfigDescriptor's end
        with self.assertRaisesRegex(boxes.BoxError, "descriptor at 38: expected tag 0x05 inside 48, found 0x05 of 6"):
            read(bytes(blob))
        blob = bytearray(AAC_ONLY_ESDS)
        blob[20] = 0x05                    # the second envelope is not a DecoderConfigDescriptor
        with self.assertRaisesRegex(boxes.BoxError, "descriptor at 20: expected tag 0x04 inside 54, found 0x05"):
            read(bytes(blob))

    def test_parse_asc(self):
        self.assertEqual(audio.parse_asc(bytes.fromhex("120856e500")),
                         {"audioObjectType": 2, "samplingFrequencyIndex": 4, "channelConfiguration": 1})
        self.assertEqual(audio.parse_asc(bytes.fromhex("1190")),
                         {"audioObjectType": 2, "samplingFrequencyIndex": 3, "channelConfiguration": 2})
        self.assertEqual(f"{0x1208:016b}", "0001001000001000")       # 00010 0100 0001 000
        self.assertEqual(audio.SAMPLE_RATES[audio.parse_asc(bytes.fromhex("1208"))["samplingFrequencyIndex"]], 44100)

    def test_parse_asc_refuses_escapes(self):
        for asc in ("f800", "1788", "12"):     # object type 31; rate index 15 (a 24-bit rate follows); too short
            with self.subTest(asc=asc), self.assertRaisesRegex(ValueError, "not read"):
                audio.parse_asc(bytes.fromhex(asc))

    def test_asc_feeds_adts(self):
        # Episode 20 wrote these fields by hand; now they come out of the file, and the ADTS header is the same
        asc = audio.parse_asc(audio.read_esds(PHONE, esds_of(PHONE))["ASC"])
        self.assertEqual(audio.adts_header(asc, 238).hex(), "fff14c801ebffc")
        asc = audio.parse_asc(audio.read_esds(AAC_ONLY, esds_of(AAC_ONLY))["ASC"])
        self.assertEqual(audio.adts_header(asc, 264).hex(), "fff1504021fffc")

    def test_sound_tables(self):
        stbl = boxes.find(boxes.walk(AAC_ONLY), "moov/trak/mdia/minf/stbl")
        self.assertIsNone(tables.read_stss(AAC_ONLY, boxes.find(stbl.children, "stss")))   # every frame a start
        sizes = tables.read_stsz(AAC_ONLY, boxes.find(stbl.children, "stsz"))
        self.assertEqual((len(sizes), sum(sizes), min(sizes), max(sizes)), (88, 16441, 5, 278))

    def test_registry(self):
        self.assertIs(boxes.DECODERS["mp4a"], tables.read_audio_entry)
        self.assertIs(boxes.DECODERS["enca"], tables.read_audio_entry)
        self.assertIs(boxes.DECODERS["esds"], audio.read_esds)

    def test_cmd_dump_find_esds(self):
        printed = run_cli("dump", "testfiles/out/aac-only.m4a", "--find", "esds")
        self.assertEqual(printed, EXPECTED.read_text())
        self.assertIn(" sample_rate=44100 ", printed)

    def test_cmd_dump_find_esds_none(self):
        for name in ("f1.mp4", "hevc.mp4", "av1.mp4"):
            with self.subTest(name=name):
                self.assertEqual(run_cli_code("dump", f"testfiles/out/{name}", "--find", "esds"), (0, "no esds box\n"))

    def test_pcm_reads_the_entry(self):
        printed = run_cli("dump", "testfiles/out/aac-only.m4a", "--pcm")
        self.assertTrue(printed.startswith("track 1 soun mp4a: 44100 samples/s (mdhd), channelcount 1, samplesize 16\n"))
