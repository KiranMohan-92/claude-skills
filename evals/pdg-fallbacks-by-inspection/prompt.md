---
description: "trigger case for page-delivery-gates. Source: 2026-10-21: a 3D page was handed over with its reduced-motion and no-WebGL views never rendered"
tags: [page-delivery-gates, trigger]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer says not to write 'verified' for views that were never loaded, and says either to load them (emulate prefers-reduced-motion; refuse or disable WebGL) and ch..."
---

I'm writing the hand-off note for our 3D explainer page. I didn't render the reduced-motion path or the no-WebGL fallback, but all the text is plain HTML in both, so the content should still show. I'll write 'fallbacks verified'. OK?

Don't run any commands. Answer in under 200 words: what you'd do and why.
