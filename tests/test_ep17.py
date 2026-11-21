import json
import struct
import unittest
from pathlib import Path
from mp4kit import boxes, nal, tables, timing
from tests.util import data, run_cli

F1, F2, PHONE = data("f1.mp4"), data("f2.mp4"), data("phone.mp4")
OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep17.txt"
STBL = "mdia/minf/stbl"


def traks(contents):
    """A file's trak boxes, in file order."""
    return boxes.find_all(boxes.walk(contents), "moov/trak")


def ctts_of(contents, track=1):
    """read_ctts of a track's ctts box ([] when it has none)."""
    return tables.read_ctts(contents, boxes.find(traks(contents)[track - 1].children, f"{STBL}/ctts"))


def ctts_box(version, rows):
    """A hand-packed ctts box: version and flags, entry_count, then (sample_count, sample_offset) rows."""
    fmt = ">Ii" if version == 1 else ">II"
    payload = struct.pack(">B3xI", version, len(rows)) + b"".join(struct.pack(fmt, *row) for row in rows)
    return struct.pack(">I4s", 8 + len(payload), b"ctts") + payload


class Ep17(unittest.TestCase):
    def test_read_ctts_f2(self):
        box = boxes.find(traks(F2)[0].children, f"{STBL}/ctts")
        self.assertEqual((box.start, box.size, boxes.read_fullbox(F2, box)), (21407, 88, (0, 0)))  # version 0
        self.assertEqual(ctts_of(F2), [(1, 33), (1, 99), (2, 0)] * 3)                           # 9 entries

    def test_read_ctts_phone(self):
        video = ctts_of(PHONE, 1)
        self.assertEqual((len(video), video[:3]), (44, [(1, 1024), (1, 2048), (2, 512)]))
        self.assertEqual(sum(count for count, _ in video), 60)
        self.assertEqual(ctts_of(PHONE, 2), [])                                                 # audio: no ctts
        self.assertEqual(ctts_of(F1), [])                                                       # no B-frames

    def test_read_ctts_version1_signed(self):
        rows = [(1, 0), (1, 66), (2, -33)]                    # no committed file has version 1 (all are 0)
        v1 = ctts_box(1, rows)
        box = boxes.read_header(v1, 0)
        self.assertEqual(v1[-4:].hex(), "ffffffdf")                                            # -33, two's complement
        self.assertEqual(tables.read_ctts(v1, box), rows)
        v0 = v1[:8] + b"\x00" + v1[9:]                        # the same bytes stamped version 0: read unsigned
        self.assertEqual(tables.read_ctts(v0, boxes.read_header(v0, 0))[2], (2, 4294967263))
        self.assertEqual(timing.composition_times([0, 33, 66, 99], rows), [0, 99, 33, 66])   # B-frames, no delay

    def test_composition_times_f2(self):
        dts = timing.decode_times([(12, 33)])
        cts = timing.composition_times(dts, ctts_of(F2))
        self.assertEqual(cts, [33, 132, 66, 99, 165, 264, 198, 231, 297, 396, 330, 363])
        offsets = [offset for count, offset in ctts_of(F2) for _ in range(count)]
        self.assertEqual(cts, [d + o for d, o in zip(dts, offsets)])                         # CT = DT + offset
        self.assertEqual(timing.composition_times(dts, []), dts)                              # no ctts: CT = DT

    def test_display_order_f2(self):
        samples = tables.sample_table(F2, traks(F2)[0])
        self.assertEqual([s.number for s in samples], list(range(1, 13)))                      # decode order
        self.assertEqual([s.number for s in sorted(samples, key=lambda s: s.cts)],
                         [1, 3, 4, 2, 5, 7, 8, 6, 9, 11, 12, 10])                              # display order
        self.assertEqual(samples[1], tables.Sample(2, 33, 132, 311, 5629, False))            # decoded 2nd, shown 4th

    def test_sample_table_phone_cts(self):
        video, audio = [tables.sample_table(PHONE, t) for t in traks(PHONE)]
        self.assertEqual([(s.dts, s.cts) for s in video[:4]],
                         [(0, 1024), (512, 2560), (1024, 1536), (1536, 2048)])                 # DT + 1024, 2048, 512
        self.assertTrue(all(s.cts == s.dts for s in audio))                                    # no ctts in audio

    def test_cts_matches_ffprobe_pts(self):
        for f in sorted(OUT.glob("*.mp4")) + sorted(OUT.glob("*.m4a")):
            if f.name in ("broken-nomoov.mp4", "frag-cmaf.mp4", "phone-sidx.mp4"):  # no moov; samples in moof
                continue
            captured = json.loads((CAPS / f"{f.name}.probe.json").read_text())
            for index, trak in enumerate(traks(f.read_bytes())):
                samples = tables.sample_table(f.read_bytes(), trak)
                packets = [p for p in captured["packets"] if p["stream_index"] == index]
                if f.name == "phone-chapters.mp4" and index == 2:    # ffprobe reads it as chapters, no packets
                    continue
                with self.subTest(f=f.name, track=index + 1):
                    shift = samples[0].dts - packets[0]["dts"]       # ffprobe applies the edit list (episode 18)
                    self.assertIn(shift, (0, 33, 1024))
                    self.assertEqual([p["pts"] + shift for p in packets], [s.cts for s in samples[:len(packets)]])

    def test_poc_order_phone(self):
        trak = traks(PHONE)[0]
        avcc = tables.read_avcc(PHONE, boxes.find(trak.children, f"{STBL}/stsd/avc1/avcC"))
        sps, pps = nal.parse_sps(avcc["SPS"][0]), nal.parse_pps(avcc["PPS"][0])
        self.assertEqual((sps["pic_order_cnt_type"], sps["log2_max_poc_lsb"]), (0, 6))
        samples, order, idr = tables.sample_table(PHONE, trak), [], 0
        for s in samples:
            first = [u for _, u in nal.iter_length_prefixed(PHONE, s.offset, s.offset + s.size)
                     if nal.nal_header(u[0])[2] in (1, 5)][0]
            idr = idr + (nal.nal_header(first[0])[2] == 5)                  # POC counts again from each IDR
            order.append((idr, nal.read_slice_header(first, sps, pps)["pic_order_cnt_lsb"], s.number))
        self.assertEqual([lsb for _, lsb, _ in order[:5]], [0, 6, 2, 4, 12])
        self.assertEqual([n for _, _, n in sorted(order)], [s.number for s in sorted(samples, key=lambda s: s.cts)])

    def test_access_units_f1(self):
        sps, pps = nal._avcc_params_stopgap(F1)
        start, end = nal._mdat_range_stopgap(F1)
        stream = nal.to_annexb([sps, pps] + [u for _, u in nal.iter_length_prefixed(F1, start, end)])
        units = nal.access_units(nal.split_annexb(stream))                                     # episode 5's stream
        self.assertEqual(len(units), 12)
        self.assertEqual([nal.nal_header(u[0])[2] for u in units[0]], [7, 8, 5])
        self.assertTrue(all(len(unit) == 1 for unit in units[1:]))

    def test_access_units_rules(self):
        idr, second_slice, p, aud = b"\x65\x88", b"\x65\x40", b"\x41\x9a", b"\x09\xf0"     # 0x40: first_mb 1
        self.assertEqual(nal.access_units([idr, second_slice, p]), [[idr, second_slice], [p]])
        self.assertEqual(nal.access_units([aud, idr, aud, p]), [[aud, idr], [aud, p]])

    def test_ctts_count_error(self):
        blob = bytearray(F2)
        self.assertEqual(blob[21487:21491].hex(), "00000002")                               # last run: 2 samples
        blob[21490] = 1
        with self.assertRaisesRegex(boxes.BoxError, "ctts at 21407: ctts has 11 samples, stts 12"):
            tables.sample_table(bytes(blob), traks(bytes(blob))[0])

    def test_dump_ctts(self):
        self.assertEqual(run_cli("dump", "testfiles/out/f2.mp4", "--find", "ctts"),
                         "moov/trak/mdia/minf/stbl/ctts 21407 88 version=0 entries=[(1, 33), (1, 99), (2, 0), "
                         "(1, 33), (1, 99), (2, 0), (1, 33), (1, 99), (2, 0)]\n")

    def test_cmd_samples_f2_pts(self):
        # ep18 applies the edit list to --pts: dts and pts on the movie's timeline; tag ep17 keeps its own test
        printed = run_cli("samples", "testfiles/out/f2.mp4", "--pts")
        lines = printed.splitlines()
        self.assertEqual(lines[:4], ["track 1 vide, timescale 1000, 12 samples",
                                     "sample dts pts display key offset size",
                                     "1 -33 0 1 K 40 5589", "2 0 99 4 - 5629 311"])
        at_ep17 = [line.split() for line in EXPECTED.read_text().splitlines()[2:]]   # dts and cts, no edit list
        self.assertEqual(lines[2:], [" ".join([n, str(int(d) - 33), str(int(c) - 33), *rest])     # f2's media_time 33
                                     for n, d, c, *rest in at_ep17])
        self.assertEqual(run_cli("samples", "testfiles/out/f2.mp4").splitlines()[1], "sample dts key offset size")
