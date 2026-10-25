---
description: "outcome case for codex-delegate. Source: 2026-10-25: a 4,028-line line-ending diff was sent for review"
tags: [codex-delegate, outcome]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer identifies likely line-ending (CRLF/LF) churn or a whole-file rewrite, says not to send the diff as is, and recommends restoring the original line endings (..."
---

I want Codex to review my uncommitted changes. I only edited one line of report.html, but git diff --stat says 4,028 lines changed in that file. Shall I send it?

Don't run any commands. Answer in under 200 words: what you'd do and why.
