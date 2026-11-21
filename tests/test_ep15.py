import json
import struct
import unittest
from pathlib import Path
from mp4kit import boxes, tables
from tests.util import data, run_cli

F1, PHONE, LARGE = data("f1.mp4"), data("phone.mp4"), data("phone-large.mp4")
OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep15.txt"
STBL = "moov/trak/mdia/minf/stbl"


def drawers(contents):
    """(stsc, stco or co64, stsz) for every track of a file, in file order."""
    found = []
    for trak in boxes.find_all(boxes.walk(contents), "moov/trak"):
        stbl = boxes.find(trak.children, "mdia/minf/stbl")
        offsets = boxes.find(stbl.children, "stco") or boxes.find(stbl.children, "co64")
        found.append((tables.read_stsc(contents, boxes.find(stbl.children, "stsc")),
                      tables.read_stco(contents, offsets),
                      tables.read_stsz(contents, boxes.find(stbl.children, "stsz"))))
    return found


def sample_offset(stsc, stco, stsz, n):
    """By hand, as ep15 does it on screen (ep16's sample_table does it for every sample): find sample n's chunk by
    counting chunk_sizes, then add the sizes of the samples before it in that chunk to the chunk's offset."""
    first = 1                                                       # the first sample in the chunk
    for chunk, count in enumerate(tables.chunk_sizes(stsc, len(stco))):
        if n < first + count:
            return stco[chunk] + sum(stsz[first - 1:n - 1])
        first = first + count


def chunk_spans(stsc, stco, stsz):
    """(offset, bytes) of every chunk: its offset from stco, and the sum of its samples' sizes from stsz."""
    spans = []
    first = 0
    for offset, count in zip(stco, tables.chunk_sizes(stsc, len(stco))):
        spans.append((offset, sum(stsz[first:first + count])))
        first = first + count
    return spans


