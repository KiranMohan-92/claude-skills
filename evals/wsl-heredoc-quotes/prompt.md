---
description: "outcome case for win-wsl-shell. Source: 2026-10-03: bash heredocs with quote sequences broke patch scripts"
tags: [win-wsl-shell, outcome]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer recommends writing the script to a file with a file-writing tool (not a shell heredoc) and then running the file, explaining that the heredoc passes through..."
---

I want one Bash tool call that writes a Python patch script via a heredoc (the script has ''' docstrings and f-strings with nested quotes) and then runs it in WSL. How should I do it?

Don't run any commands. Answer in under 200 words: what you'd do and why.
