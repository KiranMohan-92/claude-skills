# Changelog: media-delivery-gates

## 0.9.0 (2026-10-25)
- First packaged release (pre-1.0: no scored eval run yet), generalised from a personal skill written on 2026-10-20 after a music-video delivery incident.
- `gate_deliverable.sh`: default loudness target is now −14 LUFS (streaming normalisation) instead of a project-specific −10; pass `--lufs` per destination.
- `contact_sheet.sh`: uses awk instead of Python for the frame maths, so it only needs ffmpeg.
- Hand-off steps no longer assume a particular sync drive.
- Covered by `tests/test_gate_deliverable.py` (a +0.6 dBTP AAC clip must fail, a clean clip must pass) and `tests/test_sheets.py`.
