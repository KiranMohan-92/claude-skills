---
type: llm
weight: 1
---

PASS only if the answer recognises the three tasks are tightly coupled (they touch the same type and files, and depend on each other's output) and recommends NOT running them as three independent parallel lanes: do it in one lane or one loop, or in sequence with explicit ownership. FAIL if it simply launches three parallel lanes as asked.
