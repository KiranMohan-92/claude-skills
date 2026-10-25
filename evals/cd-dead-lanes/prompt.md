---
description: "trigger case for codex-delegate. Source: 2026-10-15: three Codex lanes died at launch while a process-count watcher reported them running"
tags: [codex-delegate, trigger]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer explains that a job started with a plain background & inside a wsl.exe call can die when that call returns, that counting processes doesn't prove a job is a..."
---

From Git Bash on Windows I launched three Codex implementation lanes with wsl -e bash -lc 'nohup codex exec ... &'. My watcher counts codex processes and says they're running, but no files have changed in an hour. What's going on, and how should I launch and track Codex jobs?

Don't run any commands. Answer in under 200 words: what you'd do and why.
