import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_gitattributes_forces_lf_for_scripts():
    text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    for line in ("*.sh text eol=lf", "*.py text eol=lf", "*.ps1 text eol=crlf"):
        assert line in text, line
    assert "*.md merge=union" in text


def test_tool_hooks_match_powershell_too():
    s = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    for entry in s["hooks"]["PreToolUse"]:
        if "Bash" in entry["matcher"]:
            assert "PowerShell" in entry["matcher"], entry["matcher"]


def test_windows_notify_is_a_toast():
    src = (ROOT / ".claude" / "skills" / "drive-screen" / "scripts" / "screenctl.py").read_text(encoding="utf-8")
    win = src[src.index('if OS == "Windows":'):src.index('elif OS == "Darwin":')]
    assert "ToastNotificationManager" in win and "powershell.exe" in win and "ToastText02" in win
    assert win.count("def notify(") == 1


def test_windows_toast_failure_is_not_reported_as_notified():
    src = (ROOT / ".claude" / "skills" / "drive-screen" / "scripts" / "screenctl.py").read_text(encoding="utf-8")
    toast = src[src.index("_TOAST = r"):src.index("def notify(", src.index("_TOAST = r"))]
    assert "$ErrorActionPreference = 'Stop'" in toast
    assert toast.index("$ErrorActionPreference = 'Stop'") < toast.index(".Show(") < toast.index("Asterisk.Play()")
