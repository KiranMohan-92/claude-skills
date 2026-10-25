# Changelog: media-delivery-gates

## 0.9.1 (2026-10-25)
- When the encoded true peak is over the limit, diagnose first: same meter on the master and the decoded file, compare loudness, and look for a gain stage before re-mastering.
  - In eval run 1, both the with-plugin and baseline answers did this and the old guidance didn't. A rise of more than about 1.5 dB is unusual for AAC alone.
- The matching eval grader now accepts either diagnosing first or re-mastering, and still fails encoder-flag tweaks.

## 0.9.0 (2026-10-25)
- First packaged release (pre-1.0: no scored eval run yet), generalised from a personal skill written on 2026-10-20 after a music-video delivery incident.
- `gate_deliverable.sh`: default loudness target is now −14 LUFS (streaming normalisation) instead of a project-specific −10; pass `--lufs` per destination.
- `contact_sheet.sh`: uses awk instead of Python for the frame maths, so it only needs ffmpeg.
- Hand-off steps no longer assume a particular sync drive.
- Covered by `tests/test_gate_deliverable.py` (a +0.6 dBTP AAC clip must fail, a clean clip must pass) and `tests/test_sheets.py`.
