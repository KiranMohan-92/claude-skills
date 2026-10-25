---
description: "outcome case for media-delivery-gates. Source: 2026-10-20: -shortest trims the final frame to the audio"
tags: [media-delivery-gates, outcome]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer says one frame fewer is expected and acceptable with -shortest (it trims the last frame to the audio length) and should be noted in the report rather than t..."
---

The edit decision list totals 4,800 frames. The gate on the final encode reports 4,799 frames. I encoded with ffmpeg -shortest. Is this a failed delivery?

Don't run any commands. Answer in under 200 words: what you'd do and why.
