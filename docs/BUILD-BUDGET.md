# Build-it budget per tag

What each episode's Build it adds to `mp4kit/`, and the longest function at that tag.

- **Diff:** `git diff --numstat <previous> <tag> -- mp4kit` (added / removed lines, per file). ep01 is
  measured against the scaffold commit (87f69b6); ep06 is measured at e532452 (its nal.py line is the
  `_mdat_range_stopgap` docstring).
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
| ep06 | boxes.py +42/-1, cli.py +23/-2, nal.py +1/-1 | 45 | ~24 | `cli.cmd_boxes` 10 (12) is the longest new one; `nal.parse_sps` 12 (14) overall |

## Functions over 15 lines

None. `parse_sps` was expected to be over (minimux's is 21 lines); in ep04 the chroma and
picture-order-count branches became their own helpers (`_sps_chroma`, `_sps_poc`) and the size
arithmetic became `picture_size`, so its body is 12 lines.

## Episodes over their budget

- **ep04 (114 code lines, plan ~40).** It carries the review rulings folded into the episode before
  push: the per-command `_add_<cmd>(sub)` registration in `cli.main`, the `separate_colour_plane` and
  field-coding refusals, scaling-list refusal, and the `_sps_chroma` / `_sps_poc` helpers. It is the
  densest Build it so far and the first to trim at G2 of ep04 (show the helpers as finished code, build
  only `parse_sps`, `picture_size` and `cmd_sps` on screen).
- **ep05 (52, plan ~22).** Accepted at ~50 by ruling: four functions, the command and the mdat stopgap.
- **ep06 (45, plan ~24).** The `Box` dataclass with its two properties is 9 lines on its own; the
  on-screen code keeps one statement per line (no packed assignments), the header check is two plain
  `if`s with their own messages, and `cmd_boxes` catches `ValueError` to print `error: …` and exit 1
  (`BoxError` arrives in ep07).
- ep01–ep03 are 6–10 lines over their estimates.
