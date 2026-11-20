import json
import unittest
from pathlib import Path
from mp4kit import audio, boxes, tables
from tests.util import data, run_cli, run_cli_code

PHONE, AAC_ONLY = data("phone.mp4"), data("aac-only.m4a")
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep22.txt"
STBL = "mdia/minf/stbl"
# aac-only's three boxes, as xxd shows them: elst at 16709, sgpd at 17448, sbgp at 17474
AAC_ONLY_ELST = bytes.fromhex("0000001c 656c7374 00000000 00000001" "00015888 00000400 0001 0000")
AAC_ONLY_SGPD = bytes.fromhex("0000001a 73677064 01000000 726f6c6c" "00000002 00000001 ffff")
AAC_ONLY_SBGP = bytes.fromhex("0000001c 73626770 00000000 726f6c6c" "00000001 00000058 00000001")


def sound_trak(contents):
    """The file's sound track (hdlr soun)."""
    for trak in boxes.find_all(boxes.walk(contents), "moov/trak"):
        if tables.read_hdlr(contents, boxes.find(trak.children, "mdia/hdlr"))["handler_type"] == "soun":
            return trak
    return None


def clocks(contents, trak):
    """(the track's elst, its mdhd timescale and duration, the movie's mvhd timescale)."""
    mdhd = tables.read_mdhd(contents, boxes.find(trak.children, "mdia/mdhd"))
    mvhd = tables.read_mvhd(contents, boxes.find(boxes.walk(contents), "moov/mvhd"))
    elst = tables.read_elst(contents, boxes.find(trak.children, "edts/elst"))
    return elst, mdhd["timescale"], mdhd["duration"], mvhd["timescale"]


def probe(name):
    """ffprobe's audio stream and first audio packet for a committed file (captures/<name>.probe.json)."""
    capture = json.loads((CAPS / f"{name}.probe.json").read_text())
    stream = next(s for s in capture["streams"] if s["codec_type"] == "audio")
    first = next(p for p in capture["packets"] if p["stream_index"] == stream["index"])
    return stream, first


def esds_asc(contents):
    """The ASC bytes in the file's esds."""
    return audio.read_esds(contents, boxes.find(sound_trak(contents).children, STBL + "/stsd/mp4a/esds"))["ASC"]


