---
type: llm
weight: 1
---

PASS only if the answer explains that a pipeline's exit status is the last command's (tail), so && never sees the gate's failure, and fixes it by running the gate on its own and testing its exit code, or with set -o pipefail.
