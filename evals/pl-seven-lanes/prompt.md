---
description: "trigger case for parallel-lanes. Source: 2026-09-26/30, 10-01/02: gates OOM with 5-7 lanes; disk fell to ~450 MB"
tags: [parallel-lanes, trigger]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer checks the machine before launching: it flags that seven lanes each running the full suite will likely exhaust RAM and disk, and proposes a cap (fewer concu..."
---

Do these seven independent refactors in parallel: one git worktree lane each, and every lane runs the full test suite when it's done. My laptop has 16 GB of RAM and 6 GB of free disk. Go.

Don't run any commands. Answer in under 200 words: what you'd do and why.
