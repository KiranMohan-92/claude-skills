---
description: "outcome case for page-delivery-gates. Source: 2026-10-20: the scene kept moving with reduced motion on"
tags: [page-delivery-gates, outcome]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer says it is not ready: with reduced motion on, the page should hold still when nobody is scrolling, so the ambient loop must stop (for example by rendering o..."
---

Our scroll-driven 3D page respects prefers-reduced-motion: a media query turns off the scroll-triggered fade-ins. The starfield still drifts and the camera keeps a slow idle orbit, which I think is fine because it's subtle. Is the reduced-motion view ready to ship?

Don't run any commands. Answer in under 200 words: what you'd do and why.
