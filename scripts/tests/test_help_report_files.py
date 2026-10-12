"""The error and what-was-tried text reach help_report.py through files, never through shell command text."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "setup" / "help_report.py"


def test_error_and_tried_files_are_reported_literally(tmp_path):
    err, tried = tmp_path / "error.txt", tmp_path / "tried.txt"
    canary = tmp_path / "ran"
    err.write_text(f"fatal: bad $(touch {canary}) `touch {canary}`\n", encoding="utf-8")
    tried.write_text("retried once\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(tmp_path), "--step", "B3 GitHub",
                        "--error-file", str(err), "--tried-file", str(tried)], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    report = Path(next(l for l in p.stdout.splitlines() if l.startswith("REPORT "))[len("REPORT "):]).read_text(encoding="utf-8")
    assert f"$(touch {canary})" in report and "retried once" in report and not canary.exists()


def test_error_or_error_file_is_required(tmp_path):
    p = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(tmp_path), "--step", "x", "--tried", "y"],
                       capture_output=True, text=True)
    assert p.returncode == 2


def test_procedure_passes_error_text_through_files():
    text = (ROOT / "System" / "Setup Procedure.md").read_text(encoding="utf-8")
    fails = text[text.index("## When a step fails"):]
    assert "--error-file" in fails and "--tried-file" in fails and "Write tool" in fails
    assert '--error "<' not in fails
    part_b = text[text.index("## Part B"):text.index("## 1. Open, then learn")]
    assert "Programs\\Git\\bin\\bash.exe" in part_b
