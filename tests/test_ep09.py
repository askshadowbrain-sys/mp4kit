import re
import unittest
from pathlib import Path
from mp4kit import boxes
from tests.util import data, run_cli, run_cli_code

PHONE, NOMOOV = data("phone.mp4"), data("broken-nomoov.mp4")
TRACE_RE = re.compile(r"type:'(.{4})' parent:'(\w+|.{4})' sz: (\d+) ")
OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"


def flat(tree, parent="root"):
    """(type, parent, size) per box, as ffprobe's trace prints it: a largesize box's sz leaves out the 8 bytes
    of its 64-bit size (phone-large.mp4's mdat: 108712 in the file, sz 108704 in the trace)."""
    for b in tree:
        yield (b.type, parent, b.size - 8 if b.header == 16 else b.size)
        yield from flat(b.children, b.type)


class Ep09(unittest.TestCase):
    def test_walk_matches_ffprobe_trace(self):
        for f in sorted(OUT.glob("*.mp4")) + sorted(OUT.glob("*.m4a")):
            trace = CAPS / f"{f.name}.trace.txt"
            if not trace.exists():     # walk-error.txt files are walk.py's errors, not mp4kit's: walk them too
                continue
            with self.subTest(f=f.name):
                want = [m.groups() for m in TRACE_RE.finditer(trace.read_text())]
                want = [(t, p, int(s)) for t, p, s in want]
                got = list(flat(boxes.walk(f.read_bytes())))
                for item in want:     # ffprobe names a sample entry's children with parent stsd
                    in_entry = item[1] == "stsd" and any(g[0] == item[0] and g[2] == item[2] for g in got)
                    self.assertTrue(item in got or in_entry, item)

    def test_walk_reads_every_test_file(self):
        files = sorted(OUT.glob("*.mp4")) + sorted(OUT.glob("*.m4a"))
        self.assertEqual(len(files), 16)
        for f in files:
            with self.subTest(f=f.name):
                self.assertEqual(run_cli_code("dump", str(f))[0], 0)

    def test_tables(self):
        self.assertEqual(boxes.CONTAINERS, {"moov", "trak", "mdia", "minf", "stbl", "dinf", "edts", "udta", "mvex",
                                            "moof", "traf", "mfra", "sinf", "schi"})
        self.assertEqual(boxes.CHILD_OFFSET, {"stsd": 8, "dref": 8, "meta": 4, "avc1": 78, "hvc1": 78, "hev1": 78,
                                              "av01": 78, "encv": 78, "mp4a": 28, "enca": 28})

    def test_read_mp4(self):
        self.assertEqual(boxes.read_mp4(OUT / "f1.mp4"), data("f1.mp4"))

    def test_child_overrunning_parent_raises(self):
        blob = bytearray(PHONE)
        tkhd = 108868                                      # in the first trak: 108860 + 1454 = 110314
        blob[tkhd:tkhd + 4] = (2000).to_bytes(4, "big")    # past its trak's end, still inside the file
        with self.assertRaisesRegex(boxes.BoxError, "tkhd at 108868: size 2000 runs past the end \\(110314\\)"):
            boxes.walk(bytes(blob))

    def test_dump_nomoov(self):
        self.assertEqual(run_cli("dump", "testfiles/out/broken-nomoov.mp4").splitlines()[-1], "no moov box")

    def test_dump_nomoov_whole(self):
        code, printed = run_cli_code("dump", "testfiles/out/broken-nomoov.mp4")
        self.assertEqual(code, 0)
        self.assertEqual(printed.splitlines(),
                         ["ftyp 0 32 major=isom minor=512 brands=['isom', 'iso2', 'avc1', 'mp41']",
                          "free 32 8", "mdat 40 108704", "no moov box"])

    def test_dump_phone_first_lines(self):
        lines = run_cli("dump", "testfiles/out/phone.mp4").splitlines()
        # ep10 decodes mvhd; tag ep09 keeps its own test
        self.assertEqual(lines[:5], ["ftyp 0 32 major=isom minor=512 brands=['isom', 'iso2', 'avc1', 'mp41']",
                                     "free 32 8", "mdat 40 108704", "moov 108744 3412",
                                     "  mvhd 108752 108 version=0 timescale=48000 duration=96000 seconds=2.0 rate=1.0"
                                     " volume=1.0 next_track_ID=3"])
