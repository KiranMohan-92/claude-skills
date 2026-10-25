---
type: llm
weight: 1
---

PASS only if the answer identifies likely line-ending (CRLF/LF) churn or a whole-file rewrite, says not to send the diff as is, and recommends restoring the original line endings (or checking with an ignore-CR diff) so the review sees only the real one-line change.
