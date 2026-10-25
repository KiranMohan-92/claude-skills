---
description: "outcome case for media-delivery-gates. Source: 2026-10-20: AAC overshoot 3 dB over the WAV; encoder flags were unreliable fixes"
tags: [media-delivery-gates, outcome]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer steers away from encoder-flag tweaking as the main fix and recommends re-mastering the audio with a lower ceiling (around -3 dBTP or lower) and remuxing wit..."
---

My gate says the encoded MP4 has a true peak of +0.6 dBTP, but the WAV master peaks at -2.4. I'm planning to fix it by changing the AAC encoder's cutoff and bitrate. Good plan?

Don't run any commands. Answer in under 200 words: what you'd do and why.
