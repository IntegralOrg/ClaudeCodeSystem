import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ["Setup Procedure", "How This Works", "Connecting Tools", "Routines", "Adding Your Computer", "Getting Help"]


def read(name):
    return (ROOT / "System" / f"{name}.md").read_text(encoding="utf-8")


def has(text, *needles):
    low = text.lower()
    missing = [n for n in needles if n.lower() not in low]
    assert not missing, missing


def test_all_system_docs_exist_with_frontmatter():
    for name in DOCS:
        p = ROOT / "System" / f"{name}.md"
        assert p.is_file(), name
        head = p.read_text(encoding="utf-8").splitlines()[:6]
        assert head and head[0] == "---" and any(l.startswith("type:") for l in head), name


def test_setup_procedure_covers_every_step():
    text = read("Setup Procedure")
    has(text, "Eva", "five questions", "CLAUDE.md", "System/routines", "check-keys.py", "SETUP_PENDING",
        "Adding Your Computer", "two-minute demo", "connect on your call", "cloud session", "local session",
        "not live", "first run", "environment")
    for line in text.splitlines():
        if "check-keys.py" in line:
            assert ".env" not in line, line


def test_setup_procedure_matches_the_hooks_and_routine_tools():
    text = read("Setup Procedure")
    has(text, "create_trigger", "persist_session", "## Owner", "email:", "Setup completed", "live_since: not live",
        "Work/Daily/", "Claude GitHub app")
    assert "scheduled-tasks" not in text
    # nowhere may the agent be told to open, read, cat, or print the credentials file
    bad = re.compile(r"\b(read|cat|print|echo|source|grep)\b[^.\n]{0,25}(\.env\b|credentials file)", re.I)
    for name in DOCS:
        for line in read(name).splitlines():
            m = bad.search(line)
            assert not m or "never" in line.lower(), (name, line)


def test_claude_md_support_rule_present():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    has(text, "Answering questions about this system", "System/", "what it is", "our recommendation", "the steps",
        "what changes afterwards", "drive the screen", "only when the session is local", "never improvise")
    has(text, "## Owner", "email:")
    assert "Setup repo check" not in text
    assert "ClaudeCodeSystem-Original" not in text


def test_connecting_tools_sections():
    text = read("Connecting Tools")
    for h in ["## Gmail", "## Google Calendar", "## Slack", "## Fathom", "## Claude plugins"]:
        assert h in text, h
    assert ("/" + "connect") not in text and "AskUserQuestion" not in text
    assert "check-keys.py" in text


def test_connect_steps_doc_is_gone_and_unreferenced():
    assert not (ROOT / "docs" / "connect-steps.md").exists()
    for p in [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]:
        assert "connect-steps" not in p.read_text(encoding="utf-8"), p.name


def test_adding_your_computer_order_and_content():
    text = read("Adding Your Computer")
    i_desktop = text.find("Claude Desktop"); i_ghd = text.find("GitHub Desktop"); i_open = text.find("Open the folder")
    assert 0 < i_desktop < i_ghd < i_open
    has(text, "~/Brain", "iCloud", "OneDrive", "Dropbox", "git --version", "Wispr Flow", "install.sh --vault",
        "Python 3", "Accessibility", "Screen Recording", "Superpowers", "Plugins", "~/.claude/settings.json", "claude -p")


def test_how_this_works_states_the_brakes_and_gaps():
    text = read("How This Works")
    has(text, "Bash", "guard", "merge=union", "fetch `System/` from the template", "landing.log")
    has(text, "landing_health", "routine_health", "on branch", "Work/Monthly/YYYY-MM-DD Monthly Review.md")


def test_routines_doc_has_the_manual_path():
    text = read("Routines")
    has(text, "Create a routine by hand", "environment", "GitHub app", "not live")
    has(text, "create_trigger", "persist_session", "Work/Monthly/YYYY-MM-DD Monthly Review.md")
    for title in ("End of Day", "Vault Hygiene", "Monthly Review"):
        assert f"## {title}\n- live_since: not live" in text, title


def test_public_repo_clean_of_internal_names():
    for name in DOCS:
        text = read(name)
        assert "Stephen" not in text and "Integral/" not in text, name
        if name != "Getting Help":
            assert "Integral" not in text, name
        if name != "Getting Help" and name != "Setup Procedure":
            assert "Dean" not in text and "Eva" not in text, name


def test_go_live_flip_edits_the_first_bullet_never_adds_one():
    for folder in (".claude/commands", "cowork-commands"):
        for name in ("eod", "vault-audit", "monthly-review"):
            text = (ROOT / folder / f"{name}.md").read_text(encoding="utf-8")
            assert "has no `live_since`" not in text, (folder, name)
            has(text, "change that same bullet", "never add a second live_since bullet")
    for p in (ROOT / "System" / "routines").glob("*.md"):
        text = p.read_text(encoding="utf-8")
        assert "has no `live_since`" not in text, p.name
        has(text, "never add a second live_since bullet")


def test_setup_procedure_is_safe_to_re_run():
    text = read("Setup Procedure")
    has(text, "list_triggers", "reuse it", "instead of creating a duplicate", "in place",
        "Create a routine by hand", "connector-missing", "persist_session: false",
        "Delete `SETUP_PENDING` now, so an interrupted hand-off never restarts setup")
    # order after the keys step: completion line, then marker deletion, then landing, then the demo
    keys = text.index("## 4. Keys")
    done = text.index("Setup completed <date>")
    gone = text.index("Delete `SETUP_PENDING` now")
    land = text.index("land-local.sh --final")
    demo = text.index("Two-minute demo")
    assert keys < done < gone < land < demo
    assert text.count("Delete `SETUP_PENDING`") == 1


def test_credentials_file_is_named_once_for_the_human_only():
    for name in ("Connecting Tools", "Setup Procedure"):
        has(read(name), "hidden file", "Command+Shift+Period", "The agent never opens it")
    has(read("Adding Your Computer"), "hidden", "Command+Shift+Period")
    has(read("Connecting Tools"), "update_trigger", "nothing after the `=`", "connector path")
    assert "never edits MCP server configuration" not in read("Connecting Tools")


def test_connecting_tools_keeps_the_original_walkthroughs():
    text = read("Connecting Tools")
    for h in ["## ClickUp", "## Rize", "## Other tools"]:
        assert h in text, h
    has(text, "mc_live_XXX", "clickup-mcp-server", "ENOTFOUND", "apt-get", "nodejs.org", "Download JSON",
        "already have a project", "organization policy", "rize.io", "Direct Connections", "Tools That Need Login Credentials")
    assert text.count('"mcpServers"') >= 3
