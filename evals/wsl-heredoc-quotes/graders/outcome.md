---
type: llm
weight: 1
---

PASS only if the answer recommends writing the script to a file with a file-writing tool (not a shell heredoc) and then running the file, explaining that the heredoc passes through the tool's own quoting so quote sequences can end it early or truncate it.
