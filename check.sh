#!/usr/bin/env bash
# For every tag epNN (in tag order): check the tag out into a temporary worktree,
# run that episode's command on the committed file, diff against expected/epNN.txt,
# then run the unit tests at that tag. Non-zero exit on any failure.
set -u
cd "$(dirname "$0")"
REPO=$(pwd)

# Command per tag (mp4kit-plan.md section 3). Paths are relative to the worktree root.
cmd_for() {
  case "$1" in
    ep01) echo 'python3 -m mp4kit hex testfiles/out/f1.mp4 --at 0 --len 8' ;;
    ep02|ep03) echo 'python3 -m mp4kit nals testfiles/out/f1.mp4 --from 40 --to 22057' ;;
    ep04) echo 'python3 -m mp4kit sps testfiles/out/f1.mp4' ;;
    ep05) echo 'python3 -m mp4kit annexb testfiles/out/f1.mp4 -o "$TMPOUT/f1.h264"' ;;
    ep06) echo 'python3 -m mp4kit boxes testfiles/out/f1.mp4' ;;
    ep07) echo 'python3 -m mp4kit boxes testfiles/out/phone-large.mp4' ;;
    ep08) echo 'python3 -m mp4kit boxes testfiles/out/aac-only.m4a' ;;
    ep09) echo 'python3 -m mp4kit dump testfiles/out/phone.mp4' ;;
    ep10) echo 'python3 -m mp4kit dump testfiles/out/phone.mp4 --find mvhd' ;;
    *) return 1 ;;
  esac
}

tags=$(git tag -l 'ep[0-9][0-9]' | sort)
if [ -z "$tags" ]; then
  echo "no epNN tags yet"
  exit 0
fi

echo "ffmpeg build: $(ffmpeg -version 2>/dev/null | head -1 || echo missing)"
fail=0
wt=""
TMPOUT=""
# Remove this tag's worktree and scratch folder; also runs on exit (Ctrl-C, a failed step).
cleanup() {
  if [ -n "$wt" ]; then git worktree remove --force "$wt" 2>/dev/null; rm -rf "${wt:?}"; fi
  if [ -n "$TMPOUT" ]; then rm -rf "${TMPOUT:?}"; fi
  wt=""
  TMPOUT=""
}
trap cleanup EXIT
for tag in $tags; do
  cmd=$(cmd_for "$tag") || { echo "$tag FAIL: no command in check.sh table"; fail=1; continue; }
  wt=$(mktemp -d)
  TMPOUT=$(mktemp -d)
  export TMPOUT
  git worktree add --detach -q "$wt" "$tag" || { echo "$tag FAIL: worktree"; fail=1; cleanup; continue; }
  ok=1
  out=$(cd "$wt" && eval "$cmd" 2>&1) || { echo "$tag command failed:"; echo "$out"; ok=0; }
  if [ ! -f "$wt/expected/$tag.txt" ]; then
    echo "$tag FAIL: expected/$tag.txt missing"; ok=0
  elif [ $ok = 1 ]; then
    d=$(diff <(printf '%s\n' "$out") "$wt/expected/$tag.txt") || { echo "$tag output differs:"; echo "$d"; ok=0; }
  fi
  ut=$(cd "$wt" && python3 -m unittest 2>&1) || { echo "$tag unit tests failed:"; echo "$ut"; ok=0; }
  cleanup
  if [ $ok = 1 ]; then echo "$tag ok"; else fail=1; fi
done
exit $fail
