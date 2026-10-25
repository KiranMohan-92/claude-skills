# Changelog: daily-retro

## 0.9.1 (2026-10-25)
- Fix: automated prompts no longer count as user messages. Mining a project folder of automated security-review runs had reported 55 "user messages" and 17 "corrections".
  - The miner keeps a prompt only when `turnOrigin` is `human`. It skips SDK runs, agent-to-agent messages, task notifications and sidechains, and in older transcripts any `sdk-*` entrypoint.
  - A session made only of automated prompts is skipped whole, including its tool errors.
  - `--include-automated` restores the old behaviour.
- The digest reports how many automated prompts and sessions it skipped.
- Covered by three new tests; each filter branch was mutation-checked.

## 0.9.0 (2026-10-25)
- First packaged release (pre-1.0: no scored eval run yet), generalised from a personal skill written on 2026-10-20.
- `mine_transcript.py`: by default reads every project under `~/.claude/projects` (one level deep) instead of one hard-coded project.
- Output steps no longer assume a particular review page or failure-log location.
- Covered by `tests/test_mine_transcript.py`.
