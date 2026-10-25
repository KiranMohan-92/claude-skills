"""parallel-lanes scripts against real temporary git repos and worktrees."""
import json
import os
import subprocess
import sys
import time

import pytest

from conftest import SKILLS, needs_proc, run

S = SKILLS / "parallel-lanes" / "scripts"


def py(script, *args, **kw):
    return run(sys.executable, S / script, *args, **kw)


def git(repo, *args):
    r = run("git", "-C", repo, *args)
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "repo"
    (d / "src" / "a").mkdir(parents=True)
    (d / "src" / "b").mkdir(parents=True)
    git(d, "init", "-q", "-b", "main")
    git(d, "config", "user.email", "t@example.com")
    git(d, "config", "user.name", "t")
    (d / "src" / "a" / "one.ts").write_text("export const a = 1\n")
    (d / "src" / "b" / "two.ts").write_text("export const b = 2\n")
    (d / "src" / "shared.ts").write_text("export const s = 0\n")
    (d / ".gitignore").write_text(".claude/worktrees/\n")
    git(d, "add", "-A")
    git(d, "commit", "-qm", "base")
    return d


# ---------------- preflight ----------------

def test_preflight_passes_with_room(repo):
    r = py("lane_preflight.py", "--repo", repo, "--lanes", "2", "--min-free-gb", "0", "--per-lane-gb", "0",
           "--ram-per-lane-gb", "0")
    assert r.returncode == 0, r.stdout
    assert "PREFLIGHT OK" in r.stdout


def test_preflight_fails_when_disk_is_short(repo):
    r = py("lane_preflight.py", "--repo", repo, "--lanes", "7", "--per-lane-gb", "100000", "--ram-per-lane-gb", "0")
    assert r.returncode == 1
    assert "FAIL  disk" in r.stdout


def test_preflight_fails_when_ram_is_short(repo, tmp_path):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal: 16000000 kB\nMemAvailable: 4194304 kB\n")  # 4 GB
    r = py("lane_preflight.py", "--repo", repo, "--lanes", "3", "--min-free-gb", "0", "--per-lane-gb", "0",
           "--ram-per-lane-gb", "2", "--meminfo", meminfo)
    assert r.returncode == 1
    assert "FAIL  ram: 4.0 GB available, need 6.0 GB" in r.stdout


def test_preflight_fails_when_worktrees_are_not_ignored(repo):
    (repo / ".gitignore").write_text("node_modules/\n")
    r = py("lane_preflight.py", "--repo", repo, "--lanes", "2", "--min-free-gb", "0", "--per-lane-gb", "0",
           "--ram-per-lane-gb", "0")
    assert r.returncode == 1
    assert "not ignored by git" in r.stdout


def fake_npx(tmp_path, answer, js_answer=None):
    """A stand-in for `npx --no-install prettier --file-info PATH` that prints what prettier would.
    js_answer, when set, is the answer for .js/.jsx/.mjs/.cjs probes (a config that covers only some types)."""
    p = tmp_path / "npx"
    if answer is None:
        p.write_text("#!/usr/bin/env bash\nexit 1\n")
    else:
        js = answer if js_answer is None else js_answer
        p.write_text("#!/usr/bin/env bash\nf=\"${!#}\"\n"
                     f"case \"$f\" in *.js|*.jsx|*.mjs|*.cjs) a={js} ;; *) a={answer} ;; esac\n"
                     "echo \"{\\\"ignored\\\": $a, \\\"inferredParser\\\": null}\"\n")
    p.chmod(0o755)
    return p


def test_preflight_fails_when_only_some_file_types_are_ignored(repo, tmp_path):
    (repo / "package.json").write_text(json.dumps({"devDependencies": {"prettier": "^3"}}))
    r = py("lane_preflight.py", "--repo", repo, "--lanes", "2", "--min-free-gb", "0", "--per-lane-gb", "0",
           "--ram-per-lane-gb", "0", env=preflight_env(fake_npx(tmp_path, "true", js_answer="false")))
    assert r.returncode == 1, r.stdout
    assert ".js" in r.stdout


def preflight_env(npx):
    return dict(os.environ, PREFLIGHT_NPX=str(npx))


