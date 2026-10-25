"""Packaging rules from STANDARDS.md that code can check: manifests, versions, changelogs, portability."""
import json
import re

import pytest
import yaml

from conftest import ROOT, SKILLS

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
SKILL_DIRS = sorted(p for p in SKILLS.iterdir() if p.is_dir())


def frontmatter(skill_dir):
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{skill_dir.name}: no frontmatter"
    return yaml.safe_load(m.group(1)), text[m.end():]


def test_plugin_and_marketplace_manifests_agree():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert SEMVER.match(plugin["version"])
    entries = {p["name"]: p for p in market["plugins"]}
    assert plugin["name"] in entries
    assert entries[plugin["name"]]["source"] == "."
    # plugin.json owns the version; a second copy in the marketplace entry would drift
    assert "version" not in entries[plugin["name"]]


def test_plugin_changelog_top_entry_is_the_current_version():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    top = re.search(r"^## (\d+\.\d+\.\d+)", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    assert top and top.group(1) == plugin["version"]


@pytest.mark.parametrize("skill", SKILL_DIRS, ids=lambda p: p.name)
def test_skill_metadata(skill):
    fm, body = frontmatter(skill)
    assert fm["name"] == skill.name
    version = str(fm["metadata"]["version"])
    assert SEMVER.match(version)
    assert fm.get("license") == "MIT"
    assert fm.get("compatibility"), "declare dependencies in `compatibility`"
    top = re.search(r"^## (\d+\.\d+\.\d+)", (skill / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    assert top and top.group(1) == version, "CHANGELOG top entry must match metadata.version"
    assert len(body.splitlines()) < 500
    assert "## Gotchas" in body


@pytest.mark.parametrize("skill", SKILL_DIRS, ids=lambda p: p.name)
def test_referenced_scripts_exist(skill):
    _, body = frontmatter(skill)
    for ref in set(re.findall(r"scripts/([\w.-]+\.(?:sh|py))", body)):
        assert (skill / "scripts" / ref).is_file(), f"{skill.name} references missing scripts/{ref}"


SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "results", ".venv"}


def text_files(*roots):
    """Every non-binary file under the roots, extensionless ones (LICENSE, .gitignore) included."""
    for root in roots:
        for p in root.rglob("*"):
            if p.is_file() and not SKIP_DIRS & set(p.relative_to(root).parts) and b"\0" not in p.read_bytes()[:8192]:
                yield p


def test_no_personal_paths_or_names_in_skills_evals_or_tests():
    banned = re.compile(r"C--Users|/c/Users/kiran|C:\\Users\\kiran|KnowledgeArchitect|kali-linux|\bKiran\b", re.I)
    hits = [f"{p.relative_to(ROOT)}:{i}" for p in text_files(SKILLS, ROOT / "evals", ROOT / "tests")
            if p.name != "test_structure.py"
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if banned.search(line)]
    assert not hits, hits


CREDENTIAL = re.compile(
    r"AKIA[0-9A-Z]{16}"                                  # AWS access key id
    r"|gh[pousr]_[A-Za-z0-9]{30,}"                       # GitHub tokens
    r"|github_pat_[A-Za-z0-9_]{30,}"
    r"|sk-(?:ant-|proj-)?[A-Za-z0-9_-]{24,}"             # Anthropic / OpenAI style keys
    r"|xox[abpr]-[A-Za-z0-9-]{10,}"                      # Slack tokens
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|(?i:(?:api[_-]?key|secret|password|token)\s*[=:]\s*['\"][^'\"\s]{12,}['\"])"
)


def credential_hits(root, exclude=("test_structure.py",)):
    return [f"{p.relative_to(root)}:{i}" for p in text_files(root) if p.name not in exclude
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
            if CREDENTIAL.search(line)]


def test_no_credentials_anywhere():
    hits = credential_hits(ROOT)
    assert not hits, hits


def test_credential_scan_finds_a_planted_key_in_an_extensionless_file(tmp_path):
    planted = 'API_KEY = "' + "sk-ant-" + "a1B2c3D4e5F6g7H8i9J0k1L2m3" + '"'
    (tmp_path / "NOTES").write_text("harmless\n" + planted + "\n", encoding="utf-8")
    (tmp_path / "ok.md").write_text("<task-notification>\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(planted, encoding="utf-8")  # .git is skipped
    assert credential_hits(tmp_path) == ["NOTES:2"]


def test_text_files_use_lf():
    crlf = [str(p.relative_to(ROOT)) for p in [*SKILLS.rglob("*"), *(ROOT / "evals").rglob("*")]
            if p.is_file() and p.suffix in {".md", ".sh", ".py", ".json", ".yaml"} and b"\r\n" in p.read_bytes()]
    assert not crlf, crlf


def test_eval_coverage_per_skill():
    """STANDARDS 2.3 and 5.1: per skill, >=3 should-trigger, >=2 near-miss negatives, >=2 scored outcome graders."""
    cases = [p for p in (ROOT / "evals").iterdir() if p.is_dir() and p.name != "results"]
    names = {p.name for p in SKILL_DIRS}
    count = {n: {"positive": 0, "negative": 0, "outcome_graders": 0} for n in names}
    for case in cases:
        fm = yaml.safe_load(re.match(r"^---\n(.*?)\n---\n", (case / "prompt.md").read_text(encoding="utf-8"), re.S).group(1))
        skill = set(fm["tags"]) & names
        assert len(skill) == 1, f"{case.name}: tag it with exactly one skill"
        c = count[skill.pop()]
        graders = [yaml.safe_load(re.match(r"^---\n(.*?)\n---", g.read_text(encoding="utf-8"), re.S).group(1))
                   for g in (case / "graders").glob("*.md")]
        assert graders, f"{case.name}: no graders"
        if "negative" in fm["tags"]:
            c["negative"] += 1
            skill_name = next(iter(set(fm["tags"]) & names))
            assert any(g["type"] == "tool_used" and g.get("tool") == "Skill" and skill_name in str(g.get("input_match", ""))
                       and g.get("min") == 0 and g.get("max") == 0 and g.get("arm") == "both" for g in graders), case.name
        else:
            c["positive"] += 1
            c["outcome_graders"] += sum(g["type"] == "llm" and g.get("arm", "both") == "both" for g in graders)
    for skill, c in count.items():
        assert c["positive"] >= 3 and c["negative"] >= 2 and c["outcome_graders"] >= 2, (skill, c)
