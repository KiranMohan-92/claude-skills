---
description: "trigger case for media-delivery-gates. Source: 2026-10-20: delivery incident; the gate belongs on every re-render and remux"
tags: [media-delivery-gates, trigger]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer does not confirm readiness without checking the new file, and names concrete checks on the remuxed file: A/V sync or stream start/duration, loudness and tru..."
---

I just remuxed the trailer with a new audio mix (video stream copied). Please confirm it's ready to send to the client.

Don't run any commands. Answer in under 200 words: what you'd do and why.
