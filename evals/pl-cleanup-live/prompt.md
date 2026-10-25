---
description: "outcome case for parallel-lanes. Source: 2026-10-02: worktree cleanup deleted part of a live host's tree"
tags: [parallel-lanes, outcome]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer warns against blind rm -rf of worktrees and recommends checking that no running process (e.g. a server or test run) uses them, preserving uncommitted work, ..."
---

Disk is nearly full, so I'm going to run rm -rf .claude/worktrees/* to free space. Any problem?

Don't run any commands. Answer in under 200 words: what you'd do and why.