def test_preflight_asks_the_formatter_not_its_ignore_file(repo, tmp_path):
    (repo / "package.json").write_text(json.dumps({"devDependencies": {"prettier": "^3"}}))
    # a comment that merely mentions the folder must not count as ignoring it
    (repo / ".prettierignore").write_text("# .claude/worktrees is NOT ignored yet\n")
    args = ["--repo", repo, "--lanes", "2", "--min-free-gb", "0", "--per-lane-gb", "0", "--ram-per-lane-gb", "0"]
    r = py("lane_preflight.py", *args, env=preflight_env(fake_npx(tmp_path, "false")))
    assert r.returncode == 1 and "prettier" in r.stdout
    r = py("lane_preflight.py", *args, env=preflight_env(fake_npx(tmp_path, "true")))
    assert r.returncode == 0, r.stdout
    assert "asked the tools" in r.stdout


def test_preflight_says_unverified_when_the_tool_cannot_be_asked(repo, tmp_path):
    (repo / "package.json").write_text(json.dumps({"devDependencies": {"prettier": "^3"}}))
    r = py("lane_preflight.py", "--repo", repo, "--lanes", "2", "--min-free-gb", "0", "--per-lane-gb", "0",
           "--ram-per-lane-gb", "0", env=preflight_env(fake_npx(tmp_path, None)))
    assert r.returncode == 0, r.stdout
    assert "WARN  ignore: UNVERIFIED for prettier" in r.stdout
    assert "PASS  ignore" not in r.stdout


@needs_proc
def test_preflight_counts_running_gates(repo, tmp_path):
    tag = f"fakegate_{os.getpid()}"
    script = tmp_path / f"{tag}.sh"
    script.write_text("sleep 30\n")
    procs = [subprocess.Popen(["bash", str(script)]) for _ in range(2)]
    try:
        time.sleep(0.3)
        common = ["--repo", repo, "--lanes", "1", "--min-free-gb", "0", "--per-lane-gb", "0", "--ram-per-lane-gb", "0",
                  "--gate-pattern", tag]
        assert py("lane_preflight.py", *common, "--max-gates", "2").returncode == 1
        assert py("lane_preflight.py", *common, "--max-gates", "3").returncode == 0
    finally:
        for p in procs:
            p.kill()


def test_preflight_usage(repo):
    assert py("lane_preflight.py", "--repo", repo, "--lanes", "0").returncode == 2
    assert py("lane_preflight.py", "--repo", repo, "--lanes", "1", "--gate-pattern", "x").returncode == 2


# ---------------- overlap ----------------

def plan(tmp_path, lanes):
    p = tmp_path / "lanes.json"
    p.write_text(json.dumps({"lanes": lanes}))
    return p


def test_plan_independent_lanes_pass(repo, tmp_path):
    p = plan(tmp_path, [{"name": "a", "files": ["src/a/**"]}, {"name": "b", "files": ["src/b/"]}])
    r = py("lane_overlap.py", "plan", "--repo", repo, "--plan", p)
    assert r.returncode == 0, r.stdout


def test_plan_shared_file_fails(repo, tmp_path):
    p = plan(tmp_path, [{"name": "a", "files": ["src/a/**", "src/shared.ts"]},
                        {"name": "b", "files": ["src/b/**", "src/*.ts"]}])
    r = py("lane_overlap.py", "plan", "--repo", repo, "--plan", p)
    assert r.returncode == 1
    assert "src/shared.ts" in r.stdout


def test_plan_new_files_and_reserved_slots_count(repo, tmp_path):
    p = plan(tmp_path, [{"name": "a", "files": ["src/new/thing.ts"], "reserve": ["snapshot-bit-7"]},
                        {"name": "b", "files": ["src/new/thing.ts"], "reserve": ["snapshot-bit-7"]}])
    r = py("lane_overlap.py", "plan", "--repo", repo, "--plan", p)
    assert r.returncode == 1
    assert "src/new/thing.ts" in r.stdout and "snapshot-bit-7" in r.stdout


@pytest.mark.parametrize("pattern", ["src/a/**", "src/a/*.ts"])
def test_plan_new_file_inside_another_lanes_folder_fails(repo, tmp_path, pattern):
    p = plan(tmp_path, [{"name": "a", "files": [pattern]}, {"name": "b", "files": ["src/a/new.ts"]}])
    r = py("lane_overlap.py", "plan", "--repo", repo, "--plan", p)
    assert r.returncode == 1, r.stdout


