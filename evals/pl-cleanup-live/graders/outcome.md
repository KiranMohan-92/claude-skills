---
type: llm
weight: 1
---

PASS only if the answer warns against blind rm -rf of worktrees and recommends checking that no running process (e.g. a server or test run) uses them, preserving uncommitted work, and removing them with git worktree remove (then prune) rather than rm.
