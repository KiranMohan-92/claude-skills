#!/usr/bin/env bash
# Build a progress contact sheet from frames of one or more videos (Linux, macOS or WSL; needs ffmpeg).
#   progress_sheet.sh <out.jpg> <video>[:t] [<video>[:t] ...]      t = seconds (default 1.0)
# Tiles 2 columns of 960 px wide frames; each frame labelled with its file name and time.
# Put out.jpg somewhere the user can open, then send it to them.
set -euo pipefail
[[ $# -ge 1 ]] || { echo "usage: progress_sheet.sh <out.jpg> <video>[:t] ..." >&2; exit 2; }
OUT=$1; shift
[[ $# -ge 1 ]] || { echo "need at least one video" >&2; exit 2; }
TMP=$(mktemp -d); i=0
for spec in "$@"; do
  if [[ "$spec" =~ ^(.+):([0-9]+(\.[0-9]+)?)$ ]]; then v=${BASH_REMATCH[1]}; t=${BASH_REMATCH[2]}; else v=$spec; t=1.0; fi
  [[ -f "$v" ]] || { echo "missing $v" >&2; exit 2; }
  lab=$(basename "$v" | sed 's/[^A-Za-z0-9_.-]/_/g')
  ffmpeg -v error -y -ss "$t" -i "$v" -frames:v 1 \
    -vf "scale=960:-2,drawtext=text='${lab} @ ${t}s':x=8:y=8:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.6" \
    "$TMP/f_$(printf %03d $i).jpg"
  i=$((i+1))
done
rows=$(( (i + 1) / 2 ))
ffmpeg -v error -y -pattern_type glob -i "$TMP/f_*.jpg" -vf "tile=2x${rows}:padding=4" -frames:v 1 -q:v 3 "$OUT"
rm -rf "$TMP"
echo "wrote $OUT ($i frames)"