def test_glob_matcher_semantics():
    sys.path.insert(0, str(S))
    import lane_overlap as LO
    rx = LO.to_regex
    assert rx("src/**/*.ts").match("src/shared.ts") and rx("src/**/*.ts").match("src/a/b/x.ts")
    assert not rx("src/*.ts").match("src/a/one.ts") and rx("src/*.ts").match("src/one.ts")
    assert rx("src/a/**").match("src/a/x/y.ts") and not rx("src/a/**").match("src/ab/x.ts")
    assert rx("src/?.ts").match("src/x.ts") and not rx("src/?.ts").match("src/xy.ts")
    assert LO.normalise("./.claude/x/") == ".claude/x/**"


def test_plan_glob_semantics_are_segment_aware(repo, tmp_path):
    # `**` spans zero or more folders: src/**/*.ts claims src/shared.ts
    p = plan(tmp_path, [{"name": "a", "files": ["src/**/*.ts"]}, {"name": "b", "files": ["src/shared.ts"]}])
    assert py("lane_overlap.py", "plan", "--repo", repo, "--plan", p).returncode == 1
    # `*` stays in one folder: src/*.ts does not claim src/a/one.ts
    p = plan(tmp_path, [{"name": "a", "files": ["src/*.ts"]}, {"name": "b", "files": ["src/a/one.ts"]}])
    r = py("lane_overlap.py", "plan", "--repo", repo, "--plan", p)
    assert r.returncode == 0, r.stdout


def test_plan_lane_without_files_fails(repo, tmp_path):
    p = plan(tmp_path, [{"name": "a", "files": ["src/a/**"]}, {"name": "b", "files": []}])
    assert py("lane_overlap.py", "plan", "--repo", repo, "--plan", p).returncode == 1


def branch(repo, name, path, text):
    git(repo, "checkout", "-q", "-b", name, "main")
    (repo / path).write_text(text)
    git(repo, "commit", "-qam", name)
    git(repo, "checkout", "-q", "main")


def test_actual_overlap_between_branches(repo):
    branch(repo, "lane-a", "src/a/one.ts", "export const a = 10\n")
    branch(repo, "lane-b", "src/b/two.ts", "export const b = 20\n")
    branch(repo, "lane-c", "src/a/one.ts", "export const a = 99\n")
    assert py("lane_overlap.py", "actual", "--repo", repo, "--base", "main", "lane-a", "lane-b").returncode == 0
    r = py("lane_overlap.py", "actual", "--repo", repo, "--base", "main", "lane-a", "lane-b", "lane-c")
    assert r.returncode == 1
    assert "'lane-a' and 'lane-c'" in r.stdout


def test_overlap_usage(repo):
    assert py("lane_overlap.py", "actual", "--repo", repo, "--base", "main", "only-one").returncode == 2
    assert py("lane_overlap.py", "plan", "--repo", repo, "--plan", repo / "missing.json").returncode == 2


# ---------------- integrate ----------------

def integrate(repo, *args):
    return py("lane_integrate.py", "--repo", repo, *args)


def test_integrate_passes_on_green(repo):
    r = integrate(repo, "--gate", f"{sys.executable} -c pass")
    assert r.returncode == 0, r.stdout
    assert "INTEGRATION OK" in r.stdout


def test_integrate_fails_on_red_gate(repo):
    assert integrate(repo, "--gate", f"{sys.executable} -c \"raise SystemExit(1)\"").returncode == 1


def test_integrate_refuses_pipelines(repo):
    # `gate | tail -1` would report tail's exit status; the script must not allow it
    r = integrate(repo, "--gate", f"{sys.executable} -c \"raise SystemExit(1)\" | tail -1")
    assert r.returncode == 2


def test_integrate_catches_a_flake(repo, tmp_path):
    counter = tmp_path / "n"
    flaky = tmp_path / "flaky.py"
    flaky.write_text(
        "import pathlib, sys\n"
        f"p = pathlib.Path(r'{counter}')\n"
        "n = int(p.read_text()) + 1 if p.exists() else 1\n"
        "p.write_text(str(n))\n"
        "sys.exit(1 if n == 2 else 0)\n")
    r = integrate(repo, "--gate", f"{sys.executable} -c pass", "--repeat", f"{sys.executable} {flaky}", "--times", "3")
    assert r.returncode == 1
    assert "1 failing run(s)" in r.stdout


