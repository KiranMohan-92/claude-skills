import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
needs_proc = pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="needs /proc (Linux or WSL)")


def run(*args, timeout=120, **kw):
    """Run a command and return CompletedProcess with text output (never raises on non-zero exit)."""
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=timeout, **kw)


def make_clip(path, amplitude=0.125, seconds=4, rate=25, audio=True):
    """A test video: testsrc picture plus a 997 Hz sine at `amplitude`, AAC 320k, like a real deliverable."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size=320x240:rate={rate}:duration={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"aevalsrc={amplitude}*sin(2*PI*997*t):s=48000:d={seconds}",
                "-c:a", "aac", "-b:a", "320k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    r = run(*cmd)
    assert r.returncode == 0, r.stderr
    return path


sys.path.insert(0, str(SKILLS / "daily-retro" / "scripts"))
