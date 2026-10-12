import re
import platform
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / ".claude" / "skills" / "drive-screen" / "scripts" / "screenctl.js"
COMMANDS = ["doctor", "request", "shot", "click", "key", "handback"]
mac_only = pytest.mark.skipif(platform.system() != "Darwin", reason="osascript is macOS only")


def osa(*args):
    return subprocess.run(["osascript", "-l", "JavaScript", str(JS), *args],
                          capture_output=True, text=True, timeout=60)


def test_file_exists_names_the_six_commands_and_needs_no_python():
    text = JS.read_text(encoding="utf-8")
    assert "var COMMANDS = ['doctor', 'request', 'shot', 'click', 'key', 'handback'];" in text
    for token in ("DOCTOR_OK", "HANDED_BACK", "SHOT:", "CLICKED", "SENT:", "NO_ACCESSIBILITY",
                  "CAPTURE_FAILED", "com.anthropic.claudefordesktop", "CGRequestScreenCaptureAccess",
                  "AXIsProcessTrustedWithOptions", "screencapture"):
        assert token in text, token
    # it may talk about python3 in comments; it may never run it
    assert not re.search(r"sh\([^;]*python", text) and "/usr/bin/python" not in text
    assert "\r\n" not in text
    assert (ROOT / ".gitattributes").read_text(encoding="utf-8").count("*.js text eol=lf") == 1


@mac_only
def test_help_lists_the_commands_and_exits_zero():
    p = osa("--help")
    assert p.returncode == 0, p.stderr
    for c in COMMANDS:
        assert c in p.stdout, c
    assert "screenctl.py" in p.stdout


@mac_only
def test_unknown_command_is_refused():
    p = osa("nonsense")
    assert p.returncode == 1 and "BAD_COMMAND" in p.stdout


@mac_only
def test_shot_refuses_when_no_png(tmp_path):
    # No --out at all is a plain refusal; a window that does not exist is another. Both exit 1
    # with a stable token and never print SHOT: for a capture that did not happen.
    p = osa("shot", "--title", "no-such-window-xyz")
    assert p.returncode == 1 and "NO_OUT" in p.stdout
    p = osa("shot", "--title", "no-such-window-xyz", "--out", str(tmp_path / "a.png"))
    assert p.returncode == 1 and ("NOT_FOUND" in p.stdout or "NO_ACCESSIBILITY" in p.stdout)
    assert "SHOT:" not in p.stdout and not (tmp_path / "a.png").exists()


@mac_only
def test_click_needs_a_button_or_coordinates():
    p = osa("click", "--title", "no-such-window-xyz")
    assert p.returncode == 1 and "CLICKED" not in p.stdout
    assert any(t in p.stdout for t in ("NOT_FOUND", "NO_ACCESSIBILITY", "NO_COORDS")), p.stdout


@mac_only
def test_doctor_reaches_a_verdict_without_a_bridge_error():
    # Every CoreGraphics and HIServices call is bound by name; a missing binding shows up as
    # an "execution error" with no verdict, which is exactly what a clean Mac must never see.
    p = osa("doctor")
    assert "execution error" not in p.stderr, p.stderr
    assert ("DOCTOR_OK" in p.stdout) or ("DOCTOR_PROBLEMS" in p.stdout), p.stdout
    for line in ("post_events:", "screen_recording:", "accessibility:", "windows_visible:"):
        assert line in p.stdout, line
