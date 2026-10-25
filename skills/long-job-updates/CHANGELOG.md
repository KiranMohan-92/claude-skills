# Changelog: long-job-updates

## 0.9.0 (2026-10-25)
- First packaged release (pre-1.0: no scored eval run yet), generalised from a personal skill written on 2026-10-20 after a session where the user chased status 10 times.
- Adds "write results incrementally" after a scrape that saved only at the end stalled invisibly.
- `waitfor.sh` and `progress_sheet.sh` covered by `tests/test_waitfor.py` and `tests/test_sheets.py`, including the self-match case that once made a finished job look like it was still running.
