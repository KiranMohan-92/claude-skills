---
type: llm
weight: 1
---

PASS only if the answer identifies that $B arrived empty because of the quoting or Git Bash (MSYS) argument handling between Git Bash and wsl.exe, AND that the later ';'-separated commands still ran in the wrong directory because only the cd was guarded. It should suggest a script file run inside WSL (or MSYS_NO_PATHCONV=1) and making a failed cd stop the script.
