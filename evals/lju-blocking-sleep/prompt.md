---
description: "outcome case for long-job-updates. Source: 2026-10-20: blocked sleeps and fixed waits during long renders"
tags: [long-job-updates, outcome]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer advises against one long blocking sleep, and suggests running the job in the background with bounded, repeated waits (a wait-until-done helper or monitor) t..."
---

The render will take about 40 minutes. I'll just run `sleep 2400; tail render.log` in one tool call and check at the end. OK?

Don't run any commands. Answer in under 200 words: what you'd do and why.
