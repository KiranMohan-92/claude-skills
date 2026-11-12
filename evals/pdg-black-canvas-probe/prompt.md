---
description: "outcome case for page-delivery-gates. Source: 2026-08-07: a pixel probe that screenshotted the canvas element read black in headless Chromium and failed a working scene"
tags: [page-delivery-gates, outcome]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer does not conclude the scene is broken from this evidence, explains that reading or screenshotting a WebGL canvas directly can come back empty or black in he..."
---

My Playwright check screenshots the canvas element of our WebGL hero and fails the build because every pixel is black. The page looks fine when I open it in Chrome. The check runs in headless Chromium on CI. Is the scene broken, and how should I check it instead?

Don't run any commands. Answer in under 200 words: what you'd do and why.
