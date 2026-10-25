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
