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
- ep01–ep03 are 6–10 lines over their estimates.
