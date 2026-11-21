# Build-it budget per tag

What each episode's Build it adds to `mp4kit/`, and the longest function at that tag.

- **Diff:** `git diff --numstat <previous> <tag> -- mp4kit` (added / removed lines, per file). ep01 is
  measured against the scaffold commit (87f69b6). ep06 is measured at the ep06 tag (its nal.py line is
  the `_mdat_range_stopgap` docstring).
- **Code lines:** added lines that are not blank, a docstring line or a comment. This is the closest
  measure to the plan's budget (mp4kit-plan.md section 4.2: function bodies and signatures).
- **Longest function:** body lines after the `def` line and the docstring (the plan's rule: each
  function body is at most 15 lines), with the whole `def`-to-end length in brackets.

| tag | diff (added / removed) | code lines | plan budget | longest function |
|---|---|---|---|---|
| ep01 | boxes.py +17/-1, cli.py +30/-1 | 27 | ~21 | `cli.main` 9 (11) |
| ep02 | cli.py +16/-0, nal.py +13/-1 | 22 | ~13 | `cli.main` 14 (16) |
| ep03 | cli.py +3/-1, nal.py +44/-1 | 31 | ~21 | `cli.main` 14 (16) |
| ep04 | cli.py +35/-4, nal.py +122/-1 | 114 | ~40 | `nal.parse_sps` 12 (14), `nal._sps_chroma` 12 (14) |
| ep05 | cli.py +24/-1, nal.py +50/-5 | 52 | ~22 | `nal.parse_sps` 12 (14) |
| ep06 | boxes.py +44/-1, cli.py +23/-2, nal.py +1/-1 | 47 | ~24 | `cli.cmd_boxes` 10 (12) and `boxes.read_header` 9 (11) are the longest new ones; `nal.parse_sps` 12 (14) overall |
| ep07 | boxes.py +29/-13, cli.py +3/-3 | 23 | ~13 | `boxes.read_header` 15 (17), at the limit; `cli.cmd_boxes` 10 (12) |
| ep08 | boxes.py +16/-0, cli.py +6/-2 | 13 | ~9 | `cli.cmd_boxes` 14 (16); `boxes.read_header` 15 (17) overall |
| ep09 (finale) | boxes.py +21/-0, cli.py +32/-1 | 36 | ~34 (finale ≤ ~90) | `cli.cmd_dump` 11 (13); `boxes.read_header` 15 (17) overall |
| ep10 | boxes.py +14/-0, cli.py +22/-2, tables.py +25 (new), timing.py +6 (new) | 49 | ~17 | `tables.read_mvhd` 15 (17) and `cli.cmd_dump` 15 (18), both at the limit; `boxes.read_header` 15 (17) overall |
| ep11 | boxes.py +14/-0, cli.py +1/-1, tables.py +40/-1 | 35 | ~21 | `tables.read_tkhd` 14 (17), `boxes.find_all` 9 (11); `boxes.read_header`, `tables.read_mvhd` and `cli.cmd_dump` 15 overall |
| ep12 | cli.py +1/-1, tables.py +46/-1 | 28 | ~14 | `tables.read_mdhd` 13 (16), `tables.read_hdlr` 6 (9), `tables.language` 4 (7); `boxes.read_header`, `tables.read_mvhd` and `cli.cmd_dump` 15 overall |
| ep13 | cli.py +20/-9, tables.py +59/-1 | 49 | ~29 | `tables.read_avcc` 13 (17), `cli.cmd_sps` 13 (16), `tables.read_visual_entry` 7 (12), `tables.read_stsd` 5 (8), `tables.codec_string` 2 (5), `cli._show` 3 (5); `boxes.read_header`, `tables.read_mvhd` and `cli.cmd_dump` 15 overall |
| ep14 | tables.py +31/-1, timing.py +13/-1 | 23 | ~15 | `timing.decode_times` 7 (10), `tables.read_table` 6 (9), `tables.read_stss` 3 (6), `tables.read_stts` 1 (4); `boxes.read_header`, `tables.read_mvhd` and `cli.cmd_dump` 15 overall |
| ep15 | tables.py +53/-1 | 29 | ~16 | `tables.read_stsz` 9 (12), `tables.chunk_sizes` 5 (8), `tables._stsc_fields` 4 (7), `tables.read_stco` 2 (5), `tables.read_stsc` 1 (4); `boxes.read_header`, `tables.read_mvhd` and `cli.cmd_dump` 15 overall |
| ep16 | cli.py +29/-1, tables.py +44/-1 | 50 | ~30 | `tables.sample_table` 15 (20), at the limit, `cli.cmd_samples` 14 (17), `tables._check_counts` 3 (5), `cli._add_samples` 4 (6); `boxes.read_header`, `tables.read_mvhd` and `cli.cmd_dump` 15 overall |
| ep17 | cli.py +13/-5, nal.py +23/-2, tables.py +32/-5, timing.py +9/-1 | 41 | ~21 | `nal.access_units` 11 (15), `tables._clocks` 7 (10), `tables.read_ctts` 4 (8), `timing.composition_times` 2 (5), `cli._time_columns` 2 (4); `nal.read_slice_header` 13 (16) with its POC branch; `tables.sample_table` 15 (20) and `cli.cmd_samples` 14 (18) keep their ep16 bodies; `boxes.read_header`, `tables.read_mvhd`, `cli.cmd_dump` and `tables.sample_table` 15 overall |
| ep18 | cli.py +17/-7, tables.py +17/-1, timing.py +15/-1 | 27 | ~14 | `cli._time_columns` 10 (13), `timing.presentation_times` 6 (11), `tables.read_elst` 4 (9); `cli.cmd_samples` 14 (19) keeps its ep16 body (its docstring is a line longer); `boxes.read_header`, `tables.read_mvhd`, `cli.cmd_dump` and `tables.sample_table` 15 overall |
| ep19 (finale) | boxes.py +8/-2, cli.py +76/-1, timing.py +21/-1 | 72 | ~25 (finale ≤ ~90) | `cli.cmd_frame` 15 (21) and `cli._frame_route` 15 (18), both at the limit, `cli._annexb_samples` 8 (11), `timing.sync_before` 6 (9), `timing.sample_at` 4 (7), `cli._print_route` 4 (7), `boxes.read_mp4` 4 (8); `boxes.read_header`, `tables.read_mvhd`, `cli.cmd_dump` and `tables.sample_table` 15 overall |
| ep20 | audio.py +42 (new), cli.py +52/-6 | 60 | ~23 | `cli._sound_tracks` 14 (18), `cli._print_pcm` 13 (16), `audio.split_adts` 12 (15), `cli._dump_view` 6 (8), `audio.adts_header` 3 (7); `cli.cmd_dump` drops from 15 to 12 (its view choice moved to `_dump_view`); `boxes.read_header`, `tables.read_mvhd`, `tables.sample_table`, `cli.cmd_frame` and `cli._frame_route` 15 overall |
| ep21 | audio.py +59/-1, cli.py +6/-5, tables.py +16/-1 | 48 | ~28 | `audio.read_esds` 14 (18), `audio.read_descriptor` 6 (10), `audio.parse_asc` 6 (10), `tables.read_audio_entry` 5 (10), `audio._open` 5 (7); `cli._sound_tracks` goes from 14 to 15 (its two raw reads become `read_audio_entry`); `boxes.read_header`, `tables.read_mvhd`, `tables.sample_table`, `cli.cmd_frame`, `cli._frame_route` and `cli._sound_tracks` 15 overall |
| ep22 | audio.py +30/-1, cli.py +28/-5, tables.py +36/-1 | 55 | ~12 | `cli._print_priming` 14 (18), `tables.read_sgpd` 12 (16), `tables.read_sbgp` 7 (11), `audio.asc_bytes` 4 (8), `audio.edit_window` 4 (8), `audio.priming` 1 (5); `boxes.read_header`, `tables.read_mvhd`, `tables.sample_table`, `cli.cmd_frame`, `cli._frame_route` and `cli._sound_tracks` 15 overall |
| ep23 | boxes.py +1/-1, cli.py +81/-1, nal.py +14/-1, tables.py +50/-2 | 93 | ~34 | `cli.cmd_extract` 15 (19), at the limit, `tables.read_tracks` 9 (11), `cli._srt_track` 8 (11), `cli._plain_stream` 7 (9), `nal.annexb_sample` 6 (10), `cli._annexb_track` 5 (7), `tables._entry` 4 (7), `cli._adts_track` 3 (5), `cli._srt_time` 2 (4), `tables.read_tref` 1 (4); `boxes.read_header`, `tables.read_mvhd`, `tables.sample_table`, `cli.cmd_frame`, `cli._frame_route` and `cli._sound_tracks` 15 overall |
| ep24 | cli.py +56/-1, mux.py +28 (new), tables.py +19/-4 | 62 | ~25 | `cli.cmd_chunks` 15 (20), at the limit, `cli._print_chunks` 12 (15), `mux.interleave` 8 (13), `tables.chunk_list` 5 (9), `cli._chunk_columns` 4 (7), `mux.timeline` 2 (6); `tables.sample_table` keeps 15 (its chunk number rides on two existing lines); `boxes.read_header`, `tables.read_mvhd`, `tables.sample_table`, `cli.cmd_frame`, `cli._frame_route`, `cli._sound_tracks` and `cli.cmd_chunks` 15 overall |
| ep25 | cli.py +58/-1, timing.py +34/-1 | 59 | ~20 | `cli.cmd_packets` 15 (20), at the limit, `timing.packets` 11 (16), `cli._print_packets` 11 (14), `cli._print_streams` 8 (11), `timing.play_order` 1 (4), `timing.reorder_depth` 1 (4); `boxes.read_header`, `tables.read_mvhd`, `tables.sample_table`, `cli.cmd_frame`, `cli._frame_route`, `cli._sound_tracks`, `cli.cmd_chunks` and `cli.cmd_packets` 15 overall |
| ep26 | boxes.py +15/-1, cli.py +60/-1, mux.py +56/-2 | 79 | ~28 | `cli.cmd_rewrite_check` 15 (19), at the limit, `cli._compare_stbl` 13 (19), `mux.write_stbl` 12 (17), `cli._rewrite_track` 10 (13), `mux.runs` 7 (10), `mux.write_stsz` 3 (6), `boxes.box` 2 (6), `mux.stsc_rules` 1 (5), `mux.table_box` 1 (4), `boxes.full_box` 1 (4); `cli.cmd_samples` keeps 15 (`--rewrite-check` is an argparse `store_const` that swaps `func`, no line in its body); `boxes.read_header`, `tables.read_mvhd`, `tables.sample_table`, `cli.cmd_frame`, `cli._frame_route`, `cli._sound_tracks`, `cli.cmd_chunks`, `cli.cmd_packets`, `cli.cmd_samples` and `cli.cmd_rewrite_check` 15 overall |
| ep27 | cli.py +44/-1, mux.py +38/-2 | 56 | ~23 | `mux.faststart` 15 (21), at the limit, `cli._print_move` 13 (16), `cli.cmd_faststart` 11 (15), `mux.shift_chunk_offsets` 6 (10), `cli._add_faststart` 4 (6); `boxes.read_header`, `tables.read_mvhd`, `tables.sample_table`, `cli.cmd_frame`, `cli._frame_route`, `cli._sound_tracks`, `cli.cmd_chunks`, `cli.cmd_packets`, `cli.cmd_samples`, `cli.cmd_rewrite_check` and `mux.faststart` 15 overall |
| ep28 | cli.py +99/-0, mux.py +77/-2 | 106 | ~36 | `cli._rewrite_track_headers` 15 (19), at the limit, `cli._compare_box` 14 (18), `cli.cmd_header_check` 13 (17), `cli._rewrite_entry` 9 (12), `cli._rewrite_movie` 8 (11), `mux.write_avcc` 7 (10), `cli._bare_avc1` 5 (8), `mux.write_tkhd` 3 (7), `mux.write_avc1` 3 (6), `mux.write_mvhd` 2 (5), `mux.write_mdhd` 2 (5), `mux.write_ftyp`, `write_hdlr`, `write_media_header`, `write_dinf`, `write_elst` 1 each; `cli.cmd_dump` keeps its body (`--rewrite-check` is an argparse `store_const` that swaps `func`); `boxes.read_header`, `tables.read_mvhd`, `tables.sample_table`, `cli.cmd_frame`, `cli._frame_route`, `cli._sound_tracks`, `cli.cmd_chunks`, `cli.cmd_packets`, `cli.cmd_samples`, `cli.cmd_rewrite_check`, `mux.faststart` and `cli._rewrite_track_headers` 15 overall |
| ep29 | cli.py +48/-1, mux.py +130/-1, tables.py +4/-2 | 119 | ~73 | `mux.video_track` 14 (19), `mux.mux` 14 (18), `cli.cmd_mux` 12 (16), `cli._print_built` 12 (15), `mux.display_order` 8 (12), `mux.write_trak` 8 (11), `cli._add_mux` 8 (10), `mux.audio_track` 7 (11), `mux.write_stsd` 7 (9), `mux.write_esds` 4 (8), `mux.video_clock` 4 (7), `mux.descriptor` 2 (5), `mux.write_mp4a` 2 (5); `tables.Track` gains one field (`payloads`); `boxes.read_header`, `tables.read_mvhd`, `tables.sample_table`, `cli.cmd_frame`, `cli._frame_route`, `cli._sound_tracks`, `cli.cmd_chunks`, `cli.cmd_packets`, `cli.cmd_samples`, `cli.cmd_rewrite_check`, `mux.faststart` and `cli._rewrite_track_headers` 15 overall |

