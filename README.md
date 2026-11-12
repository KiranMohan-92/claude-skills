# claude-skills

[![ci](https://github.com/KiranMohan-92/claude-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/KiranMohan-92/claude-skills/actions/workflows/ci.yml)

A Claude Code plugin marketplace with one plugin, **`agent-ops`**: seven skills for running long, multi-step agent work reliably. Each skill was written after a logged failure in my own work, then generalised, versioned, tested and given evals.

| Skill | Version | What it prevents | Scripts and tests |
|---|---|---|---|
| [`media-delivery-gates`](skills/media-delivery-gates/SKILL.md) | 0.9.1 | Delivering a video whose encoded audio peaks above the ceiling, or with a continuity error nobody looked for. | `gate_deliverable.sh`, `contact_sheet.sh`; CI proves a +0.6 dBTP AAC clip fails and a clean clip passes. |
| [`long-job-updates`](skills/long-job-updates/SKILL.md) | 0.9.0 | Users chasing status ("And?") during long renders, batches and scrapes. | `waitfor.sh` (bounded, can't match itself), `progress_sheet.sh`. |
| [`win-wsl-shell`](skills/win-wsl-shell/SKILL.md) | 0.9.0 | Quoting, path-conversion, line-ending and wait failures between Git Bash, PowerShell and WSL. | Rules only; each traces to a logged failure. |
| [`daily-retro`](skills/daily-retro/SKILL.md) | 0.9.1 | Repeating yesterday's friction. Mines transcripts into a digest and drafts skills and rules from it. | `mine_transcript.py` with pytest; skips automated (SDK, agent-to-agent) prompts. |
| [`codex-delegate`](skills/codex-delegate/SKILL.md) | 0.10.1 | Delegating to Codex CLI and getting nothing back: dead lanes reported as running, empty reviews read as "no findings", review loops that never converge. | `codex_run.sh` (probe, detached launch, PID status, diff scope), `review_loop.py` (verdict, pinning, stop rule); tested against a fake `codex`. |
| [`page-delivery-gates`](skills/page-delivery-gates/SKILL.md) | 0.11.1 | Handing over a web page that breaks for some viewers: wider than a phone screen only while something animates in, blank or still moving with reduced motion on, dead without WebGL. Also stops the check itself inventing defects (a "black" canvas, holes in the screenshot). | `gate_page.py` loads the page at desktop and phone width three ways (normal, reduced motion, WebGL refused) and writes contact sheets; tested in a real headless browser on fixture pages, one per incident. |
| [`parallel-lanes`](skills/parallel-lanes/SKILL.md) | 0.10.0 | Fanning out work that isn't independent, running the machine out of RAM or disk, "green" lanes that break main, and cleanup that deletes a live worktree. Starts with whether to fan out at all. | `lane_overlap.py`, `lane_preflight.py`, `lane_integrate.py`, `worktree_safe_remove.py`; tested on real repos and worktrees. |

## Install

```text
/plugin marketplace add KiranMohan-92/claude-skills
/plugin install agent-ops@kiranmohan-skills
```

### Pin it for a team
The plugin's version lives in `plugin.json`, and each release is tagged (`v0.9.0`, `v0.10.0`, `v0.10.1`, `v0.11.0`, `v0.11.1`, …). Point the marketplace at a tag or a full commit SHA so nobody gets an update before it's reviewed. `enabledPlugins` alone doesn't pin a version. In managed or project settings:

```json
{
  "extraKnownMarketplaces": {
    "kiranmohan-skills": {
      "source": { "source": "github", "repo": "KiranMohan-92/claude-skills", "ref": "v0.11.1" }
    }
  },
  "enabledPlugins": { "agent-ops@kiranmohan-skills": true }
}
```

To pin harder, a team's own marketplace can list the plugin with `"source": {"source": "github", "repo": "KiranMohan-92/claude-skills", "ref": "v0.11.1", "sha": "<40-char commit>"}`. When both are set, the SHA wins.

## Quality gates

Every push runs [CI](.github/workflows/ci.yml):

| Check | What it enforces |
|---|---|
| Anthropic's `quick_validate.py` (pinned commit of `anthropics/skills`) | Frontmatter: name, description length, allowed keys |
| `claude plugin validate` (pinned CLI version) | `plugin.json` and `marketplace.json` |
| `shellcheck -S warning` | Every shell script |
| `tests/test_structure.py` | Versions match changelogs; no personal paths or credential patterns anywhere in the repo; LF endings; referenced scripts exist; eval coverage per skill |
| `pytest` with ffmpeg fixtures, a fake `codex`, real temporary git repos and worktrees, and fixture pages in headless Chromium | Script behaviour, including the scripted incidents (a +0.6 dBTP AAC file, a wait that matched its own command line, a job killed when its session hung up, an empty review, a worktree removed under a live process, a page that overflows a phone screen only after scrolling, a view that loses its text when WebGL is refused). Each regression test was checked by breaking the code and confirming it fails. |
| Eval cases match `evals/build_cases.py` | No hand-edited drift in the eval suite |

[`STANDARDS.md`](STANDARDS.md) is the rubric behind these checks, written so another engineer can grade a skill in 15 minutes.

## Evals

`evals/` holds 44 cases for [`claude plugin eval`](https://code.claude.com/docs/en/plugin-evals), generated from one table in [`evals/build_cases.py`](evals/build_cases.py): 30 built from logged failures (each names its source) and 14 designed near-misses.
- **Should-trigger cases (30):** an LLM grader checks the behaviour the skill should produce. It's scored in both arms, so the with-minus-without delta is what the skill adds. A `tool_used: Skill` indicator records whether the skill fired.
- **Near-miss cases (14):** same vocabulary, different need (e.g. "what is LUFS?", a Linux-only shell question, a team sprint retro, asyncio "parallel" requests). A scored grader requires that the skill does **not** fire.

Run them (needs a logged-in Claude Code ≥ 2.1.269; on Windows, run under WSL 2):

```bash
claude plugin eval . --trust-plugin --runs 3 --no-publish
claude plugin eval . --trust-plugin --tag media-delivery-gates --model haiku
```

**Results** (Opus 5.5, 3 runs per arm; full tables and caveats in [`evals/RESULTS.md`](evals/RESULTS.md)):

| Run | Should-trigger cases | With plugin | Without | Δ | Skill fired | False triggers |
|---|---|---|---|---|---|---|
| 2 (0.10.0) | 25 | 0.85 | 0.60 | **+0.25** | 28/75 | 0/36 |
| 1 (0.9.0) | 17 | 0.76 | 0.55 | **+0.22** | 20/51 | 0/24 |

Run 3 (0.11.0) covered only the 7 new `page-delivery-gates` cases: 0.93 with the plugin, 0.80 without (Δ +0.13), no false triggers in 12 runs. The skill fired in 0 of 15 runs, so that gain can't be credited to it yet; its script is covered by browser tests, which this eval doesn't run.

When a skill fires in at least 2 of 3 runs, the mean gain is +0.56. When it never fires, +0.07. Triggering is the bottleneck: `daily-retro` has not fired yet, and fixing that is the next release.

**Before 1.0.0** (from [`STANDARDS.md`](STANDARDS.md)): the baseline run (5.2) is done. Still open: every grader checked once against a response that should fail it (5.4), and runs on Haiku and Sonnet (5.3).

## Layout

```text
.claude-plugin/     plugin.json (version) + marketplace.json
skills/<name>/      SKILL.md, CHANGELOG.md, scripts/
evals/              build_cases.py + one folder per case (prompt.md, graders/)
tests/              pytest: scripts, fixtures, packaging rules
STANDARDS.md        the skill rubric
```

## License

[MIT](LICENSE)
