---
description: "trigger case for win-wsl-shell. Source: 2026-10-20: a wait loop matched its own command line"
tags: [win-wsl-shell, trigger]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer explains that pgrep -f matches the waiting shell's own command line (which contains render_v5.sh), and fixes it with the bracket trick (pgrep -f '[r]ender_v..."
---

Inside WSL I wait for a render with: bash -c 'while pgrep -f render_v5.sh; do sleep 5; done; echo done'. The render finished ten minutes ago but the loop never ends. Why?

Don't run any commands. Answer in under 200 words: what you'd do and why.
