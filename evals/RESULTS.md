# Eval results

All runs use `claude plugin eval . --runs 3 -j 4` with the default with-without ablation. The agent under test is Opus 5.5 (`claude-opus-5-5`, from the run trace). Outcome criteria are judged by the default judge model (Haiku per the docs; the result file doesn't record it), with 3 votes per run. Cases allow read-only tools only (`Read, Glob, Grep, Skill`), so each answer is a plan or a diagnosis, not executed work, and the eval never runs the skills' scripts.

## Run 2: 2026-10-25, plugin 0.10.0 (37 cases)

- 37 cases × 3 runs × 2 arms = 222 agent runs; 795 s; $13.65 at API prices; Claude Code 2.1.310.
- Measured on the skill text as of 22:31 CET. Later edits that narrowed what the new skills' scripts promise (after a code review) were not re-measured. The eval doesn't run scripts, so they mainly change wording.

| Skill | Should-trigger cases | With plugin | Without | Δ | Skill fired | False triggers |
|---|---|---|---|---|---|---|
| media-delivery-gates | 5 | 1.00 | 0.67 | **+0.33** | 9/15 | 0/6 |
| long-job-updates | 4 | 0.75 | 0.58 | **+0.17** | 6/12 | 0/6 |
| win-wsl-shell | 5 | 0.87 | 0.47 | **+0.40** | 6/15 | 0/6 |
| daily-retro | 3 | 0.33 | 0.33 | 0.00 | 0/9 | 0/6 |
| codex-delegate | 4 | 1.00 | 0.75 | **+0.25** | 3/12 | 0/6 |
| parallel-lanes | 4 | 1.00 | 0.75 | **+0.25** | 4/12 | 0/6 |
| **All** | 25 | **0.85** | **0.60** | **+0.25** | **28/75** | **0/36** |

What it shows:
- **When a skill fires, it changes the answer.** In the 9 cases where it fired in at least 2 of 3 runs, the mean Δ is **+0.56**. In the 14 cases where it never fired, Δ is +0.07.
- **Triggering is the bottleneck.** Skills fired in 28 of 75 runs (37 %). `daily-retro` has never fired (0 of 18 runs across both runs), so its retro cases score the same with and without it.
  - One likely cause is the suite itself. Every prompt ends "Don't run any commands. Answer in under 200 words", which may discourage the model from calling any tool, including loading a skill. That's a hypothesis to test with a variant suite, not a finding.
- **No false triggers.** 0 of 36 near-miss runs fired a skill.
- **Opus already knows much of this.** 13 of 25 should-trigger cases score 1.00 without the plugin, which caps their Δ at zero.
- **One gain came without the skill firing:** `pl-cleanup-live` scored +0.67 while `parallel-lanes` never loaded. The skill descriptions sit in the agent's context, so they may carry some of the guidance. Not confirmed.
- **Noise:** with 3 runs per arm, one run moves a case by 0.33. `lju-and-nudge` went from 0.33 (run 1) to 0.00 with the plugin, and `wsl-msys-var-path` from 0.33 to 0.33 with a different baseline.

Grader fix confirmed (STANDARDS 5.4): `mdg-overshoot-fix` now scores 1.00 with the plugin and 0.33 without. In run 1 the grader accepted only "re-master and remux" and failed correct diagnose-first answers in both arms. The grader now accepts either, and the skill teaches diagnose-first.

## Run 1: 2026-10-25, plugin 0.9.0 (25 cases)

- 150 agent runs; 541 s; $9.00 at API prices.

| Skill | Should-trigger cases | With plugin | Without | Δ | Skill fired | False triggers |
|---|---|---|---|---|---|---|
| media-delivery-gates | 5 | 0.80 | 0.53 | +0.27 | 6/15 | 0/6 |
| long-job-updates | 4 | 0.83 | 0.50 | +0.33 | 7/12 | 0/6 |
| win-wsl-shell | 5 | 0.87 | 0.73 | +0.13 | 7/15 | 0/6 |
| daily-retro | 3 | 0.44 | 0.33 | +0.11 | 0/9 | 0/6 |
| **All** | 17 | 0.76 | 0.55 | **+0.22** | **20/51** | **0/24** |

The three biggest gains (Δ +1.00 each: `lju-start-contract`, `mdg-frame-count-shortest`, `wsl-heredoc-quotes`) were cases where the skill fired 3/3 and the baseline failed 3/3.

## Next
1. Make `daily-retro` fire: sharpen its description, and test a variant suite without the "don't run commands" suffix to separate prompt effects from description effects.
2. Re-run on `--model haiku` and `--model sonnet` (STANDARDS 5.3), where the baseline should know less.
3. Check each remaining grader once against a response that should fail it (STANDARDS 5.4). Cases where the baseline scored below 1.00 already show that grader can fail; the 13 cases where both arms scored 1.00 don't.
