"""After merging a lane: prove the merged result, not the lane's own report.

usage:
  python lane_integrate.py --repo DIR --gate "CMD" [--repeat "CMD" --times 3] [--remeasure "CMD"]

  --gate       the project's full gate (tests, types, lint), run on the merged tree. Judged by ITS OWN exit code.
               Each CMD is one command run without a shell (split like a shell would, but no pipes, `&&` or
               redirects), so it can't be piped through grep/head, whose exit status would hide a red gate. The
               guarantee is about the command you give: a wrapper script that pipes internally can still hide one.
  --repeat     run new or touched tests --times times: one green run hid a ~50 % flake.
  --remeasure  re-run any number the lane reported (a benchmark, a win rate): a number measured on one base is
               a claim about that base, not about the merge.
Also requires a clean `git status` before and after, so nothing half-merged or generated is left behind.
Exit 0 = merged result proven, 1 = something failed, 2 = usage.
"""
import argparse
import os
import shlex
import subprocess
import sys

SHELL_OPERATORS = {"|", "||", "&&", ";", "&", ">", ">>", "<", "2>&1"}


def split_windows(cmd):
    """Split like the Microsoft C runtime: double quotes group and are removed anywhere in an argument
    (`--x="a b"` is one argument), `""` inside a quoted run is one literal quote, and backslashes are literal
    except before a double quote, where 2n backslashes give n and 2n+1 give n plus a literal quote."""
    args, cur, quoted, started, i = [], [], False, False, 0
    while i < len(cmd):
        c = cmd[i]
        if c == "\\":
            j = i
            while j < len(cmd) and cmd[j] == "\\":
                j += 1
            n = j - i
            if j < len(cmd) and cmd[j] == '"':
                cur.append("\\" * (n // 2))
                if n % 2:
                    cur.append('"')
                    j += 1
            else:
                cur.append("\\" * n)
            started, i = True, j
        elif c == '"':
            if quoted and i + 1 < len(cmd) and cmd[i + 1] == '"':
                cur.append('"')  # "" inside a quoted run is one literal quote; the run stays open
                started, i = True, i + 2
            else:
                quoted, started, i = not quoted, True, i + 1
        elif c in " \t" and not quoted:
            if started:
                args.append("".join(cur))
                cur, started = [], False
            i += 1
        else:
            cur.append(c)
            started, i = True, i + 1
    if started:
        args.append("".join(cur))
    return args


def parse(cmd, windows=None):
    """Split CMD into argv; refuse shell operators so the exit code is the command's own.
    On Windows, backslashes are path separators, not escapes, so split by the Windows rules instead."""
    windows = os.name == "nt" if windows is None else windows
    argv = split_windows(cmd) if windows else shlex.split(cmd)
    bad = [t for t in argv if t in SHELL_OPERATORS]
    if not argv or bad:
        raise ValueError(f"{cmd!r}: give one command, without pipes or chaining ({' '.join(bad) or 'empty'})")
    return argv


def sh(argv, repo):
    try:
        return subprocess.run(argv, cwd=repo).returncode
    except FileNotFoundError:
        print(f"FAIL  command not found: {argv[0]}")
        return 127


def dirty(repo):
    r = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True, text=True)
    if r.returncode != 0:
        return "not a git repository"
    return r.stdout.strip()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--repeat")
    ap.add_argument("--times", type=int, default=3)
    ap.add_argument("--remeasure")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    if a.times < 2:
        print("--times must be at least 2 to catch a flake", file=sys.stderr)
        return 2
    try:
        gate = parse(a.gate)
        repeat = parse(a.repeat) if a.repeat else None
        remeasure = parse(a.remeasure) if a.remeasure else None
    except ValueError as e:
        print(f"usage: {e}", file=sys.stderr)
        return 2
    before = dirty(a.repo)
    if before:
        print(f"FAIL  working tree not clean before integration:\n{before}")
        return 1
    failures = []
    rc = sh(gate, a.repo)
    print(f"{'PASS' if rc == 0 else 'FAIL'}  gate (exit {rc})")
    if rc:
        failures.append("gate")
    if repeat:
        codes = [sh(repeat, a.repo) for _ in range(a.times)]
        bad = sum(c != 0 for c in codes)
        print(f"{'PASS' if not bad else 'FAIL'}  repeat x{a.times}: {bad} failing run(s) {codes}")
        if bad:
            failures.append("flaky or failing tests")
    if remeasure:
        rc = sh(remeasure, a.repo)
        print(f"{'PASS' if rc == 0 else 'FAIL'}  remeasure (exit {rc})")
        if rc:
            failures.append("remeasure")
    after = dirty(a.repo)
    if after:
        print(f"FAIL  working tree not clean after the gate (generated or modified files):\n{after}")
        failures.append("dirty tree")
    print("INTEGRATION OK" if not failures else "INTEGRATION FAILED: " + ", ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
