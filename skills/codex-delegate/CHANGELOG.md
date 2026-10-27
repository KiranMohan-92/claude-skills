# Changelog: codex-delegate

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
