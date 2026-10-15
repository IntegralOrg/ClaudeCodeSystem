import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "set-key.py"


def run(vault, *args, value=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SET_KEY_")}
    env["CLAUDE_PROJECT_DIR"] = str(vault)
    if value is not None:
        env["SET_KEY_FAKE_VALUE"] = value
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env, cwd=str(vault), timeout=20)


def vault(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# v\n")
    (tmp_path / ".env.example").write_text("FATHOM_API_KEY=\n")
    return tmp_path


def test_saves_the_value_and_prints_only_the_name(tmp_path):
    v = vault(tmp_path)
    p = run(v, "FATHOM_API_KEY", "--label", "Fathom API key", value="sk-test-123")
    assert p.returncode == 0 and p.stdout.strip() == "SAVED FATHOM_API_KEY"
    assert "sk-test-123" not in p.stdout + p.stderr
    assert (v / ".env").read_text() == "FATHOM_API_KEY=sk-test-123\n"
    assert oct((v / ".env").stat().st_mode)[-3:] == "600" or os.name == "nt"


def test_replaces_an_existing_line_and_keeps_the_rest(tmp_path):
    v = vault(tmp_path)
    (v / ".env").write_text("OTHER=1\nFATHOM_API_KEY=old\n")
    run(v, "FATHOM_API_KEY", value="new")
    assert (v / ".env").read_text() == "OTHER=1\nFATHOM_API_KEY=new\n"


def test_strips_pasted_decoration(tmp_path):
    v = vault(tmp_path)
    run(v, "FATHOM_API_KEY", value='FATHOM_API_KEY="<abc123>"')
    assert (v / ".env").read_text() == "FATHOM_API_KEY=abc123\n"


def test_cancel_and_empty_exit_3(tmp_path):
    v = vault(tmp_path)
    assert run(v, "FATHOM_API_KEY", value="__CANCEL__").returncode == 3
    p = run(v, "FATHOM_API_KEY", value="   ")
    assert p.returncode == 3 and p.stdout.startswith("EMPTY")


def test_bad_name_exits_1(tmp_path):
    v = vault(tmp_path)
    p = run(v, "fathom key", value="x")
    assert p.returncode == 1 and p.stdout.startswith("BAD_NAME")


def test_windows_dialog_script_is_a_masked_winforms_box():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "UseSystemPasswordChar" in src and "-NoProfile" in src and "-STA" in src
