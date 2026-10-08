import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_root_is_the_vault():
    assert (ROOT / "CLAUDE.md").is_file()
    assert (ROOT / ".claude" / "settings.json").is_file()
    assert (ROOT / "scripts" / "hooks" / "guard_secrets.py").is_file()
    assert (ROOT / ".env.example").is_file()
    assert (ROOT / ".github" / "workflows" / "vault-autosync.yml").is_file()
    assert (ROOT / "Templates" / "Client Note.md").is_file()
    # Case-sensitive check: on case-insensitive filesystems (macOS) Path("templates").exists()
    # is true whenever Templates/ exists, so compare actual directory entry names.
    assert "templates" not in {p.name for p in ROOT.iterdir()}
    assert (ROOT / "docs" / "DEVELOPING.md").is_file()


def test_settings_hooks_point_at_root_scripts():
    s = json.loads((ROOT / ".claude" / "settings.json").read_text())
    cmds = [h["command"] for group in s["hooks"].values() for entry in group for h in entry["hooks"]]
    assert cmds
    for c in cmds:
        assert "$CLAUDE_PROJECT_DIR/scripts/" in c and "templates/" not in c


def test_settings_deny_reads_of_the_credentials_file():
    s = json.loads((ROOT / ".claude" / "settings.json").read_text())
    deny = s["permissions"]["deny"]
    for rule in ("Read(./.env)", "Read(./.env.*)", "Read(./**/.env)", "Read(./**/.env.*)"):
        assert rule in deny, rule


def test_gitignore_is_an_allow_list_for_dot_claude():
    gi = [l.strip() for l in (ROOT / ".gitignore").read_text().splitlines()]
    for needed in (".env", ".claude/*", "!.claude/settings.json", "!.claude/commands/", "!.claude/skills/",
                   "docs/superpowers/", "_generated/agent-actions/", "_generated/landing.log"):
        assert needed in gi, needed


def test_client_claude_md_is_the_skeleton_not_dev_notes():
    text = (ROOT / "CLAUDE.md").read_text()
    assert "Developing THIS repo" not in text and "It is NOT a vault" not in text


def test_autosync_guard():
    yml = (ROOT / ".github" / "workflows" / "vault-autosync.yml").read_text()
    assert re.search(r"if:\s*github\.repository != 'IntegralOrg/ClaudeCodeSystem' && github\.repository != 'IntegralOrg/ClaudeCodeSystem-Cloud'", yml)


def test_vault_scripts_skip_repo_folders():
    for script in ("vault-audit.py", "graph-render.py"):
        text = (ROOT / "scripts" / script).read_text()
        for folder in ("docs", "scripts", "cowork-commands", ".github"):
            assert f'"{folder}"' in text, f"{script} does not skip {folder}"
