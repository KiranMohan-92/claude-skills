"""contact_sheet.sh and progress_sheet.sh produce tiled images of the expected size."""
import json

from conftest import SKILLS, make_clip, needs_ffmpeg, run

CONTACT = SKILLS / "media-delivery-gates" / "scripts" / "contact_sheet.sh"
PROGRESS = SKILLS / "long-job-updates" / "scripts" / "progress_sheet.sh"
pytestmark = needs_ffmpeg


def size(img):
    r = run("ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "json", img)
    s = json.loads(r.stdout)["streams"][0]
    return s["width"], s["height"]


def test_contact_sheet_tiles_the_range(tmp_path):
    v = make_clip(tmp_path / "v.mp4")
    out = tmp_path / "sheet.jpg"
    r = run("bash", CONTACT, v, out, "0", "2", "0.5", "4")
    assert r.returncode == 0, r.stderr
    assert "4 frames, 4x1" in r.stdout
    assert size(out) == (4 * 384, 288)


def test_contact_sheet_rounds_partial_steps_up(tmp_path):
    v = make_clip(tmp_path / "v.mp4")
    r = run("bash", CONTACT, v, tmp_path / "s.jpg", "0", "1.1", "0.5", "5")
    assert r.returncode == 0, r.stderr
    assert "3 frames" in r.stdout


def test_progress_sheet_tiles_one_frame_per_video(tmp_path):
    a = make_clip(tmp_path / "a.mp4")
    b = make_clip(tmp_path / "b.mp4")
    out = tmp_path / "progress.jpg"
    r = run("bash", PROGRESS, out, a, f"{b}:2.0")
    assert r.returncode == 0, r.stderr
    assert "2 frames" in r.stdout
    w, _ = size(out)
    assert w >= 2 * 960


def test_progress_sheet_rejects_missing_video(tmp_path):
    r = run("bash", PROGRESS, tmp_path / "p.jpg", tmp_path / "missing.mp4")
    assert r.returncode == 2


def test_contact_sheet_usage_errors_exit_2(tmp_path):
    assert run("bash", CONTACT).returncode == 2
    assert run("bash", CONTACT, tmp_path / "missing.mp4", tmp_path / "s.jpg", "0", "1", "0.5").returncode == 2
    assert run("bash", PROGRESS).returncode == 2
