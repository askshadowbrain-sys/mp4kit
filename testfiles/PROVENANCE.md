# Provenance

- Copied from `series/mp4-from-scratch/testfiles/` (`out/`, `captures/`, `MANIFEST.md`) in the NEW-B1 brain.
- NEW-B1 commit: 67df084
- ffmpeg build: ffmpeg version 9.0.2 Copyright (c) 2000-2026 the FFmpeg developers

The files are synthetic (testsrc2 and a sine). `make.sh` stays in the NEW-B1 series.
- phone-chapters.mp4 (`out/`, its three `captures/` files and the new MANIFEST.md) copied on 2026-11-21 from NEW-B1
  commit cd2f05b6, which adds its recipe to make.sh (phone.mp4 + a two-chapter FFMETADATA file, `-map_chapters 1
  -c copy -movie_timescale 48000`). The other 16 files and their captures rebuild byte-identically with it.
- streams/phone.h264 and streams/phone.aac (episode 29's `mux` inputs) copied on 2026-11-21 from NEW-B1's
  `series/mp4-from-scratch/testfiles/streams/`, made by its make.sh from phone.mp4 (`-map 0:v:0 -c copy -f h264`,
  `-map 0:a:0 -c copy -f adts`); byte-identical to `mp4kit extract phone.mp4 --track 1` / `--track 2`. They live outside
  `out/` because the ep09-ep28 tests walk every file in `out/` as an MP4.
- phone-sidx.mp4 (`out/`, its three `captures/` files and the new MANIFEST.md) copied on 2026-11-22 from NEW-B1
  commit 18bee861, which adds its recipe to make.sh (phone.mp4 `-c copy -movflags
  +frag_keyframe+empty_moov+default_base_moof+global_sidx -movie_timescale 48000`: two sidx, one per track, then two
  moof+mdat pairs and an mfra). The other 17 files and their captures rebuild byte-identically with it. The MANIFEST
  copy also brings in the streams/ paragraph NEW-B1 added for episode 29.
- vp9opus.mp4 (`out/`, its three `captures/` files and the new MANIFEST.md) copied on 2026-11-22 from NEW-B1 commit
  e7958211, which adds make_scratch.sh's recipe to make.sh (1 s testsrc2 320x180 in libvpx-vp9 + a 48 kHz sine in
  libopus, +bitexact; libvpx 1.17.0, libopus 1.6.1). The other 18 files and their captures rebuild byte-identically with
  it. The MANIFEST copy also brings in NEW-B1's correction that hevc.mp4's keyframe sample 28 is a CRA (type 21).
