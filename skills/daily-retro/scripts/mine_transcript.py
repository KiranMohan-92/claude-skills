"""Mine Claude Code session transcripts (jsonl) into a friction digest for the daily retro.

usage:
  python -I mine_transcript.py [--project-dir DIR] [--since HOURS] [--out OUT.md] [FILE.jsonl ...]
With no files: every *.jsonl under --project-dir (default: all projects in ~/.claude/projects, one level deep)
modified in the last --since hours (default 24). Writes a markdown digest (default: stdout):
  - stats: user messages, tool calls, tool errors, nudges, interrupts
  - nudges: the user chasing status ("and?", "ok im waiting", "any update", "show me progress")
  - interrupts / rejections: where he stopped a tool call
  - corrections: messages that reject or redo work ("doesn't look", "wrong", "fix", "not what")
  - error signatures: tool errors clustered by tool + normalised first line
  - all user messages (trimmed) with timestamps, for the narrative
Task notifications, system reminders and continuation summaries are not counted as user messages.
"""
import argparse
import collections
import json
import re
import sys
import time
from pathlib import Path

NUDGE = re.compile(r"^\s*(and\??|ok,? ?i'?m waiting|any update\??|status\??|show me (some )?progress|"
                   r"ok can you show me some progress|still (running|waiting)\??|\?+)\s*[.!?]*\s*($|can you try again)",
                   re.I)
CORRECTION = re.compile(r"doesn'?t look|does not look|wrong|not what|weird|fix (it|this|that)|please fix|"
                        r"rectify|puppet|don'?t like|not like|instead|remove", re.I)
SKIP_PREFIX = ("<task-notification>", "<command-", "<local-command", "This session is being continued")


def text_of(content):
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text")


def mine(files):
    users, errors, interrupts = [], [], []
    tools = collections.Counter()
    ids = {}
    for f in files:
        for line in open(f, encoding="utf-8", errors="replace"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            msg = e.get("message") or {}
            t = (e.get("timestamp") or "")[:19].replace("T", " ")
            if e.get("type") == "assistant":
                for c in msg.get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        tools[c.get("name")] += 1
                        ids[c.get("id")] = c.get("name")
                continue
            if e.get("type") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, list) and any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error"):
                        body = c.get("content")
                        body = text_of(body) if isinstance(body, list) else str(body)
                        name = ids.get(c.get("tool_use_id"), "?")
                        if "rejected" in body or "interrupted" in body.lower():
                            interrupts.append((t, name, body[:160]))
                        errors.append((t, name, body.replace("\x00", "").strip()))
                continue
            txt = re.sub(r"<system-reminder>.*?</system-reminder>", "", text_of(content), flags=re.S).strip()
            if not txt or e.get("isMeta") or txt.startswith(SKIP_PREFIX):
                continue
            if txt.startswith("[Request interrupted"):
                interrupts.append((t, "user", txt))
                continue
            users.append((t, txt))
    return users, errors, interrupts, tools


def signature(name, body):
    first = body.splitlines()[0] if body else ""
    return name, re.sub(r"0x[0-9a-f]+|[0-9a-f]{8,}|\d+(\.\d+)?", "#", first)[:100]


def digest(users, errors, interrupts, tools):
    nudges = [(t, m) for t, m in users if NUDGE.match(m.strip().splitlines()[0] if m.strip() else "")]
    corrections = [(t, m) for t, m in users if CORRECTION.search(m) and (t, m) not in nudges]
    sig = collections.Counter(signature(n, b) for _, n, b in errors)
    out = ["# Session friction digest", "",
           f"- user messages: {len(users)}",
           f"- tool calls: {sum(tools.values())} ({', '.join(f'{k} {v}' for k, v in tools.most_common(6))})",
           f"- tool errors: {len(errors)}",
           f"- status nudges: {len(nudges)} ({(100 * len(nudges) / max(1, len(users))):.0f}% of user messages)",
           f"- interrupts/rejections: {len(interrupts)}", "", "## Nudges (user chasing status)"]
    out += [f"- [{t}] {m.splitlines()[0][:80]}" for t, m in nudges] or ["- none"]
    out += ["", "## Corrections (taste or instruction fixes)"]
    out += [f"- [{t}] {m[:220].replace(chr(10), ' ')}" for t, m in corrections] or ["- none"]
    out += ["", "## Interrupts / rejections"]
    out += [f"- [{t}] {n}: {b[:120]}" for t, n, b in interrupts] or ["- none"]
    out += ["", "## Tool error signatures (most frequent first)"]
    out += [f"- {v}x {n}: `{s}`" for (n, s), v in sig.most_common(25)] or ["- none"]
    out += ["", "## All user messages"]
    out += [f"- [{t}] {m[:400].replace(chr(10), ' / ')}" for t, m in users]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--project-dir", default=str(Path.home() / ".claude" / "projects"))
    ap.add_argument("--since", type=float, default=24.0, help="hours")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    files = [Path(f) for f in a.files]
    if not files:
        cutoff = time.time() - a.since * 3600
        root = Path(a.project_dir)
        files = sorted(p for p in [*root.glob("*.jsonl"), *root.glob("*/*.jsonl")] if p.stat().st_mtime >= cutoff)
    if not files:
        print("no transcripts found", file=sys.stderr)
        return 1
    md = digest(*mine(files))
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
        print(f"wrote {a.out} from {len(files)} transcript(s)")
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
