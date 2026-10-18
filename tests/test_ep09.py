import re
import unittest
from pathlib import Path
from mp4kit import boxes
from tests.util import data, run_cli

PHONE, NOMOOV = data("phone.mp4"), data("broken-nomoov.mp4")
TRACE_RE = re.compile(r"type:'(.{4})' parent:'(\w+|.{4})' sz: (\d+) ")
OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"


def flat(tree, parent="root"):
    for b in tree:
        yield (b.type, parent, b.size)
        yield from flat(b.children, b.type)


class Ep09(unittest.TestCase):
    def test_walk_matches_ffprobe_trace(self):
        for f in sorted(OUT.glob("*.mp4")) + sorted(OUT.glob("*.m4a")):
            trace = CAPS / f"{f.name}.trace.txt"
            if not trace.exists() or (CAPS / f"{f.name}.walk-error.txt").exists():
                continue
            with self.subTest(f=f.name):
                want = [m.groups() for m in TRACE_RE.finditer(trace.read_text())]
                want = [(t, p, int(s)) for t, p, s in want]
                got = list(flat(boxes.walk(f.read_bytes())))
                for item in want:     # ffprobe names a sample entry's children with parent stsd
                    in_entry = item[1] == "stsd" and any(g[0] == item[0] and g[2] == item[2] for g in got)
                    self.assertTrue(item in got or in_entry, item)

    def test_child_overrunning_parent_raises(self):
        blob = bytearray(PHONE)
        tkhd = 108868                                      # in the first trak: 108860 + 1454 = 110314
        blob[tkhd:tkhd + 4] = (2000).to_bytes(4, "big")    # past its trak's end, still inside the file
        with self.assertRaisesRegex(boxes.BoxError, "tkhd at 108868: size 2000 runs past the end \\(110314\\)"):
            boxes.walk(bytes(blob))

    def test_dump_nomoov(self):
        self.assertEqual(run_cli("dump", "testfiles/out/broken-nomoov.mp4").splitlines()[-1], "no moov box")

    def test_dump_phone_first_lines(self):
        lines = run_cli("dump", "testfiles/out/phone.mp4").splitlines()
        self.assertEqual(lines[:5], ["ftyp 0 32 major=isom minor=512 brands=['isom', 'iso2', 'avc1', 'mp41']",
                                     "free 32 8", "mdat 40 108704", "moov 108744 3412", "  mvhd 108752 108"])
