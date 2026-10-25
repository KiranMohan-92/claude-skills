"""Record each review round and enforce the stop rule, so review loops end on evidence, not on fatigue.

usage:
  python review_loop.py record --ledger LEDGER.jsonl --output REVIEW.md [--new N]
  python review_loop.py status --ledger LEDGER.jsonl

record reads the reviewer's final message, whose last non-empty line must be exactly "VERDICT: ship" or
  "VERDICT: fix first" (a verdict quoted from an earlier round, or one followed by more text, doesn't count).
  --new is how many findings are new this round (not repeats of earlier ones); the lead decides. Without it,
  the count of lines naming a P1 or P2 is used.
Exit codes for record:
  0  ship
  1  fix first: fix and run another round
  3  fix first, and the next round will be round 4 or later: its brief must be PINNED to the open findings plus
     new factual errors only
  4  STOP: three fix-first rounds in a row each found something new. Re-scope or ask the user; don't run round N+1
  2  usage, or no verdict line (an empty or verdict-less review is a failure, never "no findings")
"""
import argparse
import json
import re
import sys
from pathlib import Path

VERDICT = re.compile(r"VERDICT:\s*(ship|fix first)", re.I)


def final_verdict(text):
    """The verdict is the whole final non-empty line, unquoted: 'VERDICT: ship' or 'VERDICT: fix first'.
    A verdict quoted from an earlier round, or followed by more text, doesn't count."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    m = VERDICT.fullmatch(lines[-1].strip("*_ "))
    return m.group(1).lower() if m else None
FINDING = re.compile(r"\bP[12]\b")
STOP_AFTER = 3
PIN_FROM = 4


def read_ledger(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def record(ledger, output, new=None):
    text = Path(output).read_text(encoding="utf-8", errors="replace") if Path(output).exists() else ""
    verdict = final_verdict(text)
    if verdict is None:
        print(f"NO VERDICT on the last line of {output} ({len(text)} bytes): treat as a failed review and re-run it")
        return 2
    if new is None:
        new = sum(1 for line in text.splitlines() if FINDING.search(line)) if verdict == "fix first" else 0
    rounds = read_ledger(ledger)
    entry = {"round": len(rounds) + 1, "verdict": verdict, "new": new}
    rounds.append(entry)
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"round {entry['round']}: {verdict}, {new} new finding(s)")
    if verdict == "ship":
        return 0
    last = rounds[-STOP_AFTER:]
    if len(last) == STOP_AFTER and all(r["verdict"] == "fix first" and r["new"] > 0 for r in last):
        print(f"STOP: {STOP_AFTER} fix-first rounds in a row each found something new. "
              "The scope is too big or the approach is wrong: re-scope, or ask the user.")
        return 4
    if entry["round"] + 1 >= PIN_FROM:
        print(f"PIN the next brief (round {entry['round'] + 1}): open findings plus new factual errors only.")
        return 3
    return 1


def status(ledger):
    rounds = read_ledger(ledger)
    if not rounds:
        print("no rounds recorded")
        return 0
    for r in rounds:
        print(f"round {r['round']}: {r['verdict']}, {r['new']} new")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--ledger", required=True)
    rec.add_argument("--output", required=True)
    rec.add_argument("--new", type=int)
    st = sub.add_parser("status")
    st.add_argument("--ledger", required=True)
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    if a.cmd == "record":
        if a.new is not None and a.new < 0:
            print("--new must be >= 0", file=sys.stderr)
            return 2
        return record(a.ledger, a.output, a.new)
    return status(a.ledger)


if __name__ == "__main__":
    sys.exit(main())
