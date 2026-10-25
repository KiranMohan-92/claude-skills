---
type: llm
weight: 1
---

PASS only if the plan writes results incrementally (not only at the end), reports progress while running, caps retries or backs off on rate-limit errors, and tests the parser on one known item before the full batch. At least three of these four must be explicit.
