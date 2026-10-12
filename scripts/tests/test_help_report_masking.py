"""Every secret form a setup error line can carry stays out of the help report (all values below are fake)."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "setup" / "help_report.py"


def run(v, error):
    p = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(v), "--step", "B3 GitHub",
                        "--error", error, "--tried", "retried once"], capture_output=True, text=True)
    return p.returncode, p.stdout


def report_text(out):
    return Path(next(l for l in out.splitlines() if l.startswith("REPORT "))[len("REPORT "):]).read_text()


@pytest.mark.parametrize("secret_line,leak", [
    ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJlc2lnbmF0dXJl", "eyJzdWIiOiIxIn0"),
    ("fatal: https://pat:hunter2secret@github.com/pat/brain.git", "hunter2secret"),
    ('{"access_token": "ya29.a0AfH6SMBexampletokenvalue"}', "ya29.a0AfH6SMB"),
    ("FATHOM_API_KEY: abcdef123456", "abcdef123456"),
    ("Fathom_api_key=lowercasevalue99", "lowercasevalue99"),
    ("token gho_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 rejected", "gho_ABCDEFGHIJ"),
])
def test_report_masks_every_secret_form(tmp_path, secret_line, leak):
    rc, out = run(tmp_path, secret_line)
    assert rc == 0
    assert leak not in report_text(out) and leak not in out


def test_say_does_not_point_at_inbox_when_the_report_was_not_written(tmp_path):
    (tmp_path / "Inbox").write_text("a file where the folder should be")
    rc, out = run(tmp_path, "push failed")
    say = next(l for l in out.splitlines() if l.startswith("SAY "))
    assert "Inbox" not in say and "onboarding contact" in say
