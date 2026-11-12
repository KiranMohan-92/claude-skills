---
description: "trigger case for page-delivery-gates. Source: 2026-10-27: a phone-width page was 394px wide in a 390px view, only while stamps animated in mid-page"
tags: [page-delivery-gates, trigger]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer does not call the page ready on that evidence, and names concrete checks still to run: sideways overflow at phone width at several scroll positions or while..."
---

I finished the landing page: index.html, a three.js scene behind scrolling sections. It looks right in my desktop browser, and at phone width there's no horizontal scrollbar at the top of the page. Can I tell the client it's ready and deploy it?

Don't run any commands. Answer in under 200 words: what you'd do and why.
