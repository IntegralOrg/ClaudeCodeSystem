import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "setup" / "script-doc.py"
spec = importlib.util.spec_from_file_location("script_doc", SCRIPT)
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)

SAMPLE = '''## 1. Welcome

Say, in these words: "Welcome. I will set up your system now. It takes about ten minutes." Then stop.

## 2. Questions

- "Which email and calendar do you use?" Options: Google; Microsoft; Other.
- A line with "two words" only.
'''


def test_extract_takes_long_quotes_and_option_questions():
    items = sd.extract(SAMPLE, "Setup Procedure")
    assert ("1. Welcome", "say", "Welcome. I will set up your system now. It takes about ten minutes.") in items
    assert ("2. Questions", "ask", "Which email and calendar do you use? Options: Google; Microsoft; Other.") in items
    assert not any("two words" in t for _, _, t in items)


def test_committed_doc_is_current():
    p = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, cwd=str(ROOT))
    assert p.returncode == 0, p.stdout + p.stderr


def test_doc_lists_every_source_file():
    text = (ROOT / "docs" / "setup-script.md").read_text(encoding="utf-8")
    for name in ("Start.md", "Setup Procedure.md", "Adding Your Computer.md"):
        assert f"## {name}" in text


def test_inline_code_spans_are_ignored():
    line = 'Run `tool --text "ignore me please thank you"` and say "Hello there, this is the real sentence here."'
    items = sd.extract("## S\n\n" + line + "\n", "X")
    assert items == [("S", "say", "Hello there, this is the real sentence here.")]
    assert not any("ignore me" in t for _, _, t in items)
