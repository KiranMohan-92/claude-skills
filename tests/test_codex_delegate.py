"""codex-delegate scripts, against a fake `codex` executable so no network or credentials are needed."""
import http.server
import json
import os
import subprocess
import sys
import threading
import time

import pytest

from conftest import SKILLS, needs_proc, run

RUN = SKILLS / "codex-delegate" / "scripts" / "codex_run.sh"
LOOP = SKILLS / "codex-delegate" / "scripts" / "review_loop.py"

FAKE = r"""#!/usr/bin/env bash
# fake codex: --version, and `exec ... -o FILE ... -` reading the brief on stdin
if [[ "$1" == "--version" ]]; then echo "codex-cli ${FAKE_VERSION:-0.159.1}"; exit 0; fi
out=""
while [[ $# -gt 0 ]]; do [[ "$1" == "-o" ]] && out=$2; shift; done
brief=$(cat)
sleep "${FAKE_SLEEP:-0}"
case "${FAKE_MODE:-ok}" in
  ok) if [[ "$brief" == "Reply with exactly: OK" ]]; then echo OK > "$out"
      else printf '%s\nVERDICT: ship\n' "${brief:0:40}" > "$out"; fi ;;
  okexit1) echo OK > "$out"; exit 1 ;;
  notok) echo "NOT OK: authentication failed" > "$out" ;;
  spaced) printf 'O K\n' > "$out" ;;
  split) printf 'O\nK\n' > "$out" ;;
  padded) printf '  OK \n\n' > "$out" ;;
  fail) echo "partial notes" > "$out"; echo "boom" >&2; exit 3 ;;
  empty) : ;;
esac
echo "fake codex done"
"""


@pytest.fixture
def fake(tmp_path):
    p = tmp_path / "codex"
    p.write_text(FAKE)
    p.chmod(0o755)
    return p


def env(fake, **kw):
    e = dict(os.environ, CODEX_BIN=str(fake))
    e.update({k: str(v) for k, v in kw.items()})
    return e


@pytest.fixture
def server():
    srv = http.server.HTTPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


# ---------------- probe ----------------

def test_probe_ok_with_reachable_host(fake, server):
    r = run("bash", RUN, "probe", "--min-version", "0.159.0", "--url", server, env=env(fake))
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.startswith("OK: codex 0.159.1")


def test_probe_fails_when_host_unreachable(fake):
    r = run("bash", RUN, "probe", "--url", "http://127.0.0.1:9/", env=env(fake))
    assert r.returncode == 3
    assert "UNREACHABLE" in r.stdout


def test_probe_fails_when_cli_too_old(fake, server):
    r = run("bash", RUN, "probe", "--min-version", "0.159.0", "--url", server, env=env(fake, FAKE_VERSION="0.157.2"))
    assert r.returncode == 4
    assert "TOO OLD" in r.stdout


def test_probe_fails_when_codex_missing(tmp_path, server):
    r = run("bash", RUN, "probe", "--url", server, env=dict(os.environ, CODEX_BIN=str(tmp_path / "nope")))
    assert r.returncode == 3


@pytest.mark.parametrize("mode,ok", [("ok", True), ("padded", True), ("empty", False), ("notok", False),
                                     ("okexit1", False), ("spaced", False), ("split", False)])
def test_live_probe_needs_exit_0_and_exactly_ok(fake, server, mode, ok):
    r = run("bash", RUN, "probe", "--live", "--url", server, env=env(fake, FAKE_MODE=mode))
    assert (r.returncode == 0) == ok, r.stdout


# ---------------- launch + status ----------------

def launch(tmp_path, fake, rel=False, **kw):
    brief = tmp_path / "brief.md"
    brief.write_text("Review the diff and end with a VERDICT line.\n")
    out, log = tmp_path / "out.md", tmp_path / "lane.log"
    paths = (["--brief", "brief.md", "--out", "out.md", "--log", "lane.log", "--cd", "/"] if rel
             else ["--brief", str(brief), "--out", str(out), "--log", str(log)])
    # Launched from a short-lived session that then hangs up its whole process group, the way a closing
    # terminal or `wsl.exe` session does. A job started with a plain `&` dies here; setsid + nohup survives.
    r = run("setsid", "bash", "-c",
            f"bash {RUN} launch {' '.join(paths)}; rc=$?; kill -HUP -$$; exit $rc",
            env=env(fake, **kw), cwd=tmp_path)
    assert r.returncode in (0, 1, -1, 129), r.stdout + r.stderr  # the shell may die of its own SIGHUP
    assert (tmp_path / "lane.log.pid").exists(), r.stdout + r.stderr
    return out, log


