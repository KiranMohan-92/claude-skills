---
description: "trigger case for win-wsl-shell. Source: 2026-10-25: `sed -i` in Git Bash rewrote a CRLF file's line endings"
tags: [win-wsl-shell, trigger]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer warns that sed -i in Git Bash can rewrite the file's CRLF line endings so the diff shows every line changed, and recommends a newline-preserving edit (an ed..."
---

On my Windows checkout I want to change one line in backend/templates/report.html with sed -i from Git Bash, then send the git diff to a reviewer. Any risk?

Don't run any commands. Answer in under 200 words: what you'd do and why.
