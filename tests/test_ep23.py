import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from mp4kit import audio, boxes, cli, nal, tables
from tests.util import data, run_cli, run_cli_code

PHONE, SUBS, CHAPTERS = data("phone.mp4"), data("subs.mp4"), data("phone-chapters.mp4")
OUT = Path(__file__).parents[1] / "testfiles" / "out"
CAPS = Path(__file__).parents[1] / "testfiles" / "captures"
EXPECTED = Path(__file__).parents[1] / "expected" / "ep23.txt"
# phone-chapters' video tref, as xxd shows it at 109030: size 20, tref; size 12, chap; track_ID 3
TREF = bytes.fromhex("00000014 74726566" "0000000c 63686170 00000003")
# sha256 and size of ffmpeg 9.0.2's own streams (captures/ep23 C6): -c copy -bsf:v h264_mp4toannexb -f h264;
# -c:a copy -f adts; -c:s srt
FFMPEG = {("phone.mp4", 1): ("6c171e7d79531880ce39f62f21db0a8465ebb90dff5b4a8557aab75277d6300f", 84427),
          ("phone.mp4", 2): ("2da8e41153b728ca73e57418e1f082245369c3588e8ca63586c0f23856e6aef0", 25012),
          ("subs.mp4", 3): ("39f2010f14aee98dba3de7d0f54b708c68cfb8a8980849b778abf688c94376ea", 87),
          ("f1.mp4", 1): ("af93e691e171bce81609ba26e86e52ab500ac4ad1c61bec82c5013c78eadb9fe", 22131),
          ("aac-only.m4a", 1): ("796e0e97ee8a05838a43e7464e99853818ce0ce75deb8db375945ecf908a7041", 17057)}
SUBS_SRT = "1\n00:00:00,000 --> 00:00:00,900\nFirst cue\n\n2\n00:00:01,000 --> 00:00:01,900\nSecond cue\n\n"
CHAPTERS_SRT = "1\n00:00:00,000 --> 00:00:01,000\nOne\n\n2\n00:00:01,000 --> 00:00:02,000\nTwo\n\n"


def tracks(contents):
    return tables.read_tracks(contents, boxes.walk(contents))


