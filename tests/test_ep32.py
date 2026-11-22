import contextlib
import csv
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from mp4kit import boxes, cli, frag, mux, tables
from tests.util import data, run_cli, run_cli_code

OUT = Path(__file__).parents[1] / "testfiles" / "out"
EXPECTED = Path(__file__).parents[1] / "expected"


def ffmpeg(*argv):
    """Run ffprobe or ffmpeg (required from ep29: a written file is judged by ffmpeg) and return (exit code, stdout,
    stderr)."""
    if shutil.which(argv[0]) is None:
        raise AssertionError(f"{argv[0]} required from ep29")
    done = subprocess.run(argv, capture_output=True)
    return done.returncode, done.stdout, done.stderr


def packets(path):
    """ffprobe's packets, per stream: (pts, dts, duration, size, flags)."""
    out = ffmpeg("ffprobe", "-v", "error", "-show_entries", "packet=stream_index,pts,dts,duration,size,flags",
                 "-of", "csv=p=0", str(path))[1].decode()
    rows = {}
    for st, pts, dts, duration, size, flags, *_ in csv.reader(io.StringIO(out)):
        rows.setdefault(int(st), []).append((int(pts), int(dts), int(duration), int(size), flags))
    return rows


def phone():
    contents = data("phone.mp4")
    return contents, tables.read_tracks(contents, boxes.walk(contents))


def terrace():
    out = frag.fragment(data("phone.mp4"))
    return out, boxes.walk(out)


