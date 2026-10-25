#!/usr/bin/env bash
# Bounded wait for a long job (Linux or WSL; needs /proc). Returns within --max seconds (default 570, under the
# 10-minute tool timeout) so the caller can post a check-in, then call it again.
#   waitfor.sh --gone <process-pattern>   wait until no process matches (pgrep -f, self-match safe)
#   waitfor.sh --file <path>              wait until the file exists and is non-empty
#   waitfor.sh --log <file> <regex>       wait until the log matches the regex
#   --status "<shell cmd>"                printed after the wait (e.g. "tail -2 ~/x.log")
#   --max <seconds>                       cap (default 570); the --status command gets at most 35 s more
# Exit 0 = condition met (prints DONE), 10 = still running at the cap (prints RUNNING), 2 = usage or bad pattern.
set -u
MODE=""; A=""; B=""; STATUS=""; MAX=570
usage() { echo "usage: waitfor.sh --gone PAT | --file PATH | --log FILE REGEX [--status CMD] [--max S]" >&2; exit 2; }
need() { [[ $1 -gt $2 ]] || usage; }  # need <args left> <values the option takes>
while [[ $# -gt 0 ]]; do
  case "$1" in
    --gone) need $# 1; MODE="gone"; A="$2"; shift 2 ;;
    --file) need $# 1; MODE="file"; A="$2"; shift 2 ;;
    --log) need $# 2; MODE="log"; A="$2"; B="$3"; shift 3 ;;
    --status) need $# 1; STATUS="$2"; shift 2 ;;
    --max) need $# 1; MAX="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; usage ;;
  esac
done
[[ -n "$MODE" && -n "$A" ]] || usage
[[ "$MAX" =~ ^[0-9]+$ ]] || { echo "--max must be whole seconds" >&2; exit 2; }
# Bracket the first character so pgrep -f can't match its own pattern argument. Only for a plain first
# character: bracketing "^", "(" or "." would change the regex and could report a live job as gone.
PAT="$A"; [[ "$MODE" == gone && "$PAT" =~ ^[A-Za-z0-9_/-] ]] && PAT="[${PAT:0:1}]${PAT:1}"
# ...and ignore this script's own ancestry: a caller like  bash -lc 'waitfor.sh --gone foo'  has "foo" in its
# command line too, which matched and made a finished job look RUNNING forever (found in testing)
SKIP=" $$ "; p=$$
while [[ "$p" -gt 1 ]]; do
  # field 4 of /proc/PID/stat, read after the ")" that closes the command name (names can contain spaces)
  p=$(sed 's/.*) //' "/proc/$p/stat" 2>/dev/null | awk '{print $2}'); [[ "$p" =~ ^[0-9]+$ ]] || p=1
  SKIP+="$p "
done
alive() {  # 0 = a matching process other than us is running, 1 = none, 2 = pgrep error
  local q out rc
  out=$(pgrep -f -- "$PAT"); rc=$?
  (( rc > 1 )) && return 2
  for q in $out; do [[ "$SKIP" == *" $q "* ]] || return 0; done
  return 1
}
met() {  # 0 = condition met, 1 = not yet, 2 = error
  local rc
  case "$MODE" in
    gone) alive; rc=$?; (( rc == 2 )) && return 2; (( rc == 1 )) ;;
    file) [[ -s "$A" ]] ;;
    log) [[ -f "$A" ]] || return 1; grep -Eq -- "$B" "$A"; rc=$?; (( rc > 1 )) && return 2; (( rc == 0 )) ;;
  esac
}
t0=$(date +%s); state=RUNNING
while :; do
  met; rc=$?
  if (( rc == 2 )); then echo "ERROR: bad pattern or unreadable input (pgrep/grep failed)" >&2; exit 2; fi
  if (( rc == 0 )); then state=DONE; break; fi
  left=$(( MAX - ($(date +%s) - t0) ))
  (( left <= 0 )) && break
  sleep $(( left < 10 ? left : 10 ))
done
echo "$state after $(( $(date +%s) - t0 ))s at $(date +%H:%M)"
[[ -n "$STATUS" ]] && timeout --kill-after=5 30 bash -c "$STATUS"
[[ $state == DONE ]] && exit 0 || exit 10
