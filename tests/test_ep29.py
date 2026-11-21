import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from mp4kit import audio, boxes, mux, nal, tables
from tests.util import data, run_cli, run_cli_code

OUT = Path(__file__).parents[1] / "testfiles" / "out"
STREAMS = Path(__file__).parents[1] / "testfiles" / "streams"
EXPECTED = Path(__file__).parents[1] / "expected"
H264, AAC = (STREAMS / "phone.h264").read_bytes(), (STREAMS / "phone.aac").read_bytes()


def ffmpeg(*argv):
    """Run ffprobe or ffmpeg (required from ep29: a written file is judged by ffmpeg) and return (exit code, stdout,
    stderr)."""
    if shutil.which(argv[0]) is None:
        raise AssertionError(f"{argv[0]} required from ep29")
    done = subprocess.run(argv, capture_output=True)
    return done.returncode, done.stdout, done.stderr


def phone():
    contents = data("phone.mp4")
    return contents, tables.read_tracks(contents, boxes.walk(contents))


def built():
    return mux.video_track(H264, 30), mux.audio_track(AAC, 1024)


def times(track):
    """What a player needs of each sample: decode time, composition time, size, keyframe (not where it sits)."""
    return [(s.dts, s.cts, s.size, s.key) for s in track.samples]


class Ep29(unittest.TestCase):
    def test_write_esds(self):
        asc = audio.asc_bytes({"audioObjectType": 2, "samplingFrequencyIndex": 3, "channelConfiguration": 2})
        written = mux.write_esds(asc, 96106, 2)
        e = audio.read_esds(written, boxes.walk(written)[0])
        self.assertEqual((e["objectTypeIndication"], e["streamType"], e["ASC"], e["ES_ID"], e["avgBitrate"],
                          e["maxBitrate"], e["SLConfig_predefined"]), (0x40, 5, b"\x11\x90", 2, 96106, 96106, 2))
        self.assertEqual(len(written), 51)

    def test_write_esds_is_phones(self):
        contents, _ = phone()
        box = boxes.find(boxes.walk(contents), "moov/trak/mdia/minf/stbl/stsd/mp4a/esds")
        e = audio.read_esds(contents, box)                                    # ASC 11 90 56 e5 00, 96,360 b/s, ES_ID 2
        self.assertEqual(mux.write_esds(e["ASC"], e["avgBitrate"], e["ES_ID"]), contents[box.start:box.end])

    def test_write_mp4a(self):
        contents, _ = phone()
        box = boxes.find(boxes.walk(contents), "moov/trak/mdia/minf/stbl/stsd/mp4a")
        esds = boxes.find(box.children, "esds")
        written = mux.write_mp4a(2, 48000, contents[esds.start:esds.end])
        a = tables.read_audio_entry(written, boxes.walk(written)[0])
        self.assertEqual((a["channelcount"], a["samplesize"], a["samplerate"], a["data_reference_index"]),
                         (2, 16, 48000, 1))
        self.assertEqual(written[36:], contents[esds.start:esds.end])          # 8 + 28 bytes of fields, then esds
        self.assertEqual(written, boxes.box("mp4a", contents[box.payload:box.payload + 28],
                                            contents[esds.start:esds.end]))    # phone's, without its btrt
        self.assertEqual((len(written), box.size), (90, 110))

    def test_video_clock(self):
        self.assertEqual([mux.video_clock(f) for f in (30, 25, 24, 60, 10000)], [15360, 12800, 12288, 15360, 10000])

    def test_streams_are_phones(self):
        with tempfile.TemporaryDirectory() as tmp:                            # mp4kit's own extract (episode 23)
            run_cli("extract", str(OUT / "phone.mp4"), "--track", "1", "-o", f"{tmp}/v")
            run_cli("extract", str(OUT / "phone.mp4"), "--track", "2", "-o", f"{tmp}/a")
            self.assertEqual((Path(f"{tmp}/v").read_bytes(), Path(f"{tmp}/a").read_bytes()), (H264, AAC))

    def test_video_track(self):
        video, (phone_video, _) = mux.video_track(H264, 30), phone()[1]
        self.assertEqual((video.timescale, video.duration, len(video.samples)), (15360, 30720, 60))
        self.assertEqual([s.size for s in video.samples], [s.size for s in phone_video.samples])
        self.assertEqual([s.number for s in video.samples if s.key], [1, 31])
        self.assertEqual([s.dts for s in video.samples], [s.dts for s in phone_video.samples])
        self.assertEqual(video.elst, [(30720, 512, 1, 0)])                     # one frame, not ffmpeg's two
        self.assertEqual(min(s.cts for s in video.samples), 512)               # media_time = smallest CT
        mine = [s.cts - 512 for s in video.samples]
        self.assertEqual(mine, [s.cts - 1024 for s in phone_video.samples])     # every PTS is phone's
        probe = json.loads((OUT.parent / "captures" / "phone.mp4.probe.json").read_text())
        self.assertEqual(mine, [int(p["pts"]) for p in probe["packets"] if p["stream_index"] == 0])
        self.assertTrue(all(s.cts >= s.dts for s in video.samples))
        self.assertEqual([s.cts - s.dts for s in video.samples[:4]], [512, 1536, 0, 0])
        self.assertEqual([s.cts - s.dts for s in phone_video.samples[:4]], [1024, 2048, 512, 512])
        self.assertEqual([u[0] & 31 for _, u in nal.iter_length_prefixed(video.payloads[0], 0, 5824)], [6, 5])

    def test_display_order(self):
        units = nal.access_units(nal.split_annexb(H264))
        self.assertEqual([u[0] & 31 for u in units[0]], [6, 7, 8, 5])          # SEI, SPS, PPS, IDR
        sps, pps = units[0][1], units[0][2]
        self.assertEqual(mux.display_order(units, sps, pps)[:8], [0, 3, 1, 2, 6, 4, 5, 8])

    def test_video_track_25_fps(self):
        video = mux.video_track(H264, 25)
        self.assertEqual((video.timescale, video.samples[1].dts, video.elst[0][1]), (12800, 512, 512))

    def test_audio_track(self):
        sound, (_, phone_sound) = mux.audio_track(AAC, 1024), phone()[1]
        self.assertEqual([s.size for s in sound.samples], [s.size for s in phone_sound.samples])
        self.assertEqual((len(sound.samples), sound.timescale, sound.duration), (95, 48000, 97280))
        self.assertEqual(sound.elst, [(96256, 1024, 1, 0)])                    # phone: (96,000, 1,024)
        self.assertEqual((sound.entry["esds"]["ASC"], sound.entry["esds"]["avgBitrate"]), (b"\x11\x90", 96106))
        self.assertEqual(phone_sound.duration, 97024)                          # its last frame is 768: not in ADTS
        self.assertEqual(mux.audio_track(AAC).elst, [(97280, 0, 1, 0)])

    def test_mux_reads_back(self):
        video, sound = built()
        written = mux.mux([video, sound])
        back = tables.read_tracks(written, boxes.walk(written))
        self.assertEqual([times(t) for t in back], [times(video), times(sound)])
        self.assertEqual([(t.id, t.handler, t.timescale, t.duration) for t in back],
                         [(1, "vide", 15360, 30720), (2, "soun", 48000, 97280)])
        self.assertEqual([t.elst for t in back], [[(96000, 512, 1, 0)], [(96256, 1024, 1, 0)]])
        for track, mine in zip(back, (video, sound)):                         # every parcel where the tables say
            self.assertEqual([written[s.offset:s.offset + s.size] for s in track.samples], mine.payloads)
        self.assertEqual(back[0].entry["avcC"]["SPS"], phone()[1][0].entry["avcC"]["SPS"])

    def test_mux_is_phones_parcels(self):
        written, (contents, tracks) = mux.mux(list(built())), phone()
        back = tables.read_tracks(written, boxes.walk(written))
        for mine, theirs in zip(back, tracks):
            self.assertEqual([written[s.offset:s.offset + s.size] for s in mine.samples],
                             [contents[s.offset:s.offset + s.size] for s in theirs.samples])
        top = [(b.type, b.start, b.size) for b in boxes.walk(written)]
        self.assertEqual(top, [("ftyp", 0, 32), ("free", 32, 8), ("mdat", 40, 108704), ("moov", 108744, 3238)])

    def test_mux_fast(self):
        slow, fast = mux.mux(list(built())), mux.mux(list(built()), fast=True)
        self.assertEqual(fast, mux.faststart(slow))
        self.assertEqual([b.type for b in boxes.walk(fast)], ["ftyp", "moov", "free", "mdat"])
        back = tables.read_tracks(fast, boxes.walk(fast))
        self.assertEqual([times(t) for t in back], [times(t) for t in built()])

    def test_write_trak(self):
        video = built()[0]
        trak = mux.write_trak(video, mux.write_stsd(video), [48], [60], 48000)
        tree = boxes.walk(trak)
        self.assertEqual([b.type for b in tree[0].children], ["tkhd", "edts", "mdia"])
        self.assertEqual(tables.read_tkhd(trak, tree[0].children[0])["duration"], 96000)
        self.assertEqual(tables.sample_table(trak, tree[0])[5].cts, video.samples[5].cts)
        sound = built()[1]
        tkhd = boxes.walk(mux.write_trak(sound, mux.write_stsd(sound), [48], [95], 48000))[0].children[0]
        self.assertEqual(mux.write_trak(sound, mux.write_stsd(sound), [48], [95], 48000)[tkhd.end - 50:tkhd.end - 46],
                         b"\x00\x01\x01\x00")                                   # alternate group 1, volume 1.0

    def test_cmd_mux(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_cli("mux", "--video", str(STREAMS / "phone.h264"), "--audio", str(STREAMS / "phone.aac"),
                          "--fps", "30", "--priming", "1024", "-o", f"{tmp}/out.mp4")
            self.assertEqual(out, (EXPECTED / "ep29.txt").read_text())
            self.assertEqual(ffmpeg("ffmpeg", "-v", "error", "-i", f"{tmp}/out.mp4", "-f", "null", "-"), (0, b"", b""))
            code, probe, _ = ffmpeg("ffprobe", "-v", "error", "-show_streams", "-show_packets", "-of", "json",
                                    f"{tmp}/out.mp4")
            self.assertEqual(json.loads(probe), json.loads((EXPECTED / "ep29.probe.json").read_text()))

    def test_decodes_as_phone(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(f"{tmp}/out.mp4").write_bytes(mux.mux(list(built())))
            frames = [ffmpeg("ffmpeg", "-v", "error", "-i", f, "-map", "0:v", "-f", "framemd5", "-")[1]
                      for f in (f"{tmp}/out.mp4", str(OUT / "phone.mp4"))]
            self.assertEqual(frames[0].split(b"\n")[4:], frames[1].split(b"\n")[4:])   # every picture, and its pts
            pcm = [ffmpeg("ffmpeg", "-v", "error", "-i", f, "-map", "0:a", "-f", "s16le", "-")[1]
                   for f in (f"{tmp}/out.mp4", str(OUT / "phone.mp4"))]
            self.assertEqual((len(pcm[0]), len(pcm[1])), (385024, 384000))       # 96,256 and 96,000 samples x 2 x 2
            self.assertEqual(pcm[0][:384000], pcm[1])                            # phone's sound, then 256 more

    def test_cmd_mux_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run_cli_code("mux", "--video", str(STREAMS / "phone.aac"), "--audio",
                                     str(STREAMS / "phone.aac"), "-o", f"{tmp}/x.mp4")
            self.assertEqual(code, 1)
            self.assertTrue(out.startswith("error: needs an SPS and a PPS"))
            code, out = run_cli_code("mux", "--video", str(STREAMS / "phone.h264"), "--audio",
                                     str(STREAMS / "phone.h264"), "-o", f"{tmp}/y.mp4")
            self.assertEqual((code, out), (1, "error: no ADTS sync word at byte 0\n"))
            self.assertFalse(Path(f"{tmp}/x.mp4").exists() or Path(f"{tmp}/y.mp4").exists())


if __name__ == "__main__":
    unittest.main()