def wait_status(fake, out, log, limit=20):
    deadline = time.time() + limit
    while True:
        s = run("bash", RUN, "status", "--out", out, "--log", log, env=env(fake))
        if s.returncode != 10 or time.time() > deadline:
            return s
        time.sleep(0.3)


@needs_proc
def test_launch_survives_its_shell_and_status_tracks_it(tmp_path, fake):
    out, log = launch(tmp_path, fake, FAKE_SLEEP=3)
    s = run("bash", RUN, "status", "--out", out, "--log", log, env=env(fake))
    assert s.returncode == 10, s.stdout
    s = wait_status(fake, out, log)
    assert s.returncode == 0, s.stdout
    assert "VERDICT: ship" in out.read_text()


@needs_proc
def test_relative_paths_are_resolved_before_cd(tmp_path, fake):
    out, log = launch(tmp_path, fake, rel=True)
    s = wait_status(fake, out, log)
    assert s.returncode == 0, s.stdout
    assert "Review the diff" in out.read_text()


@needs_proc
def test_empty_result_is_a_failure_not_no_findings(tmp_path, fake):
    out, log = launch(tmp_path, fake, FAKE_MODE="empty")
    s = wait_status(fake, out, log)
    assert s.returncode == 1
    assert "FAILED" in s.stdout


@needs_proc
def test_nonzero_exit_fails_even_with_output(tmp_path, fake):
    out, log = launch(tmp_path, fake, FAKE_MODE="fail", FAKE_SLEEP=2)
    s = wait_status(fake, out, log)
    assert s.returncode == 1
    assert "exited 3" in s.stdout


@needs_proc
def test_a_reused_pid_is_not_our_job(tmp_path, fake):
    other = subprocess.Popen(["sleep", "30"])
    try:
        log, out = tmp_path / "lane.log", tmp_path / "out.md"
        (tmp_path / "lane.log.pid").write_text(str(other.pid))
        (tmp_path / "lane.log.job").write_text("codex-delegate-job-123-456-789")
        log.write_text("")
        s = run("bash", RUN, "status", "--out", out, "--log", log, env=env(fake))
        assert s.returncode == 1, s.stdout  # alive, but not running our job
    finally:
        other.kill()


def test_launch_refuses_unwritable_destinations(tmp_path, fake):
    brief = tmp_path / "b.md"
    brief.write_text("x")
    for out, log in ((tmp_path / "nope" / "o.md", tmp_path / "l.log"), (tmp_path / "o.md", tmp_path / "nope" / "l.log")):
        r = run("bash", RUN, "launch", "--brief", brief, "--out", out, "--log", log, env=env(fake))
        assert r.returncode == 2, r.stdout
        assert "LAUNCHED" not in r.stdout


def test_launch_usage_errors(tmp_path, fake):
    empty = tmp_path / "empty.md"
    empty.write_text("")
    base = ["bash", RUN, "launch", "--out", tmp_path / "o", "--log", tmp_path / "l"]
    assert run(*base, "--brief", empty, env=env(fake)).returncode == 2
    brief = tmp_path / "b.md"
    brief.write_text("x")
    assert run(*base, "--brief", brief, "--sandbox", "danger-full-access", env=env(fake)).returncode == 2
    assert run("bash", RUN, env=env(fake)).returncode == 2
    assert run("bash", RUN, "status", "--out", tmp_path / "o", "--log", tmp_path / "never", env=env(fake)).returncode == 2


# ---------------- scope ----------------

def git(repo, *args):
    r = run("git", "-C", repo, *args)
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    git(d, "init", "-q")
    git(d, "config", "user.email", "t@example.com")
    git(d, "config", "user.name", "t")
    git(d, "config", "core.autocrlf", "false")
    (d / "a.txt").write_bytes(b"".join(b"line %d\n" % i for i in range(400)))
    git(d, "add", "a.txt")
    git(d, "commit", "-qm", "base")
    return d


def scope(repo, *args):
    return run("bash", RUN, "scope", *args, cwd=repo)


def test_scope_small_change_is_in_scope(repo):
    (repo / "a.txt").write_bytes((repo / "a.txt").read_bytes().replace(b"line 5\n", b"line five\n"))
    r = scope(repo, "--uncommitted")
    assert r.returncode == 0, r.stdout
    assert "IN SCOPE" in r.stdout


def test_scope_refuses_line_ending_churn(repo):
    (repo / "a.txt").write_bytes((repo / "a.txt").read_bytes().replace(b"\n", b"\r\n"))
    r = scope(repo, "--uncommitted")
    assert r.returncode == 1
    assert "line-ending churn" in r.stdout


def test_scope_refuses_oversized_diffs_including_untracked(repo):
    (repo / "new.txt").write_text("x\n" * 119 + "unterminated last line")
    r = scope(repo, "--uncommitted", "--max-lines", "100")
    assert r.returncode == 1
    assert "120 untracked lines" in r.stdout
    assert scope(repo, "--uncommitted", "--max-lines", "500").returncode == 0


