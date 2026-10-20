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
- ep01–ep03 are 6–10 lines over their estimates.
