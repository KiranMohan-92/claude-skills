---
type: llm
weight: 1
---

PASS only if the answer says no: an empty result is a failed review run, not a clean one, and the run must be investigated (its log, exit status) and re-run before merging. FAIL if it treats the empty file as 'no findings'.
