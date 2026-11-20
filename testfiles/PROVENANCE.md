# Provenance

- Copied from `series/mp4-from-scratch/testfiles/` (`out/`, `captures/`, `MANIFEST.md`) in the NEW-B1 brain.
- NEW-B1 commit: 67df084
- ffmpeg build: ffmpeg version 9.0.2 Copyright (c) 2000-2026 the FFmpeg developers

The files are synthetic (testsrc2 and a sine). `make.sh` stays in the NEW-B1 series.
- phone-chapters.mp4 (`out/`, its three `captures/` files and the new MANIFEST.md) copied on 2026-11-21 from NEW-B1
  commit cd2f05b6, which adds its recipe to make.sh (phone.mp4 + a two-chapter FFMETADATA file, `-map_chapters 1
  -c copy -movie_timescale 48000`). The other 16 files and their captures rebuild byte-identically with it.
