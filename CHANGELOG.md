# Changelog: agent-ops plugin

The plugin version moves when any skill changes. Each skill also keeps its own `metadata.version` and `CHANGELOG.md`.

## 0.9.0 (2026-10-25)
- First public release: `media-delivery-gates` 0.9.0, `long-job-updates` 0.9.0, `win-wsl-shell` 0.9.0, `daily-retro` 0.9.0.
- Pre-1.0 because `STANDARDS.md` requires a scored baseline run (5.2) and grader failure checks (5.4) before 1.0.0; neither has run yet.
- CI: Anthropic's `quick_validate.py` (pinned commit), `claude plugin validate` (pinned CLI), shellcheck, and pytest with ffmpeg fixtures.
- 25 eval cases (17 from logged failures, 8 designed near-misses), runnable with `claude plugin eval`.
