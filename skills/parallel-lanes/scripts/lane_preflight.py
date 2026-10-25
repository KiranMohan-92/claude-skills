"""Check the machine and repo can take N parallel worktree lanes before launching them.

usage:
  python lane_preflight.py --repo DIR --lanes N [--worktree-dir PATH] [--min-free-gb 5] [--per-lane-gb 2]
                           [--ram-per-lane-gb 3] [--gate-pattern REGEX --max-gates K]
Checks (each prints PASS, FAIL or SKIP):
  disk    free space on the repo's filesystem >= min-free + lanes x per-lane
  ram     available memory >= lanes x ram-per-lane (Linux/WSL: /proc/meminfo; skipped elsewhere)
  ignore  the worktree dir is ignored by git, and by prettier/eslint when the repo uses them, so a formatter or
          linter run in one lane can't walk into the others. The tools are asked directly (`prettier --file-info`,
          ESLint's isPathIgnored); when one can't be asked the check prints WARN ... UNVERIFIED, not PASS
  gates   fewer than --max-gates processes match --gate-pattern already (Linux/WSL; skipped elsewhere)
Exit 0 = all checks pass or skip, 1 = a check failed, 2 = usage.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

GB = 1024 ** 3


def check_disk(repo, lanes, min_free, per_lane):
    free = shutil.disk_usage(repo).free / GB
    need = min_free + lanes * per_lane
    ok = free >= need
    return ok, f"disk: {free:.1f} GB free, need {need:.1f} GB ({min_free:g} + {lanes} x {per_lane:g})"


def mem_available_gb(meminfo="/proc/meminfo"):
    try:
        for line in Path(meminfo).read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024 / 1024
    except OSError:
        return None
    return None


def check_ram(lanes, per_lane, meminfo="/proc/meminfo"):
    avail = mem_available_gb(meminfo)
    if avail is None:
        return None, "ram: SKIP (no /proc/meminfo on this system)"
    need = lanes * per_lane
    return avail >= need, f"ram: {avail:.1f} GB available, need {need:.1f} GB ({lanes} x {per_lane:g})"


def uses_tool(repo, tool):
    pkg = repo / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if tool in deps or tool in json.dumps(data.get("scripts", {})):
            return True
    return any(p.name.startswith((f".{tool}rc", f"{tool}.config")) for p in repo.iterdir())


PROBE_EXTENSIONS = ("ts", "tsx", "js", "jsx", "mjs", "cjs", "json", "md", "css")
ESLINT_QUERY = ("const {ESLint} = await import('eslint');"
                "const e = new ESLint({cwd: process.cwd()});"
                "console.log(JSON.stringify({ignored: await e.isPathIgnored(process.argv[1])}));")


def tool_ignores(repo, tool, probe):
    """Ask the tool itself whether it ignores `probe`: True, False, or None when it can't be asked."""
    if tool == "prettier":
        cmd = [os.environ.get("PREFLIGHT_NPX", "npx"), "--no-install", "prettier", "--file-info", probe]
    else:
        cmd = [os.environ.get("PREFLIGHT_NODE", "node"), "--input-type=module", "-e", ESLINT_QUERY, probe]
    try:
        r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return None
        return bool(json.loads(r.stdout.strip().splitlines()[-1])["ignored"])
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, IndexError):
        return None


def check_ignore(repo, worktree_dir):
    wt = Path(worktree_dir)
    wt = wt if wt.is_absolute() else repo / wt
    try:
        rel = wt.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return True, f"ignore: worktree dir {wt} is outside the repo, nothing can walk into it"
    problems, unverified = [], []
    # one probe per common source type: a config that only covers some extensions must not pass for the folder
    probes = [f"{rel}/probe/probe.{ext}" for ext in PROBE_EXTENSIONS]
    r = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", probes[0]], capture_output=True)
    if r.returncode != 0:
        problems.append("git (add it to .gitignore)")
    for tool in ("prettier", "eslint"):
        if not uses_tool(repo, tool):
            continue
        verdicts = [tool_ignores(repo, tool, p) for p in probes]
        if False in verdicts:
            missed = [p.rsplit(".", 1)[1] for p, v in zip(probes, verdicts) if v is False]
            problems.append(f"{tool} (add '{rel}' to its ignore list; .{', .'.join(missed)} files are not ignored)")
        elif None in verdicts:
            unverified.append(tool)
    if problems:
        return False, f"ignore: '{rel}' is not ignored by " + ", ".join(problems)
    if unverified:
        return None, (f"ignore: UNVERIFIED for {', '.join(unverified)}: the tool couldn't be asked (dependencies "
                      f"not installed?). Check that it skips '{rel}' before running it in lanes")
    return True, f"ignore: '{rel}' ignored by git and the repo's formatter/linter (asked the tools)"


def count_processes(pattern, proc="/proc"):
    if not Path(proc).is_dir():
        return None
    rx = re.compile(pattern)
    me = {os.getpid(), os.getppid()}
    n = 0
    for d in Path(proc).iterdir():
        if not d.name.isdigit() or int(d.name) in me:
            continue
        try:
            cmd = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            continue
        if cmd and rx.search(cmd):
            n += 1
    return n


def check_gates(pattern, max_gates, proc="/proc"):
    n = count_processes(pattern, proc)
    if n is None:
        return None, "gates: SKIP (no /proc on this system)"
    return n < max_gates, f"gates: {n} running process(es) match /{pattern}/, limit {max_gates}"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--lanes", type=int, required=True)
    ap.add_argument("--worktree-dir", default=".claude/worktrees")
    ap.add_argument("--min-free-gb", type=float, default=5.0)
    ap.add_argument("--per-lane-gb", type=float, default=2.0)
    ap.add_argument("--ram-per-lane-gb", type=float, default=3.0)
    ap.add_argument("--gate-pattern")
    ap.add_argument("--max-gates", type=int)
    ap.add_argument("--meminfo", default="/proc/meminfo", help=argparse.SUPPRESS)
    ap.add_argument("--proc", default="/proc", help=argparse.SUPPRESS)
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    repo = Path(a.repo)
    if a.lanes < 1 or not repo.is_dir() or (a.gate_pattern is None) != (a.max_gates is None):
        print("usage: --lanes >= 1, --repo must exist, and --gate-pattern needs --max-gates", file=sys.stderr)
        return 2
    results = [check_disk(repo, a.lanes, a.min_free_gb, a.per_lane_gb),
               check_ram(a.lanes, a.ram_per_lane_gb, a.meminfo),
               check_ignore(repo, a.worktree_dir)]
    if a.gate_pattern:
        results.append(check_gates(a.gate_pattern, a.max_gates, a.proc))
    failed = False
    for ok, msg in results:
        tag = ("WARN" if "UNVERIFIED" in msg else "SKIP") if ok is None else ("PASS" if ok else "FAIL")
        print(f"{tag}  {msg}")
        failed |= ok is False
    print("PREFLIGHT FAILED: fix the above or run fewer lanes" if failed else f"PREFLIGHT OK for {a.lanes} lane(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
