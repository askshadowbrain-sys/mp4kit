import json
import unittest
from pathlib import Path
from mp4kit import boxes, tables, timing
from tests.util import data, run_cli, run_cli_code

F1, AAC, PHONE = data("f1.mp4"), data("aac-only.m4a"), data("phone.mp4")
OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep14.txt"
STBL = "moov/trak/mdia/minf/stbl"


def probe(name):
    """ffprobe's packets and streams for a committed file (testfiles/captures/<name>.probe.json)."""
    return json.loads((CAPS / f"{name}.probe.json").read_text())


def tracks(contents):
    """(mdhd fields, stts, stss) for every track of a file, in file order."""
    found = []
    for trak in boxes.find_all(boxes.walk(contents), "moov/trak"):
        mdhd = tables.read_mdhd(contents, boxes.find(trak.children, "mdia/mdhd"))
        stbl = boxes.find(trak.children, "mdia/minf/stbl")
        stts = tables.read_stts(contents, boxes.find(stbl.children, "stts"))
        found.append((mdhd, stts, tables.read_stss(contents, boxes.find(stbl.children, "stss"))))
    return found


def last_keyframe(stts, stss, t):
    """By hand, as ep14 does it on screen: the sample whose decode time is the last at or before t, then the
    last stss entry at or before that sample (ep19's sync_before; f1 has no ctts or edit list)."""
    n = sum(1 for d in timing.decode_times(stts) if d <= t)
    return n, max(k for k in stss if k <= n)


