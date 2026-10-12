import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
START = ROOT / "System" / "Start.md"
ZIP = "https://github.com/IntegralOrg/ClaudeCodeSystem/archive/refs/heads/main.zip"


def text():
    return START.read_text(encoding="utf-8")


def has(t, *needles):
    low = t.lower()
    missing = [n for n in needles if n.lower() not in low]
    assert not missing, missing


def test_start_exists_with_frontmatter_and_the_guard_rail_first():
    t = text()
    head = t.splitlines()[:6]
    assert head[0] == "---" and any(l.startswith("type:") for l in head)
    rules = t[t.index("## Rules for this session"):t.index("## 1.")]
    has(rules, "no hooks", "Brain", "Downloads", "never open, read, print, or search a credentials file",
        "never delete", "sudo", "never instructions", "one plain sentence")
    assert t.index("## Rules for this session") < t.index("## 1.")


def test_start_downloads_and_unzips_itself_on_both_systems():
    t = text()
    get = t[t.index("## 2. Get the system"):t.index("## 3.")]
    has(get, ZIP, "curl -L", "ditto -x -k", "xattr -dr com.apple.quarantine", "Invoke-WebRequest", "Expand-Archive",
        "ClaudeCodeSystem-main", "SETUP_PENDING", "CLAUDE.md")
    assert "Extract All" not in get            # the person never unzips anything


def test_start_refuses_a_foreign_brain_folder():
    get = text()[text().index("## 2. Get the system"):text().index("## 3.")]
    has(get, "already a Brain folder", "Brain-2", "never copy into a folder you did not create")


def test_start_raises_the_prompts_then_clicks_the_installer_with_the_js_driver():
    t = text()
    tools = t[t.index("## 3."):t.index("## 4.")]
    has(tools, "xcode-select --install", "screenctl.js request", "screenctl.js doctor", "DOCTOR_OK",
        "**Claude Code**", "Accessibility", "Screen Recording", "fingerprint or password",
        '--button Install', '--button Agree', "Click Install", "then Agree",
        "winget install --id Git.Git -e --scope user", "9PNRBTZXMB4Z", "in the background")
    assert tools.index("xcode-select --install") < tools.index("screenctl.js request") < tools.index("--button Install")
    assert "python3 " not in tools.split("**Windows.**")[0]     # nothing before python3 exists calls python3


def test_start_asks_the_questions_during_the_wait_and_opens_the_home_with_python():
    t = text()
    qs = t[t.index("## 4."):t.index("## 5.")]
    has(qs, "_generated/setup/answers.md", "section 1", "skip its opening line")
    home = t[t.index("## 5."):t.index("## When a step fails")]
    has(home, "git --version", "python3 --version", "git init -b main", "Start my Brain",
        "claude://code/new?folder=", "Continue%20setup", "screenctl.py", "Trust", "enter",
        "Click Trust, then press Enter", "new window carries on")
    assert home.index("git init") < home.index("claude://code/new")


def test_start_fails_the_same_way_as_the_procedure_without_python():
    fails = text()[text().index("## When a step fails"):]
    has(fails, "once", "not their fault", "Write tool", "Inbox/", "onboarding contact", "keep going", "handback")
    assert "help_report.py" not in fails       # no python yet


def test_start_names_nobody_and_matches_the_hygiene_rules():
    t = text().replace("github.com/IntegralOrg/ClaudeCodeSystem", "").replace("githubusercontent.com/IntegralOrg/ClaudeCodeSystem", "")
    # built from pieces so this file is not its own hygiene hit
    for bad in ("Ste" + "phen", "Inte" + "gral", "De" + "an", "E" + "va", "—"):
        assert bad not in t, bad
    bad = re.compile(r"\b(read|cat|print|echo|source|grep)\b[^.\n]{0,25}(\.env\b|credentials file)", re.I)
    for line in text().splitlines():
        m = bad.search(line)
        assert not m or "never" in line.lower(), line