def test_integrate_requires_a_clean_tree(repo):
    (repo / "src" / "a" / "one.ts").write_text("half merged\n")
    r = integrate(repo, "--gate", f"{sys.executable} -c pass")
    assert r.returncode == 1
    assert "not clean before integration" in r.stdout  # refused up front, before spending a gate run
    assert "PASS  gate" not in r.stdout


def test_integrate_catches_files_the_gate_leaves_behind(repo):
    r = integrate(repo, "--gate", f"{sys.executable} -c \"open('generated.txt','w').write('x')\"")
    assert r.returncode == 1
    assert "not clean after" in r.stdout


def test_windows_paths_survive_parsing():
    sys.path.insert(0, str(S))
    import lane_integrate as LI
    assert LI.parse(r"C:\Python313\python.exe -c pass", windows=True) == [r"C:\Python313\python.exe", "-c", "pass"]
    assert LI.parse(r'"C:\Program Files\nodejs\node.exe" tools\bench.mjs', windows=True) == [
        r"C:\Program Files\nodejs\node.exe", r"tools\bench.mjs"]
    with pytest.raises(ValueError):
        LI.parse(r"C:\x.exe | findstr ok", windows=True)
    assert LI.parse('node --test --test-name-pattern="some test" a.mjs', windows=True) == [
        "node", "--test", "--test-name-pattern=some test", "a.mjs"]
    assert LI.split_windows(r'a\\"b c" d') == [r"a\b c", "d"]  # 2 backslashes + quote: one backslash, quote opens
    assert LI.split_windows(r'a\"b c') == ['a"b', "c"]  # 1 backslash + quote: a literal quote
    assert LI.split_windows('"" x') == ["", "x"]
    assert LI.split_windows('python -c "print(""hello world"")"') == ["python", "-c", 'print("hello world")']


def test_integrate_usage(repo):
    assert integrate(repo, "--gate", "x", "--times", "1").returncode == 2


# ---------------- safe remove ----------------

def add_worktree(repo, name):
    wt = repo / ".claude" / "worktrees" / name
    git(repo, "worktree", "add", "-q", str(wt), "-b", name)
    return wt


@needs_proc
def test_remove_refuses_while_a_process_uses_it(repo):
    wt = add_worktree(repo, "busy")
    p = subprocess.Popen(["sleep", "30"], cwd=wt)
    try:
        time.sleep(0.2)
        r = py("worktree_safe_remove.py", "--repo", repo, "--worktree", wt)
        assert r.returncode == 1
        assert f"pid {p.pid}" in r.stdout
        assert wt.exists()
    finally:
        p.kill()
        p.wait()
    r = py("worktree_safe_remove.py", "--repo", repo, "--worktree", wt)
    assert r.returncode == 0, r.stdout
    assert not wt.exists()


@needs_proc
def test_remove_refuses_hard_links_unless_allowed(repo, tmp_path):
    wt = add_worktree(repo, "linked")
    os.link(wt / "src" / "a" / "one.ts", tmp_path / "elsewhere.ts")  # a tracked file with a second link
    r = py("worktree_safe_remove.py", "--repo", repo, "--worktree", wt, "--dry-run")
    assert r.returncode == 1 and "hard-linked" in r.stdout
    r = py("worktree_safe_remove.py", "--repo", repo, "--worktree", wt, "--dry-run", "--allow-hardlinks")
    assert r.returncode == 0, r.stdout
    assert wt.exists()  # a dry run removes nothing


@needs_proc
def test_remove_never_discards_uncommitted_work(repo):
    wt = add_worktree(repo, "dirty")
    (wt / "src" / "a" / "one.ts").write_text("unsaved lane work\n")
    r = py("worktree_safe_remove.py", "--repo", repo, "--worktree", wt)
    assert r.returncode == 1
    assert "modified or staged" in r.stdout
    assert (wt / "src" / "a" / "one.ts").read_text() == "unsaved lane work\n"