class Ep15(unittest.TestCase):
    def test_drawers_3_to_5_in_f1(self):
        stbl = boxes.find(boxes.walk(F1), STBL)
        self.assertEqual([(c.type, c.start, c.size) for c in stbl.children][3:],
                         [("stsc", 22638, 40), ("stsz", 22678, 68), ("stco", 22746, 32)])
        self.assertEqual(22746 + 32, stbl.end)                                     # stco is stbl's last box

    def test_read_stsc_f1(self):
        stsc = boxes.find(boxes.walk(F1), STBL + "/stsc")
        self.assertEqual(F1[22638:22678].hex(), "00000028" "73747363" "00000000" "00000002"
                         "00000001" "00000004" "00000001" "00000003" "00000002" "00000001")
        self.assertEqual(tables.read_stsc(F1, stsc), [(1, 4, 1), (3, 2, 1)])

    def test_read_stco_f1(self):
        stco = boxes.find(boxes.walk(F1), STBL + "/stco")
        self.assertEqual(F1[22746:22778].hex(), "00000020" "7374636f" "00000000" "00000004"
                         "00000028" "000019c6" "00003814" "0000529d")
        self.assertEqual(tables.read_stco(F1, stco), [40, 6598, 14356, 21149])    # 0x28, 0x19c6, 0x3814, 0x529d

    def test_read_stsz_f1(self):
        stsz = boxes.find(boxes.walk(F1), STBL + "/stsz")
        self.assertEqual(F1[22678:22698].hex(), "00000044" "7374737a" "00000000" "00000000" "0000000c")
        self.assertEqual(F1[22698:22702].hex(), "000014b9")                        # 0x14b9 = 5305
        sizes = tables.read_stsz(F1, stsz)
        self.assertEqual(sizes, [5305, 362, 432, 459, 6210, 499, 510, 539, 6356, 437, 489, 419])
        self.assertEqual(sum(sizes), 22017)                                        # mdat 32 22025: its payload

    def test_read_stsz_constant(self):
        blob = struct.pack(">I4sIII", 20, b"stsz", 0, 1024, 3)                    # sample_size 1024, no entries
        self.assertEqual(tables.read_stsz(blob, boxes.read_header(blob, 0)), [1024, 1024, 1024])

    def test_read_stsz_overrun(self):
        blob = bytearray(F1[22678:22746])
        blob[19] = 13                                                              # sample_count 13, room for 12
        with self.assertRaisesRegex(boxes.BoxError, "stsz at 0: sample_count 13 needs 72 bytes, box has 68"):
            tables.read_stsz(bytes(blob), boxes.read_header(bytes(blob), 0))

    def test_read_co64_phone_large(self):
        video, audio = boxes.find_all(boxes.walk(LARGE), "moov/trak")
        co64 = boxes.find(video.children, "mdia/minf/stbl/co64")
        self.assertEqual((co64.start, co64.size), (110062, 488))                   # 16 + 59 x 8
        self.assertEqual(LARGE[110062:110086].hex(), "000001e8" "636f3634" "00000000" "0000003b"
                         "0000000000000030")                                       # 59 entries, the first 48
        self.assertIsNone(boxes.find(video.children, "mdia/minf/stbl/stco"))
        phone_video, phone_audio = boxes.find_all(boxes.walk(PHONE), "moov/trak")
        for trak, phone_trak in ((video, phone_video), (audio, phone_audio)):
            with self.subTest(start=trak.start):
                self.assertEqual(tables.read_stco(LARGE, boxes.find(trak.children, "mdia/minf/stbl/co64")),
                                 tables.read_stco(PHONE, boxes.find(phone_trak.children, "mdia/minf/stbl/stco")))

    def test_read_co64_in_memory(self):
        blob = struct.pack(">I4sIIQQ", 32, b"co64", 0, 2, 48, 5_000_000_000)      # past 4 GiB: needs 64 bits
        self.assertEqual(tables.read_stco(blob, boxes.read_header(blob, 0)), [48, 5_000_000_000])

    def test_chunk_sizes(self):
        self.assertEqual(tables.chunk_sizes([(1, 4, 1), (3, 2, 1)], 4), [4, 4, 2, 2])
        self.assertEqual(tables.chunk_sizes([(1, 2, 1), (2, 1, 1)], 59), [2] + [1] * 58)      # phone video
        self.assertEqual(tables.chunk_sizes([(1, 1, 1), (2, 2, 1), (3, 1, 1)], 3), [1, 2, 1])  # subs' subtitle
        self.assertEqual(tables.chunk_sizes([(1, 88, 1)], 1), [88])                            # aac-only
        self.assertEqual(tables.chunk_sizes([], 0), [])                                        # frag-cmaf

    def test_phone_drawers(self):
        (vstsc, vstco, vstsz), (astsc, astco, astsz) = drawers(PHONE)
        self.assertEqual((vstsc, len(vstco), len(vstsz)), ([(1, 2, 1), (2, 1, 1)], 59, 60))
        self.assertEqual((len(astsc), astsc[:3], len(astco), len(astsz)), (51, [(1, 1, 1), (2, 2, 1), (4, 1, 1)],
                                                                           59, 95))
        self.assertEqual(sum(tables.chunk_sizes(astsc, len(astco))), 95)

    def test_sample_offsets_by_hand_f1(self):
        stsc, stco, stsz = drawers(F1)[0]
        answers = {1: 40, 5: 6598, 7: 13307, 12: 21638}
        for n, offset in answers.items():
            with self.subTest(sample=n):
                self.assertEqual(sample_offset(stsc, stco, stsz, n), offset)
        self.assertEqual(6598 + 6210 + 499, 13307)                                 # sample 7: chunk 2, third
        self.assertEqual(F1[13307:13312].hex(), "000001fa41")                      # 506 = 510 - 4, then a slice

    def test_chunks_fill_mdat(self):
        f1 = chunk_spans(*drawers(F1)[0])
        self.assertEqual(f1, [(40, 6558), (6598, 7758), (14356, 6793), (21149, 908)])
        self.assertEqual([offset + size for offset, size in f1], [6598, 14356, 21149, 22057])  # 22057 = moov
        spans = sorted(span for track in drawers(PHONE) for span in chunk_spans(*track))
        self.assertEqual(spans[:3], [(48, 7963), (8011, 238), (8249, 1040)])       # video, audio, video
        ends = [offset + size for offset, size in spans]
        self.assertEqual([offset for offset, _ in spans[1:]], ends[:-1])           # no gaps, no overlaps
        self.assertEqual((spans[0][0], ends[-1], len(spans)), (48, 108744, 118))   # mdat's payload, 59 + 59

    def test_matches_ffprobe(self):
        for f in sorted(OUT.glob("*.mp4")) + sorted(OUT.glob("*.m4a")):
            if f.name in ("broken-nomoov.mp4", "frag-cmaf.mp4", "phone-sidx.mp4"):  # no moov; samples in moof
                continue
            captured = json.loads((CAPS / f"{f.name}.probe.json").read_text())
            for index, (stsc, stco, stsz) in enumerate(drawers(f.read_bytes())):
                packets = [p for p in captured["packets"] if p["stream_index"] == index]
                with self.subTest(f=f.name, track=index + 1):
                    self.assertEqual(sum(tables.chunk_sizes(stsc, len(stco))), len(stsz))
                    self.assertEqual(len(stsz), int(captured["streams"][index]["nb_frames"]))
                    positions = [sample_offset(stsc, stco, stsz, n) for n in range(1, len(packets) + 1)]
                    self.assertEqual([int(p["pos"]) for p in packets], positions)
                    self.assertEqual([int(p["size"]) for p in packets], stsz[:len(packets)])   # subs: 3 of 4

    def test_sample_description_index(self):
        for f in sorted(OUT.glob("*.mp4")) + sorted(OUT.glob("*.m4a")):
            if f.name == "broken-nomoov.mp4":
                continue
            for index, (stsc, _, _) in enumerate(drawers(f.read_bytes())):
                with self.subTest(f=f.name, track=index + 1):
                    self.assertTrue(all(row[2] == 1 for row in stsc))              # one sheet in every stsd

    def test_registry(self):
        tree = boxes.walk(F1)
        self.assertEqual(boxes.decode(F1, boxes.find(tree, STBL + "/stsc")),
                         {"entries": [(1, 4, 1), (3, 2, 1)], "chunk_sizes": [4, 4, 2, 2]})
        self.assertEqual(boxes.decode(F1, boxes.find(tree, STBL + "/stco")),
                         {"chunk_offset": [40, 6598, 14356, 21149]})
        self.assertEqual(boxes.decode(F1, boxes.find(tree, STBL + "/stsz"))["entry_size"][:2], [5305, 362])

    def test_cmd_dump_find_stsc(self):
        printed = run_cli("dump", "testfiles/out/f1.mp4", "--find", "stsc")
        self.assertEqual(printed, EXPECTED.read_text())
        self.assertTrue(printed.rstrip().endswith("chunk_sizes=[4, 4, 2, 2]"))

    def test_cmd_dump_find_co64(self):
        lines = run_cli("dump", "testfiles/out/phone-large.mp4", "--find", "co64").splitlines()
        self.assertEqual([line.split(" chunk_offset=[")[0] for line in lines],
                         ["moov/trak/mdia/minf/stbl/co64 110062 488", "moov/trak/mdia/minf/stbl/co64 112025 488"])
        self.assertTrue(lines[1].split("=")[1].startswith("[8011, 9289, "))
        stsc = run_cli("dump", "testfiles/out/phone-large.mp4", "--find", "stsc").splitlines()[0]
        self.assertTrue(stsc.endswith("chunk_sizes=[2" + ", 1" * 58 + "]"))       # 59 chunks, counted from co64
