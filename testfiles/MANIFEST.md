# MP4 from Scratch: test files

Every file the course cites by name, how it was made, and the numbers episodes quote from it. All of it is
rebuilt by `make.sh`; `check.sh` rebuilds into a temporary directory and fails if any file's **structure** (box
list with every box's size, so every offset quoted here; streams; packet count and sizes; whether walk.py
parses it) changed. On another encoder build it WILL fail: regenerate the captures with make.sh, then re-verify
every number in this file and in any script that quotes it. On the build below the rebuild is
also byte-identical, captures included.

- **Built with:** ffmpeg 9.0.2, libx264 core 165 r3222, x265 4.3+1-e9b8812, SVT-AV1 v4.2.0, native aac, mov_text.
- **Inputs:** synthetic only: lavfi `testsrc2` pictures (640×360 or 320×180, 30 fps, 2 s) and a 440 Hz `sine`.
  Every encoder runs on one thread, and every output carries `-map_metadata -1 -fflags +bitexact -flags:v +bitexact -flags:a +bitexact`.
- **Captures** (`captures/`, one set per file):
  - `<file>.probe.json` comes from `ffprobe -v error -show_format -show_streams -show_packets -of json`. If ffprobe printed anything on stderr, it is kept in `<file>.probe.err.txt`.
  - `<file>.trace.txt` holds the box lines of `ffprobe -v trace`. They are filtered with `grep -E "type:'[A-Za-z0-9 ]{4}'"`, and the ` @ 0x…` pointer is stripped.
  - `<file>.boxes.json` is the output of `python3 media/moov-series/kit/tools/walk.py <file> --json`, where walk.py parses the file. Where it does not, `<file>.walk-error.txt` holds its error.
- **Trace line format:** `type:'stco' parent:'stbl' sz: <box size> <offset of the box's end of header inside the parent> <parent payload size>`.
- **Episodes:** the "used by" column gives the episodes of `../CURRICULUM.md` that show the file (its
  `test file` column). Besides these, the tests of episode 9 (`walk`, `dump`) and 36 (`check.problems`) run on all 15.
  Six more files are pending (`../CURRICULUM.md`, "Test files"): phone-large.mp4, phone-sidx.mp4, phone-chapters.mp4,
  phone.ts, vp9opus.mp4 and phone-tagged.mp4.
- **Total size:** the 15 files plus their captures hold 1,830,861 bytes (about 1.75 MiB). On disk, `du -k` reports 2,280 KB: out/ 1,440 and captures/ 840, rounded up to 4 KB blocks.

## Files

Offsets are byte offsets from the start of the file. Sample counts are ffprobe packet counts per stream. Every remux of phone.mp4 (subs, frag-cmaf, rotated, cenc) keeps phone's movie timescale with `-movie_timescale 48000`; without it ffmpeg's `-c copy` picks 384,000 (or 48,000,000 with the subtitle track) and rewrites the mvhd/tkhd/elst durations. Sample numbers in the keyframe lists below are in decode order.

