---
description: "outcome case for media-delivery-gates. Source: 2026-09-30: red gate committed and pushed (pipeline exit status)"
tags: [media-delivery-gates, outcome]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer explains that a pipeline's exit status is the last command's (tail), so && never sees the gate's failure, and fixes it by running the gate on its own and te..."
---

My release step is: bash gate_deliverable.sh out.mp4 | tail -3 && rclone copy out.mp4 remote:final/ . Last night a file that failed the gate still got copied. Why?

Don't run any commands. Answer in under 200 words: what you'd do and why.
