---
type: llm
weight: 1
---

PASS only if the answer explains that a job started with a plain background & inside a wsl.exe call can die when that call returns, that counting processes doesn't prove a job is alive or productive, and recommends a detached launch (setsid/nohup/disown or equivalent) tracked by its own PID plus a non-empty result file. Checking network or connectivity from inside WSL first is a plus.
