---
type: llm
weight: 1
---

PASS only if the answer does not conclude the scene is broken from this evidence, explains that reading or screenshotting a WebGL canvas directly can come back empty or black in headless Chromium, and recommends judging the scene from the composited page (a page screenshot of the canvas area) or first confirming that headless browser has WebGL at all. FAIL if it tells the user to debug the shaders or the scene first.
