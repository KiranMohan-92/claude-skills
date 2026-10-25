# Skill standards

A rubric another engineer can apply to any Claude Code skill, in this repo or elsewhere. It combines Anthropic's published guidance (the skill-creator skill, plugin-dev's skill-development guide, and the Agent Skills best-practices page) with the rules this repo's skills had to learn the hard way.

Each criterion says **how it's checked**:
- **CI**: a script fails the build (`tests/test_structure.py`, `quick_validate.py`, `claude plugin validate`, shellcheck).
- **Eval**: measured by `claude plugin eval`.
- **Review**: a person reads for it. Use the questions given.

Grade each criterion A (strong), B (adequate), C (weak) or D (absent). A skill ships at B or better on every criterion marked *required*.

## 1. Purpose and evidence

| # | Criterion | Required | Check |
|---|---|---|---|
| 1.1 | **Born from evidence.** The skill opens with the failure or friction it prevents, measured where possible ("a +0.6 dBTP file was nearly delivered"; "13% of messages were status chases"). | yes | Review: can you name the incident, and would the skill have stopped it? |
| 1.2 | **One job.** It does one coherent workflow and nothing it doesn't announce. | yes | Review: does any step surprise you, given the description? |
| 1.3 | **Not a duplicate.** No existing skill already covers it; overlaps are merged or cross-referenced. | yes | Review: list skills with overlapping triggers. |

## 2. Triggering

| # | Criterion | Required | Check |
|---|---|---|---|
| 2.1 | **Valid frontmatter.** `name` is kebab-case, ≤64 characters, equal to the folder name; `description` ≤1,024 characters, no angle brackets. | yes | CI |
| 2.2 | **The description is the trigger.** Third person; says what the skill does and when to use it; includes phrases users actually say ("and?", "show me progress"). | yes | Review, then Eval |
| 2.3 | **Trigger evals with near-misses.** At least 3 should-trigger and 2 should-not-trigger cases per skill, the negatives being near-misses (same vocabulary, different need). | yes | CI counts cases; Eval measures false triggers (`tool_used: Skill`, `min: 0`, `max: 0`, `arm: both`) |

## 3. Body and structure

| # | Criterion | Required | Check |
|---|---|---|---|
| 3.1 | **Lean body.** Under 500 lines; detail goes into `scripts/` or `references/`, one level deep. | yes | CI (line count) |
| 3.2 | **Explains why.** Rules carry their reason; prefer reasons to capitalised MUSTs. | yes | Review: pick three rules; is the reason stated? |
| 3.3 | **Gotchas section.** The traps that cost time, each specific enough to act on. | yes | CI (heading present), Review (content) |
| 3.4 | **Portable.** Forward slashes, no personal paths or names, no time-sensitive text, dependencies declared in `compatibility`. | yes | CI (banned-pattern scan, `compatibility` present) |

## 4. Scripts

| # | Criterion | Required | Check |
|---|---|---|---|
| 4.1 | **Scripts for fragile steps.** Anything with quoting, parsing or thresholds lives in a script, not in prose. A skill made only of rules for the agent to follow (e.g. how to call shells) is exempt, and says so in its README entry. | yes | Review |
| 4.2 | **Self-checking exit codes.** A script that judges something exits non-zero on failure and prints why (e.g. `0` pass, `1` fail, `2` usage). | yes | CI (tests assert the codes) |
| 4.3 | **Tested, including the incident.** Each script has tests, and at least one test reproduces the original failure (the +0.6 dBTP clip must fail; a finished job must not look like it's still running). Each such test is checked once by breaking the code and confirming the test fails. | yes | CI (pytest), Review (mutation check) |
| 4.4 | **Lint clean.** Shell passes `shellcheck -S warning`; no unexplained constants. | yes | CI |
| 4.5 | **Every referenced script exists.** | yes | CI |

## 5. Outcomes

| # | Criterion | Required | Check |
|---|---|---|---|
| 5.1 | **Outcome evals.** At least 2 cases per skill where an LLM grader checks the behaviour the skill should produce, scored in both arms. | yes | Eval |
| 5.2 | **Measured against a baseline.** Run with and without the plugin; report the delta per skill, not just a pass rate. | before 1.0.0, then every minor release | Eval (`--ablation with-without`) |
| 5.3 | **Across models.** Run the suite on Haiku, Sonnet and Opus before a minor release; note where a model needs the skill most. | recommended | Eval (`--model`) |
| 5.4 | **Graders that can fail.** Each grader is checked once against a response that should fail it. | before 1.0.0 | Review |

## 6. Versioning and release

| # | Criterion | Required | Check |
|---|---|---|---|
| 6.1 | **Semantic versions.** Each skill has `metadata.version`; the plugin has `version` in `plugin.json` only (not duplicated in the marketplace entry). | yes | CI |
| 6.2 | **Changelog per skill.** The top entry matches the current version and says what changed and why. | yes | CI (version match), Review (content) |
| 6.3 | **Version bumps.** Patch: wording or bug fix with no trigger change. Minor: new steps, scripts or trigger phrases. Major: a removed step, renamed script or changed exit code. | yes | Review |
| 6.4 | **Pinned consumers.** Teams install from a tag or commit SHA (see README), never a moving branch. | yes | Review of the consumer's settings |

## 7. Safety

| # | Criterion | Required | Check |
|---|---|---|---|
| 7.1 | **No secrets, no personal data** in skills, scripts, evals or test fixtures. | yes | CI (credential patterns across every text file; personal paths and names across skills, evals and tests), Review |
| 7.2 | **Destructive steps are gated.** Deleting, overwriting or publishing needs a verified copy or the user's confirmation, stated in the skill. | yes | Review |
| 7.3 | **No self-editing of guardrails.** A skill never edits gate scripts, thresholds, permissions or hooks; it flags them for a person. | yes | Review |

## How to review a skill in 15 minutes
1. Read the description cold and write down three prompts you'd expect to trigger it and one you wouldn't. Compare with its eval cases.
2. Read the opening incident. Would the steps below it have prevented it?
3. Run the tests; break the threshold or the parser once and confirm a test fails.
4. Grade sections 1–7 and file a short note: grade per criterion, required ones below B, and the one change that would raise the skill most.