| file | purpose | used by (episodes) | size (B) | key numbers | recipe (see make.sh) |
|---|---|---|---|---|---|
| `f1.mp4` | The moov kit's file 1: one video track, no B-frames, moov last. Our own minimux.py output. | 1, 2, 3, 4, 5, 6, 8, 13, 14, 15, 16, 26 | 22,778 | ftyp 0 (32); mdat 32 (22,025); moov 22,057 (721). 12 samples, keyframes at samples 1, 5 and 9. Chunks of 4, 4, 2 and 2 samples. | `cp media/moov-series/kit/sample/in/f1.mp4` |
| `f2.mp4` | The same, with two B-frames, ctts version 0 and an edit list. | 17, 18, 19, 25, 26 | 21,663 | ftyp 0 (32); mdat 32 (20,786); moov 20,818 (845). 12 samples. | `cp media/moov-series/kit/sample/in/f2.mp4` |
| `phone.mp4` | A "real" ffmpeg file: H.264 High with B-frames, plus AAC, interleaved, moov last. | 3, 6, 7, 9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 32, 34, 35, 36 | 112,156 | ftyp 0 (32); free 32 (8); mdat 40 (108,704); moov 108,744 (3,412). mvhd timescale 48,000, duration 96,000. Video has 60 samples, keyframes at samples 1 and 31. Audio has 95 samples (AAC, 1,024 each). The first video chunk starts at byte 48. | `libx264 -profile:v high -crf 30 -g 30 -keyint_min 30 -sc_threshold 0 -bf 2` + `aac -ac 2 -b:a 96k`, 48 kHz |
| `phone-fast.mp4` | phone.mp4 with the moov first: the same samples, with every stco entry moved by +3,412. | 27 | 112,156 | ftyp 0 (32); moov 32 (3,412); free 3,444 (8); mdat 3,452 (108,704). 60 + 95 samples. | the phone.mp4 encode + `-movflags +faststart` |
| `aac-only.m4a` | Audio only: mp4a, esds and the AAC priming edit list. | 8, 14, 20, 21, 22 | 17,563 | ftyp 0 (28); free 28 (8); mdat 36 (16,449); moov 16,485 (1,078). 88 samples, AAC-LC, 44.1 kHz, mono. | `sine=…:sample_rate=44100` → `aac -ac 1 -b:a 64k` |
| `subs.mp4` | phone.mp4 plus a timed-text track: tx3g sample entry, nmhd, language eng. | 12, 23 | 112,739 | mdat 40 (108,731); moov 108,771 (3,968). Three tracks: 60 video, 95 audio and 4 subtitle samples. The subtitle stsz holds 4 samples [11, 2, 12, 2]: cue 1 at 0.0 s (11 B), an empty gap at 0.9 s (2 B), cue 2 at 1.0 s (12 B) and a trailing empty sample (2 B) whose stts delta is 0. ffprobe lists 3: it lists the gap at 0.9 s and drops the trailing zero-duration sample. mvhd timescale 48,000, duration 96,000. | phone.mp4 + 2-cue SRT, `-c copy -c:s mov_text -metadata:s:s:0 language=eng -movie_timescale 48000` |
| `frag-cmaf.mp4` | Fragmented CMAF: an empty moov with mvex/trex, then one moof+mdat per video keyframe, both tracks in each moof, then mfra. | 30, 31, 32 | 111,538 | ftyp 0 (28); moov 28 (1,214); moof 1,242 (608); mdat 1,850 (53,166); moof 55,016 (828); mdat 55,844 (55,546); mfra 111,390 (148). 60 + 95 samples. mvhd timescale 48,000, duration 0 (the empty moov). | phone.mp4 `-c copy -movflags +frag_keyframe+empty_moov+default_base_moof+cmaf -movie_timescale 48000` |
| `hevc.mp4` | HEVC in an hvc1 sample entry: the parameter sets are only in hvcC, and the first sample is a single IDR slice NAL (type 20). | 33 | 33,235 | ftyp 0 (28); free 28 (8); mdat 36 (29,248); moov 29,284 (3,951). 60 samples, 320×180, Main profile. Keyframes at samples 1 and 28; sample 28 is shown at 1.0 s and sits early in decode order because of B-frames. | `libx265 -tag:v hvc1 -crf 32`, `pools=none:frame-threads=1:keyint=30:min-keyint=30:scenecut=0` |
| `hevc-hev1.mp4` | The same encode in an hev1 sample entry with x265 `repeat-headers=1`. Each keyframe sample now starts with VPS (32), SPS (33), PPS (34) and a prefix SEI (39) before the IDR slice (20). hvcC carries the parameter sets as well. | 33 | 38,070 | ftyp 0 (28); free 28 (8); mdat 36 (34,086); moov 34,122 (3,948). 60 samples, keyframes at samples 1 and 28. Sample 1 is 4,941 B against 2,522 B in hevc.mp4: NAL sizes 24, 43, 7, 2,329 and 2,518. | hevc.mp4 recipe with `-tag:v hev1` and `repeat-headers=1` |
| `av1.mp4` | AV1: av01 sample entry and av1C (OBUs, no start codes). | 33 | 50,474 | ftyp 0 (32); free 32 (8); mdat 40 (49,363); moov 49,403 (1,071). 60 samples, 320×180, Main profile. Keyframes at samples 1 and 31 (no reordering). | `libsvtav1 -preset 8 -crf 40 -svtav1-params lp=1:keyint=30` |
| `hdr.mp4` | HDR10 metadata: colr (nclx: BT.2020, PQ, BT.2020nc), mdcv and clli in the sample entry. | 34 | 31,837 | mdat 36 (27,615); moov 27,651 (4,186). 60 samples, Main 10, keyframes at samples 1 and 28. mdcv: G(13250,34500) B(7500,3000) R(34000,16000) WP(15635,16450) L(10000000,1). clli: 1000/400. | two-pass libx265 10-bit; see the note below |
| `rotated.mp4` | phone.mp4 with a 90° display matrix in the video tkhd. | 11 | 112,156 | Same layout and mvhd timescale (48,000) as phone.mp4. The tkhd matrix is `0 -65536 0 / 65536 0 0 / 0 0 1073741824`, and ffprobe reports rotation = 90. `cmp -l` against phone.mp4 finds exactly 8 differing bytes. Five are in the tkhd matrix, at zero-based bytes 108,917, 108,920, 108,921, 108,929 and 108,933. Three are the avc1 btrt avgBitrate, at zero-based bytes 109,343–109,345 (`cmp -l` prints 1-based offsets, one higher): 0 in phone.mp4, and 337,396 here because the remux computes it. | `-display_rotation:v:0 90 -i phone.mp4 -c copy -movie_timescale 48000` |
| `cenc.mp4` | Common Encryption (cenc, AES-CTR) on both tracks: encv/enca with sinf (frma, schm, schi/tenc), plus senc, saiz and saio. | 35 | 114,208 | mdat 40 (108,704); moov 108,744 (5,464). 60 + 95 samples, the same sizes as phone.mp4. mvhd timescale 48,000, duration 96,000. No pssh box: ffmpeg writes none. | phone.mp4 `-c copy -movie_timescale 48000 -encryption_scheme cenc-aes-ctr -encryption_key … -encryption_kid …` |
| `broken-nomoov.mp4` | A recording that stopped before its moov was written. ffprobe says "moov atom not found". | 9, 19, 36 | 108,744 | ftyp 0 (32); free 32 (8); mdat 40 (108,704). The file ends at 108,744, where phone.mp4's moov starts. | `head -c $(python3 patch_stco.py --mdat-end phone.mp4) phone.mp4` |
| `broken-stco.mp4` | phone.mp4 with one wrong chunk offset. The video track's stco entry 1 changes from 48 to 1,048, so the decoder reads the wrong bytes. | 36 | 112,156 | stco box at 110,062. Entry 1 is at byte 110,078 and changes from 48 to 1,048. Everything else is byte-identical to phone.mp4. | `python3 patch_stco.py phone.mp4 broken-stco.mp4 1000` |

