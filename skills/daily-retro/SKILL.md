---
name: daily-retro
description: Runs a self-improvement retro over Claude Code session transcripts. Finds where the user struggled, how either side could have done better, and which skills, rules or memories would make tomorrow's setup better, then drafts those improvements for review. Use when the user asks for a retro, a session review, "what went wrong", "how could we do better", "build skills from this session", or at the end of a long working day.
license: MIT
compatibility: Needs Python 3.9+. Reads Claude Code transcripts from ~/.claude/projects.
metadata:
  version: 0.9.1
---

# Daily retro

Two costs went unnoticed until someone read the transcripts back. In one session the user chased status 10 times (13% of their messages), the most common friction across all sessions. In one session about a third of 36 tool errors were shell plumbing, not real work. The retro that found them produced the `long-job-updates` and `win-wsl-shell` skills.

Goal: every day starts from a better setup than the last. The evidence comes from the transcript, not from memory of the session.

## 1. Mine
```bash
python -I scripts/mine_transcript.py --since 24 --out retro_digest.md
```
(`scripts/` is in this skill's folder; write the digest to a scratch location.)
- By default it reads every transcript modified in the last 24 h across `~/.claude/projects`. Pass `--project-dir` for one project, or `.jsonl` paths for specific sessions.
- The digest has stats, status nudges (the user chasing progress), corrections, interrupts, tool-error signatures and every user message.
- Read the whole digest. For anything unclear, search the transcript around that timestamp. Don't guess.

## 2. Diagnose both sides, by cause
For each friction point:
- **What happened:** timestamp, short quote, cost (time, credits, a redo).
- **Cause:** a mechanism, not the symptom. Cluster points with one cause: ten "And?" messages are one cause (no update contract).
- **Better for the user:** something concrete, e.g. give references before generation, say "remove X" rather than "unless…", keep enough disk free.
- **Better for Claude:** a concrete behaviour change.

## 3. Choose one home for each fix
- **A skill** (new or sharpened): a repeatable workflow with steps, scripts or gotchas. Check existing skills first and sharpen one before adding a near-duplicate.
- **A one-line rule:** project `CLAUDE.md` or memory.
- **A failure log** (if the project keeps one): gate failures in a "what the check saw / mechanism / reusable pattern" format, append-only.
- **Never edit gate scripts, thresholds, permissions or hooks yourself.** Flag them for the user.

## 4. Build drafts the user can review
- Each new or updated skill has:
  - a `name` and a trigger-precise `description` (what it does, when to use it, phrases the user actually says);
  - steps, scripts that were actually run once, and a Gotchas section.
- Test every script: Python gets a pytest file; shell scripts run once on real data and the output is checked.
- Write `RETRO-YYYY-MM-DD.md`: the diagnosis, each skill (path, one-line purpose, evidence), the rules proposed, and open questions.

## 5. Hand off
- In chat: the top three struggles (one line each), the skills built (name → what it prevents), the rules proposed.
- Ask which skills to keep, change or drop. Personal skills go live as soon as they're written, so say so and how to disable one.

## Gotchas
- Transcripts get big (150 MB for a multi-day session). Use the miner; never read the `.jsonl` whole.
- Task notifications, continuation summaries, agent-to-agent messages and SDK-launched runs (e.g. automated security reviews) all appear as "user" events. The miner skips them, and skips a session made only of automated prompts whole. Any hand-rolled search must do the same: keep a prompt when its `turnOrigin` is `human`. Older transcripts have no `turnOrigin`; keep those prompts unless the entrypoint starts with `sdk` or the event is a sidechain. Before this rule, one project's digest counted 55 automated review prompts as user messages, 17 of them as "corrections".
- Quote the user sparingly and accurately. Never copy secrets that appear in transcripts; refer to them as "a key pasted in chat".