def test_scope_never_follows_untracked_symlinks(repo, tmp_path):
    secret = tmp_path / "outside.txt"
    secret.write_text("y\n" * 5000)
    (repo / "link.txt").symlink_to(secret)
    (repo / "--help").write_text("z\n")  # a filename that looks like an option
    r = scope(repo, "--uncommitted", "--max-lines", "100")
    assert r.returncode == 0, r.stdout
    assert "1 untracked lines" in r.stdout and "1 symlink/special file(s) skipped" in r.stdout


def test_scope_lists_untracked_binaries_without_counting_them(repo):
    (repo / "tool.bin").write_bytes(b"\x7fELF\x00\x01\x02" + b"\n" * 300)
    r = scope(repo, "--uncommitted", "--max-lines", "100")
    assert r.returncode == 0, r.stdout
    assert "0 untracked lines, 1 binary file(s)" in r.stdout


def test_scope_fails_on_unknown_refs(repo):
    for args, msg in ((["--base", "no-such-branch"], "unknown base"), (["--commit", "deadbeef"], "unknown commit")):
        r = scope(repo, *args)
        assert r.returncode == 1, r.stdout
        assert msg in r.stdout and "IN SCOPE" not in r.stdout


def test_scope_fails_when_git_diff_fails(repo):
    # a real branch with no common history: the ref resolves, then `git diff base...HEAD` itself fails
    home = git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    git(repo, "checkout", "-q", "--orphan", "unrelated")
    (repo / "b.txt").write_text("other history\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "unrelated root")
    git(repo, "checkout", "-q", home)
    r = scope(repo, "--base", "unrelated")
    assert r.returncode == 1, r.stdout
    assert "git diff failed" in r.stdout and "IN SCOPE" not in r.stdout


def test_scope_commit_and_base_modes(repo):
    (repo / "a.txt").write_bytes((repo / "a.txt").read_bytes() + b"more\n")
    git(repo, "commit", "-qam", "more")
    assert scope(repo, "--commit", "HEAD").returncode == 0
    assert scope(repo, "--base", "HEAD~1").returncode == 0
    assert scope(repo).returncode == 2


# ---------------- review loop ----------------

def loop(tmp_path, text, *extra):
    out = tmp_path / "review.md"
    out.write_text(text)
    return subprocess.run([sys.executable, str(LOOP), "record", "--ledger", str(tmp_path / "ledger.jsonl"),
                           "--output", str(out), *extra], capture_output=True, text=True)


def test_ship_and_fix_first(tmp_path):
    assert loop(tmp_path, "All good.\nVERDICT: ship\n").returncode == 0
    assert loop(tmp_path, "- P1: broken\n**VERDICT: fix first**\n\n").returncode == 1


@pytest.mark.parametrize("text", [
    "",
    "Looks fine overall.",
    "> VERDICT: ship (quoted from round 1)\nReview aborted.\n",
    "VERDICT: ship is NOT justified\n",
    "VERDICT: ship\nOne more thing: the tests fail.\n",
])
def test_missing_quoted_or_qualified_verdicts_fail_closed(tmp_path, text):
    assert loop(tmp_path, text).returncode == 2
    assert not (tmp_path / "ledger.jsonl").exists()


def test_only_the_final_line_counts(tmp_path):
    assert loop(tmp_path, "> VERDICT: ship (quoted from round 1)\n- P2: x\nVERDICT: fix first\n").returncode == 1


def test_stop_after_three_rounds_that_each_find_something_new(tmp_path):
    codes = [loop(tmp_path, "- P2: new thing\nVERDICT: fix first\n").returncode for _ in range(3)]
    assert codes == [1, 1, 4]  # round 3 is the third fix-first round with new findings: stop, don't pin
    rows = [json.loads(line) for line in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert [r["round"] for r in rows] == [1, 2, 3]


def test_a_round_with_nothing_new_resets_the_stop_rule(tmp_path):
    loop(tmp_path, "- P2: a\nVERDICT: fix first\n")
    loop(tmp_path, "- P2: b\nVERDICT: fix first\n")
    r = loop(tmp_path, "- P2: a again\nVERDICT: fix first\n", "--new", "0")
    assert r.returncode == 3  # not a stop, but round 4 must be pinned
    assert "PIN" in r.stdout


def test_default_new_count_reads_p1_p2_lines(tmp_path):
    loop(tmp_path, "- P1: a\n- P2: b\n- P3: c\nVERDICT: fix first\n")
    row = json.loads((tmp_path / "ledger.jsonl").read_text().splitlines()[0])
    assert row["new"] == 2
