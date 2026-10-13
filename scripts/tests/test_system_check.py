"""scripts/system-check.py: how a vault is configured and whether it is working, from the vault alone.
A fixture vault carries the drift the check must find before a person does; a planted secret value must
never appear in anything the check writes or prints."""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "system-check.py"
TODAY = "2026-10-14"
SECRET = "zq7-" + "fixture-value-" + "4c1d9e8b7a6f5e43"  # a fake value; it must never be printed
GIT_ID = ["-c", "user.name=fixture", "-c", "user.email=fixture@example.com", "-c", "commit.gpgsign=false"]
SEVERITIES = {"blocks cloud", "local only", "fine"}


def load():
    spec = importlib.util.spec_from_file_location("system_check_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(root, *args, env=None):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run(["git", "-C", str(root), *GIT_ID, *args], capture_output=True, text=True, env=e)
    assert p.returncode == 0, p.stderr
    return p.stdout


def commit_all(root, message, date=None):
    git(root, "add", "-A")
    env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date} if date else None
    git(root, "commit", "-q", "-m", message, env=env)


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def base_vault(tmp_path):
    """A vault made from the template: the files the check reads, committed as the first commit."""
    root = tmp_path / "vault"
    root.mkdir()
    shutil.copytree(ROOT / "scripts", root / "scripts", ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "System", root / "System")
    shutil.copytree(ROOT / ".github", root / ".github")
    (root / ".claude").mkdir()
    shutil.copy(ROOT / ".claude" / "settings.json", root / ".claude" / "settings.json")
    for name in ("CLAUDE.md", "CHANGELOG.md", ".gitignore"):
        shutil.copy(ROOT / name, root / name)
    for i in range(1, 13):
        write(root, f"Notes/n{i:02d}.md", f"# Note {i}\n")
    for i in range(1, 13):
        write(root, f"Docs/d{i:02d}.md", f"# Doc {i}\n")
    write(root, "Notes/Plan.md", "# Plan\n")
    git(root, "init", "-q", "-b", "main")
    commit_all(root, "Initial commit", date="2026-09-01T12:00:00")
    return root


def plant_drift(root):
    # 1. a hook with an absolute home-folder path, carrying an inline secret value in its command
    s = json.loads((root / ".claude" / "settings.json").read_text())
    s["hooks"]["SessionStart"][0]["hooks"].append(
        {"type": "command", "command": f"FAKE_TOKEN={SECRET} python3 /Users/someone/bin/sync-helper.py", "timeout": 10})
    (root / ".claude" / "settings.json").write_text(json.dumps(s, indent=2))
    # 2. .mcp.json with one inline value and one placeholder
    write(root, ".mcp.json", json.dumps({"mcpServers": {
        "crm": {"command": "npx", "args": ["crm-mcp"], "env": {"CRM_TOKEN": SECRET}},
        "docs": {"type": "http", "url": "https://example.com/mcp", "headers": {"Authorization": "Bearer ${DOCS_TOKEN}"}}}}))
    # 3. the credentials file holds the same value (the check may read names, never values)
    write(root, ".e" + "nv", f"CRM_TOKEN={SECRET}\n")
    # 4. a stray script that reads its config from the home folder
    write(root, "scripts/my_sync.py", f'from pathlib import Path\nCONFIG = Path.home() / "config.json"\nTOKEN = "{SECRET}"\n')
    commit_all(root, "Session 1234abcd: land 2 file(s) (hook)")
    # 5. a landing commit that deleted 12 files
    for i in range(1, 13):
        (root / f"Notes/n{i:02d}.md").unlink()
    commit_all(root, "Session 1234abcd: land 12 file(s) (hook)")
    # 6. a cloud landing that rewrote 12 files the session never touched (its evidence names one)
    for i in range(1, 13):
        write(root, f"Docs/d{i:02d}.md", f"# Doc {i}\nolder text\n")
    commit_all(root, "Cloud session deadbeef: land 12 file(s), 0 deletion(s) (hook)")
    evidence(root, "deadbeef-0000-4000-8000-000000000001", "2026-10-13T10:00:00Z", [], files=["/home/user/vault/Docs/d01.md"])
    # 7. a refusal marker from a cloud session
    write(root, "_generated/landing/cloud-refusals/2026-10-12-abcdef12.json", json.dumps({
        "session_id": "abcdef12-0000", "reason": "no start snapshot: 3 deletion(s) refused, 0 change(s) landed",
        "refused_deletions": 3, "refused_changes": 0, "stale_at_start": 40, "sample": [f"Notes/{SECRET}.md"]}))
    # 8. three numbered copies beside a tracked file
    for n in (2, 3, 4):
        write(root, f"Notes/Plan {n}.md", "# Plan\n")
    # 9. a routine that declares Gmail, which the daily notes say is missing on three runs
    for d in ("2026-10-11", "2026-10-12", "2026-10-13"):
        write(root, f"Work/Daily/{d}.md", f"# {d}\n\n## Routine health\n- Vault Hygiene: OK\n- Connectors: Google Calendar connected, Gmail missing\n")
    # 10. a claude/* branch left behind for weeks
    git(root, "branch", "claude/old-work", git(root, "rev-list", "--max-parents=0", "HEAD").strip())
    # 11. friction in the journal: hook blocks, a few rate limits, and a private session that must not count
    evidence(root, "s-public-1", "2026-10-13T12:00:00Z",
             [{"name": "Bash", "ok": False, "error_class": "hook_blocked"}] * 4
             + [{"name": "mcp__fathom__list_meetings", "ok": False, "error_class": "HTTP 429"}] * 2
             + [{"name": "Read", "ok": True}])
    evidence(root, "s-private-1", "2026-10-13T13:00:00Z",
             [{"name": "WebFetch", "ok": False, "error_class": "HTTP 500"}] * 9, private=True)
    return root


