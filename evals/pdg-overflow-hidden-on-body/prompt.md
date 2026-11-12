---
description: "outcome case for page-delivery-gates. Source: 2026-10-27: the phone-width overflow was fixed by clipping the panel; measured since: overflow-x hidden on body alone leaves the page 40px too wide and still scrollable"
tags: [page-delivery-gates, outcome]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer says overflow-x: hidden on body alone is not a reliable fix (the page can still be wider than the viewport and still scroll sideways), recommends clipping o..."
---

At 390 px my page scrolls sideways by a few pixels halfway down, when some decorative stamps animate in from the right. I fixed it by adding overflow-x: hidden to body. Done?

Don't run any commands. Answer in under 200 words: what you'd do and why.