def extract(name, track):
    """Run `extract` into a temporary file; return (exit code, what it printed, the bytes written)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        code, printed = run_cli_code("extract", str(OUT / name), "--track", str(track), "-o", str(out))
        return code, printed, out.read_bytes() if out.exists() else None


class Ep23(unittest.TestCase):
    def test_read_tracks_subs(self):
        got = [(t.id, t.handler, t.timescale, t.entry["type"], len(t.samples), t.tref, t.duration)
               for t in tracks(SUBS)]
        self.assertEqual(got, [(1, "vide", 15360, "avc1", 60, {}, 30720), (2, "soun", 48000, "mp4a", 95, {}, 97024),
                               (3, "sbtl", 1000000, "tx3g", 4, {}, 1900000)])
        third = tracks(SUBS)[2]
        self.assertEqual([s.size for s in third.samples], [11, 2, 12, 2])        # stsz: 4, ffprobe lists 3
        self.assertEqual([s.dts for s in third.samples], [0, 900000, 1000000, 1900000])
        self.assertEqual(third.elst, [(91200, 0, 1, 0)])

    def test_track_fields_match_the_tables(self):
        video, sound = tracks(PHONE)
        trak = boxes.find_all(boxes.walk(PHONE), "moov/trak")[0]
        self.assertEqual(video.samples, tables.sample_table(PHONE, trak))
        self.assertEqual(video.elst, [(96000, 1024, 1, 0)])
        self.assertEqual(([s.number for s in video.samples if s.key]), [1, 31])
        self.assertEqual((video.entry["width"], video.entry["height"], video.entry["avcC"]["codec"]),
                         (640, 360, "avc1.64001E"))
        self.assertEqual((sound.entry["channelcount"], sound.entry["samplerate"], sound.entry["esds"]["codec"],
                          sound.entry["esds"]["ASC"].hex()), (2, 48000.0, "mp4a.40.2", "119056e500"))
        self.assertEqual(set(video.entry), {"type", "data_reference_index", "width", "height", "compressorname",
                                            "depth", "avcC", "pasp", "btrt"})

    def test_read_tracks_matches_ffprobe(self):
        for f in sorted(OUT.glob("*.mp4")) + sorted(OUT.glob("*.m4a")):
            streams = json.loads((CAPS / f"{f.name}.probe.json").read_text()).get("streams", [])
            got = tracks(f.read_bytes())
            with self.subTest(f=f.name):
                self.assertEqual([t.id for t in got], [int(s["id"], 16) for s in streams])
                self.assertEqual([t.timescale for t in got], [int(s["time_base"].split("/")[1]) for s in streams])
                for t, s in zip(got, streams):
                    if "nb_frames" in s:                                     # frag-cmaf's moov holds no samples
                        self.assertEqual(len(t.samples), int(s["nb_frames"]))
                    if not t.entry["type"].startswith("enc"):                # cenc: ffprobe names the original (frma)
                        self.assertEqual(t.entry["type"], s["codec_tag_string"])

    def test_read_tracks_no_moov(self):
        self.assertEqual(tracks(data("broken-nomoov.mp4")), [])
        self.assertEqual([len(t.samples) for t in tracks(data("frag-cmaf.mp4"))], [0, 0])     # samples in moof

    def test_read_tref(self):
        for start in (109030, 110504):
            tref = [b for b in boxes.walk(CHAPTERS, start, start + 20)][0]
            with self.subTest(start=start):
                self.assertEqual(bytes(CHAPTERS[start:start + 20]), TREF)
                self.assertEqual(tables.read_tref(CHAPTERS, tref), {"chap": [3]})
        blob = bytes.fromhex("00000018 74726566" "00000010 63686170 00000003 00000004")    # one signpost, two IDs
        self.assertEqual(tables.read_tref(blob, boxes.walk(blob)[0]), {"chap": [3, 4]})

    def test_signposts_point_one_way(self):
        video, sound, text = tracks(CHAPTERS)
        self.assertEqual((video.tref, sound.tref, text.tref), ({"chap": [3]}, {"chap": [3]}, {}))
        self.assertEqual((text.id, text.handler, text.entry["type"], text.timescale), (3, "text", "text", 48000))
        tkhd = tables.read_tkhd(CHAPTERS, boxes.find_all(boxes.walk(CHAPTERS), "moov/trak/tkhd")[2])
        self.assertEqual(tkhd["flags"], 2)                    # in movie, not enabled: players do not draw it
        for f in OUT.iterdir():
            if f.name != "phone-chapters.mp4":
                with self.subTest(f=f.name):
                    self.assertTrue(all(t.tref == {} for t in tracks(f.read_bytes())))

    def test_chapter_samples(self):
        text = tracks(CHAPTERS)[2]
        self.assertEqual([(s.dts, s.size) for s in text.samples], [(0, 17), (48000, 17)])
        first = bytes(CHAPTERS[text.samples[0].offset:text.samples[0].offset + 17])
        self.assertEqual(first[:5], b"\x00\x03One")              # a 2-byte length, the title
        self.assertEqual(first[5:], bytes.fromhex("0000000c 656e6364 00000100"))   # then an encd box: UTF-8 (256)

    def test_annexb_sample(self):
        sps, pps, sei, idr, p = b"\x67\x01", b"\x68\x02", b"\x06\x03", b"\x65\x04", b"\x41\x05"
        four, three = b"\x00\x00\x00\x01", b"\x00\x00\x01"
        self.assertEqual(nal.annexb_sample([sei, idr], [sps, pps]), four + sei + four + sps + four + pps + three + idr)
        self.assertEqual(nal.annexb_sample([idr], [sps, pps]), four + sps + four + pps + three + idr)
        self.assertEqual(nal.annexb_sample([p], [sps, pps]), four + p)
        self.assertEqual(nal.annexb_sample([idr, idr], [sps, pps]),
                         four + sps + four + pps + three + idr + three + idr)

    def test_extract_matches_ffmpeg(self):
        for (name, track), (sha, size) in FFMPEG.items():
            code, _, stream = extract(name, track)
            with self.subTest(name=name, track=track):
                self.assertEqual((code, len(stream), hashlib.sha256(stream).hexdigest()), (0, size, sha))

    def test_extract_every_copy_of_phone(self):
        want = [extract("phone.mp4", n)[2] for n in (1, 2)]
        for name in ("phone-fast.mp4", "phone-large.mp4", "rotated.mp4", "subs.mp4", "phone-chapters.mp4"):
            with self.subTest(name=name):
                self.assertEqual([extract(name, n)[2] for n in (1, 2)], want)    # the same parcels, other houses

    def test_extract_keeps_the_parcels(self):
        video, sound = tracks(PHONE)
        stream = extract("phone.mp4", 1)[2]
        units = nal.split_annexb(stream)
        config = video.entry["avcC"]
        mine = [u for s in video.samples for _, u in nal.iter_length_prefixed(PHONE, s.offset, s.offset + s.size)]
        self.assertEqual([u for u in units if u[0] & 0x1F not in (7, 8)], mine)        # every NAL, byte for byte
        self.assertEqual([u for u in units if u[0] & 0x1F in (7, 8)], (config["SPS"] + config["PPS"]) * 2)
        fields, payloads = audio.split_adts(extract("phone.mp4", 2)[2])
        self.assertEqual(payloads, [bytes(PHONE[s.offset:s.offset + s.size]) for s in sound.samples])
        self.assertEqual(len(extract("phone.mp4", 2)[2]), sum(s.size for s in sound.samples) + 95 * 7)

    def test_a_copied_cut_starts_at_a_keyframe(self):
        video = tracks(PHONE)[0]
        stream = extract("phone.mp4", 1)[2]
        params = video.entry["avcC"]["SPS"] + video.entry["avcC"]["PPS"]
        tail = b"".join(nal.annexb_sample([u for _, u in nal.iter_length_prefixed(PHONE, s.offset, s.offset + s.size)],
                                          params) for s in video.samples[30:])
        self.assertEqual(stream.index(tail), 41676)                       # from keyframe 31: the stream's own tail
        self.assertEqual(nal.split_annexb(tail)[0][0] & 0x1F, 7)           # it opens with SPS, PPS, then the IDR
        later = nal.annexb_sample([u for _, u in nal.iter_length_prefixed(PHONE, video.samples[39].offset,
                                   video.samples[39].offset + video.samples[39].size)], params)
        self.assertEqual(nal.split_annexb(later)[0][0] & 0x1F, 1)          # sample 40: a P slice, nothing to start from

    def test_extract_srt(self):
        self.assertEqual(extract("subs.mp4", 3)[2].decode(), SUBS_SRT)      # the gap and the 0-length tail: no cue
        self.assertEqual(extract("phone-chapters.mp4", 3)[2].decode(), CHAPTERS_SRT)
        self.assertEqual(cli._srt_time(900000, 1000000), "00:00:00,900")
        self.assertEqual(cli._srt_time(3723456 * 48, 48000), "01:02:03,456")

    def test_cmd_extract(self):
        code, printed, _ = extract("phone.mp4", 2)
        self.assertEqual(code, 0)
        self.assertEqual(printed, EXPECTED.read_text())

    def test_cmd_extract_lists_signposts(self):
        printed = extract("phone-chapters.mp4", 3)[1]
        self.assertEqual(printed.splitlines(), [
            "track 1: track_ID 1 vide avc1, 60 samples, chap -> track_ID [3]",
            "track 2: track_ID 2 soun mp4a, 95 samples, chap -> track_ID [3]",
            "track 3: track_ID 3 text text, 2 samples",
            "wrote track 3 as SRT: 2 samples (34 bytes) -> 74 bytes"])

    def test_cmd_extract_errors(self):
        for name, track, tail in (("phone.mp4", 3, "error: no track 3, the file has 2"),
                                  ("broken-nomoov.mp4", 1, "error: no track 1, the file has 0"),
                                  ("cenc.mp4", 1, "error: track 1 (encv, 60 samples): no plain stream for it"),
                                  ("hevc.mp4", 1, "error: track 1 (hvc1, 60 samples): no plain stream for it"),
                                  ("frag-cmaf.mp4", 2, "error: track 2 (mp4a, 0 samples): no plain stream for it")):
            code, printed, stream = extract(name, track)
            with self.subTest(name=name):
                self.assertEqual((code, printed.splitlines()[-1], stream), (1, tail, None))

    def test_registry(self):
        self.assertIs(boxes.DECODERS["tref"], tables.read_tref)
        self.assertIn("tref", boxes.CONTAINERS)
        self.assertEqual(run_cli("dump", str(OUT / "phone-chapters.mp4"), "--find", "tref").splitlines(),
                         ["moov/trak/tref 109030 20 chap=[3]", "moov/trak/tref 110504 20 chap=[3]"])
        self.assertEqual(run_cli("dump", str(OUT / "phone.mp4"), "--find", "tref"), "no tref box\n")


if __name__ == "__main__":
    unittest.main()
