---
description: "trigger case for long-job-updates. Source: 2026-10-20 retro: the user chased status 10 times in one session"
tags: [long-job-updates, trigger]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer gives an up-front plan with: the steps, an ETA based on the measured ~12 min/clip (about 72 min total, ideally a clock finish time), when the user will next..."
---

Kick off the 4K upscale of 6 clips in the background. Last run took about 12 minutes per clip. Before you start, tell me how this will go.

Don't run any commands. Answer in under 200 words: what you'd do and why.