class Ep32(unittest.TestCase):
    def test_write_init(self):
        contents, tracks = phone()
        trays = [contents[b.start:b.end] for b in boxes.find_all(boxes.walk(contents), "moov/trak/mdia/minf/stbl/stsd")]
        init = frag.write_init(tracks, trays)
        tree = boxes.walk(init)
        self.assertEqual([(b.type, b.start, b.size) for b in tree], [("ftyp", 0, 28), ("moov", 28, 1225)])
        self.assertEqual(boxes.read_ftyp(init, tree[0])["brands"], ["iso5", "iso6", "mp41"])
        self.assertEqual([b.type for b in tree[1].children], ["mvhd", "trak", "trak", "mvex"])   # mvex after the traks
        self.assertEqual(tables.read_mvhd(init, tree[1].children[0])["duration"], 0)
        for trak, track, tray in zip(boxes.find_all(tree, "moov/trak"), tracks, trays):
            self.assertEqual(tables.read_tkhd(init, boxes.find(trak.children, "tkhd"))["duration"], 0)
            self.assertEqual(tables.read_mdhd(init, boxes.find(trak.children, "mdia/mdhd"))["duration"], 0)
            self.assertEqual(tables.read_elst(init, boxes.find(trak.children, "edts/elst")), [(0, 1024, 1, 0)])
            stsd = boxes.find(trak.children, "mdia/minf/stbl/stsd")
            self.assertEqual(init[stsd.start:stsd.end], tray)                       # the sheets, as they are
        self.assertEqual([frag.read_trex(init, b) for b in boxes.find_all(tree, "moov/mvex/trex")],
                         [{"track_ID": n, "sample_description_index": 1, "default_sample_duration": 0,
                           "default_sample_size": 0, "default_sample_flags": 0} for n in (1, 2)])
        back = tables.read_tracks(init, tree)
        self.assertEqual([(t.id, t.handler, t.timescale, len(t.samples)) for t in back],
                         [(1, "vide", 15360, 0), (2, "soun", 48000, 0)])
        self.assertEqual([t.entry for t in back], [t.entry for t in tracks])

    def test_write_fragment(self):
        _, tracks = phone()
        video = tracks[0]
        video.payloads = [bytes([n]) * s.size for n, s in enumerate(video.samples)]
        piece = frag.write_fragment(7, [(video, video.samples[30:33])])
        tree = boxes.walk(piece)
        self.assertEqual([b.type for b in tree], ["moof", "mdat"])
        moof = tree[0]
        self.assertEqual(boxes.u32(piece, boxes.find(moof.children, "mfhd").payload + 4), 7)
        traf = boxes.find(moof.children, "traf")
        tfhd = frag.read_tfhd(piece, boxes.find(traf.children, "tfhd"))
        trun = frag.read_trun(piece, boxes.find(traf.children, "trun"))
        self.assertEqual(tfhd, {"flags": 0x020000, "track_ID": 1})                 # default-base-is-moof, no defaults
        self.assertEqual(frag.read_tfdt(piece, boxes.find(traf.children, "tfdt")), 15360)
        self.assertEqual((trun["version"], trun["flags"], trun["sample_count"]), (0, 0x000F01, 3))
        self.assertEqual(trun["data_offset"], moof.size + 8)                      # the first byte after mdat's header
        self.assertEqual(trun["sample_flags"], [0x02000000, 0x01010000, 0x01010000])
        trex = {"default_sample_duration": 0, "default_sample_size": 0, "default_sample_flags": 0}
        got = frag.traf_samples(piece, moof, traf, trex, moof.start)
        self.assertEqual([(s.dts, s.cts, s.size, s.key) for s in got],
                         [(s.dts, s.cts, s.size, s.key) for s in video.samples[30:33]])
        self.assertEqual(piece[got[0].offset:got[0].offset + 3], bytes([30]) * 3)

    def test_negative_slips_take_trun_version_1(self):
        _, tracks = phone()
        video = tracks[0]
        video.payloads = [b"\0" * s.size for s in video.samples]
        moved = [tables.Sample(s.number, s.dts, s.cts - 1024, s.size, 0, s.key) for s in video.samples[:3]]
        piece = frag.write_fragment(1, [(video, moved)])
        trun = frag.read_trun(piece, boxes.find_all(boxes.walk(piece), "moof/traf/trun")[0])
        self.assertEqual((trun["version"], trun["sample_composition_time_offset"]), (1, [0, 1024, -512]))

    def test_fragment_keeps_phones_samples(self):
        _, tracks = phone()
        out, tree = terrace()
        self.assertEqual([(b.type, b.start, b.size) for b in tree],
                         [("ftyp", 0, 28), ("moov", 28, 1225), ("moof", 1253, 1352), ("mdat", 2605, 53166),
                          ("moof", 55771, 1432), ("mdat", 57203, 55546)])
        got = frag.fragment_samples(out, tree)
        source = data("phone.mp4")
        for track in tracks:
            mine = got[track.id]
            self.assertEqual([(s.dts, s.cts, s.size, s.key) for s in mine],
                             [(s.dts, s.cts, s.size, s.key) for s in track.samples])
            self.assertEqual([out[s.offset:s.offset + s.size] for s in mine],
                             [source[s.offset:s.offset + s.size] for s in track.samples])
        self.assertEqual([sum(s.chunk == n for s in got[1]) for n in (1, 2)], [30, 30])
        self.assertEqual([sum(s.chunk == n for s in got[2]) for n in (1, 2)], [45, 50])
        self.assertEqual([s.number for s in got[1] if s.key], [1, 31])           # each piece opens with a keyframe

    def test_sound_cut_follows_the_timeline(self):
        _, (video, sound) = phone()
        cut = mux.timeline(video)[30]                                           # (15,360 - 1,024) / 15,360 s
        sound_times = mux.timeline(sound)
        self.assertEqual((float(cut), float(sound_times[44]), float(sound_times[45])),
                         (14336 / 15360, 44032 / 48000, 45056 / 48000))
        self.assertTrue(sound_times[44] < cut <= sound_times[45])               # sound 45 before, 46 after

    def test_rfc8216_section_3_3(self):
        out, tree = terrace()
        self.assertIn("iso6", boxes.read_ftyp(out, tree[0])["brands"])
        tracks = [tables.read_tkhd(out, b)["track_ID"] for b in boxes.find_all(tree, "moov/trak/tkhd")]
        for traf in boxes.find_all(tree, "moof/traf"):
            tfhd = frag.read_tfhd(out, boxes.find(traf.children, "tfhd"))
            self.assertIn(tfhd["track_ID"], tracks)
            self.assertIsNotNone(boxes.find(traf.children, "tfdt"))
            self.assertNotIn("base_data_offset", tfhd)
            self.assertTrue(tfhd["flags"] & frag.DEFAULT_BASE_IS_MOOF)
        for stsz in boxes.find_all(tree, "moov/trak/mdia/minf/stbl/stsz"):
            self.assertEqual(tables.read_stsz(out, stsz), [])
        self.assertEqual([b.type for b in boxes.find_all(tree, "moov/trak/mdia/minf/dinf/dref")[0].children],
                         ["url "])
        self.assertEqual(boxes.find_all(tree, "moov/trak/mdia/minf/dinf/dref/url ")[0].size, 12)   # flags 1, no URL

    def test_playlist_for_frag_cmaf(self):
        with contextlib.redirect_stdout(io.StringIO()):
            init, pieces = cli._print_terrace(data("frag-cmaf.mp4"))
        self.assertEqual((init, pieces), ((1242, 0), [(53774, 1242, 1.0), (56374, 55016, 1.0)]))   # plan row 298
        text = frag.hls_playlist("frag-cmaf.mp4", init, pieces)
        self.assertIn('#EXT-X-MAP:URI="frag-cmaf.mp4",BYTERANGE="1242@0"\n', text)
        self.assertIn("#EXTINF:1.000000,\n#EXT-X-BYTERANGE:53774@1242\nfrag-cmaf.mp4\n", text)
        self.assertIn("#EXTINF:1.000000,\n#EXT-X-BYTERANGE:56374@55016\nfrag-cmaf.mp4\n", text)

    def test_hls_playlist(self):
        text = frag.hls_playlist("a.mp4", (100, 0), [(10, 100, 1.4), (20, 110, 2.5), (5, 130, 0.25)])
        self.assertEqual(text.splitlines(), [
            "#EXTM3U", "#EXT-X-VERSION:6", "#EXT-X-TARGETDURATION:3", "#EXT-X-MEDIA-SEQUENCE:0",
            "#EXT-X-PLAYLIST-TYPE:VOD", "#EXT-X-INDEPENDENT-SEGMENTS", '#EXT-X-MAP:URI="a.mp4",BYTERANGE="100@0"',
            "#EXTINF:1.400000,", "#EXT-X-BYTERANGE:10@100", "a.mp4", "#EXTINF:2.500000,", "#EXT-X-BYTERANGE:20@110",
            "a.mp4", "#EXTINF:0.250000,", "#EXT-X-BYTERANGE:5@130", "a.mp4", "#EXT-X-ENDLIST"])
        self.assertTrue(text.endswith("#EXT-X-ENDLIST\n"))

    def test_cmd_frag(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_cli("frag", str(OUT / "phone.mp4"), "-o", f"{tmp}/frag.mp4", "--hls", f"{tmp}/frag.m3u8")
            self.assertEqual(out, (EXPECTED / "ep32.txt").read_text())
            self.assertEqual(Path(f"{tmp}/frag.m3u8").read_text(), (EXPECTED / "ep32.m3u8").read_text())
            for played in (f"{tmp}/frag.mp4", f"{tmp}/frag.m3u8"):
                self.assertEqual(ffmpeg("ffmpeg", "-v", "error", "-i", played, "-f", "null", "-"), (0, b"", b""))
            code, probe, _ = ffmpeg("ffprobe", "-v", "error", "-show_streams", "-show_packets", "-of", "json",
                                    f"{tmp}/frag.mp4")
            self.assertEqual(json.loads(probe), json.loads((EXPECTED / "ep32.probe.json").read_text()))

    def test_playlist_names_the_file_relative_to_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(f"{tmp}/media").mkdir()
            run_cli("frag", str(OUT / "f1.mp4"), "-o", f"{tmp}/media/f1-frag.mp4", "--hls", f"{tmp}/f1.m3u8")
            text = Path(f"{tmp}/f1.m3u8").read_text()
            self.assertIn('URI="media/f1-frag.mp4"', text)
            self.assertEqual(ffmpeg("ffmpeg", "-v", "error", "-i", f"{tmp}/f1.m3u8", "-f", "null", "-"), (0, b"", b""))

    def test_ffprobe_packets_are_phones(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_cli("frag", str(OUT / "phone.mp4"), "-o", f"{tmp}/frag.mp4", "--hls", f"{tmp}/frag.m3u8")
            mine, theirs, played = packets(f"{tmp}/frag.mp4"), packets(OUT / "phone.mp4"), packets(f"{tmp}/frag.m3u8")
        self.assertEqual(mine[0], theirs[0])                                    # pictures: pts, dts, duration, size, K
        self.assertEqual([p[:4] for p in mine[1]], [p[:4] for p in theirs[1]])  # sound: pts from -1,024, as phone's
        self.assertEqual([n for n, (a, b) in enumerate(zip(mine[1], theirs[1])) if a[4] != b[4]], [0])
        self.assertEqual((mine[1][0][4], theirs[1][0][4]), ("K__", "KD_"))     # phone marks the priming "discard"
        self.assertEqual(played, mine)                                          # the playlist gives the same packets

    def test_decodes_as_phone(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(f"{tmp}/frag.mp4").write_bytes(terrace()[0])
            frames = [ffmpeg("ffmpeg", "-v", "error", "-i", f, "-map", "0:v", "-f", "framemd5", "-")[1]
                      for f in (f"{tmp}/frag.mp4", str(OUT / "phone.mp4"))]
            self.assertEqual(frames[0].split(b"\n")[4:], frames[1].split(b"\n")[4:])   # every picture, and its pts
            pcm = [ffmpeg("ffmpeg", "-v", "error", "-i", f, "-map", "0:a", "-f", "s16le", "-")[1]
                   for f in (f"{tmp}/frag.mp4", str(OUT / "phone.mp4"))]
        self.assertEqual((len(pcm[0]), len(pcm[1])), (385024, 384000))       # the last frame's 256 trimmed samples
        self.assertEqual(pcm[0][:384000], pcm[1])                             # priming skipped, as phone's

    def test_cmd_frag_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("aac-only.m4a", "frag-cmaf.mp4"):
                code, out = run_cli_code("frag", str(OUT / name), "-o", f"{tmp}/x.mp4")
                self.assertEqual((code, out.startswith("error: no video keyframe")), (1, True))
                self.assertFalse(Path(f"{tmp}/x.mp4").exists())

if __name__ == "__main__":
    unittest.main()