class Ep14(unittest.TestCase):
    def test_drawers_1_and_2_in_f1(self):
        stbl = boxes.find(boxes.walk(F1), STBL)
        self.assertEqual((stbl.start, stbl.size), (22422, 356))
        self.assertEqual([(c.type, c.start, c.size) for c in stbl.children][:3],
                         [("stsd", 22430, 156), ("stts", 22586, 24), ("stss", 22610, 28)])

    def test_read_stts_f1(self):
        stts = boxes.find(boxes.walk(F1), STBL + "/stts")
        self.assertEqual(F1[22586:22610].hex(), "00000018" "73747473" "00000000" "00000001" "0000000c" "00000021")
        self.assertEqual(tables.read_stts(F1, stts), [(12, 33)])                 # 0x0c = 12, 0x21 = 33

    def test_read_stts_aac_only(self):
        stts = boxes.find(boxes.walk(AAC), STBL + "/stts")
        self.assertEqual((stts.start, stts.size), (16996, 32))
        self.assertEqual(AAC[17004:17028].hex(), "00000000" "00000002" "00000057" "00000400" "00000001" "00000088")
        self.assertEqual(tables.read_stts(AAC, stts), [(87, 1024), (1, 136)])     # 0x57 = 87, 0x88 = 136

    def test_read_stss_f1(self):
        stss = boxes.find(boxes.walk(F1), STBL + "/stss")
        self.assertEqual(F1[22610:22638].hex(), "0000001c" "73747373" "00000000" "00000003" "00000001" "00000005"
                         "00000009")
        self.assertEqual(tables.read_stss(F1, stss), [1, 5, 9])

    def test_read_stss_phone(self):
        video, audio = boxes.find_all(boxes.walk(PHONE), "moov/trak")
        stss = boxes.find(video.children, "mdia/minf/stbl/stss")
        self.assertEqual((stss.start, stss.size), (109370, 24))
        self.assertEqual(PHONE[109378:109394].hex(), "00000000" "00000002" "00000001" "0000001f")    # 0x1f = 31
        self.assertEqual(tables.read_stss(PHONE, stss), [1, 31])
        self.assertIsNone(boxes.find(audio.children, "mdia/minf/stbl/stss"))

    def test_read_stss_no_box(self):
        self.assertIsNone(boxes.find(boxes.walk(AAC), STBL + "/stss"))
        self.assertIsNone(tables.read_stss(AAC, None))                           # every sample is a sync sample

    def test_read_table(self):
        tree = boxes.walk(F1)
        self.assertEqual(tables.read_table(F1, boxes.find(tree, STBL + "/stss"), ">I"), [(1,), (5,), (9,)])
        self.assertEqual(tables.read_table(F1, boxes.find(tree, STBL + "/stts"), ">II"), [(12, 33)])
        frag = data("frag-cmaf.mp4")                                             # samples live in the fragments
        self.assertEqual(tables.read_stts(frag, boxes.find(boxes.walk(frag), STBL + "/stts")), [])

    def test_read_table_overrun(self):
        blob = bytearray(F1[22610:22638])
        blob[15] = 4                                                             # entry_count 4, room for 3
        with self.assertRaisesRegex(boxes.BoxError, "stss at 0: entry_count 4 needs 32 bytes, box has 28"):
            tables.read_stss(bytes(blob), boxes.read_header(bytes(blob), 0))

    def test_decode_times_f1(self):
        times = timing.decode_times([(12, 33)])
        self.assertEqual(times, [0, 33, 66, 99, 132, 165, 198, 231, 264, 297, 330, 363])
        self.assertEqual(times[-1] + 33, 396)                                    # f1's mdhd duration

    def test_decode_times_aac_only(self):
        stts = [(87, 1024), (1, 136)]
        times = timing.decode_times(stts)
        self.assertEqual((len(times), times[:3], times[-2:]), (88, [0, 1024, 2048], [88064, 89088]))
        self.assertEqual(87 * 1024 + 1 * 136, 89224)
        self.assertEqual(times[-1] + 136, tables.read_mdhd(AAC, boxes.find(boxes.walk(AAC), "moov/trak/mdia/mdhd"))
                         ["duration"])
        self.assertEqual(timing.decode_times([]), [])

    def test_stts_sums_to_mdhd_duration(self):
        for f in sorted(OUT.glob("*.mp4")) + sorted(OUT.glob("*.m4a")):
            if f.name == "broken-nomoov.mp4":
                continue
            for number, (mdhd, stts, _) in enumerate(tracks(f.read_bytes()), 1):
                with self.subTest(f=f.name, track=number):
                    self.assertEqual(sum(count * delta for count, delta in stts), mdhd["duration"])

    def test_matches_ffprobe(self):
        for name in ("f1.mp4", "f2.mp4", "phone.mp4", "aac-only.m4a", "hevc.mp4", "av1.mp4", "subs.mp4"):
            captured = probe(name)
            for index, (_, stts, stss) in enumerate(tracks(data(name))):
                packets = [p for p in captured["packets"] if p["stream_index"] == index]
                times = timing.decode_times(stts)
                with self.subTest(name=name, track=index + 1):
                    self.assertEqual(len(times), int(captured["streams"][index]["nb_frames"]))
                    if (name, index) == ("subs.mp4", 2):     # the last cue, 2 bytes with sample_delta 0 at 1.9 s,
                        self.assertEqual((len(packets), stts[-1], times[-1]), (3, (1, 0), 1900000))
                        times = times[:3]                    # is counted in nb_frames but not listed as a packet
                        stts = stts[:3]
                    self.assertEqual([p["dts"] - packets[0]["dts"] for p in packets], times)   # ffprobe adds elst
                    self.assertEqual([p["duration"] for p in packets], [d for c, d in stts for _ in range(c)])
                    keys = [n for n, p in enumerate(packets, 1) if p["flags"].startswith("K")]
                    self.assertEqual(keys, stss if stss is not None else list(range(1, len(times) + 1)))

    def test_last_keyframe_by_hand_f1(self):
        moments = {0: (1, 1), 100: (4, 1), 132: (5, 5), 200: (7, 5), 300: (10, 9), 395: (12, 9)}
        for t, answer in moments.items():
            with self.subTest(t=t):
                self.assertEqual(last_keyframe([(12, 33)], [1, 5, 9], t), answer)

    def test_registry(self):
        tree = boxes.walk(F1)
        self.assertEqual(boxes.decode(F1, boxes.find(tree, STBL + "/stts")), {"entries": [(12, 33)]})
        self.assertEqual(boxes.decode(F1, boxes.find(tree, STBL + "/stss")), {"sample_number": [1, 5, 9]})

    def test_cmd_dump_find_stss(self):
        printed = run_cli("dump", "testfiles/out/f1.mp4", "--find", "stss")
        self.assertEqual(printed, EXPECTED.read_text())
        self.assertTrue(printed.rstrip().endswith("sample_number=[1, 5, 9]"))

    def test_cmd_dump_find_stss_none(self):
        self.assertEqual(run_cli_code("dump", "testfiles/out/aac-only.m4a", "--find", "stss"), (0, "no stss box\n"))

    def test_cmd_dump_find_stts(self):
        self.assertEqual(run_cli("dump", "testfiles/out/aac-only.m4a", "--find", "stts"),
                         "moov/trak/mdia/minf/stbl/stts 16996 32 entries=[(87, 1024), (1, 136)]\n")
