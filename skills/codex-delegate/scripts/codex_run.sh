#!/usr/bin/env bash
# Drive Codex CLI from another agent and get a verified result back (Linux or WSL; needs bash, curl, git,
# coreutils `timeout`, util-linux `setsid` and `ps`).
#
#   codex_run.sh probe  [--min-version X.Y.Z] [--url URL] [--live]
#       Codex installed and new enough; the API host reachable from THIS environment; with --live, a one-line
#       `codex exec` must exit 0 and answer exactly OK. Exit 0 ok, 3 unreachable or not installed, 4 CLI too old.
#   codex_run.sh launch --brief FILE --out FILE --log FILE [--sandbox read-only|workspace-write] [--cd DIR] [-- ARGS...]
#       Starts `codex exec` in its own session (survives the launching shell), brief on stdin, final message to
#       --out. Records <log>.pid, <log>.job (a token in the job's command line) and, when it ends, <log>.exit.
#       Extra ARGS go to codex (e.g. -c model="..."). Exit 0 started, 1 died at startup.
#   codex_run.sh status --out FILE --log FILE
#       Exit 10 still running (the recorded process, identified by its token), 0 exited 0 with a non-empty final
#       message, 1 anything else (non-zero exit, empty result, killed without an exit record).
#   codex_run.sh scope  [--max-lines N] (--uncommitted | --base REF | --commit SHA)
#       Before a review: refuse a diff bigger than N changed lines (default 1500, untracked text files included),
#       one that is mostly line-ending churn, or a git error. Exit 0 in scope, 1 out of scope or git failed.
# Exit 2 = usage or missing dependency. CODEX_BIN overrides the codex executable; CODEX_PROBE_URL the probe URL.
set -uo pipefail
CODEX=${CODEX_BIN:-codex}
die() { echo "$*" >&2; exit 2; }
usage() { sed -n '2,20p' "$0" >&2; exit 2; }
need() { command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1"; }
ver_ge() {  # ver_ge A B: true when version A >= B
  [[ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" == "$2" ]]
}
abspath() { case "$1" in /*) printf '%s\n' "$1" ;; *) printf '%s/%s\n' "$PWD" "$1" ;; esac; }

probe() {
  local min="" url=${CODEX_PROBE_URL:-https://chatgpt.com} live=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --min-version) [[ $# -ge 2 ]] || usage; min=$2; shift 2 ;;
      --url) [[ $# -ge 2 ]] || usage; url=$2; shift 2 ;;
      --live) live=1; shift ;;
      *) usage ;;
    esac
  done
  need curl
  if ! command -v "$CODEX" >/dev/null 2>&1; then echo "UNAVAILABLE: '$CODEX' not on PATH"; return 3; fi
  local v
  v=$("$CODEX" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  [[ -n "$v" ]] || { echo "UNAVAILABLE: could not read the codex version"; return 3; }
  if [[ -n "$min" ]] && ! ver_ge "$v" "$min"; then echo "TOO OLD: codex $v < $min (upgrade before using this model)"; return 4; fi
  local code
  code=$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$url" 2>/dev/null); code=${code:-000}
  if [[ "$code" == "000" ]]; then echo "UNREACHABLE: $url from $(hostname) (no network in this environment?)"; return 3; fi
  if (( live )); then
    need timeout
    local out rc answer
    out=$(mktemp)
    timeout 180 "$CODEX" exec --skip-git-repo-check --ephemeral -s read-only -o "$out" - <<<"Reply with exactly: OK" >/dev/null 2>&1
    rc=$?
    answer=$(cat "$out" 2>/dev/null)
    answer="${answer#"${answer%%[![:space:]]*}"}"; answer="${answer%"${answer##*[![:space:]]}"}"  # trim the ends only
    rm -f "$out"
    if [[ $rc -ne 0 || "$answer" != "OK" ]]; then echo "UNREACHABLE: codex exec exited $rc and answered '${answer:0:40}', not OK"; return 3; fi
  fi
  echo "OK: codex $v, $url reachable (HTTP $code)$( ((live)) && echo ', live exec OK')"
}

launch() {
  local brief="" out="" log="" sandbox="read-only" cd=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --brief) [[ $# -ge 2 ]] || usage; brief=$2; shift 2 ;;
      --out) [[ $# -ge 2 ]] || usage; out=$2; shift 2 ;;
      --log) [[ $# -ge 2 ]] || usage; log=$2; shift 2 ;;
      --sandbox) [[ $# -ge 2 ]] || usage; sandbox=$2; shift 2 ;;
      --cd) [[ $# -ge 2 ]] || usage; cd=$2; shift 2 ;;
      --) shift; break ;;
      *) usage ;;
    esac
  done
  [[ -n "$brief" && -n "$out" && -n "$log" ]] || usage
  need setsid; need ps
  # resolve every path before changing directory, so --cd can't change what they mean
  brief=$(abspath "$brief"); out=$(abspath "$out"); log=$(abspath "$log")
  [[ -f "$brief" && -s "$brief" ]] || die "brief missing or empty: $brief"
  case "$sandbox" in read-only|workspace-write) ;; *) die "sandbox must be read-only or workspace-write";; esac
  if [[ -n "$cd" ]]; then cd "$cd" || die "cannot cd to $cd"; fi
  command -v "$CODEX" >/dev/null 2>&1 || die "'$CODEX' not on PATH"
  local d
  for d in "$(dirname "$out")" "$(dirname "$log")"; do [[ -d "$d" && -w "$d" ]] || die "cannot write to $d"; done
  rm -f "$out" "$log.exit" "$log.exit.tmp"
  local token; token="codex-delegate-job-$(date +%s)-$$-$RANDOM"
  echo "$token" >"$log.job" || die "cannot write $log.job"
  # setsid + nohup: the job runs in its own session and outlives the shell that started it (a plain `&` died
  # with its session). The wrapper records codex's exit status, so status can tell success from a crash.
  setsid nohup bash -c 'codex="$1"; brief="$2"; out="$3"; sandbox="$4"; exitf="$5"; shift 6
    "$codex" exec --skip-git-repo-check -s "$sandbox" -o "$out" "$@" - <"$brief"; echo $? >"$exitf.tmp"; mv -f "$exitf.tmp" "$exitf"' \
    codex-delegate "$CODEX" "$brief" "$out" "$sandbox" "$log.exit" "$token" "$@" >"$log" 2>&1 </dev/null &
  local pid=$!
  disown "$pid" 2>/dev/null || true
  echo "$pid" >"$log.pid" || die "cannot write $log.pid"
  sleep 1
  if [[ -f "$log.exit" ]]; then
    if [[ "$(cat "$log.exit")" != "0" ]]; then
      echo "FAILED at startup (exit $(cat "$log.exit")). Last log lines:"; tail -5 "$log" 2>/dev/null; return 1
    fi
  elif [[ "$(ps -o args= -p "$pid" 2>/dev/null)" != *"$token"* ]]; then
    echo "FAILED at startup: the job isn't running and recorded no exit status. Last log lines:"
    tail -5 "$log" 2>/dev/null; return 1
  fi
  echo "LAUNCHED pid $pid (log $log, result $out)"
}

status() {
  local out="" log=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --out) [[ $# -ge 2 ]] || usage; out=$2; shift 2 ;;
      --log) [[ $# -ge 2 ]] || usage; log=$2; shift 2 ;;
      *) usage ;;
    esac
  done
  [[ -n "$out" && -n "$log" ]] || usage
  [[ -f "$log.pid" && -f "$log.job" ]] || die "no job record for $log (was it started with launch?)"
  need ps
  local pid token
  pid=$(cat "$log.pid"); token=$(cat "$log.job")
  if [[ -f "$log.exit" ]]; then exit_report "$out" "$log"; return; fi
  # alive = that PID still runs OUR job (its command line carries the token) and isn't a zombie;
  # a reused PID or a counted process is not proof (a process counter once reported dead lanes as running)
  local args state
  args=$(ps -o args= -p "$pid" 2>/dev/null); state=$(ps -o stat= -p "$pid" 2>/dev/null)
  if [[ "$args" == *"$token"* && "$state" != Z* ]]; then echo "RUNNING pid $pid, log $(wc -c <"$log" 2>/dev/null || echo 0) bytes"; return 10; fi
  # the job may have recorded its exit and ended between the first check and ps: look again before calling it killed
  if [[ -f "$log.exit" ]]; then exit_report "$out" "$log"; return; fi
  echo "FAILED: the job ended without recording an exit status (killed?). Last log lines:"; tail -5 "$log" 2>/dev/null
  return 1
}

exit_report() {  # exit_report OUT LOG: judge a job that recorded its exit status
  local out=$1 log=$2 rc
  rc=$(cat "$log.exit")
  if [[ "$rc" == "0" && -s "$out" ]]; then echo "DONE: exit 0, $(wc -c <"$out") bytes in $out"; return 0; fi
  # an empty result is a failure, never "no findings"
  echo "FAILED: codex exited $rc$([[ -s "$out" ]] || echo ' with no final message'). Last log lines:"; tail -5 "$log" 2>/dev/null
  return 1
}

scope() {
  local max=1500 range="" untracked_mode=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max-lines) [[ $# -ge 2 ]] || usage; max=$2; shift 2 ;;
      --uncommitted) range="HEAD"; untracked_mode=1; shift ;;
      --base) [[ $# -ge 2 ]] || usage; range="$2"; shift 2
        git rev-parse --verify --quiet "$range^{commit}" >/dev/null || { echo "OUT OF SCOPE: unknown base '$range'"; return 1; }
        range="$range...HEAD" ;;
      --commit) [[ $# -ge 2 ]] || usage; range="$2"; shift 2
        git rev-parse --verify --quiet "$range^{commit}" >/dev/null || { echo "OUT OF SCOPE: unknown commit '$range'"; return 1; }
        range="$range^!" ;;
      *) usage ;;
    esac
  done
  [[ -n "$range" ]] || usage
  [[ "$max" =~ ^[0-9]+$ ]] || die "--max-lines must be a number"
  git rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository"
  local raw_ns eol_ns
  if ! raw_ns=$(git diff --numstat "$range" --); then echo "OUT OF SCOPE: git diff failed"; return 1; fi
  if ! eol_ns=$(git diff --numstat --ignore-cr-at-eol "$range" --); then echo "OUT OF SCOPE: git diff failed"; return 1; fi
  sum() { awk '$1!="-"{s+=$1+$2} END{print s+0}'; }
  local raw eol binary untracked=0 skipped=0
  raw=$(sum <<<"$raw_ns"); eol=$(sum <<<"$eol_ns")
  binary=$(awk '$1=="-"{n++} END{print n+0}' <<<"$raw_ns")
  if (( untracked_mode )); then
    local f n
    while IFS= read -r -d '' f; do
      # count regular files only; never follow a symlink out of the checkout or read a device or FIFO
      if [[ -L "$f" || ! -f "$f" ]]; then skipped=$((skipped + 1)); continue; fi
      # a NUL byte in the first 8 KB means binary, like git's own test: list it, don't count it as lines
      if [[ $(head -c 8192 <"./$f" | tr -dc '\000' | wc -c) -gt 0 ]]; then binary=$((binary + 1)); continue; fi
      n=$(awk 'END{print NR}' <"./$f") || { echo "OUT OF SCOPE: cannot read untracked file"; return 1; }
      untracked=$((untracked + n))
    done < <(git ls-files --others --exclude-standard -z)
  fi
  local total=$(( raw + untracked ))
  echo "diff: $raw changed lines ($eol ignoring CR at end of line), $untracked untracked lines, $binary binary file(s) not counted, $skipped symlink/special file(s) skipped"
  if (( raw > 200 && raw > 3 * eol )); then
    echo "OUT OF SCOPE: mostly line-ending churn ($raw lines, $eol real). Restore the line endings first."; return 1
  fi
  if (( total > max )); then echo "OUT OF SCOPE: $total lines > $max. Split the review."; return 1; fi
  echo "IN SCOPE"
}

[[ $# -ge 1 ]] || usage
cmd=$1; shift
case "$cmd" in
  probe) probe "$@" ;;
  launch) launch "$@" ;;
  status) status "$@" ;;
  scope) scope "$@" ;;
  *) usage ;;
esac
