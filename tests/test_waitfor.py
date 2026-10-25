"""waitfor.sh: bounded, and immune to matching its own command line."""
import subprocess
import time
import uuid

from conftest import SKILLS, needs_proc, run

WAITFOR = SKILLS / "long-job-updates" / "scripts" / "waitfor.sh"
pytestmark = needs_proc


def test_file_already_present_is_done(tmp_path):
    f = tmp_path / "out.txt"
    f.write_text("x")
    r = run("bash", WAITFOR, "--file", f, "--max", "5")
    assert r.returncode == 0
    assert r.stdout.startswith("DONE")


def test_log_match_and_status_command(tmp_path):
    log = tmp_path / "job.log"
    log.write_text("chunk 3/5\nALL CHUNKS OK\n")
    r = run("bash", WAITFOR, "--log", log, "ALL CHUNKS", "--status", f"tail -1 {log}", "--max", "5")
    assert r.returncode == 0
    assert "ALL CHUNKS OK" in r.stdout


def test_gone_ignores_its_own_caller(tmp_path):
    # The caller's command line contains the pattern. The trailing "; exit $?" stops bash from exec-ing
    # waitfor.sh in place, so the caller really is a separate ancestor process. Without the ancestry skip
    # this loops until --max.
    name = f"nosuchjob_{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    r = run("bash", "-c", f"bash {WAITFOR} --gone {name} --max 30; exit $?")
    assert r.returncode == 0, r.stdout
    assert time.time() - t0 < 5


def test_running_job_returns_10_at_the_cap(tmp_path):
    name = f"longjob_{uuid.uuid4().hex[:8]}"
    script = tmp_path / f"{name}.sh"
    script.write_text("sleep 60\n")
    p = subprocess.Popen(["bash", str(script)])
    try:
        r = run("bash", WAITFOR, "--gone", name, "--max", "1", timeout=40)
        assert r.returncode == 10
        assert r.stdout.startswith("RUNNING")
    finally:
        p.kill()


def test_gone_reports_done_when_job_exits(tmp_path):
    name = f"shortjob_{uuid.uuid4().hex[:8]}"
    script = tmp_path / f"{name}.sh"
    script.write_text("sleep 2\n")
    p = subprocess.Popen(["bash", str(script)])
    try:
        r = run("bash", WAITFOR, "--gone", name, "--max", "30", timeout=40)
        assert r.returncode == 0
        assert r.stdout.startswith("DONE")
    finally:
        p.kill()


def test_anchored_regex_still_sees_a_live_job(tmp_path):
    # bracketing the first character of "^bash ..." would break the regex and report a live job as gone
    name = f"anchored_{uuid.uuid4().hex[:8]}"
    script = tmp_path / f"{name}.sh"
    script.write_text("sleep 60\n")
    p = subprocess.Popen(["bash", str(script)])
    try:
        time.sleep(0.5)
        r = run("bash", WAITFOR, "--gone", f"^bash .*{name}", "--max", "0", timeout=20)
        assert r.returncode == 10, r.stdout + r.stderr
    finally:
        p.kill()


def test_leading_dot_pattern_still_sees_a_live_job(tmp_path):
    # "." is a regex wildcard: bracketing it as "[.]" would only match a literal dot and miss "xreview_..."
    tag = uuid.uuid4().hex[:8]
    script = tmp_path / f"xreview_{tag}.sh"
    script.write_text("sleep 60\n")
    p = subprocess.Popen(["bash", str(script)])
    try:
        time.sleep(0.5)
        r = run("bash", WAITFOR, "--gone", f".review_{tag}", "--max", "0", timeout=20)
        assert r.returncode == 10, r.stdout + r.stderr
    finally:
        p.kill()


def test_invalid_pattern_is_an_error_not_done():
    r = run("bash", WAITFOR, "--gone", "(unclosed", "--max", "5")
    assert r.returncode == 2
    assert "ERROR" in r.stderr


def test_wait_is_bounded_by_max(tmp_path):
    t0 = time.time()
    r = run("bash", WAITFOR, "--file", tmp_path / "never.txt", "--max", "2", timeout=20)
    assert r.returncode == 10
    assert time.time() - t0 < 5


def test_bad_arguments_exit_2():
    assert run("bash", WAITFOR).returncode == 2
    assert run("bash", WAITFOR, "--nope").returncode == 2
    assert run("bash", WAITFOR, "--gone").returncode == 2
    assert run("bash", WAITFOR, "--log", "only-one-arg").returncode == 2
    assert run("bash", WAITFOR, "--file", "x", "--max", "soon").returncode == 2
