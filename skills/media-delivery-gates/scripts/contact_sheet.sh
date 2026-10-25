#!/usr/bin/env bash
# Timestamped contact sheet of a time range (Linux, macOS or WSL; needs ffmpeg).
#   contact_sheet.sh <video> <out.jpg> <start_s> <end_s> <step_s> [cols=5]
# Each tile is 384 px wide with the absolute timestamp burned in (yellow, top-left). Rows grow to fit.
# The drawtext filter lives in this file because %{pts\:hms\:<offset>} breaks inside nested shell quotes.
set -euo pipefail
[[ $# -ge 5 ]] || { echo "usage: contact_sheet.sh <video> <out.jpg> <start_s> <end_s> <step_s> [cols]" >&2; exit 2; }
V=$1; O=$2; A=$3; B=$4; ST=$5; C=${6:-5}
[[ -f "$V" ]] || { echo "missing $V" >&2; exit 2; }
N=$(awk -v a="$A" -v b="$B" -v s="$ST" 'BEGIN{n=(b-a)/s; c=int(n); if (c<n) c++; if (c<1) c=1; print c}')
ROWS=$(( (N + C - 1) / C ))
FPS=$(awk -v s="$ST" 'BEGIN{printf "%.6f", 1/s}')
ffmpeg -v error -y -ss "$A" -to "$B" -i "$V" \
  -vf "fps=$FPS,scale=384:-2,drawtext=text='%{pts\:hms\:$A}':x=6:y=6:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=${C}x${ROWS}" \
  -frames:v 1 -q:v 4 "$O"
echo "wrote $O ($N frames, ${C}x${ROWS})"