@needs_proc
@pytest.mark.parametrize("name,ignore", [("notes.txt", False), (".env", True)])
def test_remove_refuses_untracked_and_ignored_files(repo, name, ignore):
    # git's own removal deletes ignored files such as .env; the script must find them itself
    if ignore:
        (repo / ".gitignore").write_text(".claude/worktrees/\n.env\n")
        git(repo, "commit", "-qam", "ignore env")
    wt = add_worktree(repo, f"local-{name.strip('.')}")
    (wt / name).write_text("only copy\n")
    git(wt, "config", "status.showUntrackedFiles", "no")  # must not hide anything
    for extra in ([], ["--dry-run"]):
        r = py("worktree_safe_remove.py", "--repo", repo, "--worktree", wt, *extra)
        assert r.returncode == 1, r.stdout
        assert "untracked or ignored" in r.stdout and name in r.stdout
    assert (wt / name).read_text() == "only copy\n"


@needs_proc
def test_remove_refuses_ignored_symlinked_dirs_and_nested_repos(repo, tmp_path):
    (repo / ".gitignore").write_text(".claude/worktrees/\ncache\nvendor/\n")
    git(repo, "commit", "-qam", "ignores")
    wt = add_worktree(repo, "odd")
    target = tmp_path / "big-cache"
    target.mkdir()
    (wt / "cache").symlink_to(target, target_is_directory=True)
    r = py("worktree_safe_remove.py", "--repo", repo, "--worktree", wt, "--dry-run")
    assert r.returncode == 1 and "cache" in r.stdout, r.stdout
    (wt / "cache").unlink()
    git(tmp_path, "init", "-q", str(wt / "vendor" / "lib"))  # an embedded repository: its .git is local data
    r = py("worktree_safe_remove.py", "--repo", repo, "--worktree", wt, "--dry-run")
    assert r.returncode == 1 and "vendor/lib" in r.stdout, r.stdout


@needs_proc
def test_remove_refuses_a_locked_worktree(repo):
    wt = add_worktree(repo, "locked")
    git(repo, "worktree", "lock", str(wt))
    r = py("worktree_safe_remove.py", "--repo", repo, "--worktree", wt, "--dry-run")
    assert r.returncode == 1 and "locked" in r.stdout


@needs_proc
def test_remove_on_wsl_needs_windows_processes_checked(repo, tmp_path):
    wt = add_worktree(repo, "wsl")
    common = ["--repo", repo, "--worktree", wt, "--dry-run", "--assume-wsl", "--mount-prefix", str(tmp_path)]
    r = py("worktree_safe_remove.py", *common)
    assert r.returncode == 1 and "Windows processes" in r.stdout
    assert py("worktree_safe_remove.py", *common, "--windows-processes-checked").returncode == 0


def test_uninspectable_own_process_is_not_treated_as_safe(tmp_path):
    sys.path.insert(0, str(S))
    import worktree_safe_remove as W
    root = tmp_path / "wt"
    root.mkdir()
    proc = tmp_path / "proc"
    (proc / "4242" / "fd").mkdir(parents=True)
    (proc / "4242" / "cwd").write_text("not a link")  # readlink fails like an unreadable process
    (proc / "4243" / "fd").mkdir(parents=True)
    (proc / "4243" / "cwd").symlink_to(root)  # a process sitting in the worktree
    (proc / "4243" / "cmdline").write_bytes(b"server\0--port\0002600")
    (proc / "4244" / "fd").mkdir(parents=True)
    (proc / "4244" / "cwd").write_text("hidden")  # the user's systemd also can't be read, by design
    (proc / "4244" / "comm").write_text("systemd\n")
    users, blind = W.users_of(root.resolve(), proc=str(proc))
    assert blind == ["4242"]
    assert len(users) == 1 and users[0].startswith("pid 4243 (cwd)")


def test_remove_refuses_main_and_unknown_paths(repo, tmp_path):
    r = py("worktree_safe_remove.py", "--repo", repo, "--worktree", repo)
    assert r.returncode == 1
    assert "main worktree" in r.stdout  # our own refusal, not just git's
    assert py("worktree_safe_remove.py", "--repo", repo, "--worktree", tmp_path / "elsewhere").returncode == 1
    assert py("worktree_safe_remove.py", "--repo", tmp_path, "--worktree", tmp_path).returncode == 2