def evidence(root, sid, ended, tools, files=None, private=False):
    rec = {"schema": "evidence/2", "session_id": sid, "project": "p", "cwd": "/home/user/vault", "started": ended, "ended": ended,
           "models": {"m": 1}, "turns": [{"i": 0, "t": ended, "role": "assistant", "tools": tools}],
           "tokens_by_model": {"m": {"input": 1, "output": 1, "cache_read": 0, "cache_creation": 0}},
           "files_touched": files or []}
    if private:
        rec["private"] = True
    write(root, f"_generated/system-journal/evidence/{ended[:7]}/{sid}.json", json.dumps(rec))


def run_check(root, *extra):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    p = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(root), "--today", TODAY, *extra],
                       capture_output=True, text=True, env=env, timeout=120)
    assert p.returncode == 0, p.stderr
    out = root / "_generated" / "system-check"
    data = json.loads((out / f"{TODAY}.json").read_text()) if (out / f"{TODAY}.json").is_file() else None
    md = (out / f"{TODAY}.md").read_text() if (out / f"{TODAY}.md").is_file() else ""
    return p, data, md


def by_id(data, prefix):
    return [f for f in data["findings"] if f["id"] == prefix or f["id"].startswith(prefix + ":")]


def test_planted_drift_is_found(tmp_path):
    root = plant_drift(base_vault(tmp_path))
    _, data, _ = run_check(root, "--template", str(ROOT))

    [hook] = by_id(data, "hook-outside-vault")
    assert hook["tier"] == 2 and hook["severity"] == "blocks cloud" and "sync-helper.py" in hook["title"]

    [mcp] = by_id(data, "mcp-inline-values")
    assert mcp["count"] == 1 and mcp["tier"] == 2 and mcp["paths"] == [".mcp.json"]

    [home] = by_id(data, "script-reads-outside-vault")
    assert home["paths"] == ["scripts/my_sync.py"] and "cloud" in home["detail"].lower()

    [stray] = by_id(data, "script-not-from-template")
    assert "scripts/my_sync.py" in stray["paths"] and "scripts/system-check.py" not in stray["paths"]

    [refusal] = by_id(data, "cloud-refusal")
    assert refusal["count"] == 1 and refusal["tier"] == 2 and refusal["severity"] == "blocks cloud"

    [deleted] = by_id(data, "landing-mass-deletion")
    assert deleted["count"] == 12 and deleted["tier"] == 2 and deleted["severity"] == "blocks cloud"

    [reverts] = by_id(data, "landing-untouched-changes")
    assert reverts["count"] == 11 and reverts["tier"] == 2

    [copies] = by_id(data, "numbered-copies")
    assert copies["count"] == 3 and copies["tier"] == 1 and all(re.search(r"Plan \d\.md$", p) for p in copies["paths"])

    [conn] = by_id(data, "connector-missing")
    assert conn["routine"] == "eod" and "Gmail" in conn["title"] and conn["count"] == 3 and conn["tier"] == 2

    [branches] = by_id(data, "stale-claude-branches")
    assert branches["count"] == 1

    [blocked] = by_id(data, "error-class:hook_blocked")
    assert blocked["count"] == 4 and blocked["tier"] == 1 and blocked["first"] == blocked["last"] == "2026-10-13"

    [rate] = by_id(data, "rate-limit:fathom")
    assert rate["count"] == 2 and rate["severity"] == "fine"

    assert data["problems"] == sum(1 for f in data["findings"] if f["severity"] != "fine") > 0
    assert data["template"] == "compared"


