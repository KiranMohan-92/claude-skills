---
description: "outcome case for long-job-updates. Source: 2026-10-24: description scrape stalled with no output after ~25 min"
tags: [long-job-updates, outcome]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the plan writes results incrementally (not only at the end), reports progress while running, caps retries or backs off on rate-limit errors, and tests the parser on on..."
---

Plan a script that fetches 212 job descriptions from a rate-limited site, 2.5 s apart, and saves the results. It will run in the background for about 10 minutes.

Don't run any commands. Answer in under 200 words: what you'd do and why.
