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
- ep01–ep03 are 6–10 lines over their estimates.
