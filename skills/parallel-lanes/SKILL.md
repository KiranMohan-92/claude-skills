---
name: parallel-lanes
description: Decides whether work should fan out into parallel lanes (subagents, workflow agents, git worktrees, or Codex workers) and, when it should, runs and merges them on one machine without breaking main, the disk or each other. Use when the user says "use swarms", "do these in parallel", "fan out", "orchestrate agents", "spin up lanes", or when several tasks could run at once. Checks first that the lanes split by context, then runs a preflight (disk, RAM, ignore rules, gate concurrency), checks file and slot ownership, proves each merge on the merged tree, and removes worktrees only when nothing would be lost and no visible process is using them. Not for a single task, or for questions about git branches in general.
license: MIT
compatibility: Python 3.9+ and git 2.30+. Process checks (preflight gate count, safe removal) need /proc, so Linux or WSL; elsewhere they report SKIP or refuse.
metadata:
  version: 0.10.0
---

# Parallel lanes

On one game project, a lead agent fanned work out to 22 named worktree lanes plus workflow fan-outs and made 104 merges. The failures fell into five groups:
- **Lanes that weren't independent broke each other with no merge conflict.** One lane used a variable another had removed. Two lanes both claimed the same wire-format bit. Bot win rates tuned on one base shifted after the merge (24/47/66 % became 29/44/56 %).
- **The machine ran out.** Five to seven lanes running gates at once hit "out of memory" with up to 98 node processes, and the disk fell to about 450 MB.
- **A formatter run in one lane walked into the others**, because the worktree folder wasn't in the formatter's ignore list.
- **"Green" wasn't green.** A lane's passing gate failed on the lead's re-run, and one green run hid a test that failed about half the time.
- **Cleanup deleted part of a worktree that a live server was still serving from.**

There was also constant friction: 120 tool calls across 17 lane agents were refused because their commands were too complex to verify as staying inside the worktree.

## 0. Should this fan out at all?
Anthropic's guidance on agent design favours **one agent loop with skills** over many agents: fewer context windows, fewer lossy handoffs, and newer models handle much more in one loop. Fan out only when the work splits **by context**, not by topic:
- independent components with clean interfaces and their own files;
- independent research paths;
- black-box verification of finished work (see `codex-delegate`).

Each lane must need little from the rest and return a compact result. **Fold work back into one loop** (or run it in sequence) when:
- the pieces chain on each other's output, or touch the same files or data;
- they're usually needed together;
- the job is small enough that briefing a lane costs more than doing it.

Split lanes by context, never one lane per team or topic. If the overlap check below fails, that's the signal to fold.

## 1. Plan ownership, then check it
Write `lanes.json` with one entry per lane: the files or globs it owns, and any shared slots it reserves (an enum value, a wire-format bit, a port, a database migration number):
```json
{"lanes": [{"name": "ui", "files": ["src/ui/**"], "reserve": []},
           {"name": "netcode", "files": ["src/net/**"], "reserve": ["snapshot-bit-7"]}]}
```
```bash
python scripts/lane_overlap.py plan --repo . --plan lanes.json
```
(`scripts/` is in this skill's folder.) Patterns are matched folder by folder (`*` stays in one folder, `**` spans folders, a trailing `/` means everything under it), and new files count: a lane claiming `src/ui/new.ts` overlaps a lane owning `src/ui/**`. The check errs towards reporting an overlap. Exit 1 means two lanes can claim the same path or slot: re-split, or fold them into one lane.

## 2. Preflight the machine
```bash
python scripts/lane_preflight.py --repo . --lanes 4 --worktree-dir .claude/worktrees --gate-pattern "vitest|tsc|eslint" --max-gates 2
```
It checks disk (default 5 GB plus 2 GB per lane), available RAM (default 3 GB per lane), and how many gate processes are already running. It also checks that the worktree folder is ignored by git, and by prettier and eslint when the repo uses them; it asks the tools themselves, and prints `WARN … UNVERIFIED` when one can't be asked (dependencies not installed). Exit 1 means fix it or run fewer lanes. Tune the per-lane numbers to your stack; measure one lane first.

## 3. Brief each lane
- Its files and reserved slots (from `lanes.json`), the base commit, and what to return: a short summary, the gate result, and any measured number together with the commit it was measured on.
- One plain command per tool call, run from the worktree root. Long `cd … && …` chains are what got refused 120 times.
- No dev servers, end-to-end browser runs or GPU jobs inside lanes; the lead runs those, one at a time.
- Run the project's gate on its own and read its exit code; never pipe it through `grep` or `head`.
- For "where are we?", keep a one-line-per-lane board: lane, branch, gate, review round, ETA, blocker.

## 4. Merge one lane at a time, and prove the merged tree
```bash
python scripts/lane_overlap.py actual --repo . --base main lane-a lane-b lane-c
python scripts/lane_integrate.py --repo . --gate "pnpm check" --repeat "pnpm vitest run src/new.test.ts" --times 3 --remeasure "node tools/bench.mjs"
```
- `actual` lists branches that changed the same files. Merge those one at a time, with a full gate in between.
- After each merge, `lane_integrate` runs the full gate on the merged tree, runs new tests several times to catch flakes, and re-runs any number the lane reported. A number measured on one base is a claim about that base. It needs a clean `git status` before and after.
- Commands are run without a shell, so a pipe can't hide a red gate.
- Review the integrated result once, not just each lane's diff.

## 5. Clean up safely
```bash
python scripts/worktree_safe_remove.py --repo . --worktree .claude/worktrees/lane-a
```
It refuses when:
- any file inside isn't tracked, including ignored ones such as `.env`. It finds them by walking the folder, because `git worktree remove` deletes ignored files;
- a tracked file is modified, or the worktree is locked or has submodules;
- a process it can see has its working directory or an open file inside, or one of your own processes can't be inspected;
- files inside are hard-linked elsewhere, or it's the main worktree.

On WSL it can't see Windows processes, so a worktree under `/mnt/` also needs `--windows-processes-checked` once you've checked yourself. The process check is a snapshot: stop whatever might start in the worktree first. `--dry-run` runs every check and removes nothing.

## Gotchas
- Lanes compete for the same CPU, RAM, disk and GPU. Running more lanes past the machine's limit makes everything slower and flakier, not faster.
- Shared configuration (formatter, linter, test discovery) walks every folder it isn't told to skip, including other lanes' worktrees.
- On Windows with WSL, the WSL disk is a file on a Windows drive, so check that drive's free space too (see `win-wsl-shell`).
- A lane agent's summary is a lossy handoff. Trust only what the merged tree re-proves.
- Measure one change at a time. If folding a lane back into the main loop scores the same or better on your checks, keep it folded.
