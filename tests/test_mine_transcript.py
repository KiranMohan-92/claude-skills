"""mine_transcript.py on synthetic transcripts."""
import json
import os
import time

import mine_transcript as M


def write(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return path


def user(t, text):
    return {"type": "user", "timestamp": t, "message": {"content": text}}


def test_counts_nudges_errors_and_skips_notifications(tmp_path):
    p = write(tmp_path / "s.jsonl", [
        user("2026-10-20T09:00:00Z", "render the 4K please"),
        {"type": "assistant", "timestamp": "2026-10-20T09:00:05Z",
         "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}]}},
        {"type": "user", "timestamp": "2026-10-20T09:00:06Z", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "Exit code 127 bash: x: not found"}]}},
        user("2026-10-20T09:30:00Z", "<task-notification>\n<status>completed</status>\n</task-notification>"),
        user("2026-10-20T09:40:00Z", "And?"),
        user("2026-10-20T09:50:00Z", "ok im waiting"),
        user("2026-10-20T10:00:00Z", "the clip at 4:53 has wrong hand dynamics please fix it."),
        user("2026-10-20T10:05:00Z", "[Request interrupted by user]"),
    ])
    users, errors, interrupts, tools = M.mine([p])
    assert [m for _, m in users][0] == "render the 4K please"
    assert not any("task-notification" in m for _, m in users)
    assert len(errors) == 1 and errors[0][1] == "Bash"
    assert len(interrupts) == 1
    md = M.digest(users, errors, interrupts, tools)
    assert "status nudges: 2" in md
    assert "wrong hand dynamics" in md.split("## Corrections")[1]
    assert "1x Bash" in md


def test_main_writes_file(tmp_path):
    p = write(tmp_path / "s.jsonl", [user("2026-10-20T09:00:00Z", "hello")])
    out = tmp_path / "d.md"
    assert M.main([str(p), "--out", str(out)]) == 0
    assert "user messages: 1" in out.read_text(encoding="utf-8")


def test_default_discovery_reads_project_folders_and_skips_old_files(tmp_path):
    fresh = write(tmp_path / "proj-a" / "fresh.jsonl", [user("2026-10-20T09:00:00Z", "from project a")])
    old = write(tmp_path / "proj-b" / "old.jsonl", [user("2026-10-01T09:00:00Z", "stale")])
    week_ago = time.time() - 7 * 86400
    os.utime(old, (week_ago, week_ago))
    out = tmp_path / "d.md"
    assert M.main(["--project-dir", str(tmp_path), "--since", "24", "--out", str(out)]) == 0
    md = out.read_text(encoding="utf-8")
    assert "from project a" in md and "stale" not in md
    assert fresh.exists()


def test_no_transcripts_returns_1(tmp_path):
    assert M.main(["--project-dir", str(tmp_path)]) == 1


def turn(t, text, **fields):
    e = user(t, text)
    e.update(fields)
    return e


def test_automated_prompts_are_not_user_messages(tmp_path):
    # shapes taken from real transcripts: desktop turns carry turnOrigin, SDK runs and agent messages don't say "human"
    p = write(tmp_path / "s.jsonl", [
        turn("2026-10-25T09:00:00Z", "please fix the wrong colours", entrypoint="claude-desktop", turnOrigin="human"),
        turn("2026-10-25T09:01:00Z", "Lane 3 finished: fix the wrong import", entrypoint="claude-desktop", turnOrigin="peer"),
        turn("2026-10-25T09:02:00Z", "Background task finished", entrypoint="claude-desktop", turnOrigin="task_notification"),
        turn("2026-10-25T09:03:00Z", "Warmup", isSidechain=True),
        turn("2026-10-25T09:04:00Z", "old-format message, no origin fields"),
    ])
    stats = {}
    users, *_ = M.mine([p], stats=stats)
    assert [m for _, m in users] == ["please fix the wrong colours", "old-format message, no origin fields"]
    assert stats["automated_prompts"] == 3


def test_automated_session_is_skipped_whole(tmp_path):
    review = write(tmp_path / "review.jsonl", [
        turn("2026-10-25T10:00:00Z", "Review this change for security vulnerabilities. Fix anything wrong.",
             entrypoint="sdk-py", promptSource="sdk", turnOrigin="sdk"),
        {"type": "assistant", "timestamp": "2026-10-25T10:00:05Z",
         "message": {"content": [{"type": "tool_use", "id": "r1", "name": "Bash", "input": {}}]}},
        {"type": "user", "timestamp": "2026-10-25T10:00:06Z", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "r1", "is_error": True, "content": "Exit code 1"}]}},
        turn("2026-10-25T10:01:00Z", "follow-up, no origin field", entrypoint="sdk-py"),
    ])
    real = write(tmp_path / "real.jsonl", [turn("2026-10-25T11:00:00Z", "And?", turnOrigin="human")])
    stats = {}
    users, errors, _, tools = M.mine([review, real], stats=stats)
    assert [m for _, m in users] == ["And?"]
    assert errors == [] and sum(tools.values()) == 0
    assert stats == {"automated_prompts": 2, "automated_sessions": 1}
    md = M.digest(users, errors, [], tools, stats=stats)
    assert "status nudges: 1 (100% of user messages)" in md
    corrections_section = md.split("## Corrections")[1].split("\n## ")[0]
    assert "- none" in corrections_section  # the review prompt's "Fix anything wrong" is not a correction


def test_include_automated_keeps_them(tmp_path):
    p = write(tmp_path / "s.jsonl", [turn("2026-10-25T10:00:00Z", "Review this change", entrypoint="sdk-py", turnOrigin="sdk")])
    users, *_ = M.mine([p], include_automated=True)
    assert len(users) == 1
    out = tmp_path / "d.md"
    assert M.main([str(p), "--include-automated", "--out", str(out)]) == 0
    assert "user messages: 1" in out.read_text(encoding="utf-8")
