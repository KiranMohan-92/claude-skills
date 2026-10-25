"""Are these lanes really independent? Check planned file ownership before launch, and actual changes before merge.

usage:
  python lane_overlap.py plan  --repo DIR --plan lanes.json
  python lane_overlap.py actual --repo DIR --base REF BRANCH [BRANCH ...]

plan: lanes.json is {"lanes": [{"name": "...", "files": ["pattern", ...], "reserve": ["shared-slot", ...]}, ...]}.
  Patterns are path globs matched segment by segment: `*` and `?` stay within one folder, `**` spans folders
  (`src/**/*.ts` also matches `src/x.ts`), and a path ending in `/` means everything under it. Two lanes overlap
  when their patterns can claim the same path: a tracked file matching both, a literal path (a new file) matching
  the other's pattern, or one pattern's fixed folder lying inside the other's recursive claim. The check errs
  towards reporting an overlap. Two lanes reserving the same slot (an enum value, a wire-format bit, a port)
  overlap too.
actual: fails when two branches changed the same file since BASE. Merge those lanes one at a time with a full
  gate in between, or fold them into one lane: lanes that touch the same files are coupled.
Exit 0 = independent, 1 = overlap found, 2 = usage.
"""
import argparse
import json
import re
import subprocess
import sys
from itertools import combinations
from pathlib import Path

GLOB_CHARS = set("*?[")


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout


def normalise(p):
    p = p.strip()
    while p.startswith("./"):
        p = p.removeprefix("./")
    return p + "**" if p.endswith("/") else p


def to_regex(pattern):
    out = []
    segs = pattern.split("/")
    for n, seg in enumerate(segs):
        last = n == len(segs) - 1
        if seg == "**":
            out.append(".*" if last else "(?:[^/]+/)*")
            continue
        part = ""
        for ch in seg:
            part += "[^/]*" if ch == "*" else "[^/]" if ch == "?" else re.escape(ch)
        out.append(part + ("" if last else "/"))
    return re.compile("^" + "".join(out) + "$")


def is_glob(p):
    return any(c in GLOB_CHARS for c in p)


def static_dir(p):
    """The fixed folder prefix before the first glob segment."""
    fixed = []
    for seg in p.split("/"):
        if is_glob(seg):
            break
        fixed.append(seg)
    return "/".join(fixed)


def overlap(a, b, tracked):
    ra, rb = to_regex(a), to_regex(b)
    if any(ra.match(f) and rb.match(f) for f in tracked):
        return True
    if not is_glob(a) and rb.match(a) or not is_glob(b) and ra.match(b):
        return True
    if not is_glob(a) and not is_glob(b):
        return a == b
    # one pattern's fixed folder inside the other's recursive (**) claim
    for x, y in ((a, b), (b, a)):
        if "**" in x and is_glob(x):
            base = static_dir(x)
            other = static_dir(y) if is_glob(y) else y
            if not base or other == base or other.startswith(base + "/"):
                return True
    return False


def plan(repo, plan_path):
    data = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    lanes = data["lanes"]
    names = [lane["name"] for lane in lanes]
    if len(set(names)) != len(names):
        print("plan: lane names must be unique")
        return 2
    tracked = set(git(repo, "ls-files").splitlines())
    claims = {lane["name"]: [normalise(p) for p in lane.get("files", [])] for lane in lanes}
    problems = []
    for lane in lanes:
        if not claims[lane["name"]]:
            problems.append(f"lane '{lane['name']}' claims no files: give it explicit ownership")
    for a, b in combinations(names, 2):
        shared = [f"{x} / {y}" for x in claims[a] for y in claims[b] if overlap(x, y, tracked)]
        if shared:
            problems.append(f"lanes '{a}' and '{b}' can both claim: {'; '.join(shared[:4])}")
    seen = {}
    for lane in lanes:
        for slot in lane.get("reserve", []):
            if slot in seen:
                problems.append(f"lanes '{seen[slot]}' and '{lane['name']}' both reserve '{slot}'")
            seen.setdefault(slot, lane["name"])
    for p in problems:
        print("OVERLAP  " + p)
    print("PLAN OK: lanes are independent" if not problems else "PLAN FAILED: split by context, or fold coupled lanes")
    return 1 if problems else 0


def actual(repo, base, branches):
    changed = {b: set(git(repo, "diff", "--name-only", f"{base}...{b}").splitlines()) for b in branches}
    problems = []
    for a, b in combinations(branches, 2):
        shared = sorted(changed[a] & changed[b])
        if shared:
            problems.append(f"'{a}' and '{b}' both changed {len(shared)} file(s): {', '.join(shared[:5])}")
    for p in problems:
        print("OVERLAP  " + p)
    for b in branches:
        print(f"         {b}: {len(changed[b])} file(s) changed since {base}")
    print("ACTUAL OK: no shared files" if not problems
          else "ACTUAL FAILED: merge these one at a time with a full gate in between")
    return 1 if problems else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--repo", required=True)
    p.add_argument("--plan", required=True)
    a_ = sub.add_parser("actual")
    a_.add_argument("--repo", required=True)
    a_.add_argument("--base", required=True)
    a_.add_argument("branches", nargs="+")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        if a.cmd == "plan":
            return plan(a.repo, a.plan)
        if len(a.branches) < 2:
            print("actual: give at least two branches", file=sys.stderr)
            return 2
        return actual(a.repo, a.base, a.branches)
    except (RuntimeError, OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
