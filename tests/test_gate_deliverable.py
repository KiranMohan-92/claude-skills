"""The gate must FAIL a +0.6 dBTP clip (the incident) and PASS a clean one."""
import re

from conftest import SKILLS, make_clip, needs_ffmpeg, run

GATE = SKILLS / "media-delivery-gates" / "scripts" / "gate_deliverable.sh"
pytestmark = needs_ffmpeg


def gate(f, *args):
    return run("bash", GATE, f, *args)


def test_clean_clip_passes(tmp_path):
    f = make_clip(tmp_path / "clean.mp4", amplitude=0.125)  # 997 Hz at -18 dBFS: about -21 LUFS, -18 dBTP
    r = gate(f, "--frames", "100", "--lufs", "-21", "--lufs-tol", "1.5")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


def test_hot_clip_fails_on_true_peak_after_aac(tmp_path):
    # 1.085 full-scale sine: the AAC-encoded file measures about +0.6 dBTP, the over-the-ceiling incident
    f = make_clip(tmp_path / "hot.mp4", amplitude=1.085)
    r = gate(f, "--frames", "100", "--lufs", "-3.5", "--lufs-tol", "1.5")  # loudness on target: only the peak fails
    assert r.returncode == 1, r.stdout
    tp = float(re.search(r"true-peak=(-?[\d.]+) dBTP", r.stdout).group(1))
    assert 0.0 <= tp <= 1.5, tp
    assert "FAIL: true peak" in r.stdout
    assert "FAIL: loudness" not in r.stdout


def test_frame_count_off_by_one_is_a_note_not_a_failure(tmp_path):
    f = make_clip(tmp_path / "clip.mp4")
    r = gate(f, "--frames", "101", "--lufs", "-21", "--lufs-tol", "1.5")
    assert r.returncode == 0, r.stdout
    assert "-shortest trimmed the last frame" in r.stdout


def test_wrong_frame_count_fails(tmp_path):
    f = make_clip(tmp_path / "clip.mp4")
    r = gate(f, "--frames", "120", "--lufs", "-21", "--lufs-tol", "1.5")
    assert r.returncode == 1
    assert "frames 100, want 120" in r.stdout


def test_missing_audio_fails(tmp_path):
    f = make_clip(tmp_path / "silent.mp4", audio=False)
    r = gate(f, "--frames", "100")
    assert r.returncode == 1
    assert "no audio stream" in r.stdout


def test_corrupt_video_data_fails_even_though_metadata_looks_fine(tmp_path):
    f = make_clip(tmp_path / "clip.mp4")
    data = bytearray(f.read_bytes())
    start, end = len(data) * 3 // 10, len(data) * 7 // 10  # inside mdat: the header and moov stay intact
    data[start:end] = bytes((i * 151 + 7) % 256 for i in range(end - start))
    f.write_bytes(bytes(data))
    r = gate(f, "--frames", "100", "--lufs", "-21", "--lufs-tol", "30")
    assert r.returncode == 1, r.stdout
    assert "FAIL: decode errors" in r.stdout


def test_container_without_stream_durations_is_measured_from_packets(tmp_path):
    # Matroska stores no per-stream duration; 1 s of video against 3 s of audio must not pass as "in sync"
    f = tmp_path / "mismatch.mkv"
    r = run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=1",
            "-f", "lavfi", "-i", "aevalsrc=0.125*sin(2*PI*997*t):s=48000:d=3",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", f)
    assert r.returncode == 0, r.stderr
    g = gate(f, "--lufs", "-21", "--lufs-tol", "1.5")
    assert g.returncode == 1, g.stdout
    assert "differ by more than" in g.stdout


def test_matching_mkv_passes(tmp_path):
    f = tmp_path / "ok.mkv"
    r = run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=3",
            "-f", "lavfi", "-i", "aevalsrc=0.125*sin(2*PI*997*t):s=48000:d=3",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", f)
    assert r.returncode == 0, r.stderr
    g = gate(f, "--frames", "75", "--lufs", "-21", "--lufs-tol", "1.5")
    assert g.returncode == 0, g.stdout


def test_usage_errors_exit_2(tmp_path):
    assert run("bash", GATE).returncode == 2
    assert gate(tmp_path / "nope.mp4").returncode == 2
    f = make_clip(tmp_path / "clip.mp4")
    assert gate(f, "--bogus", "1").returncode == 2
    assert gate(f, "--frames").returncode == 2
