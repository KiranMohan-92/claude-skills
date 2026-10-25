---
name: media-delivery-gates
description: Final gates for a rendered video deliverable with an audio track (music videos, explainers, trailers, ads). Use before saying a render is done, before uploading or copying it anywhere, and after any re-render, remux or audio change. Gates the ENCODED file, not the master (both streams decode cleanly, frame count, A/V sync, integrated loudness, true peak after AAC), then runs a timestamped contact-sheet review of the changed sections and checks disk space before the hand-off. Not for audio-only files.
license: MIT
compatibility: Needs bash, ffmpeg and ffprobe (Linux, macOS or WSL). contact_sheet.sh uses awk only.
metadata:
  version: 0.9.0
---

# Media delivery gates

This skill exists because of two real failures:
- **A +0.6 dBTP file was nearly delivered.** The WAV master peaked at −2.4 dBTP, but the AAC-encoded MP4 measured +0.6 dBTP; a manual check caught it before hand-off. The render script's own true-peak gate never ran: stopping an optional encode ended the script under `set -e` before reaching the gate.
- **A continuity error (a character leaping twice) was caught only by a manual review** after the full render, when it could have been caught on the changed section alone.

So: gate the file the viewer will actually get, and treat a skipped step as a skipped gate.

## 1. Technical gate on the final encoded file
```bash
bash scripts/gate_deliverable.sh <file.mp4> [--frames N] [--lufs -14] [--lufs-tol 1.0] [--max-tp -1.0] [--sync-tol 0.1]
```
(`scripts/` is in this skill's folder.) It decodes every packet of both streams (metadata can look fine while the video data is corrupt), prints resolution, fps, frame count, stream starts and durations, integrated loudness and true peak, then exits 0 (PASS), 1 (FAIL, each failure printed) or 2 (usage). When a container stores no stream durations (e.g. Matroska), it measures them from the packets; a value it can't measure is a failure, never an assumed zero.
- **Loudness target:** pick it per destination and say which. −14 LUFS is the default (common streaming normalisation); music masters are often louder on purpose, so pass `--lufs` explicitly.
- **Expected frames:** the edit's total. One frame fewer is accepted and reported, because `-shortest` trims the last frame to the audio.
- **True peak above −1.0 dBTP after AAC:** re-master with a lower ceiling (−3.0 dBTP on the WAV left headroom in the incident above) and remux with `-c:v copy`. Encoder flags (cutoff, coder, bitrate) were unreliable fixes, because the overshoot depends on the content.
- **If any step in the pipeline was skipped, killed or failed**, assume every gate after it was skipped too, and run this gate by hand.

## 2. Visual review: changed sections densely, the whole piece sparsely
```bash
bash scripts/contact_sheet.sh <video> <out.jpg> <start_s> <end_s> <step_s> [cols]
```
- Sample each section changed in this version at 0.2–0.33 s steps, and the whole piece at about 4 s. Read every sheet.
- Write one line per item for each changed section:
  - **Continuity:** no repeated action, no position jump across a cut, cause before effect.
  - **Anatomy** (generated people): proportions, hands and fingers, limb count, consistent faces.
  - **Timing:** hits land on the planned beat or word.
  - **Text:** in sync, legible, nothing cut off.
  - **Artefacts:** black frames, colour noise, banding, flicker.
- Fix a defect found here before delivery. Re-render only the affected chunk when the pipeline allows it.

## 3. Space and hand-off
- Check free space on the disk that really holds the file. On Windows with WSL, the WSL virtual disk and most sync-drive caches live on `C:`, so a Linux `df` overstates what's free. Need: deliverable size × 2 + 2 GB.
- If space is short, delete only files with a verified identical copy elsewhere: same SHA-256 (`sha256sum`, or `Get-FileHash` on Windows). Equal byte size alone isn't proof. Say what was removed and where the copies are.
- After copying to a sync drive or upload target, confirm the remote copy: byte size at least, plus the provider's checksum when it exposes one (many cloud drives report an MD5). Don't delete the local file on size alone.
- The final message gives: where the file is, the gate numbers, what changed, what was removed to make space, and what isn't verified.

## Gotchas
- `drawtext` with `%{pts\:hms}` breaks inside nested shell quotes. `contact_sheet.sh` keeps the filter in the script for that reason.
- ffprobe's CSV field order isn't the `-show_entries` order. The gate parses `key=value` output instead, after a mis-parse failed a good file.
- A gate inside a filtered pipeline (`gate | grep … && next`) tests `grep`'s exit status, not the gate's. Run the gate on its own and test its exit code.