## Notes on the recipes

- **The CENC key is a test key, published on purpose.**
  - key `00112233445566778899aabbccddeeff`
  - KID `0123456789abcdef0123456789abcdef`
  
  The course decrypts cenc.mp4 by hand, so the key has to be public. Never use it for real content. With `+bitexact`, ffmpeg's cenc writer uses a fixed IV instead of a random one, which is why cenc.mp4 rebuilds byte-identically. `captures/cenc.mp4.probe.err.txt` shows what ffprobe's decoder makes of the ciphertext without the key.
- **hdr.mp4 takes two passes.**
  - x265's `master-display`/`max-cll` params only reach the bitstream SEI, so a one-pass encode has no mdcv or clli box.
  - In ffmpeg 9, `-color_primaries`/`-color_trc` alone also left the colr box out, because the colour comes from the frames. `setparams` tags the frames.
  - Pass 1 writes raw HEVC with the SEI. Pass 2 decodes it, so the SEI become frame side data, re-encodes, and the muxer writes colr, mdcv and clli.
- **`-display_rotation` is an input option** in this ffmpeg. It is applied to phone.mp4 when it is read, then stream-copied.
- **`-movflags +cmaf`** exists in this ffmpeg as a movflags value. The brief's flags were used verbatim.
- **broken-stco.mp4 is made by `patch_stco.py`.** The script is stdlib Python and documented. It finds the first stco depth first (the video track's) and adds 1,000 to entry 1. It changes 4 bytes. It handles 64-bit largesize box headers, where children start 16 bytes in. The same script prints the mdat end that broken-nomoov.mp4 is cut at.
- **The trace grep deviates from the brief.** The brief's filter `[a-z0-9 ]{4}` drops box types with capitals: avcC, hvcC, av1C. make.sh uses `[A-Za-z0-9 ]{4}` instead.
- **Keyframes every 30 frames everywhere.** hevc, hevc-hev1 and hdr use x265 `keyint=30:min-keyint=30:scenecut=0`; av1 uses SVT `keyint=30`. The encoders' defaults are longer than 2 s.
- **Remuxes drop `-map_metadata -1`.** They keep phone.mp4's stream tags. Dropping them loses the "Lavc libx264" encoder tag, and the muxer then blanks the avc1 compressorname.

## What walk.py parses (course work, not bugs)

walk.py is the moov kit's one-video-track teaching parser. Building it out is what the course does.

| file | walk.py | why |
|---|---|---|
| f1, f2, phone, phone-fast, subs, rotated, broken-stco, hevc, hevc-hev1, av1, hdr | parses | It reads only the first `mdhd`/`stbl` tables it meets, which belong to the video track. In phone, subs and the other multi-track files, the audio and subtitle tracks are silently ignored. |
| aac-only.m4a | parses | The single track is audio. walk.py reads its tables as if they were video. |
| cenc.mp4 | parses the tables | It does not step into the `encv`/`enca` sample entries (sinf, tenc), does not read senc, and its "frame bytes" are ciphertext. |
| frag-cmaf.mp4 | **does not parse** | `ValueError: moof at 1242: one traf with one trun expected`. Each CMAF moof here carries two trafs, one per track. |
| broken-nomoov.mp4 | **does not parse** | `KeyError: 'mdhd'`. There is no moov, so it has no tables. This is the case a course parser must report clearly. |
