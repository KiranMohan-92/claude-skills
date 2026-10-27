# Changelog: codex-delegate

## 0.10.1 (2026-10-27)
- `status`: a job that records its exit status and ends between the first check and `ps` is now judged by that record, not reported as killed. This race made a test fail in 2 of 11 full-suite runs.
- The wrapper writes the exit record to a temporary file and renames it, so `status` never reads a half-written one. That window is too short to hit reliably, so it has no test.
- New tests for the zombie guard, the race and the `setsid` dependency check; each fails when its guard is removed.

## 0.10.0 (2026-10-25)
- First release. Built from one month of game development where Claude led and Codex reviewed and implemented (94 `codex exec` and about 360 review commands), and from Codex use in six other projects.
- `codex_run.sh`:
  - `probe`: version floor, reachability from the same environment, and an optional live exec that must exit 0 and answer exactly OK.
  - `launch`: paths resolved before `--cd`, `setsid nohup`, the brief on stdin, a PID plus a job token, and the exit status recorded when the job ends.
  - `status`: our job identified by its token (a reused PID or a zombie isn't), and success only on exit 0 with a non-empty result.
  - `scope`: a size cap, line-ending churn, untracked text files counted without following symlinks, and git errors fail rather than pass.
- `review_loop.py`:
  - the verdict must be the exact final line; quoted or qualified verdicts fail closed;
  - a round ledger, pinning from round 4, and a stop after three fix-first rounds in a row that each find something new.
- Tested against a fake `codex` executable, with no network or credentials. A Codex review of the first drafts of this skill and `parallel-lanes` found 11 serious problems, 6 of them in this skill: 5 in the scripts and 1 in `SKILL.md`, an overstated compatibility claim, now corrected and backed by a dependency check. Each script finding now has a regression test that fails when its fix is reverted; two guard branches (zombie detection and the `setsid` check) are not yet covered by a test.
