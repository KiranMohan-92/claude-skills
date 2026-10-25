---
description: "trigger case for media-delivery-gates. Source: 2026-10-20: encoded MP4 measured +0.6 dBTP (WAV master at -2.4); nearly delivered"
tags: [media-delivery-gates, trigger]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer refuses to call the file ready yet, says the gate must run on the ENCODED final.mp4 rather than the WAV master (AAC encoding can push true peak above the WA..."
---

I re-mastered the WAV so it peaks at -2.4 dBTP and rendered final.mp4 with AAC 320k. My render script normally runs a loudness gate at the end, but it stopped early when I killed the optional phone-size encode. The WAV is fine, so can I upload final.mp4 to YouTube now?

Don't run any commands. Answer in under 200 words: what you'd do and why.
