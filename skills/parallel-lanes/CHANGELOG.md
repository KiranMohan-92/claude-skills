# Changelog: parallel-lanes

## 0.10.0 (2026-10-25)
- First release. Built from one game project's 22 named worktree lanes and 104 merges, which produced 11 logged failures, plus lane work on two other projects.
- Section 0 applies Anthropic's guidance on folding subagents into the main loop: split by context, fold coupled work, return compact results.
- Scripts:
  - `lane_overlap.py`: folder-by-folder glob matching, so new files and nested claims count. The check errs towards reporting an overlap. It also reports shared reserved slots and files two branches both changed.
  - `lane_preflight.py`: disk, RAM and gate concurrency, and ignore rules checked by asking git, prettier and ESLint themselves. When a tool can't be asked, it reports UNVERIFIED, never PASS.
  - `lane_integrate.py`: an exit-code gate run without a shell (with Windows-safe argument parsing), repeat runs to catch flakes, re-measurement, and a clean tree before and after.
  - `worktree_safe_remove.py`: refuses on any untracked or ignored file (found by walking the folder), modified files, locks or submodules, visible processes inside, your own processes it can't inspect, hard links, or a WSL `/mnt/` path without `--windows-processes-checked`. Never uses `--force`.
- Tested against real temporary repos and worktrees. A Codex review of the first draft found 5 serious problems in these scripts; each now has a regression test, and each fragile branch was mutation-checked.
