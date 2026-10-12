import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "setup" / "help_report.py"
sys.path.insert(0, str(SCRIPT.parent))
import help_report as hr  # noqa: E402


def run(v, *extra):
    args = {"--step": "B3 GitHub", "--error": "push failed", "--tried": "retried once"}
    for i in range(0, len(extra), 2):
        args[extra[i]] = extra[i + 1]
    cmd = [sys.executable, str(SCRIPT), "--vault", str(v)]
    for k, val in args.items():
        cmd += [k, val]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout


def report_of(out):
    return Path(next(l for l in out.splitlines() if l.startswith("REPORT "))[len("REPORT "):])


def test_report_lands_in_inbox_with_step_error_and_attempt(tmp_path):
    rc, out = run(tmp_path)
    assert rc == 0, out
    path = report_of(out)
    text = path.read_text()
    assert path.parent == tmp_path / "Inbox" and path.name.startswith("Setup help request ")
    assert "B3 GitHub" in text and "push failed" in text and "retried once" in text and text.startswith("---\n")


def test_tells_the_person_to_send_it_and_opens_no_email(tmp_path):
    rc, out = run(tmp_path)
    say = next(l for l in out.splitlines() if l.startswith("SAY "))
    assert "onboarding contact" in say
    assert "mailto" not in out and "COMPOSE" not in out and "mail.google" not in out


def test_report_masks_tokens(tmp_path):
    rc, out = run(tmp_path, "--error", "auth failed for ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 FATHOM_API_KEY=abc123")
    text = report_of(out).read_text()
    assert "ghp_ABCDEF" not in text and "abc123" not in text and "FATHOM_API_KEY=[masked]" in text
    assert "ghp_ABCDEF" not in out


def test_details_file_tail_is_included_and_masked(tmp_path):
    details = tmp_path / "doctor.txt"
    details.write_text("line one\nSLACK_TOKEN_A=xoxb-1234567890-abcdef\nDOCTOR_PROBLEMS\n")
    rc, out = run(tmp_path, "--details-file", str(details))
    text = report_of(out).read_text()
    assert "DOCTOR_PROBLEMS" in text and "xoxb-1234567890" not in text


def test_mask_leaves_plain_text_alone():
    assert hr.mask("git push failed: rejected (fetch first)") == "git push failed: rejected (fetch first)"


def test_unwritable_inbox_still_exits_zero(tmp_path):
    (tmp_path / "Inbox").write_text("a file where the folder should be")
    rc, out = run(tmp_path)
    assert rc == 0 and out.startswith("REPORT_UNWRITTEN") and "B3 GitHub" in out
