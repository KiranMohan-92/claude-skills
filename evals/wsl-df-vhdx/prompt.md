---
description: "outcome case for win-wsl-shell. Source: 2026-10-16: fresh render died ENOSPC on C: although output went to WSL"
tags: [win-wsl-shell, outcome]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer says no (or not necessarily): WSL's disk is a .vhdx file stored on a Windows drive (C: by default), df shows the virtual disk's size rather than physical fr..."
---

WSL's df says I have 900 GB free, so I'll write 60 GB of render intermediates inside WSL even though Windows C: is nearly full. That avoids the C: problem, right?

Don't run any commands. Answer in under 200 words: what you'd do and why.
