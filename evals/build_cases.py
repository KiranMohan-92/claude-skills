"""Generate the eval cases in this folder from one table, so every case has the same shape.

Should-trigger cases are built from logged failures (the `source` line names the failure-log entry); the
near-miss negatives are designed, and their `source` line says what they are a near miss of.
- should-trigger cases: a with-only `tool_used: Skill` indicator (not scored) plus an `llm` outcome grader
  scored in both arms, so the with-minus-without delta is what the skill contributed.
- should-not-trigger cases (incl. near-misses): `tool_used: Skill` with min 0 / max 0 and `arm: both`, so a
  false trigger lowers the score.

Run:  python evals/build_cases.py   (rewrites evals/<case>/; does not touch evals/results/)
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUFFIX = "\n\nDon't run any commands. Answer in under 200 words: what you'd do and why."

CASES = [
    # ---- media-delivery-gates ----
    dict(name="mdg-skipped-gate-before-upload", skill="media-delivery-gates", kind="trigger",
         source="2026-10-20: encoded MP4 measured +0.6 dBTP (WAV master at -2.4); nearly delivered",
         prompt="I re-mastered the WAV so it peaks at -2.4 dBTP and rendered final.mp4 with AAC 320k. My render "
                "script normally runs a loudness gate at the end, but it stopped early when I killed the optional "
                "phone-size encode. The WAV is fine, so can I upload final.mp4 to YouTube now?",
         criteria="PASS only if the answer refuses to call the file ready yet, says the gate must run on the ENCODED "
                  "final.mp4 rather than the WAV master (AAC encoding can push true peak above the WAV's), and treats "
                  "the skipped end-of-script gate as not having run. Mentioning a true-peak limit around -1 dBTP is a "
                  "plus. FAIL if it approves the upload based on the WAV's peak."),
    dict(name="mdg-remux-ready-claim", skill="media-delivery-gates", kind="trigger",
         source="2026-10-20: delivery incident; the gate belongs on every re-render and remux",
         prompt="I just remuxed the trailer with a new audio mix (video stream copied). Please confirm it's ready "
                "to send to the client.",
         criteria="PASS only if the answer does not confirm readiness without checking the new file, and names "
                  "concrete checks on the remuxed file: A/V sync or stream start/duration, loudness and true peak "
                  "after encoding, and a look at the changed section. FAIL if it simply confirms it's ready."),
    dict(name="mdg-overshoot-fix", skill="media-delivery-gates", kind="outcome",
         source="2026-10-20: AAC overshoot 3 dB over the WAV; encoder flags were unreliable fixes",
         prompt="My gate says the encoded MP4 has a true peak of +0.6 dBTP, but the WAV master peaks at -2.4. I'm "
                "planning to fix it by changing the AAC encoder's cutoff and bitrate. Good plan?",
         criteria="PASS only if the answer steers away from encoder-flag tweaking as the main fix and recommends "
                  "re-mastering the audio with a lower ceiling (around -3 dBTP or lower) and remuxing with the video "
                  "stream copied (no video re-encode), then re-running the gate on the new file."),
    dict(name="mdg-frame-count-shortest", skill="media-delivery-gates", kind="outcome",
         source="2026-10-20: -shortest trims the final frame to the audio",
         prompt="The edit decision list totals 4,800 frames. The gate on the final encode reports 4,799 frames. I "
                "encoded with ffmpeg -shortest. Is this a failed delivery?",
         criteria="PASS only if the answer says one frame fewer is expected and acceptable with -shortest (it trims "
                  "the last frame to the audio length) and should be noted in the report rather than treated as a "
                  "failure. FAIL if it says the delivery failed or must be re-rendered for this alone."),
    dict(name="mdg-gate-in-pipeline", skill="media-delivery-gates", kind="outcome",
         source="2026-09-30: red gate committed and pushed (pipeline exit status)",
         prompt="My release step is: bash gate_deliverable.sh out.mp4 | tail -3 && rclone copy out.mp4 remote:final/ "
                ". Last night a file that failed the gate still got copied. Why?",
         criteria="PASS only if the answer explains that a pipeline's exit status is the last command's (tail), so "
                  "&& never sees the gate's failure, and fixes it by running the gate on its own and testing its "
                  "exit code, or with set -o pipefail."),
    dict(name="mdg-neg-lufs-question", skill="media-delivery-gates", kind="negative",
         source="near-miss: audio vocabulary without a deliverable",
         prompt="What is LUFS, and how is it different from RMS level? Keep it short."),
    dict(name="mdg-neg-resize-pngs", skill="media-delivery-gates", kind="negative",
         source="near-miss: media files but no rendered deliverable",
         prompt="I have a folder of PNG screenshots. What's a quick ImageMagick command to resize them all to 1280 px "
                "wide?"),
    # ---- win-wsl-shell ----
    dict(name="wsl-msys-var-path", skill="win-wsl-shell", kind="trigger",
         source="2026-10-24: Git Bash to WSL `VAR=/path` argument mangled",
         prompt="From the Git Bash tool on Windows I ran: wsl -d Ubuntu -- bash -lc 'B=\"/mnt/c/work/paper\"; cd "
                "\"$B/latex\" && pdflatex main.tex; ls' and got 'cd: /latex: No such file or directory'. Then pdflatex "
                "wrote texput.log into my current Windows folder. What went wrong?",
         criteria="PASS only if the answer identifies that $B arrived empty because of the quoting or Git Bash (MSYS) "
                  "argument handling between Git Bash and wsl.exe, AND that the later ';'-separated commands still ran "
                  "in the wrong directory because only the cd was guarded. It should suggest a script file run inside "
                  "WSL (or MSYS_NO_PATHCONV=1) and making a failed cd stop the script."),
    dict(name="wsl-sed-crlf-diff", skill="win-wsl-shell", kind="trigger",
         source="2026-10-25: `sed -i` in Git Bash rewrote a CRLF file's line endings",
         prompt="On my Windows checkout I want to change one line in backend/templates/report.html with sed -i from "
                "Git Bash, then send the git diff to a reviewer. Any risk?",
         criteria="PASS only if the answer warns that sed -i in Git Bash can rewrite the file's CRLF line endings so "
                  "the diff shows every line changed, and recommends a newline-preserving edit (an editor/Edit tool, or "
                  "Python with newline='') plus checking git diff --stat before sending the diff."),
    dict(name="wsl-pgrep-self-match", skill="win-wsl-shell", kind="trigger",
         source="2026-10-20: a wait loop matched its own command line",
         prompt="Inside WSL I wait for a render with: bash -c 'while pgrep -f render_v5.sh; do sleep 5; done; echo "
                "done'. The render finished ten minutes ago but the loop never ends. Why?",
         criteria="PASS only if the answer explains that pgrep -f matches the waiting shell's own command line (which "
                  "contains render_v5.sh), and fixes it with the bracket trick (pgrep -f '[r]ender_v5.sh') or a wait "
                  "helper that excludes its own process ancestry."),
    dict(name="wsl-heredoc-quotes", skill="win-wsl-shell", kind="outcome",
         source="2026-10-03: bash heredocs with quote sequences broke patch scripts",
         prompt="I want one Bash tool call that writes a Python patch script via a heredoc (the script has ''' "
                "docstrings and f-strings with nested quotes) and then runs it in WSL. How should I do it?",
         criteria="PASS only if the answer recommends writing the script to a file with a file-writing tool (not a "
                  "shell heredoc) and then running the file, explaining that the heredoc passes through the tool's "
                  "own quoting so quote sequences can end it early or truncate it."),
    dict(name="wsl-df-vhdx", skill="win-wsl-shell", kind="outcome",
         source="2026-10-16: fresh render died ENOSPC on C: although output went to WSL",
         prompt="WSL's df says I have 900 GB free, so I'll write 60 GB of render intermediates inside WSL even though "
                "Windows C: is nearly full. That avoids the C: problem, right?",
         criteria="PASS only if the answer says no (or not necessarily): WSL's disk is a .vhdx file stored on a "
                  "Windows drive (C: by default), df shows the virtual disk's size rather than physical free space, "
                  "and writing inside WSL still consumes space on the drive holding the .vhdx, so check that "
                  "drive's real free space first."),
    dict(name="wsl-neg-linux-port", skill="win-wsl-shell", kind="negative",
         source="near-miss: Linux shell question with no Windows or WSL involved",
         prompt="On my Ubuntu server, how do I find which process is listening on port 8080?"),
    dict(name="wsl-neg-powershell-list", skill="win-wsl-shell", kind="negative",
         source="near-miss: Windows shell question that never crosses into WSL",
         prompt="Give me a PowerShell one-liner that lists the five largest files in my Downloads folder."),
    # ---- long-job-updates ----
    dict(name="lju-start-contract", skill="long-job-updates", kind="trigger",
         source="2026-10-20 retro: the user chased status 10 times in one session",
         prompt="Kick off the 4K upscale of 6 clips in the background. Last run took about 12 minutes per clip. "
                "Before you start, tell me how this will go.",
         criteria="PASS only if the answer gives an up-front plan with: the steps, an ETA based on the measured "
                  "~12 min/clip (about 72 min total, ideally a clock finish time), when the user will next hear from "
                  "it (a check-in cadence), and what happens if a clip fails. FAIL if it only says it will start "
                  "and report back when done."),
    dict(name="lju-and-nudge", skill="long-job-updates", kind="trigger",
         source="2026-10-20 retro: 13% of user messages were 'And?' or 'ok im waiting'",
         prompt="Context: 40 minutes ago you started a background batch of 200 image generations, expected to take "
                "about 90 minutes; it logs progress lines like 'done 87/200' to gen.log. The user now writes: "
                "\"And?\" What do you reply?",
         criteria="PASS only if the reply leads immediately with a concrete status (e.g. how many of 200 are done, or "
                  "that it will read gen.log for the count), an updated finish time, and when the next update comes. "
                  "FAIL if it asks the user what they mean or gives no status."),
    dict(name="lju-scrape-incremental", skill="long-job-updates", kind="outcome",
         source="2026-10-24: description scrape stalled with no output after ~25 min",
         prompt="Plan a script that fetches 212 job descriptions from a rate-limited site, 2.5 s apart, and saves "
                "the results. It will run in the background for about 10 minutes.",
         criteria="PASS only if the plan writes results incrementally (not only at the end), reports progress while "
                  "running, caps retries or backs off on rate-limit errors, and tests the parser on one known item "
                  "before the full batch. At least three of these four must be explicit."),
    dict(name="lju-blocking-sleep", skill="long-job-updates", kind="outcome",
         source="2026-10-20: blocked sleeps and fixed waits during long renders",
         prompt="The render will take about 40 minutes. I'll just run `sleep 2400; tail render.log` in one tool "
                "call and check at the end. OK?",
         criteria="PASS only if the answer advises against one long blocking sleep, and suggests running the job in "
                  "the background with bounded, repeated waits (a wait-until-done helper or monitor) that allow "
                  "check-ins and catching failures early."),
    dict(name="lju-neg-quick-tests", skill="long-job-updates", kind="negative",
         source="near-miss: a job, but a short one",
         prompt="Run my unit tests (they take about 8 seconds) and tell me whether they pass. If you can't run them, "
                "just tell me the command you'd use for pytest."),
    dict(name="lju-neg-nohup", skill="long-job-updates", kind="negative",
         source="near-miss: background-process vocabulary, no job to track",
         prompt="Explain the difference between nohup and setsid in two sentences."),
    # ---- daily-retro ----
    dict(name="retro-end-of-day", skill="daily-retro", kind="trigger",
         source="2026-10-20: the retro that produced these skills",
         prompt="Long day. Let's do a retro on today's Claude Code sessions: what went wrong, how could we both do "
                "better, and which skills should we build? Outline how you'll approach it.",
         criteria="PASS only if the outline mines the session transcripts with a script or digest (not by reading "
                  "whole transcripts), diagnoses friction by cause (clustering repeated symptoms), proposes "
                  "improvements for both the user and the assistant, and gives each fix one home (skill, rule or "
                  "memory) as drafts for the user to review."),
    dict(name="retro-build-skills", skill="daily-retro", kind="trigger",
         source="2026-10-20: one retro produced 7 skills; 2026-10-24/25 repeated shell-quoting failures",
         prompt="We hit the same shell-quoting errors again today. Build skills from this session so it doesn't "
                "happen tomorrow. How will you go about it?",
         criteria="PASS only if the plan grounds the fixes in evidence from the session transcripts, checks existing "
                  "skills first and sharpens one rather than adding a near-duplicate, tests any scripts it writes, "
                  "and presents the result as drafts for the user to keep, change or drop."),
    dict(name="retro-pasted-secret", skill="daily-retro", kind="outcome",
         source="2026-10-20 retro gotcha: transcripts can contain pasted secrets",
         prompt="Do a retro of today's session and write it up as RETRO notes I can share with a colleague. Heads "
                "up: at one point I pasted an API key into the chat.",
         criteria="PASS only if the answer commits to keeping the key out of the retro notes (refer to it only as "
                  "'a key pasted in chat' or similar, never the value) and still describes a transcript-based "
                  "retro. Recommending the key be rotated is a plus. FAIL if it proposes quoting the key or "
                  "including raw transcript excerpts without redaction."),
    dict(name="retro-neg-team-template", skill="daily-retro", kind="negative",
         source="near-miss: 'retro' meaning a team ceremony",
         prompt="Write a short sprint retrospective template my team can paste into Confluence."),
    dict(name="retro-neg-git-summary", skill="daily-retro", kind="negative",
         source="near-miss: reviewing the past week, but from git rather than sessions",
         prompt="Summarise what changed in this repository's git history over the last week. Which command would "
                "you use?"),
]


def fm(d):
    lines = ["---"]
    for k, v in d.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def skill_regex(skill):
    return "'" + r'"skill"\s*:\s*"(?:[\w-]+:)?' + skill + '"' + "'"


def build():
    for old in HERE.iterdir():
        if old.is_dir() and old.name != "results":
            shutil.rmtree(old)
    for c in CASES:
        d = HERE / c["name"]
        (d / "graders").mkdir(parents=True)
        tags = f"[{c['skill']}, {c['kind']}]"
        meta = {"description": f"\"{c['kind']} case for {c['skill']}. Source: {c['source']}\"",
                "tags": tags, "max_turns": 6, "allowed_tools": "[Read, Glob, Grep, Skill]"}
        if c["kind"] != "negative":
            meta["expected_outcome"] = f"\"{c['criteria'][:180]}...\""
        (d / "prompt.md").write_text(fm(meta) + "\n\n" + c["prompt"] + SUFFIX + "\n", encoding="utf-8", newline="\n")
        if c["kind"] == "negative":
            (d / "graders" / "skill-not-fired.md").write_text(
                fm({"type": "tool_used", "tool": "Skill", "input_match": skill_regex(c["skill"]),
                    "min": 0, "max": 0, "arm": "both"}) + "\n\nThe skill must not fire on this near-miss.\n",
                encoding="utf-8", newline="\n")
        else:
            (d / "graders" / "skill-fired.md").write_text(
                fm({"type": "tool_used", "tool": "Skill", "input_match": skill_regex(c["skill"]),
                    "arm": "with-only"}) + "\n\nIndicator only: did the skill fire? Not part of the score.\n",
                encoding="utf-8", newline="\n")
            (d / "graders" / "outcome.md").write_text(
                fm({"type": "llm", "weight": 1}) + "\n\n" + c["criteria"] + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(CASES)} cases")


if __name__ == "__main__":
    build()
