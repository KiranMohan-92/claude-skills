#!/usr/bin/env bash
# Gate an ENCODED video deliverable (Linux, macOS or WSL; needs ffmpeg/ffprobe).
#   gate_deliverable.sh <file> [--frames N] [--lufs -14] [--lufs-tol 1.0] [--max-tp -1.0] [--sync-tol 0.1]
# Checks: one video and one audio stream that both decode without errors; frame count (N, or N-1 because
# -shortest may trim the final frame); both streams start at 0 and their durations agree within --sync-tol s;
# integrated loudness within --lufs-tol of --lufs; true peak <= --max-tp.
# A measurement that can't be made (e.g. a container without stream durations) is computed from the packets;
# if it still can't be made, the gate fails rather than assuming a value.
# Exit 0 = PASS, 1 = FAIL (each failure printed), 2 = usage.
set -uo pipefail
usage() { echo "usage: gate_deliverable.sh <file> [--frames N] [--lufs L] [--lufs-tol T] [--max-tp P] [--sync-tol S]" >&2; exit 2; }
[[ $# -ge 1 ]] || usage
F=$1; shift
FR=""; LUFS=-14; LTOL=1.0; TPMAX=-1.0; STOL=0.1
while [[ $# -gt 0 ]]; do
  [[ $# -ge 2 ]] || usage
  case "$1" in
    --frames) FR=$2 ;; --lufs) LUFS=$2 ;; --lufs-tol) LTOL=$2 ;; --max-tp) TPMAX=$2 ;; --sync-tol) STOL=$2 ;;
    *) echo "unknown option $1" >&2; usage ;;
  esac
  shift 2
done
[[ -f "$F" ]] || { echo "missing $F" >&2; exit 2; }
fail=0; bad() { echo "FAIL: $*"; fail=1; }
num() { [[ "${1:-}" =~ ^-?[0-9]+(\.[0-9]+)?$ ]]; }

# key=value output: ffprobe's csv field order is NOT the -show_entries order (that mis-parse failed a good file)
probe() { ffprobe -v error -select_streams "$1" -show_entries "stream=$2" -of default=nw=1 "$F"; }
val() { awk -F= -v k="$1" '$1==k{print $2; exit}' <<<"$2"; }
# first packet time and end of the last packet, for containers that don't store stream start/duration
pkt_span() {
  ffprobe -v error -select_streams "$1" -show_entries packet=pts_time,duration_time -of csv=p=0 "$F" |
    awk -F, '$1!="N/A"{s=$1+0; e=s+($2=="N/A"?0:$2); if(!n++||s<lo)lo=s; if(e>hi)hi=e} END{if(n)printf "%.6f %.6f\n", lo, hi-lo}'
}

v=$(probe v:0 codec_type,width,height,r_frame_rate,nb_frames,start_time,duration)
a=$(probe a:0 codec_type,codec_name,start_time,duration)
[[ -n "$v" ]] || bad "no video stream"
[[ -n "$a" ]] || bad "no audio stream"
if [[ -n "$v" && -n "$a" ]]; then
  W=$(val width "$v"); H=$(val height "$v"); R=$(val r_frame_rate "$v"); N=$(val nb_frames "$v")
  VS=$(val start_time "$v"); VD=$(val duration "$v"); AC=$(val codec_name "$a"); AS=$(val start_time "$a"); AD=$(val duration "$a")
  if ! num "$VS" || ! num "$VD"; then read -r VS VD < <(pkt_span v:0); fi
  if ! num "$AS" || ! num "$AD"; then read -r AS AD < <(pkt_span a:0); fi
  if ! num "$N"; then N=$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of default=nw=1:nk=1 "$F"); fi
  echo "video: ${W}x${H} @ $R, $N frames, start $VS, ${VD}s"; echo "audio: $AC, start $AS, ${AD}s"

  # decode every packet of both streams: metadata can look fine while the video data is corrupt
  derr=$(ffmpeg -hide_banner -nostats -v error -xerror -i "$F" -map 0:v:0 -map 0:a:0 -f null - 2>&1); drc=$?
  if [[ $drc -ne 0 || -n "$derr" ]]; then bad "decode errors (exit $drc): $(head -c 300 <<<"$derr" | tr '\n' ' ')"; fi

  if [[ -n "$FR" ]]; then
    if ! num "$N"; then bad "frame count unavailable"
    elif [[ "$N" == "$FR" ]]; then :
    elif (( N == FR - 1 )); then echo "note: $N frames = $FR - 1 (-shortest trimmed the last frame)"
    else bad "frames $N, want $FR"; fi
  fi
  if num "$VS" && num "$AS"; then
    awk -v vs="$VS" -v as="$AS" 'BEGIN{exit !((vs<0.05&&vs>-0.05)&&(as<0.05&&as>-0.05))}' || bad "stream start video=$VS audio=$AS (want 0)"
  else bad "stream start unavailable (video=$VS audio=$AS)"; fi
  if num "$VD" && num "$AD"; then
    awk -v vd="$VD" -v ad="$AD" -v t="$STOL" 'BEGIN{d=vd-ad; if(d<0)d=-d; exit !(d<=t)}' || bad "duration video=$VD audio=$AD differ by more than $STOL s"
  else bad "stream duration unavailable (video=$VD audio=$AD)"; fi

  L=$(ffmpeg -hide_banner -nostats -i "$F" -map 0:a:0 -af ebur128=peak=true -f null - 2>&1 | grep -A20 Summary)
  I=$(awk '/I:/{print $2; exit}' <<<"$L"); TP=$(awk '/Peak:/{print $2; exit}' <<<"$L")
  echo "loudness: I=$I LUFS  true-peak=$TP dBTP"
  if num "$I" && num "$TP"; then
    awk -v i="$I" -v t="$LUFS" -v tol="$LTOL" 'BEGIN{d=i-t; if(d<0)d=-d; exit !(d<=tol)}' || bad "loudness $I LUFS, want $LUFS +-$LTOL"
    awk -v tp="$TP" -v m="$TPMAX" 'BEGIN{exit !(tp<=m)}' || bad "true peak $TP dBTP > $TPMAX (re-master with a lower ceiling, remux -c:v copy)"
  else bad "loudness measurement failed (I=$I, true peak=$TP)"; fi
fi
if [[ $fail == 0 ]]; then echo "PASS $F"; else echo "GATE FAILED $F"; fi
exit $fail
