---
type: llm
weight: 1
---

PASS only if the answer says not to write 'verified' for views that were never loaded, and says either to load them (emulate prefers-reduced-motion; refuse or disable WebGL) and check that all the text is visible with no uncaught error, or to list them as not verified. It should give a reason HTML text can still fail to show, such as a reveal animation leaving it at opacity 0 or a script that dies when the WebGL context is refused. FAIL if it accepts 'verified' by inspection.