def test_planted_secret_value_never_appears(tmp_path):
    root = plant_drift(base_vault(tmp_path))
    for extra in ((), ("--template", str(ROOT)), ("--json",)):
        p, _, md = run_check(root, *extra)
        raw = (root / "_generated" / "system-check" / f"{TODAY}.json").read_text()
        for text in (p.stdout, p.stderr, raw, md):
            assert SECRET not in text
            assert "fixture-value" not in text


def test_summary_is_six_numbered_plain_lines_top_problems_first(tmp_path):
    root = plant_drift(base_vault(tmp_path))
    p, data, md = run_check(root)
    for text in (p.stdout, md):
        numbered = [l for l in text.splitlines() if re.match(r"^\d+\. ", l)]
        assert 1 <= len(numbered) <= 6
        assert chr(0x2014) not in text
        for line in numbered[:3]:
            assert "System/" in line and "Fix:" in line
    assert data["summary"] == [l for l in md.splitlines() if re.match(r"^\d+\. ", l)]
    blocking = [f for f in data["findings"] if f["severity"] == "blocks cloud"]
    assert blocking and data["summary"][0].startswith("1. ") and blocking[0]["title"] in data["summary"][0]


def test_every_finding_carries_severity_tier_fix_and_page(tmp_path):
    root = plant_drift(base_vault(tmp_path))
    _, data, _ = run_check(root)
    assert data["findings"]
    for f in data["findings"]:
        assert f["severity"] in SEVERITIES and f["tier"] in (1, 2), f
        assert f["page"].startswith("System/") and f["fix"], f
        assert chr(0x2014) not in json.dumps(f)


def test_tier2_package_is_names_and_counts_and_deduped(tmp_path):
    root = plant_drift(base_vault(tmp_path))
    _, data, _ = run_check(root)
    pkg = data["tier2_package"]
    assert pkg and all(set(item) <= {"reason", "routine", "error_class", "count", "first", "last", "paths", "due"} for item in pkg)
    assert all(item["due"] for item in pkg)
    reasons = {item["reason"] for item in pkg}
    assert "system-check:cloud-refusal" in reasons and "system-check:numbered-copies" not in reasons  # tier 1 stays home
    write(root, "_generated/routine-alerts.json", json.dumps({"system-check:cloud-refusal": "2026-10-12",
                                                             "system-check:landing-mass-deletion": "2026-10-01"}))
    _, data, _ = run_check(root)
    due = {i["reason"]: i["due"] for i in data["tier2_package"]}
    assert due["system-check:cloud-refusal"] is False and due["system-check:landing-mass-deletion"] is True


