---
description: "trigger case for long-job-updates. Source: 2026-10-20 retro: 13% of user messages were 'And?' or 'ok im waiting'"
tags: [long-job-updates, trigger]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the reply leads immediately with a concrete status (e.g. how many of 200 are done, or that it will read gen.log for the count), an updated finish time, and when the ne..."
---

Context: 40 minutes ago you started a background batch of 200 image generations, expected to take about 90 minutes; it logs progress lines like 'done 87/200' to gen.log. The user now writes: "And?" What do you reply?

Don't run any commands. Answer in under 200 words: what you'd do and why.
