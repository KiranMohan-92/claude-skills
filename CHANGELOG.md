# Changelog: agent-ops plugin

The plugin version moves when any skill changes. Each skill also keeps its own `metadata.version` and `CHANGELOG.md`.

## 0.11.1 (2026-11-12)
- `page-delivery-gates` 0.11.1: contact sheets no longer show a scroll-eased scene in mid-flight; one new test, which fails on 0.11.0.

## 0.11.0 (2026-11-12)
- New skill: `page-delivery-gates` 0.11.0, the web-page counterpart of `media-delivery-gates`. It came from mining four months of transcripts for page work: the same hand-off checks had been written by hand in up to 16 sessions each.
- 7 new eval cases (5 from logged failures, 2 near-misses), for 44 in total.
- Scored run of the new cases recorded in `evals/RESULTS.md` (run 3): 0.93 with the plugin, 0.80 without, no false triggers; the skill did not fire in any run, so the gain is not yet attributable to it.
- CI installs Playwright's Chromium and runs the new browser tests on a runner without a GPU.

## 0.10.1 (2026-10-27)
- `codex-delegate` 0.10.1: `status` no longer reports a job that finishes mid-check as killed; three new guard tests.

## 0.10.0 (2026-10-25)
- New skills: `codex-delegate` 0.10.0 and `parallel-lanes` 0.10.0, built from one month of game development (Claude leading, Codex reviewing, 22 worktree lanes) and checked against Anthropic's guidance on when to fold subagents into the main loop.
- `daily-retro` 0.9.1: automated prompts are no longer counted as user messages.
- 12 new eval cases (8 from logged failures, 4 near-misses), for 37 in total.
- First scored eval run recorded in `evals/RESULTS.md`.

## 0.9.0 (2026-10-25)
- First public release: `media-delivery-gates` 0.9.0, `long-job-updates` 0.9.0, `win-wsl-shell` 0.9.0, `daily-retro` 0.9.0.
- Pre-1.0 because `STANDARDS.md` requires a scored baseline run (5.2) and grader failure checks (5.4) before 1.0.0; neither has run yet.
- CI: Anthropic's `quick_validate.py` (pinned commit), `claude plugin validate` (pinned CLI), shellcheck, and pytest with ffmpeg fixtures.
- 25 eval cases (17 from logged failures, 8 designed near-misses), runnable with `claude plugin eval`.
