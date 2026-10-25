---
name: codex-delegate
description: Delegates work from Claude Code to OpenAI's Codex CLI, as a reviewer (verifier) or a self-contained implementation lane, and gets a verified result back. Use when the user says "use codex", "offload to codex", "run a codex review", "merge once codex is clean", "get a second opinion", or when a diff needs an independent review before commit. Probes the transport first, launches detached so the job outlives the shell, refuses oversized or line-ending-churned diffs, treats an empty result as a failure, and stops review loops that keep finding new problems. Not for questions about OpenAI APIs or for tasks Claude should do in its own loop.
license: MIT
compatibility: Needs the Codex CLI (codex-cli 0.159 or later for current models), bash, curl, git, ps, coreutils timeout and util-linux setsid, so Linux or WSL (on Windows, run Codex inside WSL; macOS needs those GNU tools installed). review_loop.py needs Python 3.9+.
metadata:
  version: 0.10.0
---

# Codex delegate

Over one month of building a game with Claude leading and Codex reviewing, delegation failed in these ways:
- **Three implementation lanes reported "running" while dead.** WSL had no network, a `nohup` child died with its `wsl.exe` session, and the watcher counted processes instead of checking the job.
- **The reviewer was unreachable twice** (in two different projects), and the requested model refused to run until the CLI went from 0.157 to 0.159.
- **A review came back as a 0-byte file and was read as "no findings"**: the script it ran had Windows line endings.
- **A 4,028-line diff that was almost all line-ending churn** was sent for review.
- **Three review loops ran 9, 10 and 5 rounds** before the work was abandoned.

When it works it pays: in a three-day period while the reviewer was down, 23 defects shipped that the project's own checks had passed; the review found them when it came back.

Each fragile step below is a script call, so the rule is enforced, not remembered.

## 0. Decide whether to delegate at all
Delegation costs context: the second agent sees only your brief, and you see only its summary. Delegate work that splits cleanly by context:
- **Black-box verification:** review a diff, test a claim, check a fix. This is the generator-verifier pattern; a second model catches what the author misses.
- **A self-contained lane:** a component with a clean interface and its own files, which needs little from the rest of the system and returns a compact result.

Keep it in your own loop when the task is tightly coupled to what you're doing, needs your conversation's context, is small, or needs things the Codex sandbox lacks: Windows programs, the GPU, a browser on the user's desktop, or local servers.

## 1. Probe before you depend on it
```bash
bash scripts/codex_run.sh probe --min-version 0.159.0 --live
```
(`scripts/` is in this skill's folder; on Windows, run it inside WSL.) Exit 0 means installed, new enough, and reachable from this environment; `--live` also requires a one-line `codex exec` to exit 0 and answer exactly OK. Exit 3 means unreachable or not installed, and 4 means the CLI is too old. On 3, don't launch lanes; use the outage path in step 6.

## 2. Write a brief that stands alone
- State the goal, the files or diff, what to check, and what's already decided, so the reviewer doesn't relitigate it.
- Ask for a compact result: findings ranked P1/P2/P3 with file:line, and a last line of exactly `VERDICT: ship` or `VERDICT: fix first`.
- Say "read-only" for reviews. Never point Codex at credential files (`~/.codex/auth.json`, `.env`).
- Save the brief to a file; never paste it through nested shell quotes.

## 3. Check the review scope
```bash
bash scripts/codex_run.sh scope --uncommitted        # or --base main, or --commit SHA
```
Exit 1 means the diff is bigger than `--max-lines` (default 1500, untracked text files included), mostly line-ending churn, or git failed (an unknown branch or commit). Binary files are listed, not counted; untracked symlinks and special files are skipped, never followed. Fix the cause or split the review before spending a run on it.

## 4. Launch detached and check completion
```bash
bash scripts/codex_run.sh launch --brief brief.md --out result.md --log run.log --sandbox read-only -- -c model="..."
bash scripts/codex_run.sh status --out result.md --log run.log
```
- `launch` resolves the paths, then starts the job with `setsid nohup` so it survives the shell that started it. It records the PID, a token in the job's command line, and codex's exit status when it ends.
- `status`: 10 means our job is still running (that PID, carrying our token, not a zombie). 0 means codex exited 0 with a non-empty result. 1 means anything else: a non-zero exit, an empty result, or a job killed before it could record its exit. **An empty result is a failed run, never "no findings".**
- Use `--sandbox workspace-write` only for implementation lanes, in their own worktree (see `parallel-lanes`).
- For a short review, `codex review --uncommitted` (or `--base`, `--commit`) in the foreground is fine; still check that its output is non-empty.

## 5. Close the loop, and stop it
```bash
python scripts/review_loop.py record --ledger review-ledger.jsonl --output result.md [--new N]
```
- Exit 0 means ship. Exit 1 means fix first: fix, re-run the project's own gate, then review again.
- Exit 3 means the next round must be **pinned**: the brief lists only the open findings and asks for new factual errors only. Unpinned reviews keep finding fresh nits.
- Exit 4 means **stop**: three fix-first rounds in a row each found something new. The scope is too big or the approach is wrong. Re-scope, or ask the user. Don't start round N+1.
- Exit 2 means the last non-empty line isn't exactly `VERDICT: ship` or `VERDICT: fix first`: a failed review. A verdict quoted from an earlier round, or followed by more text, doesn't count. Re-run it.
- Pass `--new N` when you can tell repeats from new findings; otherwise the count of P1/P2 lines is used.
- You run what Codex can't: the project's gate, browser checks, GPU measurements. Feed their failures into the next brief.

## 6. When the reviewer is down
- Say so, and keep a ledger of every commit that ships unreviewed.
- Use a fallback reviewer with fresh context (e.g. a separate Claude session given only the diff and the brief), fail-closed: a reviewer that returns nothing blocks the commit.
- When Codex is back, review the ledger's commits first.

## Gotchas
- `wsl -e bash -lc 'nohup codex … &'` dies when the `wsl.exe` call returns. `launch` uses `setsid nohup … & disown` for this reason.
- A network check from Windows says nothing about WSL. Probe from the environment that will run Codex.
- Model names need a minimum CLI version. Check with `probe --min-version` before blaming the model.
- Scripts written on Windows carry CRLF line endings and fail inside WSL, sometimes silently. Convert them with `sed -i 's/\r$//'` before running them there.
- Git run from WSL against a worktree created on Windows can't read its `.git` file path. Use `git -C` from the same side that created the worktree, or set `GIT_DIR` and `GIT_WORK_TREE` explicitly.
- Codex reads only what the brief and the repo give it. If a finding depends on runtime behaviour, check it yourself before acting on it, and dispose of each finding explicitly (fixed, rejected with evidence, or deferred).
