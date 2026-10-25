---
description: "trigger case for win-wsl-shell. Source: 2026-10-24: Git Bash to WSL `VAR=/path` argument mangled"
tags: [win-wsl-shell, trigger]
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
expected_outcome: "PASS only if the answer identifies that $B arrived empty because of the quoting or Git Bash (MSYS) argument handling between Git Bash and wsl.exe, AND that the later ';'-separated ..."
---

From the Git Bash tool on Windows I ran: wsl -d Ubuntu -- bash -lc 'B="/mnt/c/work/paper"; cd "$B/latex" && pdflatex main.tex; ls' and got 'cd: /latex: No such file or directory'. Then pdflatex wrote texput.log into my current Windows folder. What went wrong?

Don't run any commands. Answer in under 200 words: what you'd do and why.