class Ep22(unittest.TestCase):
    def test_boxes_bytes(self):
        trak = sound_trak(AAC_ONLY)
        for path, start, blob in (("edts/elst", 16709, AAC_ONLY_ELST), (STBL + "/sgpd", 17448, AAC_ONLY_SGPD),
                                  (STBL + "/sbgp", 17474, AAC_ONLY_SBGP)):
            box = boxes.find(trak.children, path)
            with self.subTest(path=path):
                self.assertEqual((box.start, bytes(AAC_ONLY[box.start:box.end])), (start, blob))
        self.assertEqual((0x15888, 0x400), (88200, 1024))      # segment_duration, media_time

    def test_priming(self):
        for contents in (AAC_ONLY, PHONE):
            elst = clocks(contents, sound_trak(contents))[0]
            self.assertEqual(audio.priming(elst), 1024)
        self.assertEqual(audio.priming([]), 0)                                      # no edit list: no way to know
        # an empty edit first, then Apple's conventional 2,112
        self.assertEqual(audio.priming([(500, -1, 1, 0), (88200, 2112, 1, 0)]), 2112)

    def test_priming_matches_ffprobe(self):
        # ffprobe: initial_padding 1024, the first packet at pts -1024 with a "Skip Samples" of 1024
        for contents, name in ((AAC_ONLY, "aac-only.m4a"), (PHONE, "phone.mp4")):
            stream, first = probe(name)
            skip = audio.priming(clocks(contents, sound_trak(contents))[0])
            with self.subTest(name=name):
                self.assertEqual(stream["initial_padding"], skip)
                self.assertEqual((first["pts"], first["side_data_list"][0]["skip_samples"]), (-skip, skip))

    def test_edit_window(self):
        elst, rate, track_ticks, movie = clocks(AAC_ONLY, sound_trak(AAC_ONLY))
        self.assertEqual((elst, rate, track_ticks, movie), ([(88200, 1024, 1, 0)], 44100, 89224, 44100))
        self.assertEqual(audio.edit_window(elst, rate, movie), (1024 / 44100, 2.0))
        self.assertEqual(track_ticks, 1024 + 88200)            # the edit skips the priming and plays to the end
        elst, rate, track_ticks, movie = clocks(PHONE, sound_trak(PHONE))
        self.assertEqual(audio.edit_window(elst, rate, movie), (1024 / 48000, 2.0))
        self.assertEqual(track_ticks, 1024 + 96000)

    def test_edit_window_clocks(self):
        # the length counts on the movie's clock, the start on the track's: phone's video (mvhd 48000, mdhd 15360)
        video = boxes.find_all(boxes.walk(PHONE), "moov/trak")[0]
        elst, rate, _, movie = clocks(PHONE, video)
        self.assertEqual((rate, movie), (15360, 48000))
        self.assertEqual(audio.edit_window(elst, rate, movie), (1024 / 15360, 2.0))
        self.assertEqual(audio.edit_window([(4410, -1, 1, 0), (88200, 1024, 1, 0)], 44100, 44100), (1024 / 44100, 2.0))
        for elst in ([], [(4410, -1, 1, 0)]):
            with self.subTest(elst=elst), self.assertRaisesRegex(ValueError, "no edit plays the track"):
                audio.edit_window(elst, 44100, 44100)

    def test_window_matches_ffprobe(self):
        for contents, name in ((AAC_ONLY, "aac-only.m4a"), (PHONE, "phone.mp4")):
            elst, rate, _, movie = clocks(contents, sound_trak(contents))
            stream = probe(name)[0]
            with self.subTest(name=name):
                self.assertEqual(audio.edit_window(elst, rate, movie)[1], float(stream["duration"]))   # 2.000000
                self.assertEqual((stream["duration_ts"], stream["start_time"]), (elst[0][0], "0.000000"))

    def test_read_sgpd(self):
        for contents, start in ((AAC_ONLY, 17448), (PHONE, 112041)):
            sgpd = boxes.find(sound_trak(contents).children, STBL + "/sgpd")
            with self.subTest(start=start):
                self.assertEqual((sgpd.start, sgpd.size), (start, 26))
                self.assertEqual(tables.read_sgpd(contents, sgpd),
                                 {"version": 1, "grouping_type": "roll", "default_length": 2, "entries": [-1]})

    def test_read_sgpd_other_forms(self):
        blob = bytes.fromhex("00000016 73677064 00000000 726f6c6c 00000001 ffff")       # version 0: not read
        self.assertEqual(tables.read_sgpd(blob, boxes.read_header(blob, 0)), {"version": 0, "grouping_type": "roll"})
        blob = bytes.fromhex("0000001b 73677064 01000000 72617020 00000001 00000003 80 00 85")  # 'rap ': kept as bytes
        self.assertEqual(tables.read_sgpd(blob, boxes.read_header(blob, 0))["entries"], [b"\x80", b"\x00", b"\x85"])
        blob = bytes.fromhex("0000001a 73677064 01000000 726f6c6c 00000002 00000002 fffc")   # 2 entries, 1 present
        with self.assertRaisesRegex(boxes.BoxError, "sgpd at 0: 2 entries of 2 bytes run past the box"):
            tables.read_sgpd(blob, boxes.read_header(blob, 0))

    def test_read_sbgp(self):
        for contents, count in ((AAC_ONLY, 88), (PHONE, 95)):
            stbl = boxes.find(sound_trak(contents).children, STBL)
            sbgp = tables.read_sbgp(contents, boxes.find(stbl.children, "sbgp"))
            with self.subTest(count=count):
                self.assertEqual(sbgp, {"version": 0, "grouping_type": "roll", "entries": [(count, 1)]})
                self.assertEqual(len(tables.read_stsz(contents, boxes.find(stbl.children, "stsz"))), count)
        # version 1 carries a grouping_type_parameter before entry_count; Opus-style runs (4 samples in no group)
        blob = bytes.fromhex("00000028 73626770 01000000 726f6c6c 00000000 00000002 00000004 00000000"
                             "0000002f 00000001")
        self.assertEqual(tables.read_sbgp(blob, boxes.read_header(blob, 0))["entries"], [(4, 0), (47, 1)])
        blob = AAC_ONLY_SBGP[:19] + b"\x02" + AAC_ONLY_SBGP[20:]
        with self.assertRaisesRegex(boxes.BoxError, "sbgp at 0: entry_count 2 runs past the box"):
            tables.read_sbgp(blob, boxes.read_header(blob, 0))

    def test_asc_bytes(self):
        self.assertEqual(audio.asc_bytes({"audioObjectType": 2, "samplingFrequencyIndex": 4,
                                          "channelConfiguration": 1}).hex(), "1208")
        for contents in (AAC_ONLY, PHONE):
            asc = esds_asc(contents)
            with self.subTest(asc=asc.hex()):
                self.assertEqual(audio.asc_bytes(audio.parse_asc(asc)), asc[:2])     # 12 08 / 11 90; not 56 e5 00

    def test_asc_round_trip(self):
        for aot in range(1, 31):
            for index in range(13):
                for channels in range(16):
                    x = {"audioObjectType": aot, "samplingFrequencyIndex": index, "channelConfiguration": channels}
                    self.assertEqual(audio.parse_asc(audio.asc_bytes(x)), x)

    def test_asc_bytes_refuses(self):
        for aot, index, channels in ((31, 4, 1), (0, 4, 1), (2, 13, 1), (2, 4, 16)):
            x = {"audioObjectType": aot, "samplingFrequencyIndex": index, "channelConfiguration": channels}
            with self.subTest(x=x), self.assertRaisesRegex(ValueError, "out of the 2-byte form's range"):
                audio.asc_bytes(x)

    def test_adts_loses_priming(self):
        # Strip the boxes: ADTS headers carry the three ASC fields, which come back whole, but no timer
        for contents, tail in ((AAC_ONLY, 888), (PHONE, 256)):
            trak = sound_trak(contents)
            elst, rate, track_ticks, _ = clocks(contents, trak)
            stbl = boxes.find(trak.children, STBL)
            sizes = tables.read_stsz(contents, boxes.find(stbl.children, "stsz"))
            fields = audio.parse_asc(esds_asc(contents))
            stream = b"".join(audio.adts_header(fields, n) + bytes(n) for n in sizes)
            back, payloads = audio.split_adts(stream)
            with self.subTest(rate=rate):
                self.assertEqual(audio.asc_bytes(back), esds_asc(contents)[:2])
                self.assertEqual(len(payloads), len(sizes))
                # every ADTS frame decodes to 1,024 samples: the priming at the start and the padding at the end stay
                self.assertEqual(len(payloads) * 1024, audio.priming(elst) + elst[0][0] + tail)
                self.assertEqual(track_ticks, len(sizes) * 1024 - tail)    # stts's short last sample cuts the tail

    def test_registry(self):
        self.assertIs(boxes.DECODERS["sgpd"], tables.read_sgpd)
        self.assertIs(boxes.DECODERS["sbgp"], tables.read_sbgp)

    def test_cmd_dump_find_elst(self):
        printed = run_cli("dump", "testfiles/out/aac-only.m4a", "--find", "elst")
        self.assertEqual(printed, EXPECTED.read_text())
        self.assertIn("priming 1024 samples", printed)

    def test_cmd_dump_find_elst_phone(self):
        lines = run_cli("dump", "testfiles/out/phone.mp4", "--find", "elst").splitlines()
        self.assertEqual(lines[2:], ["track 2 soun: priming 1024 samples (elst media_time), 21.3 ms at 48000/s",
                                     "track 2 soun: plays 2.000 s from 0.021 s, of 2.021 s in the track (mdhd)",
                                     "track 2 soun: roll slip [-1] (sgpd) on 95 of 95 samples (sbgp)"])

    def test_cmd_dump_find_elst_no_sound(self):
        # f2 has an edit list but no sound track: no priming lines; frag-cmaf has no edit list at all
        self.assertEqual(run_cli("dump", "testfiles/out/f2.mp4", "--find", "elst"),
                         "moov/trak/edts/elst 21042 28 version=0 entries=[(396, 33, 1, 0)]\n")
        self.assertEqual(run_cli_code("dump", "testfiles/out/frag-cmaf.mp4", "--find", "elst"), (0, "no elst box\n"))

    def test_cmd_dump_find_sgpd(self):
        self.assertEqual(run_cli("dump", "testfiles/out/aac-only.m4a", "--find", "sgpd"),
                         "moov/trak/mdia/minf/stbl/sgpd 17448 26 version=1 grouping_type=roll default_length=2 "
                         "entries=[-1]\n")
