"""Remove a git worktree only when nothing would be lost and nothing visible is using it.

usage:
  python worktree_safe_remove.py --repo DIR --worktree PATH [--allow-hardlinks] [--windows-processes-checked] [--dry-run]

Refuses when:
  - PATH is not a registered worktree of --repo, is the main worktree, is locked, or has submodules;
  - any file inside isn't tracked by git (untracked or ignored: `.env`, databases, build outputs). Found by
    walking the folder itself, so git settings such as status.showUntrackedFiles can't hide them;
  - a tracked file is modified or staged;
  - a process has its working directory or an open file inside (Linux/WSL: /proc). Processes you own that can't
    be inspected also refuse, except the per-user session managers `systemd --user` and `(sd-pam)`, which
    always hide themselves and run no project code. This sees only processes visible to this system at this moment: on WSL it can't see
    Windows processes, so a worktree under /mnt/ needs --windows-processes-checked after you've checked yourself;
  - a file inside has other hard links (deleting it wouldn't free the space, and the other link may be live),
    unless --allow-hardlinks.
--dry-run runs every check and reports what it would do. Removal is `git worktree remove` without --force.
Exit 0 = removed (or would be), 1 = refused, 2 = usage.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def worktrees(repo):
    r = git("-C", repo, "worktree", "list", "--porcelain")
    if r.returncode != 0:
        return None
    out, cur = [], None
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            cur = {"path": Path(line[len("worktree "):]).resolve(), "locked": False}
            out.append(cur)
        elif line.startswith("locked") and cur is not None:
            cur["locked"] = True
    return out


def inside(p, root):
    try:
        Path(p).resolve().relative_to(root)
        return True
    except (ValueError, OSError):
        return False


# Per-user session managers that mark themselves non-dumpable, so even their owner can't read their cwd or fds.
# They run no project code; any other process we own and can't inspect makes the removal refuse.
SESSION_MANAGERS = {"systemd", "(sd-pam)"}


def users_of(root, proc="/proc"):
    """(users, uninspectable_own): processes with cwd or an open fd inside root, and our own processes we could
    not inspect (session managers excepted). None when /proc is unavailable."""
    if not Path(proc).is_dir():
        return None
    me, uid = os.getpid(), os.getuid()
    found, blind = [], []
    for d in Path(proc).iterdir():
        if not d.name.isdigit() or int(d.name) == me:
            continue
        try:
            own = d.stat().st_uid == uid
        except OSError:
            continue  # exited
        hits, failed = [], False
        try:
            if inside(os.readlink(d / "cwd"), root):
                hits.append("cwd")
        except FileNotFoundError:
            continue
        except OSError:
            failed = True
        try:
            for fd in (d / "fd").iterdir():
                try:
                    if inside(os.readlink(fd), root):
                        hits.append("open file")
                        break
                except FileNotFoundError:
                    continue
        except FileNotFoundError:
            continue
        except OSError:
            failed = True
        if hits:
            try:
                cmd = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
            except OSError:
                cmd = "?"
            found.append(f"pid {d.name} ({', '.join(hits)}): {cmd[:80]}")
        elif failed and own:
            try:
                comm = (d / "comm").read_text().strip()
            except OSError:
                comm = ""
            if comm not in SESSION_MANAGERS:
                blind.append(d.name)
    return found, blind


def entries(root):
    """Every file and symlink inside root, without following symlinks. Only the worktree's own top-level `.git`
    (git's administrative pointer) is skipped; a nested `.git` (an embedded repository) is local data."""
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        if here == root:
            dirnames[:] = [d for d in dirnames if d != ".git"]
            filenames = [f for f in filenames if f != ".git"]
        for d in list(dirnames):
            if (here / d).is_symlink():  # os.walk lists directory symlinks here and doesn't descend into them
                dirnames.remove(d)
                yield here / d
        for f in filenames:
            yield here / f


def local_only_files(root):
    """Files inside the worktree that git doesn't track (including ignored ones), by walking the folder."""
    r = git("-C", str(root), "ls-files", "-z")
    if r.returncode != 0:
        return None
    tracked = {p for p in r.stdout.split("\0") if p}
    return [rel for rel in (p.relative_to(root).as_posix() for p in entries(root)) if rel not in tracked]


def hardlinked(root):
    out = []
    for p in entries(root):
        try:
            st = p.lstat()
        except OSError:
            continue
        if st.st_nlink > 1 and not p.is_symlink():
            out.append(str(p.relative_to(root)))
    return out


def on_wsl():
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--allow-hardlinks", action="store_true")
    ap.add_argument("--windows-processes-checked", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--assume-wsl", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--mount-prefix", default="/mnt/", help=argparse.SUPPRESS)
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    wts = worktrees(a.repo)
    if wts is None:
        print(f"usage: {a.repo} is not a git repository", file=sys.stderr)
        return 2
    target = Path(a.worktree).resolve()
    entry = next((w for w in wts if w["path"] == target), None)
    if entry is None:
        print(f"REFUSED: {target} is not a registered worktree of {a.repo}")
        return 1
    if entry is wts[0]:
        print("REFUSED: that is the main worktree")
        return 1
    reasons = []
    if entry["locked"]:
        reasons.append("the worktree is locked")
    if (target / ".gitmodules").exists():
        reasons.append("it has submodules (remove it by hand)")
    extra = local_only_files(target)
    if extra is None:
        reasons.append("git ls-files failed inside the worktree")
    elif extra:
        reasons.append(f"{len(extra)} untracked or ignored file(s) would be deleted, e.g. {', '.join(extra[:3])}")
    if git("-C", str(target), "diff", "--quiet", "HEAD", "--").returncode != 0:
        reasons.append("tracked files are modified or staged")
    scan = users_of(target)
    if scan is None:
        reasons.append("cannot check for live processes on this system (no /proc); close anything using it, "
                       "then remove it by hand with `git worktree remove`")
    else:
        users, blind = scan
        if users:
            reasons.append("in use by " + "; ".join(users[:5]))
        if blind:
            reasons.append(f"could not inspect {len(blind)} of your own process(es) (pids {', '.join(blind[:5])})")
    if (a.assume_wsl or on_wsl()) and str(target).startswith(a.mount_prefix) and not a.windows_processes_checked:
        reasons.append("on WSL, Windows processes are invisible here: check none uses it (e.g. a dev server), "
                       "then pass --windows-processes-checked")
    links = hardlinked(target)
    if links and not a.allow_hardlinks:
        reasons.append(f"{len(links)} hard-linked file(s), e.g. {', '.join(links[:3])}")
    if reasons:
        print("REFUSED: " + " | ".join(reasons))
        return 1
    if a.dry_run:
        print(f"OK (dry run): every check passed; would remove {target}")
        return 0
    r = git("-C", a.repo, "worktree", "remove", str(target))
    if r.returncode != 0:
        print(f"REFUSED by git: {r.stderr.strip()}")
        return 1
    print(f"REMOVED {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
