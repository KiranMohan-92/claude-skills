---
name: long-job-updates
description: Keeps the user informed during any job that runs longer than about 5 minutes (renders, upscales, training runs, generation batches, uploads, long test suites, scrapes). Use when starting a background command or a multi-step pipeline whose end is more than a few minutes away, and whenever the user asks "and?", "any update?", "still waiting" or "show me progress". Covers the up-front ETA contract, the check-in cadence, visible progress proof, and bounded waiting without blocked sleeps.
license: MIT
compatibility: waitfor.sh needs bash and /proc (Linux or WSL). progress_sheet.sh needs ffmpeg.
metadata:
  version: 0.9.0
---

# Long-job updates

In one measured session the user had to chase status 10 times; 13% of their messages were "And?" or "ok I'm waiting". It was the most common friction across all sessions. The fix is a contract stated before the job starts and kept without being asked.

## 1. Before starting: state the contract (one short block)
- **What runs:** the steps in order, e.g. "upscale 6 clips → preflight → 4K render (5 chunks) → 1080p → gates → upload".
- **ETA per step** and an overall finish time on the user's clock, not just "about an hour". Base it on measured rates from the last run (frames/s, MB/min, items/min), and say it's an estimate.
- **When they'll hear from you:** "a progress shot at about 22:40, and again when the 4K is stitched". Then keep it.
- **What could fail** and what you'll do then ("if a clip fails the gate I redo that clip, about 5 min").

## 2. While it runs
- Run the job as a harness-tracked background task. A job started with `&` inside a one-off shell can die with that shell.
- **Write results incrementally** and log progress. A batch that saves only at the end hides a stall and loses everything on a kill.
- **Check-in cadence:** every 15–20 min, or at each step boundary, whichever comes first. Each check-in is 1–2 lines: step done, step running, % or measured rate, updated finish time.
- **Show, don't tell:** at least once per long job, send visual or concrete proof: a contact sheet of fresh output (`scripts/progress_sheet.sh`), a still, a sample of rows.
- **If an ETA slips by more than 25%**, give the new time and the reason before the user notices.

## 3. Waiting correctly
- Don't `sleep N; check` in a tool call. Many harnesses block long sleeps, and a fixed sleep either wastes time or misses the event.
- Use `scripts/waitfor.sh` (in this skill's folder). It returns within about 9.5 minutes, when a process is gone, a file appears or a log line matches, and prints a status line. Call it repeatedly; each call is a check-in opportunity.
  ```bash
  bash scripts/waitfor.sh --gone render_v5.sh --status "tail -2 render.log"
  ```
- `waitfor.sh` brackets the pattern (`[r]ender…`) and skips its own ancestors, so `pgrep -f` can't match the waiting command itself. That self-match once made a finished job look like it was running forever.
- Before an overnight job, keep the machine awake if the harness offers a way to, and say whether it must stay on mains power.

## 4. When it finishes
- Lead with the result and where it is, then the gate numbers, then anything not done or not verified.
- If the user went to sleep, the morning message must stand alone: what's ready, where, what changed overnight and why, and decisions waiting for them.

## Gotchas
- A background-task notification isn't a user message; never treat it as approval.
- Long nested-quote one-liners into another shell break often. Put multi-step checks in a script file (see the `win-wsl-shell` skill).
- Don't promise a time you can't measure. "The first chunk took 70 min with 5 in parallel" beats "about an hour".
