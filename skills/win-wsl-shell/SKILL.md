---
name: win-wsl-shell
description: Runs commands reliably across Windows shells (Git Bash, PowerShell) and WSL without quoting, path, line-ending or wait failures. Use whenever a command crosses into WSL (wsl -d …), passes JSON to a CLI (gh api, curl), contains heredocs, nested quotes or ffmpeg filter escapes, edits files on a Windows checkout with sed or Python, or waits on or kills background processes.
license: MIT
compatibility: For Windows 10/11 with WSL 2 and the Git Bash or PowerShell tools. Examples use a distro named Ubuntu; substitute yours (wsl -l -v lists them).
metadata:
  version: 0.9.0
---

# Windows ↔ WSL shell bridge

About a third of one session's 36 tool errors were shell plumbing, not real work. Each rule below comes from a logged failure.

## The one rule: multi-step or quote-heavy → script file
If a command has more than one level of quotes, a heredoc, an ffmpeg filter with `\:`, Python with f-strings, or more than about 3 steps, **write it to a file first and run the file.**
- Write the file with the file-writing tool, not a shell heredoc: the heredoc body passes through the tool's own quoting first, and quote sequences like `'''` end it early or truncate it.
- Run it from Git Bash with the WSL path **inside** the quotes: `wsl -d Ubuntu -e bash -lc 'bash /mnt/c/path/to/x.sh'`.
- Make a failed `cd` stop the script (`set -e`, or `cd dir || exit 1`). A guarded `cd` followed by `;` still runs the rest in the wrong directory.

## Git Bash rewrites POSIX-looking arguments
MSYS path conversion rewrites arguments that look like POSIX paths when it calls a native `.exe` such as `wsl.exe`:
- A bare `/mnt/c/...` argument becomes `C:/Program Files/Git/mnt/c/...` (exit 127).
- `VAR=/some/path` passed as an argument arrives mangled or empty.

Fix: keep paths inside the `bash -lc '…'` string, or set `MSYS_NO_PATHCONV=1` for that call.

## Paths
| From | Windows file | WSL file |
|---|---|---|
| Git Bash | `/c/Users/<you>/...` | `wsl -d Ubuntu -e bash -lc '... ~/...'` |
| PowerShell | `C:\Users\<you>\...` | `\\wsl.localhost\Ubuntu\home\<user>\...` |
| inside WSL | `/mnt/c/Users/<you>/...` | `~/...` |

Paths with spaces need quotes at every layer.

## Line endings
- Scripts saved on Windows can carry CRLF. Run `sed -i 's/\r$//' script.sh` before running them in WSL.
- **Don't use `sed -i` to edit tracked files in a Windows checkout:** Git Bash's `sed -i` rewrote every CRLF line ending in a 4,000-line file, so a one-line fix showed as a full-file diff. Use the Edit tool, or Python with `open(p, encoding="utf-8", newline="")` and an exact-count replace. Check `git diff --stat` before committing or sending a diff for review.
- Python's `open(p, "w")` on Windows writes CRLF. Pass `newline="\n"` when the project expects LF.

## JSON to CLIs (gh api, curl)
- Don't pass JSON through PowerShell: it strips inner quotes. Use Git Bash with single-quoted JSON, or build arguments in Python (`json.dumps`) and call the CLI with `subprocess`.

## Gating on exit codes
- `cmd | grep … && next` tests `grep`'s status, not `cmd`'s. Run the gate on its own and test `$?`, or `set -o pipefail`.
- A helper ending in `grep -v` exits 1 when it selects no lines (every line was filtered out, or there was no output), so a following `&& git commit` silently never runs.

## Waiting and killing
- No `sleep N; check`. Use a background task plus a bounded wait (the `long-job-updates` skill's `waitfor.sh`), or the harness's monitor tool.
- `pgrep -f foo` and `pkill -f foo` match their own command line inside `bash -c`, so waits hang and kills hit themselves. Use the bracket trick (`pgrep -f "[f]oo"`) or `waitfor.sh`.
- After killing a pipeline, remove the partial files that run created (`*.part.mp4`, `.tmp`) before re-running. Delete only files you know that run wrote; if unsure, move them aside instead.

## Gotchas
- **"Catastrophic failure" or `wsl` hangs:** run `wsl --shutdown` from PowerShell, then retry. It usually follows an out-of-memory kill.
- **WSL's `df` shows the virtual disk's size, not physical space.** The distro's `ext4.vhdx` is a file on a Windows drive (`C:` by default, unless the distro was installed or moved elsewhere), so writing inside WSL fills that drive. Find it with `(Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss\*).BasePath` and check that drive's free space before big jobs. The file doesn't shrink when you delete data unless sparse mode is on or you compact it.
- Long writes from Windows tools through `\\wsl.localhost\...` can fail at close ("Permission denied" writing the trailer). Run the write on the filesystem's own side.