def test_private_sessions_are_never_counted(tmp_path):
    root = plant_drift(base_vault(tmp_path))
    _, data, _ = run_check(root)
    assert not by_id(data, "error-class:HTTP 500")
    assert "HTTP 500" not in json.dumps(data)


def test_rate_limits_are_fine_until_five_in_a_week(tmp_path):
    root = base_vault(tmp_path)
    evidence(root, "s-rl", "2026-10-13T12:00:00Z", [{"name": "WebFetch", "ok": False, "error_class": "HTTP 429"}] * 5)
    _, data, _ = run_check(root)
    [rate] = by_id(data, "rate-limit:WebFetch")
    assert rate["count"] == 5 and rate["severity"] != "fine"


def test_a_clean_vault_from_the_template_has_no_problems_in_its_setup(tmp_path):
    root = base_vault(tmp_path)
    _, data, _ = run_check(root, "--template", str(ROOT))
    noisy = [f for f in data["findings"] if f["severity"] != "fine"]
    assert not noisy, noisy
    assert data["problems"] == 0 and data["summary"] and len(data["summary"]) <= 6


def test_fails_open_on_an_empty_folder(tmp_path):
    _, data, _ = run_check(tmp_path)
    assert data is not None and isinstance(data["problems"], int)


def test_no_write_prints_without_writing(tmp_path):
    root = base_vault(tmp_path)
    p, data, _ = run_check(root, "--no-write")
    assert data is None and not (root / "_generated" / "system-check").exists()
    assert re.search(r"^1\. ", p.stdout, re.M)


def test_reuses_the_health_hooks_and_telemetry_instead_of_copying_them():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "import routine_health" in src and "import landing_health" in src and "telemetry-stats.py" in src
    for name in ("cloud_refusals", "refusal_markers", "disabled_note", "log_lines", "notices", "parse_routines", "problems",
                 "newest_audit_heading", "routine_health_lines", "daily_notes", "synced_service", "calls_of", "load_records"):
        assert not re.search(rf"^def {name}\(", src, re.M), name


def test_expected_hooks_match_the_template():
    mod = load()
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    assert set(mod.expected_hooks(settings)) == set(mod.EXPECTED_HOOKS)
    assert set(mod.EXPECTED_HOOK_FILES) == {p.name for p in (ROOT / "scripts" / "hooks").glob("*.py")}


def test_python_39_compatible_syntax():
    import ast
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src, feature_version=(3, 9))
    assert not any(isinstance(n, getattr(ast, "Match", ())) for n in ast.walk(tree))
    assert chr(0x2014) not in src


def _body(text):
    return text.split("---\n", 2)[2] if text.startswith("---\n") else text


def test_command_and_cowork_mirror():
    code = (ROOT / ".claude" / "commands" / "system-check.md").read_text(encoding="utf-8")
    cowork = (ROOT / "cowork-commands" / "system-check.md").read_text(encoding="utf-8")
    head = cowork.split("---")[1]
    assert re.search(r"^name: system-check$", head, re.M) and re.search(r"^description: .+", head, re.M)
    assert _body(cowork).lstrip("\n") == _body(code).lstrip("\n")
    for needle in ("scripts/system-check.py", "_generated/system-check/", "six", "help_report.py", "routine-alerts.json",
                   "Decision tiers", "list_triggers", "names and counts", "System/"):
        assert needle.lower() in code.lower(), needle
    assert chr(0x2014) not in code


def test_nightly_run_and_opportunity_scan_run_the_check():
    for folder in (".claude/commands", "cowork-commands"):
        audit = (ROOT / folder / "vault-audit.md").read_text(encoding="utf-8")
        assert "Step 0b" in audit and "scripts/system-check.py" in audit and "setup:" in audit
        scan = (ROOT / folder / "opportunity-scan.md").read_text(encoding="utf-8")
        assert re.search(r"^0\. .*scripts/system-check\.py", scan, re.M)
        eod = (ROOT / folder / "eod.md").read_text(encoding="utf-8")
        assert "Setup: N problems" in eod and "_generated/system-check/" in eod