## Functions over 15 lines

None. `parse_sps` was expected to be over (minimux's is 21 lines); in ep04 the chroma and
picture-order-count branches became their own helpers (`_sps_chroma`, `_sps_poc`) and the size
arithmetic became `picture_size`, so its body is 12 lines.

## Episodes over their budget

- **ep04 (114 code lines, plan ~40).** It carries the review rulings folded into the episode before
  push: the per-command `_add_<cmd>(sub)` registration in `cli.main`, the `separate_colour_plane` and
  field-coding refusals, scaling-list refusal, and the `_sps_chroma` / `_sps_poc` helpers. It is the
  densest Build it so far and the first to trim at G2 of ep04.
  - **On-screen trim:** show `_sps_chroma` and `_sps_poc` as finished code (named, not typed); build only
    `parse_sps`, `picture_size` and `cmd_sps` on screen.
- **ep05 (52, plan ~22).** Accepted at ~50 by ruling: four functions, the command and the mdat stopgap.
- **ep06 (47, plan ~24).** The `Box` dataclass with its two properties is 9 lines on its own; the
  on-screen code keeps one statement per line (no packed assignments), `read_header` has three plain
  checks with their own messages (fewer than 8 bytes left, a size smaller than the header, a box running
  past the end), and `cmd_boxes` catches `ValueError` to print `error: …` and exit 1 (`BoxError` arrives
  in ep07).
  - **On-screen trim:** show `_add_boxes` and the new entry in `main`'s tuple as finished code; build
    `cmd_boxes` as its 4-line loop (open, read, `for box in iter_boxes(...)`, print), and reveal the
    `try`/`except ValueError` when the cut-file demo (phone.mp4's first 50 bytes) hits the error.
- **ep07 (23, plan ~13).** `read_header` is rewritten rather than extended (most of its lines replace
  ep06's body): the `end` parameter (the parent's end, the carried M4 fix), three new branches (size 1, size 0,
  `uuid`) and the three checks now raise `BoxError`. Its body is 15 lines, so the size, the type and the
  header length are read in one packed assignment, the one exception to ep06's one-statement-per-line rule.
  A size-1 box with no room for its 64-bit size keeps size 1 and fails the header check with a `BoxError`
  (`mdat at 0: size 1 is smaller than its 8-byte header`) instead of a `struct.error`.
  - **Blocks the Build-it scene shows** (each one narrated):
    1. `class BoxError(ValueError)` and its docstring: a `ValueError`, so ep06's `except` and tests still hold.
    2. `read_header(data, at, end=None)`: `end` defaults to `len(data)`; the 8-byte guard against `end`; the
       packed read of size (u32), type (4 bytes decoded as `latin-1`, not ASCII: any byte value decodes) and
       header 8; `size == 1` (with 16 bytes to hand) → `u64` at +8, header 16; `size == 0` → runs to `end`;
       `uuid` → header + 16; the two size checks, now against `end` and the real header length.
    3. `iter_boxes`: the one changed line, `read_header(data, at, end)`.
    4. `read_fullbox`: one `u32` split into version (`>> 24`) and flags (`& 0xFFFFFF`).
    5. `cmd_boxes`: the print with ` (header N)` when the header is not 8, and `except boxes.BoxError`.
  - **On-screen trim:** show `read_header` as ep06's version edited in place (a diff view), so the six
    unchanged ideas are not retyped; type only the `end` line, the three branches and the new messages.
- **ep08 (13, plan ~9).** `read_ftyp` (3), `DECODERS` (1), `decode` (2) and the ftyp branch in `cmd_boxes`
  (an `if`/`else` around the ep07 print, 4 of the 13). The brands are decoded as `latin-1`, like the box type.
  - **Earlier tests changed at this tag** (all three for the same reason: `boxes` now prints the decoded ftyp
    line first, `ftyp: isom 512 [isom, iso2, avc1, mp41]`, in place of `ftyp 0 32`):
    `test_ep06.test_cmd_boxes`, `test_ep06.test_cmd_boxes_error` and `test_ep07.test_cmd_boxes_large`. Each
    carries the comment that its own tag keeps its original test; tags ep06 and ep07 still run their own
    tests and `expected/` files under check.sh.
  - **Blocks the Build-it scene shows:** `read_ftyp` (major at the payload, minor as a `u32` at +4, then a
    brand every 4 bytes from +8 to the box's end); `DECODERS = {"ftyp": read_ftyp}`; `decode` (look up, or
    `{}`); the `if box.type == "ftyp"` branch in `cmd_boxes`.
- **ep09 (36, plan ~34; a finale).** Within budget. `CONTAINERS` and `CHILD_OFFSET` (4 lines between them),
  `walk` (4), `read_mp4` (2), `cmd_dump` (11, with the `try`/`except BoxError` and the `no moov box` line),
  `_print_tree` (5) and `_add_dump` plus its entry in `main`'s tuple.
  - **Blocks the Build-it scene shows:** the two tables (which boxes hold boxes, and how many bytes of their
    own fields a box has before its children: stsd 8, dref 8, meta 4, visual sample entries 78, audio 28);
    `walk` (list the boxes from `start` to `end`, then walk into each container from
    `payload + CHILD_OFFSET` to its own end, so a child is checked against its parent); `read_mp4`;
    `cmd_dump` and `_print_tree` (two spaces per depth, then `type start size` and any decoded `key=value`).
  - **On-screen trim:** show `_add_dump` and the new entry in `main`'s tuple as finished code.
- **ep10 (49, plan ~17).** Season 2's opener; the plan's ~17 counted `find`, a timescale/duration-only
  `read_mvhd` and `seconds`. The extra lines are:
  - `read_mvhd` reads version 1 (64-bit creation, modification and duration) as well as version 0, checks the
    box is long enough (108 / 120 bytes) and that timescale is not 0, both as `BoxError` with the offset
    (design rule 4), and returns rate, volume and next_track_ID too (episode 28's `write_mvhd` test reads
    rate 1.0 and volume 1.0 back through it, so they belong to this episode, not a later extension). It
    also returns `seconds` from `timing.seconds`, so dump prints the length in seconds next to the ticks.
  - `find` walks on to the next sibling when the first box of a type does not lead down the path
    (`moov/trak/mdia/minf/smhd` is only in the second trak): 10 body lines, not ~4.
  - `dump --find TYPE` prints each match by its path from the top (`moov/mvhd 108752 108 …`), the very path
    `find` takes, plus `no TYPE box` when there is none: the new `_print_found` (10 body lines), a branch in
    `cmd_dump` (its `try` now also covers printing, so a broken mvhd prints `error: …` and exits 1), and the
    `--find` argument.
  - **Earlier test changed at this tag:** `test_ep09.test_dump_phone_first_lines` (dump's mvhd line now carries
    the decoded fields). It carries the comment that tag ep09 keeps its own test.
  - **Blocks the Build-it scene shows:** `find` (split the path at the first `/`, match the type, go down the
    rest); `seconds` (ticks / timescale); `read_mvhd` (version, size check, the two time widths, timescale at
    payload + 12 in version 0, duration after it, the timescale-0 check, rate 16.16, volume 8.8, next_track_ID
    76 bytes after rate); `DECODERS["mvhd"] = read_mvhd`; the `--find` branch of `cmd_dump`.
  - **On-screen trim:** show the version-1 lines of `read_mvhd`, its two checks, `_print_found` and the
    `--find` argument as finished code; type `find`, `seconds`, the version-0 path of `read_mvhd` and the
    registration line (about 20 lines).
- **ep11 (35, plan ~21).** The plan's ~21 counted `find_all` (~4), `fixed` (1), a version-0 `read_tkhd` that
  reads flags, duration, width and height, and a `rotation` for the two matrices the episode shows. The extra
  lines are:
  - `read_tkhd` reads version 1 (64-bit creation, modification and duration) as well as version 0 and checks the
    box is long enough (92 / 104 bytes) as a `BoxError` with the offset, as `read_mvhd` does (design rule 4):
    4 lines. It also returns track_ID, volume (8.8, a second use of `fixed`; episode 28's `write_tkhd` takes a
    volume), the nine matrix numbers and `rotation`, so dump prints the matrix next to the angle. It does not
    read layer or alternate_group (alternate_group is H07, episode 23, Many tracks), nor the creation and
    modification times (0 in every committed file).
  - `rotation` looks the matrix's a, b, c, d up in `TURNS`, the four plain turns (0, 90, 180, 270; 2 lines), so
    a matrix that is not a plain turn gives `None` rather than a wrong angle. No `math` (design rule 6).
  - `find_all` keeps `find`'s one-statement-per-line loop: 9 body lines, not ~4.
  - `cmd_dump` is unchanged; one comment in `cli.py` now names `read_tkhd` too (the 1/-1).
  - **No earlier test changed:** test_ep09's first-lines test stops at mvhd, so the decoded tkhd line does not
    touch it.
  - **Blocks the Build-it scene shows:** `find_all` (find's loop, but every match is kept: `append` at the end
    of the path, `extend` with the matches below); `fixed` (value / 2^frac_bits); `TURNS` and `rotation`; the
    version-0 path of `read_tkhd` (track_ID 12 bytes into the payload, duration 8 after it, then 8 reserved,
    layer, alternate_group, volume at +12, matrix at +16 as nine signed 32-bit numbers, width +52, height +56);
    `DECODERS["tkhd"] = read_tkhd`.
  - **On-screen trim:** show the version-1 lines and the size check of `read_tkhd` as finished code (ep10's
    pattern), and `TURNS`'s 180 and 270 entries as finished; type `find_all`, `fixed`, `rotation`, the
    version-0 path and the registration line (about 22 lines).
- **ep12 (28, plan ~14).** The plan's ~14 counted a version-0 `read_mdhd` (timescale, duration, language), a
  one-line `language` and a `read_hdlr` that reads handler_type and name. The extra lines are:
  - `read_mdhd` follows `read_mvhd` line for line: version 1 (64-bit creation, modification and duration; 44
    bytes) as well as version 0 (32 bytes), the size check and the timescale-0 check as `BoxError` with the
    offset (design rule 4): 5 lines. It also returns `seconds` (as `read_mvhd` does), so dump prints both clocks
    in seconds and the two-clocks point reads straight off `--find mdhd`. Every committed file's mdhd is
    version 0; the version-1 path is tested in memory.
  - `language` unpacks the three letters one statement per line (first, second, third, then the `chr` sum):
    4 body lines, not 1.
  - `read_hdlr` checks for the 32 bytes before the name (`BoxError`, 2 lines). The name is read as a C string
    (UTF-8 up to the first zero byte, or to the box's end); every committed hdlr holds one (`VideoHandler\0`,
    `SoundHandler\0`, `SubtitleHandler\0`, and a lone `00` under udta/meta). A QuickTime-style counted
    (Pascal) name is not handled; it would show its length byte as a first character.
  - `cmd_dump` is unchanged; the comment in `cli.py` now says `tables` registers "its readers" (the 1/-1), so
    later episodes need not edit it.
  - **No earlier test changed:** test_ep09's first-lines test stops at mvhd.
  - **Blocks the Build-it scene shows:** `language` (shift 10, 5, 0, mask 0x1F, add 0x60); the version-0 path of
    `read_mdhd` (timescale 12 bytes into the payload, duration after it, language 2 bytes after duration);
    `read_hdlr` (handler_type 8 bytes into the payload, after version/flags and pre_defined; three reserved
    words; the name from +24 to the zero byte); the two `DECODERS` lines.
  - **On-screen trim:** show the version-1 lines and both checks of `read_mdhd` and the size check of
    `read_hdlr` as finished code (ep10's pattern); type `language`, the version-0 path, `read_hdlr`'s four
    reading lines and the two registration lines (about 21 lines).
- **ep13 (49, plan ~29).** The four plan functions come to 28 code lines with their three checks taken out (the
  `nal` import 1, `read_stsd` 4, `read_visual_entry` 6, `codec_string` 3, `read_avcc` 12, the two `DECODERS`
  lines): the plan's estimate. The extra 21 are cli.py's 15 and the checks' 6:
  - `cmd_sps` reads the SPS and PPS from `find(walk(data), "moov/trak/mdia/minf/stbl/stsd/avc1/avcC")` and
    `read_avcc` instead of ep04's byte search (section 4.1 of the plan assigns this to episode 13): 9 added, 5
    removed, 3 of the 9 being the `no …/avc1/avcC box` error and exit 1 (a file with no avc1, such as hevc.mp4,
    would otherwise raise `AttributeError` on `None`; ep04's search raised `ValueError`). `cmd_annexb` keeps the
    stopgap.
  - `_show` (3 body lines) and the two `_show(v)` edits in `_print_tree` and `_print_found`: avcC's SPS and PPS are
    bytes, and dump now prints bytes as hex digits (`SPS=['6764001e…']`) instead of Python's `b'gd\x00\x1e…'`.
    Every other field prints exactly as before (a list of ints or strings is unchanged).
  - The checks (design rule 4), 2 lines each: `read_stsd` raises when entry_count and the boxes inside disagree;
    `read_visual_entry` when the box is under 86 bytes; `read_avcc` when the parameter sets run past the box.
  - **Left for later episodes:** `read_stsd` is not registered in `DECODERS` (it returns boxes, not fields, and
    dump already prints the entries as children); only `avc1` registers `read_visual_entry` (hvc1, hev1, av01 and
    encv have the same 78 bytes of fields, episode 33 / 35 can register them in one line each); `codec_string`
    builds `avc1.` strings from an avcC's fields only (avc3 has no committed file; hvc1/av01 strings are episode
    33); numOfSequenceParameterSetExt is not read (0 in every committed file).
  - **Field names** follow ISO/IEC 14496-15 (design rule 5): `lengthSizeMinusOne=3` (the plan's "length size 4" is
    it + 1), `SPS` / `PPS` as lists (numOfSequenceParameterSets is the low 5 bits of 0xE1 = 1), `chroma_format`,
    `bit_depth_luma_minus8`, `bit_depth_chroma_minus8`. The tail is read for any profile other than 66, 77, 88
    (the 14496-15 rule ffmpeg's writer follows) when 4 bytes are left in the box.
  - **No earlier test changed:** test_ep09's first-lines test stops at mvhd and test_ep04's `test_cmd_sps` output is
    unchanged (`profile 100 level 30 640x360 CABAC`).
  - **Blocks the Build-it scene shows:** `read_stsd` (entry_count at payload + 4, the entries walked from payload +
    8); `read_visual_entry` (data_reference_index +6, width +24, height +26, compressorname's length byte +42 and
    the name from +43, depth +74; children from +78); `read_avcc` (the five bytes at the payload, the SPS count's low
    5 bits, the SPS and PPS with their 2-byte lengths through `nal._read_param_sets`, the High tail);
    `codec_string` (100, 0x00, 30 → `64 00 1E`); the two `DECODERS` lines; `cmd_sps`'s four new lines.
  - **On-screen trim:** show the three checks, the High-profile tail, `_show` with its two call sites and
    `cmd_sps`'s `None` branch as finished code (ep10's pattern); type `read_stsd`'s three reading lines,
    `read_visual_entry`'s name and return, `read_avcc`'s reading lines, `codec_string`, the registration lines and
    `cmd_sps`'s find / read_avcc / parse lines (about 24 lines).
- **ep14 (23, plan ~15).** The four plan functions with their check taken out come to 18 code lines
  (`read_table` 4, `read_stts` 2, `read_stss` 4, `decode_times` 8); the extra are the check's 3 lines and the
  two `DECODERS` lines:
  - `read_table` raises `BoxError` when entry_count's rows run past the box (design rule 4; walk.py's `table()`
    had no check): the `if` and a `raise` wrapped over two lines to stay inside 120 columns.
  - `boxes.DECODERS["stts"]` and `["stss"]` are one-line lambdas that wrap the lists in a dict (dump prints a
    reader's dict), so `dump f1.mp4 --find stss` prints `sample_number=[1, 5, 9]` and `--find stts` prints
    `entries=[(12, 33)]`. Two lines, no named helper.
  - `decode_times` keeps one statement per line (`times`, `t`, two loops, append, add, return: 8), where
    walk.py packed it into 5.
  - **Not done here (left for later episodes):** `read_table` ignores version and flags (stts and stss are
    always version 0; ctts version 1 in ep17 needs only the format `">Ii"`); walk.py's `skip` argument is not
    carried (stsz, ep15, has its own shape); no time → sample or keyframe lookup (`sample_at`, `sync_before`
    are ep19); dump prints stts runs, not each sample's decode time.
  - **No earlier test changed:** test_ep09's first-lines test stops at mvhd, and no test compares a full dump
    of a file with an stbl.
  - **Blocks the Build-it scene shows:** `read_table` (entry_count at payload + 4, rows from payload + 8,
    `struct.calcsize(fmt)` bytes each); `read_stts` (`">II"`); `read_stss` (the `None` branch, then the first
    column of `">I"` rows); `decode_times` (the running total); the two registration lines.
  - **On-screen trim:** show `read_table`'s check and the two registration lines as finished code (ep10's
    pattern); type the rest (about 18 lines).
- **ep15 (29, plan ~16).** The four plan functions with the check taken out come to 18 code lines
  (`read_stsc` 2, `read_stco` 3, `read_stsz` 7, `chunk_sizes` 6), near the plan's estimate. The extra 11 are the
  check's 3 lines and dump's wiring, 8:
  - `read_stsz` raises `BoxError` when sample_count's entries run past the box (design rule 4), as `read_table`
    does: `stsz at 0: sample_count 13 needs 72 bytes, box has 68`. stsz does not fit `read_table`: after
    version/flags come sample_size and sample_count, and the entries are there only when sample_size is 0 (a
    non-zero sample_size means every sample is that size, and the list is expanded). So it reads its own two fields
    and its own rows (and so needs its own check). walk.py's `skip` argument would have fitted it, but it would print
    `entry_count` for stsz's sample_count; not carried (ep14's note).
  - `_stsc_fields` (4 body lines) is stsc's decoder, so the episode command prints the unrolled chunks:
    `dump f1.mp4 --find stsc` prints `entries=[(1, 4, 1), (3, 2, 1)] chunk_sizes=[4, 4, 2, 2]`. stsc alone does
    not say how many chunks there are (its last rule runs to the final chunk), and a decoder gets only `(data, box)`,
    so it walks the file again, takes the stbl that holds this stsc and counts its stco (or co64) entries.
  - Three registration lines: `stsc`, `stco` and `co64` (one chained line, both through `read_stco`), `stsz`.
    Field names follow the spec: `chunk_offset`, `entry_size`.
  - **Not done here (left for later episodes):** no sample → chunk → offset function (`sample_table`, ep16; the
    episode works sample 7's offset by hand); stsc's sample_description_index is read but not used (1 in every
    committed file); `_stsc_fields` has no check for an stbl without stco/co64 (none in the committed files; it
    would raise `AttributeError`); stz2 (compact sizes) is not read (no committed file has one).
  - **Earlier test changed at this tag:** `test_ep10.test_cmd_dump_find_many` (dump's stco lines now carry
    `chunk_offset=[…]`); it now compares each line's path, start and size, with the comment that tag ep10 keeps
    its own test.
  - **Blocks the Build-it scene shows:** `read_stsc` (`">III"`); `read_stco` (`">I"`, or `">Q"` for co64);
    `read_stsz` (sample_size at payload + 4, sample_count at + 8, the constant branch, the rows from + 12);
    `chunk_sizes` (each rule ends where the next begins, the last at n_chunks + 1); the three registration lines.
  - **On-screen trim:** show `read_stsz`'s check, `_stsc_fields` and the registration lines as finished code
    (ep10's pattern); type the rest (about 18 lines).
- **ep16 (50, plan ~30).** The three plan names with the check taken out come to 38 code lines (`Sample` 8:
  decorator, class line and six fields; `sample_table` 15 with its signature and without the check call;
  `cmd_samples` 15 with its signature), 8 over the plan's estimate, mostly `Sample`'s field lines. The extra
  12 are the check (6: `_check_counts`, 4, and its call, plus the `dataclass` import) and the command's
  registration (`_add_samples` 5, the `main` tuple 1, changed):
  - `_check_counts` raises `BoxError` when the drawers disagree on how many samples the track has (design rule 4):
    stts's runs, stsc unrolled over stco's chunk count, and stsz's sample_count. f1 with stts's sample_count 12
    changed to 11: `stbl at 22422: stts has 11 samples, stsc 12, stsz 12`. Without it, a short stts would raise a
    bare `IndexError` and a short stsc would silently drop samples (`zip` stops early). It is its own helper so
    that `sample_table`'s body stays at 15 lines.
  - `cmd_samples` prints a header line, `track 1 vide, timescale 15360, 60 samples` (hdlr and mdhd, 3 lines), so
    the dts column has a clock; then `sample dts key offset size` and one line a sample, its columns in lookup
    order (stts, stss, stsc + stco, stsz). `--track N` counts traks from 1 in file order (ffprobe's stream index
    + 1), default 1; out of range prints `error: no track 3, the file has 2`, exit 1 (broken-nomoov.mp4: `the file
    has 0`).
  - `cts` is filled with `dts`: ctts is episode 17 (`read_ctts`, `composition_times`). `sync is None or n in
    sync`: no stss means every sample is a keyframe (aac-only and every audio track).
  - **Not done here (left for later episodes):** no ctts, no edit list (17, 18; dts starts at 0, where ffprobe
    prints phone's first video dts as -1024); `cmd_samples` does not catch `BoxError` (a broken table prints a
    traceback ending in the message; none of the committed files raises one); a track whose stsd holds several
    sample entries is not split (sample_description_index is 1 everywhere); fragmented files give `[]` (frag,
    episodes 30–31).
  - **No earlier test changed.**
  - **Blocks the Build-it scene shows:** `Sample` (six fields); `sample_table` (the five lookups in mnemonic
    order, Tired Sailors Carry Oars Slowly, then the loop: each chunk's offset, plus each sample's size);
    `cmd_samples`'s header and the row print.
  - **On-screen trim:** show `_check_counts`, its call, `cmd_samples`'s track check and `_add_samples` as finished
    code (ep10's pattern); type the rest (about 30 lines).
- **ep17 (41, plan ~21).** The plan's names come to 29 code lines: `read_ctts` 5, `composition_times` 3,
  `access_units` 12 (H.264 7.4.1.2.3 needs two rules, "an AUD, SPS, PPS or SEI after a slice" and "a
  slice with first_mb_in_slice 0 after a slice", and the has-slice flag that tells them apart), the POC branch in
  `read_slice_header` 2 (section 4.1), and `--pts` in `cmd_samples` 7 (3 changed lines: the header choice and the
  print loop; the `_time_columns` helper 3; the `add_argument` line 1). The extra 12:
  - `_clocks` (8) and its call in `sample_table` (1 changed line), plus the `cts[n - 1]` change (1): stts and ctts
    read together, so that `sample_table`'s body stays at 15 lines, and a ctts that covers a different number of
    samples than stts raises `BoxError` with ctts's offset (design rule 4): f2 with its last run's sample_count 2
    changed to 1 (byte 21490): `ctts at 21407: ctts has 11 samples, stts 12`. Without it, `composition_times`'s
    `zip` stops early, so a short ctts makes `sample_table` raise a bare `IndexError` and a long one is cut silently.
  - the `ctts` decoder for `dump` (2): `dump f2.mp4 --find ctts` prints `version=0 entries=[(1, 33), (1, 99),
    (2, 0), ...]`, the slip runs the xxd scene shows.
  - `_time_columns` is its own helper so that `cmd_samples`'s body stays at its ep16 length (14).
  - **`--pts` prints** `sample dts cts display key offset size`: cts right after dts (Do Cats Purr: DTS → CTS),
    then the sample's place in display order (by cts). Without `--pts` the output is ep16's, byte for byte
    (expected/ep16.txt still passes).
  - **cts is not ffprobe's pts:** ffprobe applies the edit list, so on every track its pts = our cts − the same
    shift as its dts (33 on f2; 1024 on phone and the other ffmpeg files; 0 on f1, av1 and subs track 3). Episode 18
    (`read_elst`, `presentation_times`) applies it; at this tag the test compares pts + shift.
  - **ctts version 1:** no committed file has one (all eleven ctts boxes are version 0), so the signed read is
    tested on a hand-packed box (design rule, section 5): rows (1, 0), (1, 66), (2, −33); the same bytes stamped
    version 0 read −33 as 4,294,967,263.
  - **One earlier test changed:** test_ep16 `test_sample_table_phone` asserted cts = dts on phone's video (its
    comment said "ctts is episode 17"); it now asserts phone video's cts 1024 and 2560 for samples 1 and 2, and
    cts = dts on audio only. Tag ep16 keeps its own test.
  - **Not done here:** no edit list (18); no command uses `access_units` yet (its test groups f1's Annex B
    stream from episode 5); POC types 1 and 2 are not decoded (f1 is type 2, so its slices carry no
    pic_order_cnt_lsb; phone and f2 are type 0); POC wrap-around beyond log2_max_poc_lsb is not handled (phone's
    GOP of 30 frames reaches POC 58 < 64).
  - **Blocks the Build-it scene shows:** `read_ctts` (version 0 vs 1: `>II` or `>Ii`); `composition_times`
    (CT = DT + offset); `sample_table`'s one changed line; `access_units`; the POC branch.
  - **On-screen trim:** show `_clocks`'s count check, the `ctts` decoder, `_time_columns` and the argparse line as
    finished code (ep10's pattern); type the rest (about 25 lines).
- **ep18 (27, plan ~14).** The plan's two names come to 12 code lines: `read_elst` 5 (`>Iihh` for version 0,
  `>Qqhh` for version 1: media_time and the rate halves are signed, so an empty edit's `ff ff ff ff` reads −1) and
  `presentation_times` 7. The extra 15:
  - `--pts` applying the edit list in `cli` (13; plan 4.1: "applies the edit list (18)"): `_time_columns` now
    takes the trak, reads its elst and the two clocks (mdhd and mvhd: the timer's length is in the movie's clock)
    and runs `presentation_times` over dts and over cts (10 body lines + its `def`); `cmd_samples` changes 2 lines
    (the header and the call); the `--pts` help text 1. `cmd_samples`'s body stays at its ep16 length (14).
  - the `elst` decoder for `dump` (2): `dump phone.mp4 --find elst` prints `version=0 entries=[(96000, 1024, 1,
    0)]` for each track.
  - **`--pts` prints** `sample dts pts display key offset size`: dts and pts with the edit list applied to both
    clocks, which are ffprobe's dts and pts exactly (phone: `1 -1024 0 1 K 48 5824`). The cts column of ep17 is
    replaced by pts: the edit list moves the whole track, so a dts left unmoved next to a moved pts would mix two
    timelines, and the plan's command row asks for "first DTS −1024, PTS 0". cts stays in `Sample.cts`.
    Without `--pts` the output is ep16's, byte for byte.
  - **One earlier test changed:** test_ep17 `test_cmd_samples_f2_pts` compared `samples f2.mp4 --pts` with
    expected/ep17.txt; it now asserts the ep18 header `sample dts pts display key offset size` and that each line
    is ep17's line with dts and cts lowered by f2's media_time 33 (`1 -33 0 1 K 40 5589`). Tag ep17 keeps its own
    test and its expected file (check.sh runs each tag's own).
  - **Shapes no committed file carries** (all 21 elst boxes are version 0 with one entry and media_rate 1; f1 and
    frag-cmaf have no edts): version 1, empty edits (media_time −1), several entries and media_rate 0 are tested
    on hand-packed boxes. The empty-edit bytes are those of phone.mp4 re-muxed with `-itsoffset 0.25`, whose
    ffprobe pts the test's numbers match (captures ep18).
  - **Not done here:** samples outside the edit's window are kept (ffprobe drops subs track 3's 4th sample, which
    starts at the edit's end, 91,200 movie ticks = 1,900,000 track ticks); only the first media edit moves the
    track (later edits would cut or repeat media); media_rate is read but not applied (a dwell, rate 0, holds one
    picture). Empty-edit time is converted with floor division (every case here divides exactly).
  - **Blocks the Build-it scene shows:** `read_elst` (version 0 vs 1); `presentation_times`; the two lines of
    `_time_columns` that call it.
  - **On-screen trim:** show the `elst` decoder, the clock lookups in `_time_columns` and the argparse line as
    finished code (ep10's pattern); type the rest (about 18 lines).
- **ep19 (72, plan ~25; a finale, inside its ≤ ~90).** The plan's three names come to 36 code lines:
  `sample_at` 5, `sync_before` 7 and `cmd_frame` 16 plus `_add_frame` 6 and its entry in `main`'s tuple 2 (the
  `for add in` line is rewrapped). The extra 36:
  - `_frame_route` (16): front door to time drawer, the first `vide` track, its samples and their PTS (it calls
    ep18's `_time_columns`, so `--at` is read on the same timeline `samples --pts` prints and ffprobe uses), and
    `--at` converted from milliseconds to the track's ticks (`at * timescale // 1000`: f2 198 → 198, phone 1000 →
    15,360). Its two checks: no moov (broken-nomoov: `error: no moov box (moov atom not found): the file is
    truncated`, exit 1, the plan's message; "moov atom not found" is ffprobe's own words) and a time outside the
    movie (mvhd's duration: `--at 396` on f2, `error: --at 396 ms is outside the movie, which lasts 396 ms`).
    Split out of `cmd_frame` to keep its body at 15.
  - `_annexb_samples` (9): `--out`'s stream, SPS and PPS from avcC (ep13's `read_avcc`), then every NAL unit of
    samples keyframe..target with its length label (lengthSizeMinusOne + 1 bytes) swapped for a start code
    (ep05's `to_annexb`). A track with no avc1/avcC (hevc, av1) is refused: `--out writes H.264 only`.
  - `_print_route` (5): the two route lines, including which picture of the decoded run the target is: a
    decoder shows them in display order, so for f2 at 198 the 4 decoded samples 5–8 show as 132, 165, 198, 231
    and the target is picture 3.
  - `boxes.read_mp4` maps the file (plan 4.1: "returns an `mmap`") (5 with `import mmap`, `import os`): an empty
    file cannot be mapped, so it gives `b""`. `cli` imports `Path` (1) for the one-line write.
  - **`--at` is milliseconds** (plan section 3: `frame <file> --at <ms>`), converted to the track's ticks and
    looked up on the presentation timeline (PTS, the edit list applied). f2's clock is 1000, so its ms are its
    ticks: 198 → sample 8 (PTS 198, shown 7th). Read as raw CTS or raw DTS (no edit list) 198 is sample 7, one
    picture early (test `test_sample_at_needs_pts`); phone (15,360) tells ms from ticks: 1000 ms → sample 31.
  - **One earlier test changed:** test_ep09 `test_read_mp4` compared `read_mp4` with the file's bytes; an mmap
    does not compare equal to bytes, so it compares `bytes(read_mp4(...))`. Tag ep09 keeps its own test.
  - **Not done here:** a damaged table is not detected (broken-stco's sample 1 offset is 1,000 bytes off, so
    `--out` would cut the wrong bytes; `check`, episode 36); fragmented files have no samples in moov (frag-cmaf:
    mvhd duration 0, `outside the movie, which lasts 0 ms`; episode 31); only the first video track; the frame
    is written as an Annex B stream, not decoded to pixels (a decoder does that: `ffmpeg -i frame.h264`).
  - **Blocks the Build-it scene shows:** `sample_at` (the last picture shown at or before t); `sync_before` (the
    last keyframe at or before n); `cmd_frame`'s three lookups inside its `try`; `_annexb_samples`.
  - **On-screen trim:** show `_frame_route`'s two checks, `_print_route`, `read_mp4`'s mmap and `_add_frame` as
    finished code (ep10's pattern); type the rest (about 35 lines).
- **ep20 (60, plan ~23).** The plan's five names come to 22 code lines in the new `audio.py`: `SAMPLE_RATES` 1,
  `pcm_bytes` 2, `frame_seconds` 2, `adts_header` 4 and `split_adts` 13. The extra 38 are `dump --pcm` in `cli`
  (plan 4.1: "`--pcm` (20)"), which the plan's estimate did not count:
  - `_sound_tracks` (15): each soun track (hdlr) with samples in its stsz: the sample rate from its mdhd clock
    (ep12; the corridor's clock is the sample rate, 48,000 and 44,100), channelcount and samplesize as the sample
    entry's two u16s at 16 and 18 of its fields (episode 21's `read_audio_entry` reads the whole entry and replaces
    those two reads), its length from tkhd on the movie clock (ep11/ep10: 96,000 / 48,000 = 2 s, ffprobe's
    duration_ts 96,000) and its sizes (ep15's `read_stsz`).
  - `_print_pcm` (14): the five lines (expected/ep20.txt). The 2 s is the track's presented length, the edit
    list already applied, so `pcm_bytes(2, 48000, 2, 16)` = 384,000 is exactly what ffmpeg decodes
    (`ffmpeg -i phone.mp4 -map 0:a -f s16le - | wc -c` → 384000; aac-only → 176400). All 95 frames decode to
    95 x 1,024 = 97,280 samples (389,120 bytes; mdhd's 97,024 ticks would be 388,096); ffmpeg drops the 1,024
    priming samples and the last frame's 256 trimmed ones (stts's 768), leaving 96,000 (episode 22). One second: 192,000 bytes of PCM against 24,347 / 2 = 12,174 bytes of AAC
    on average (round half even: aac-only's 8,220.5 prints 8220). esds's avgBitrate 96,360 bit/s (12,045 B/s)
    divides by mdhd's 2.0213 s, priming included; the line divides by the presented 2 s.
  - `_dump_view` (7, 4 of them moved): `cmd_dump`'s view choice (tree, `--find`, `--pcm`) as its own function,
    because a third branch would take `cmd_dump` to 17; episodes 22 and 28 add their views here too.
  - the `--pcm` argparse line (1) and `cmd_dump`'s call (1).
  - **ADTS byte for byte:** phone's 95 samples and aac-only's 88, each behind `adts_header`, equal ffmpeg's
    `-c:a copy -f adts` output exactly (25,012 and 17,057 bytes; the test pins their SHA-256 and the first
    headers `fff14c801ebffc` and `fff1504021fffc`). ffmpeg keeps the priming frame in the ADTS stream: no timer
    survives (episode 22's "where it breaks"). `split_adts` gives back the same payloads and the same fields dict
    (`audioObjectType`, `samplingFrequencyIndex`, `channelConfiguration`: the names `parse_asc` and `asc_bytes`
    use in episodes 21 and 22); a 9-byte header (CRC present) is tested on hand-packed bytes.
  - **Not done here:** the frame length is AAC-LC's 1,024 for every soun track (frameLengthFlag, 960, is in the
    AudioSpecificConfig, episode 21); `split_adts` takes the first header's fields and does not check the CRC or
    that later headers agree; only the first sample entry is read; a fragmented file's sound has no samples in
    its stsz (frag-cmaf: `no sound track with samples`, episode 30); the ADTS asc dict is written by hand in the
    test (episode 21 reads it from esds).
  - **Blocks the Build-it scene shows:** `pcm_bytes` (the multiplication); `frame_seconds`; `adts_header` (the
    56-bit field layout); `split_adts` (jump by frame length); `_print_pcm`'s five lines.
  - **On-screen trim:** show `_sound_tracks`, `_dump_view`, `SAMPLE_RATES` and the argparse line as finished
    code (ep10's pattern); type the rest (about 36 lines).
- **ep21 (48, plan ~28).** The plan's four names come to 35 code lines: `read_audio_entry` 6 (with its size
  check), `read_descriptor` 7, `read_esds` 15 and `parse_asc` 7; their registrations (`mp4a`/`enca`, `esds`) and
  audio.py's `import boxes` are 3 more. The other 10:
  - `_open` (6): open one envelope and check it is the one expected and ends inside its parent (the box's end
    for 0x03, 0x03's end for 0x04 and 0x06, 0x04's end for 0x05): the box rule of episode 7 (a child may not run
    past its parent) for descriptors. Without it `read_esds` repeats the check three times and goes past 15.
  - `cli` (4 added, 3 removed): `cmd_dump` imports `audio` too, so `--find esds` finds its reader; `_sound_tracks`'s
    two raw u16 reads (ep20) become `read_audio_entry` (`--pcm`'s output is unchanged: expected/ep20.txt).
  - **The numbers (aac-only / phone):** mp4a at 16906 (90 B: 8 + 28 + esds 54) / 110619 (110 B: + btrt 20);
    channelcount 1 / 2, samplesize 16, samplerate 0xac44_0000 / 0xbb80_0000 = 44,100.0 / 48,000.0 (16.16).
    esds at 16942 / 110655, 54 B: ES_Descriptor `03 80 80 80 25` (37 = the rest of the box), ES_ID 1 / 2 (the
    track_ID), flags 0; DecoderConfigDescriptor `04 80 80 80 17` (23): objectTypeIndication 0x40, `15` = streamType
    5 << 2 | upStream 0 | reserved 1, bufferSizeDB 0, maxBitrate = avgBitrate 65,009 / 96,360;
    DecoderSpecificInfo `05 80 80 80 05`: ASC `12 08 56 e5 00` / `11 90 56 e5 00`; SLConfigDescriptor
    `06 80 80 80 01`, predefined 2. ASC `12 08` = 00010 0100 0001 = object type 2 (AAC LC), index 4 = 44,100, 1
    channel; `11 90` = 2, index 3 = 48,000, 2 channels. ffprobe agrees on every one it prints (sample_rate,
    channels, profile LC, bit_rate, extradata_size 5, mime_codec_string `mp4a.40.2`, the `codec` field).
  - **`parse_asc` returns exactly the three fields an ADTS header carries** (the names of ep20's dict), so
    `adts_header(parse_asc(esds["ASC"]), n)` replaces the test's hand-written dict (same first headers,
    `fff14c801ebffc` and `fff1504021fffc`), and episode 22's `parse_asc(asc_bytes(x)) == x` holds without extra
    keys. The sample rate (`SAMPLE_RATES[index]`) and the codec string are added by `read_esds`.
  - **Not done here:** `parse_asc` refuses object type 31 (escape) and rate index 15 (a 24-bit rate) instead of
    reading them; frameLengthFlag (bit 13: 960 samples) and the trailing `56 e5 00` (sync extension 0x2b7: SBR
    signalled absent) are not read; QuickTime sound entry versions 1 and 2 (more fields before the boxes) are not
    read (ffmpeg writes version 0); the ES_Descriptor's three optional fields are skipped, not returned; an esds
    for another codec (objectTypeIndication other than 0x40, e.g. 0x6B MP3) is read the same way and its
    DecoderSpecificInfo still parsed as an ASC; a descriptor after 0x05 inside 0x04 (profile-level) is ignored.
  - **Blocks the Build-it scene shows:** `read_descriptor` (the size code, 7 bits a byte); `read_esds`'s three
    `_open`s, envelope inside envelope; `parse_asc` (13 bits by shifts); `read_audio_entry`'s four fields.
  - **On-screen trim:** show `_open`, the registrations, the ES flags lines and the `cli` changes as finished
    code (ep10's pattern); type the rest (about 32 lines).
- **ep22 (55, plan ~12).** The plan's three names come to 13 code lines in `audio.py`: `priming` 2,
  `edit_window` 5, `asc_bytes` 5 and the `timing` import 1 (`edit_window` converts with ep10's `timing.seconds`).
  The extra 42:
  - **The roll slip (22):** `tables.read_sgpd` (13) and `tables.read_sbgp` (8), registered in `boxes.DECODERS`
    (1). The episode's room is "the roll slip (sgpd/sbgp)" and ep21's script promised that "sgpd and sbgp join
    in" (`p12`, `h25`); without readers dump prints them as bare `sgpd 17448 26`. `read_sgpd` reads version 1
    with a default_length (what ffmpeg writes in every committed file); a `roll`/`prol` entry is a signed 16-bit
    roll_distance, other groupings' entries stay as bytes; version 0 and 2 give only version and grouping_type.
    `read_sbgp` skips version 1's grouping_type_parameter.
  - **`cli` (20):** `_print_priming` (15): after `--find elst`, three lines a sound track (expected/ep22.txt):
    the priming in samples and ms, the window the edit plays out of the track's mdhd length, the roll slip and
    the samples sbgp puts under it. It lives under each sound track, not on the elst line, because the same
    `(96000, 1024)` on phone.mp4's **video** is the B-frame delay (ep18), not priming; f2.mp4 (no sound) prints
    no priming lines. `_sound_tracks` hands back its trak too (1 changed, `_print_pcm`'s unpack 1 changed);
    `_dump_view`'s new branch (2); `cmd_dump` catches `ValueError` (BoxError's parent) so an edit list of only
    empty edits prints `error: no edit plays the track ...` instead of a traceback (1 changed).
  - `test_ep18.test_dump_elst` now checks that phone's two elst lines start the output (ep22 adds the priming
    lines after them).
  - **The numbers (aac-only / phone audio):** elst `00015888 00000400 0001 0000` / `00017700 00000400 0001 0000`:
    segment_duration 88,200 / 96,000 on the movie clock (mvhd 44,100 / 48,000), media_time 1,024 on the track's
    (mdhd 44,100 / 48,000) = 23.2 / 21.3 ms of priming; mdhd duration 89,224 / 97,024 = 1,024 + the window
    exactly. sgpd (26 B) version 1, `roll`, default_length 2, one entry `ff ff` = -1; sbgp (28 B) version 0,
    `roll`, one run (88 / 95, 1): every sample. ffprobe: initial_padding 1024, first packet pts -1024 with Skip
    Samples 1024, start_time 0, duration 2.000000 (duration_ts 88,200 / 96,000). ffmpeg decodes 88,200 / 96,000
    samples (176,400 / 384,000 B) with the edit list, 89,224 / 97,024 (178,448 / 388,096 B) with
    `-ignore_editlist 1`, and 90,112 / 97,280 (180,224 / 389,120 B) from the ADTS stream: every frame's 1,024,
    the priming and the last frame's 888 / 256 padded samples kept. The first 1,024 decoded samples without the
    edit list peak at 22 / 54 (of 32,767), quiet but not zero. `asc_bytes` gives `12 08` / `11 90`, the ASC's
    first two bytes (the trailing `56 e5 00`, the SBR sync extension, is not written), and
    `parse_asc(asc_bytes(x)) == x` holds for all 30 x 13 x 16 field values the 2-byte form can carry.
  - **Not done here:** only the first real edit is read (a second edit, or media_rate, is ignored);
    `edit_window` does not check that the window fits in the track; `priming` takes media_time as samples, true
    when the sound track's mdhd timescale is its sample rate (ffmpeg always; not required by the standard);
    `asc_bytes` writes frameLengthFlag 0 (1,024 samples) and no extension; Apple's implicit 2,112 (no roll group)
    is not assumed; fragmented files (no edit list, episode 30) give no priming lines.
  - **Blocks the Build-it scene shows:** `priming` (one line); `edit_window` (two clocks); `asc_bytes` (13 bits
    by shifts, `parse_asc` backwards); `read_sgpd`'s roll entry (`ff ff` signed).
  - **On-screen trim:** show `read_sbgp`, the registration, `read_sgpd`'s version and length guards,
    `_print_priming` and the `cli` changes as finished code (ep10's pattern); type the rest (about 22 lines).
- **ep23 (93, plan ~34).** The plan's three names come to 43 code lines: `tables.Track` 10 (the dataclass line, its
  decorator and 8 fields), `tables.read_tracks` 10, `cli.cmd_extract` 16, `_add_extract` 6 and `main`'s tuple 1.
  `Track` keeps the plan's six fields in the plan's order (`id, handler, timescale, entry, samples, elst`), so
  episodes 24, 25, 29 and 32 can build one positionally, and adds two with defaults: `tref` (the signposts,
  `{}` when none) and `duration` (mdhd's, in the track's ticks: the last text cue's end). `entry` is a dict:
  `"type"` (avc1, mp4a, tx3g, text, encv, ...), the sample entry's fields from its registered reader, and one key
  per box inside it (`"avcC"`, `"esds"`, `"pasp"`, `"btrt"`), each that box's fields. The other 50:
  - **The signposts (4):** `tables.read_tref` (2) and its registration (1); `tref` joins `boxes.CONTAINERS` (1),
    so walk opens it (ffprobe's trace names `chap` with parent `tref`; test_ep09's trace and CONTAINERS checks
    change with it) and dump prints `tref 109030 20 chap=[3]` with its `chap` child.
  - **The tray as a dict (7):** `tables._entry` (5); tables.py imports `field` and `audio` (2: audio registers
    esds, so a sound track's entry carries its ASC).
  - **Annex B as ffmpeg writes it (13):** `nal.annexb_sample` (7) and `cli._annexb_track` (6). ep19's
    `_annexb_samples` writes SPS and PPS once and 4-byte start codes everywhere; ffmpeg's `h264_mp4toannexb`
    puts SPS and PPS in front of **each keyframe's** IDR slice and gives a NAL unit a 4-byte start code only
    when it opens the sample (and for SPS/PPS), 3 bytes otherwise. With that rule the extract is ffmpeg's
    stream byte for byte (phone: the samples' 84,349 B are 84,105 B of NAL units + 61 length labels of 4; the
    stream is 84,105 + 2 x (SPS 26 + PPS 6) + 63 start codes of 4 + 2 of 3 = 84,427 B). ep19's `frame` output is unchanged (expected/ep19.txt).
  - **ADTS (4):** `cli._adts_track`: ep20's `adts_header` on ep21's `parse_asc` of the esds ASC.
  - **SRT for the text corridors (14):** `cli._srt_track` (9), `cli._srt_time` (3), `WRITERS` (2). A tx3g or
    QuickTime `text` sample is a 2-byte length and that many bytes of text; empty ones (subs' gap at 0.9 s and its
    zero-length tail) get no cue, which is also what ffmpeg's `-c:s srt` writes (87 B, identical).
  - **`cli._plain_stream` (8):** the two refusals (no such track; no writer for the entry type, or no samples:
    encv/enca, hvc1/hev1/av01, frag-cmaf's empty moov) as `ValueError`, so `cmd_extract` stays at 15.
  - **Earlier tests:** phone-chapters.mp4 is the 17th test file (committed with this tag; NEW-B1 cd2f05b6).
    test_ep09 counts 17 files and lists `tref` in CONTAINERS; test_ep13's sample-entry kinds gain `text`;
    test_ep17 and test_ep18 skip phone-chapters' track 3, for which ffprobe lists no packets (it reads the
    track as chapters).
  - **The numbers:** subs 3 tracks (vide avc1 60, soun mp4a 95, sbtl tx3g 4: stsz's 4, ffprobe's nb_frames 4,
    3 packets listed); phone-chapters 3 tracks (text text 2, 17 B each, tkhd flags 2), `tref` `00000014 74726566
    0000000c 63686170 00000003` at 109,030 and 110,504; the extracts of phone (84,427 / 25,012 B), f1, f2,
    aac-only, subs' SRT (87 B) and every phone copy (fast, large, rotated, subs, chapters) are ffmpeg's bytes;
    the stream from keyframe 31 is the full stream's tail from byte 41,676.
  - **Not done here:** only the first sample entry is read (a sample's stsc sample_description_index is
    ignored); `extract` writes H.264, AAC and text only (HEVC, AV1 and the encrypted entries are refused, not
    written: episode 33 for hvcC/av1C); a NAL length that runs past its sample is not checked (broken-stco's
    track 1 extracts to 292,817 B of garbage where ffmpeg reports `Invalid NAL unit size`: episode 36's
    `check.nal_lengths`); in-band SPS/PPS before an IDR are not detected (ffmpeg then inserts none; no
    committed H.264 file has them); SRT times are the samples' decode times without the edit list (subs' and
    phone-chapters' text elst start at media_time 0); text is read as UTF-8 (the chapter samples' `encd` box says
    256, UTF-8) and tx3g style records after the text are ignored; a fragmented file has no samples in its moov
    (episode 31 extends `read_tracks`).
  - **Blocks the Build-it scene shows:** `Track` (the fields); `read_tracks` (Trains Make Many Stops, once per
    trak); `read_tref` (one way: a list of track_IDs); `annexb_sample` (where SPS/PPS go and why: the keyframe);
    `_adts_track` (one line: ep20 + ep21); `cmd_extract`'s listing.
  - **On-screen trim:** show `_entry`, `_plain_stream`, `_srt_track`, `_srt_time`, `WRITERS`, `_add_extract` and
    the imports as finished code (ep10's pattern); type the rest (about 45 lines).
- **ep24 (62, plan ~25).** The plan's three names come to 31 code lines: `tables.chunk_list` 6, `mux.interleave` 9 and
  `cli.cmd_chunks` 16. `chunk_list(tracks)` keeps the plan's shape, `(offset, track, first sample, sample count)` sorted
  by offset, tracks counted from 1 in the list's order (phone: `(48, 1, 1, 2)`, `(8011, 2, 1, 1)`, 118 chunks, as the
  plan says). `interleave(tracks, chunk_seconds=0.5)` keeps its signature and returns `(track, first sample, sample
  count)` per chunk in mdat order, a pure function of `Track`s that episode 29's `mux.mux` can lay mdat out from (and
  episode 26's `stsc_rules` can turn into stsc from each track's counts). The other 31:
  - **Where a sample lies (3):** `Sample.chunk` (1), the chunk number from stsc, filled by `sample_table` (2 changed
    lines, no new ones: `enumerate` over the chunks). A `Track`'s samples did not say which chunk they sat in, and the
    chunk cannot be rebuilt from offsets alone (f1's four chunks touch end to start: `[4, 4, 2, 2]` would read as
    one). It is `compare=False`: where a muxer put a sample is not part of the sample, so episode 29's "read_tracks of
    the muxed file = the input tracks" can still hold. test_ep16's field list gains `chunk`.
  - **The movie's timeline (5):** `mux.timeline` (3), each sample's dts less the first real edit's media_time
    (`audio.priming`, ep22) over the track's clock, as a `Fraction`; `mux.py`'s two imports (2). It is ffprobe's
    `dts_time` for all 155 of phone's packets, and it is the zipper's key: phone's mdat is every sample sorted by
    (timeline, track), with no exception. Sorted by the stored dts (no shift) it goes backwards 59 times.
  - **The printing (22):** `_print_chunks` (13), `_chunk_columns` (5), `_add_chunks` (4) and `main`'s tuple; they keep
    `cmd_chunks` at 15.
  - **The numbers:** phone 118 chunks, 59 per track, and they alternate track 1, track 2 at every chunk; video 1–2 samples
    a chunk (only chunk 1 holds 2), sound 1, 2 or 4 (25, 33 and 1 chunks), a video chunk lasts 1/30 s (chunk 1: 2/30), a
    sound chunk 1,024 or 2,048 samples (0.0213 or 0.0427 s; the last, 4 samples, 0.0800); mdat's payload (48 to 108,744)
    is exactly the 118 chunks, no gaps. stco/stsc sorted independently, and ffprobe's packets grouped by `pos`, give the
    same 118 rows. `interleave` with 0.5 s (or 1 or 2.5) plans phone's exact order, and so for phone-fast, phone-large,
    rotated, cenc and broken-stco; 0 gives 155 chunks, 0.03 gives 120.
  - **Where ffmpeg is not the zipper:** a single track is one chunk (aac-only 88, the HEVC/AV1 files 60), where
    `interleave` cuts every 0.5 s (aac-only: 4 chunks of 22); ffmpeg writes phone-chapters' chapter samples first, at
    48 (one chunk of 2, before any video); subs' subtitle samples sit where ffmpeg's muxer got them (its empty gap
    sample, 0.9 s, after the video at 1.0 s), 3 chunks where the zipper plans 4; f1/f2 are minimux's `[4, 4, 2, 2]`.
    `cmd_chunks` says "a different order" for these.
  - **Not done here:** empty edits (media_time -1) do not shift a track on the timeline (`audio.priming` skips
    them; no committed file has one); `interleave` cuts by time only, not by bytes; seek precision is not a chunk
    property (stss [1, 31]: 59 video chunks start a sample, but a seek to 1.5 s still decodes from sample 31).
  - **Blocks the Build-it scene shows:** `Sample.chunk` (one field); `chunk_list` (one dict, then sort by offset);
    `timeline`; `interleave` (sort the teeth, then cut the runs); `cmd_chunks`.
  - **On-screen trim:** show `_print_chunks`, `_chunk_columns`, `_add_chunks`, the imports and the `sample_table`
    change as finished code; type the rest (about 35 lines).
- **ep25 (59, plan ~20).** The plan's three names come to 30 code lines: `timing.packets` 12, `timing.play_order` 2
  and `cli.cmd_packets` 16. `packets(tracks)` keeps the plan's shape, a list of dicts in ffprobe's vocabulary (G09):
  `stream` (ffprobe's stream_index, from 0), `dts`, `pts` (ticks on the movie's timeline: stored dts / cts less the first
  real edit's media_time, as `mux.timeline`), `dts_time`, `pts_time` (Fractions, ticks / timescale), `duration` (to the
  next sample's dts; the last to mdhd's duration), `size`, `pos`, `key`, sorted by pos. With the times printed to 6
  decimals it is the committed probe.json's `packets` for all 155 of phone's and for 11 more files (every copy of phone
  but broken-stco, f1, f2, aac-only, av1, hevc, hevc-hev1, hdr). `play_order(packets)` merges them by `(dts_time,
  stream)`, the reader's belt; for every one of those files it is file order. The other 29:
  - **How far a decoder reorders (2):** `timing.reorder_depth(packets)`, the most packets decoded before one and shown
    after it (H.264's `max_num_reorder_frames` is an upper bound on it, R§19): phone 1, f2 1, f1 0, hevc 2, sound 0.
  - **The printing (26):** `_print_packets` (12; the `shown` column is a packet's place in its stream's pts order),
    `_print_streams` (9), `_add_packets` (4) and `main`'s tuple; they keep `cmd_packets` at 15. `timing.py` gains `from
    fractions import Fraction` (1).
  - **The numbers:** phone 155 packets (60 + 95), file order = play order; video's first dts is 1,024 ticks = 2 × 512
    before its pts (the elst media_time), while the packets need a reorder depth of only 1 (decode I0 P3 B1 B2, shown I0
    B1 B2 P3); the SPS says `max_num_reorder_frames` 2 and ffprobe `has_b_frames` 2. f2: depth 1, 33 ticks = 1 × 33,
    SPS 1, `has_b_frames` 1. Sound: pts = dts, depth 0, the first packet at −1,024 (the priming frame, ep22).
  - **Where play order is not file order:** subs (the empty 0.9 s subtitle sample is written after the video at 1.0 s:
    file 83rd, play 76th) and phone-chapters (the two chapter samples written first, at 48 and 65: play 6th and 83rd).
    ffprobe hands both out in file order: ffmpeg's mov reader takes the lowest pos while the streams' next dts lie
    within 1 s of each other, and the lowest dts beyond that (`mov_find_next_sample`, `interleaved_read` on).
  - **Not done here:** empty edits (as ep24); ffprobe's packets for subs (158: its last, empty subtitle sample is not a
    packet) and phone-chapters (no chapter packets) are not this list; broken-stco's first packet is a keyframe to
    mp4kit (stss) and not to ffprobe (its parser reads the wrong bytes). The reader's 1 s rule is not modelled.
  - **Blocks the Build-it scene shows:** `packets` (one dict per sample, sorted by pos); `play_order` (one sort);
    `reorder_depth`; `cmd_packets`.
  - **On-screen trim:** show `_print_packets`, `_print_streams`, `_add_packets` and the import as finished code; type
    the rest (about 35 lines).
- **ep26 (79, plan ~28).** The plan's seven names come to 34 code lines (`boxes.box` 3, `boxes.full_box` 2, `mux.runs`
  8, `mux.stsc_rules` 2, `mux.table_box` 2, `mux.write_stsz` 4, `mux.write_stbl` 13), 36 with `mux.py`'s imports
  (`struct`, `boxes`). Each keeps the plan's signature. `write_stbl(track, stsd, chunk_offsets, chunks)` writes the drawers in
  ffmpeg's order: stsd (as given), stts (each sample's duration to the next dts, the last to mdhd's duration, in `runs`),
  stss (only when some sample is not a keyframe), ctts (only when some cts is not its dts; version 1 if a slip is
  negative), stsc (`stsc_rules(chunks)`), stsz (`write_stsz`: one size for all → that size and no list), stco (co64 only
  for an offset past 4 GiB). The other 43 are the check, `samples FILE --rewrite-check`:
  - **The command (43):** `cmd_rewrite_check` (16), `_rewrite_track` (11: the file's stsd copied, its chunks from
    `tables.chunk_list([track])`), `_compare_stbl` (14: each box of the file's stbl against the written one, then the
    stbl, also without the boxes not written and in write order) and `_add_samples`' two lines. The flag is an argparse
    `store_const` on `func`, so `cmd_samples` is untouched.
  - **The numbers:** every table write_stbl writes is the file's own, byte for byte, in every track of all 16 files
    with a moov (27 tracks) but phone-large; phone's video stbl is all 1,169 bytes the same; phone's sound stbl is 1,500
    against 1,446, the same boxes without sgpd (26) and sbgp (28). stsc: phone's video 59 chunks → 2 rules (2, then 1s),
    its sound 59 chunks (1, 2 or 4 samples) → 51 rules; f1 [4, 4, 2, 2] → [(1, 4, 1), (3, 2, 1)]. stsz's one-size form
    is phone-chapters' chapter track (17, 2: 20 bytes). `mux.interleave`'s counts (ep24) give phone's stsc again.
  - **Where the stbl is not the file's:** boxes write_stbl does not make (the AAC roll slip sgpd/sbgp in every ffmpeg
    sound track with samples; sdtp in av1, hdr, hevc, hevc-hev1; senc, saio, saiz in cenc); f2's ctts comes before its
    stss (minimux's order; the same boxes, moved); phone-large's co64 holds phone's own offsets in 8 bytes each
    (patch_stco.py), which write_stbl writes as phone's stco, so the check says `no` for phone-large alone.
  - **Not done here:** sgpd/sbgp, sdtp, senc/saio/saiz; more than one sample entry (stsc's third column is always 1);
    chunks are taken in offset order (`chunk_list`), so a track whose stco is not ascending would be rewritten sorted
    (no committed file has one).
  - **Blocks the Build-it scene shows:** `box` and `full_box`; `runs`; `stsc_rules`; `table_box`; `write_stsz`;
    `write_stbl`.
  - **On-screen trim:** show `cmd_rewrite_check`, `_rewrite_track`, `_compare_stbl` and the flag as finished code; type
    the plan's seven (about 34 lines).
- **ep27 (56, plan ~23).** The plan's three names come to 35 code lines (`mux.shift_chunk_offsets` 7, `mux.faststart`
  16, `cli.cmd_faststart` 12), 36 with `mux.py`'s import of `tables`. Each keeps the plan's signature.
  `shift_chunk_offsets(data, tree, delta)` patches every stco and co64 entry in place (the moov's own bytes, so it stays
  3,412 bytes); `faststart(data)` cuts the moov from behind the mdat and puts it straight after ftyp (ffmpeg's
  `reserved_header_pos`: before the free box it writes ahead of mdat), so free and mdat move back by the moov's size and
  every chunk offset grows by the same 3,412. `faststart(phone.mp4)` is `phone-fast.mp4` byte for byte. The other 20
  are the printing: `_print_move` (14: the top-level boxes before and after, the shift, each track's first and last
  offset before and after), `_add_faststart` (5) and `main`'s tuple (1).
  - **The numbers:** phone ftyp 0 (32), free 32 (8), mdat 40 (108,704), moov 108,744 (3,412) → ftyp 0, moov 32, free
    3,444, mdat 3,452; video's 59 offsets 48 → 3,460 … 106,571 → 109,983, sound's 59 8,011 → 11,423 … 107,721 →
    111,133; the file stays 112,156 bytes. 13 committed files move (every moov-last file but cenc), each keeping every
    sample's bytes and times; phone-large's co64 shifts by its 3,884-byte moov and its trailing uuid stays behind.
  - **What it does not move:** a file with no mdat before its moov (phone-fast, frag-cmaf) comes back unchanged; it
    refuses (BoxError) no moov (broken-nomoov), fragments (moof), an mdat after the moov, and saio (cenc: its offsets
    point into the moov, which moves by another amount; ffmpeg's own faststart writes them as senc's new place), and an
    stco offset that would pass 4 GiB (ffmpeg switches to co64 and grows the moov, `compute_moov_size`; mp4kit does
    not). Several mdats before the moov all move by the one delta (tested on a synthetic two-mdat f1).
  - **Blocks the Build-it scene shows:** `shift_chunk_offsets` (unpack, add, pack back); `faststart` (cut, patch,
    splice); `cmd_faststart`.
  - **On-screen trim:** show `_print_move`, `_add_faststart` and the import as finished code; type the plan's three
    (about 35 lines).
- **ep28 (106, plan ~36).** The plan's ten names come to 32 code lines (`mux.write_ftyp` 2, `write_mvhd` 3,
  `write_tkhd` 4, `write_mdhd` 3, `write_hdlr` 2, `write_media_header` 2, `write_dinf` 2, `write_elst` 2, `write_avcc` 8,
  `write_avc1` 4), 34 with `mux.MATRIX` (the identity matrix, minimux's `MATRIX`) and `mux.py`'s import of `nal`. Each
  keeps the plan's signature but one: `write_tkhd` has a sixth argument, `group=0` (the alternate group), because
  ffmpeg writes its codec type there (0 video, 1 sound, 3 subtitle) and phone's sound tkhd is not its own without it.
  Every writer writes version 0 (32-bit times and durations; every committed file is version 0). The other 72 are the
  check, `dump FILE --rewrite-check`: `cmd_header_check` (14), `_rewrite_movie` (9: ftyp, mvhd), `_rewrite_track_headers`
  (16: tkhd, elst, mdhd, hdlr, media header, dinf; tkhd's alternate group read 50 bytes before the box's end, the one
  field no reader keeps), `_rewrite_entry` (10: avcC, avc1), `_compare_box` (15), `_bare_avc1` (6) and `_add_dump`'s two
  lines.
  - **The numbers:** phone's ftyp 32, mvhd 108 (48,000 / 96,000, next track 3), video tkhd 92 (track 1, 96,000,
    640 x 360), sound tkhd 92 (track 2, group 1, volume 1), elst 28 in both tracks (96,000 from 1,024), mdhd 32 (15,360 /
    30,720 and 48,000 / 97,024, `und` = 0x55C4), hdlr 45 (`VideoHandler`, `SoundHandler`), vmhd 20, smhd 16, dinf 36
    (dref 28, `url ` 12, flags 1), avcC 55 (8 + 6 + 2 + 26 SPS + 1 + 2 + 6 PPS + 4 tail `fd f8 f8 00`): 15 of the 16
    boxes written are phone's, byte for byte. avc1 is 141 against 177: the same once its compressorname (`0c` + "Lavc
    libx264", 13 of its 32 bytes) is blanked and its pasp (16) and btrt (20) are left out. phone's mp4a (episode 29) is
    not written. f1 and f2 (minimux) are every box the same, avc1 included (no name, no pasp, no btrt).
  - **Where a box is not the file's:** rotated's video tkhd (bytes 49 to 65: the 90-degree matrix; write_tkhd writes
    the identity), phone-chapters' chapter tkhd (byte 11: flags 2, in the movie but not enabled; write_tkhd writes 3),
    and the avc1 of every libx264 file (above). Not written: mp4a/enca/encv/hvc1/hev1/av01/tx3g/text entries, and the
    media headers nmhd (subs) and gmhd (phone-chapters' text track). f1 and frag-cmaf have no elst.
  - **Not done here:** version 1 (64-bit) mvhd/tkhd/mdhd/elst, more than one edit, more than one SPS or PPS, SPS
    extensions, a display matrix, a compressorname, pasp, btrt, colr; the udta/meta hdlr (`mdir`) is not checked.
  - **Blocks the Build-it scene shows:** the ten writers and `MATRIX`.
  - **On-screen trim:** show `cmd_header_check`, `_rewrite_movie`, `_rewrite_track_headers`, `_rewrite_entry`,
    `_compare_box`, `_bare_avc1` and the flag as finished code; type the plan's ten (about 34 lines).
- **ep29 (119, plan ~73; finale budget ~90).** The plan's seven names come to 68 code lines with their `def` lines
  (`mux.write_esds` 5, `write_mp4a` 3, `video_track` 15, `audio_track` 8, `write_trak` 9, `mux` 15, `cli.cmd_mux` 13),
  inside the plan's ~73. Four helpers carry what the plan folded into them, 25: `mux.descriptor` 3 (one MPEG-4
  envelope, ffmpeg's 4-byte length form), `video_clock` 5 (ffmpeg movenc's rule: the frame rate doubled until it
  reaches 10,000; 30 -> 15,360), `display_order` 9 (each picture's slot from its POC, restarting at each IDR) and
  `write_stsd` 8 (the tray around avc1 or mp4a: no ep26-ep28 function wrote stsd). The CLI's read-back
  `_print_built` 13, `_add_mux` 9 and `main`'s tuple 1; two imports (`dataclasses`, `itertools.accumulate`) and
  `tables.Track.payloads` 1. Signatures that differ from the plan: `video_track(annexb, fps, timescale=None)` (None:
  video_clock), `write_esds(asc, avg_bitrate, es_id=0)` (ffmpeg writes the track_ID as ES_ID; phone's is 2),
  `write_trak(track, stsd, chunk_offsets, chunks, movie_timescale)` (a built track's edit counts on its own clock and
  goes on the movie's here) and `mux(tracks, fast=False)` (`faststart` would hide episode 27's function, which it
  calls).
  - **The numbers:** phone.h264 (84,427 B) -> 60 samples with phone's 60 sizes (84,349 B; sample 1 = SEI + IDR,
    5,824), keyframes [1, 31], clock 15,360, 512 a frame; display order from POC [0, 6, 2, 4, ...] -> slots [0, 3, 1,
    2, ...]; the least shift is one frame, so ctts starts 512, 1,536, 0, 0 (phone's 1,024, 2,048, 512, 512: every run
    512 less, the same 44 runs) and the elst is (96,000, 512) where phone's is (96,000, 1,024). phone.aac (25,012 B)
    -> 95 samples with phone's sizes, ASC `11 90`, avgBitrate 96,106 (24,347 x 8 x 48,000 / 97,280), elst (96,256,
    1,024). The House: ftyp 32, free 8, mdat 108,704 at 40 (phone's size, the chunks in another order: 60 + 60 chunks
    against 59 + 59), moov 3,238 at 108,744 (phone's 3,412): 111,982 bytes. `ffmpeg -v error -i out.mp4 -f null -`
    prints nothing; every decoded picture's framemd5 and pts is phone's; the sound is phone's 96,000 samples then 256
    more (ADTS cannot say that the last frame holds 768).
  - **Not phone's twin:** the video elst (512 vs 1,024), ctts values, stsc and stco (chunking), avc1 (no name, pasp,
    btrt), esds (2-byte ASC, not ffmpeg's 5-byte `11 90 56 e5 00`; bitrate 96,106 not 96,360), mp4a (no btrt), the
    sound stts/mdhd/elst/tkhd and mvhd lengths (97,280 and 96,256: no 768-sample last frame), no sgpd/sbgp roll
    group, no udta. The same bytes: ftyp, free, the video tkhd and mdhd, both hdlr, vmhd, smhd, both dinf, avcC, the
    video stts, stss and both stsz.
  - **Not done here:** fractional frame rates (29.97), POC type 1, POC lsb wrapping inside a GOP, more than one
    SPS/PPS, AUD/end-of-stream units are kept in samples as found, ADTS with CRC (read, its CRC dropped), the encoder's
    end trimming, cslg, co64 / largesize (a moov or mdat over 4 GiB), a display matrix, language.
  - **Blocks the Build-it scene shows:** the plan's seven and `descriptor`.
  - **On-screen trim:** show `video_clock`, `display_order`, `write_stsd`, `_print_built`, `_add_mux` and the
    `Track.payloads` field as finished code; type the plan's seven and `descriptor` (about 71 lines).
- ep01–ep03 are 6–10 lines over their estimates.
