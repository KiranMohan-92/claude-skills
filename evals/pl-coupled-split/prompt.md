---
description: "trigger case for parallel-lanes. Source: 2026-09-30: merged lanes broke each other with no textual conflict (shared types and wire bits)"
tags: [parallel-lanes, trigger]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer recognises the three tasks are tightly coupled (they touch the same type and files, and depend on each other's output) and recommends NOT running them as th..."
---

Use swarms: spin up three parallel lanes. Lane 1 renames the PlayerState type to Avatar across the codebase, lane 2 updates the netcode that serialises PlayerState, and lane 3 fixes the UI labels that read its fields. How would you set this up?

Don't run any commands. Answer in under 200 words: what you'd do and why.
