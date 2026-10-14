"""scripts/setup/claude_cli.py: find the Claude CLI a Desktop-only install bundles, and run it with a clean session state."""
import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "setup" / "claude_cli.py"
sys.path.insert(0, str(SCRIPT.parent))
import claude_cli as cc  # noqa: E402

MAC_PS = ("/Applications/Claude.app/Contents/Helpers/disclaimer --pgroup -- "
          "{home}/Library/Application Support/Claude/claude-code/2.1.295/9d6405864fdc/claude.app/Contents/MacOS/claude "
          "--output-format stream-json --verbose")
SESSION_VARS = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_CHILD_SESSION")


def fake_cli(path, body="#!/bin/sh\necho CLI_RAN\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_find_cli_takes_the_one_on_path_first(tmp_path):
    on_path = fake_cli(tmp_path / "bin" / "claude")
    found = cc.find_cli(system="Darwin", home=str(tmp_path), path_dirs=[str(tmp_path / "bin")], processes=[])
    assert found == str(on_path)


def test_find_cli_reads_the_bundled_path_out_of_the_running_process(tmp_path):
    bundled = fake_cli(tmp_path / "Library/Application Support/Claude/claude-code/2.1.295/9d6405864fdc/claude.app/Contents/MacOS/claude")
    found = cc.find_cli(system="Darwin", home=str(tmp_path), path_dirs=[], processes=[MAC_PS.format(home=tmp_path)])
    assert found == str(bundled)        # the space in "Application Support" and the disclaimer prefix are both handled


def test_find_cli_falls_back_to_the_newest_bundled_version_on_disk(tmp_path):
    fake_cli(tmp_path / "Library/Application Support/Claude/claude-code/2.1.289/ee67e3f1ea60/claude.app/Contents/MacOS/claude")
    newest = fake_cli(tmp_path / "Library/Application Support/Claude/claude-code/2.1.295/9d6405864fdc/claude.app/Contents/MacOS/claude")
    fake_cli(tmp_path / "Library/Application Support/Claude/claude-code/2.1.30/aaaa/claude.app/Contents/MacOS/claude")   # 2.1.30 < 2.1.295
    found = cc.find_cli(system="Darwin", home=str(tmp_path), path_dirs=[], processes=["/usr/bin/something else"])
    assert found == str(newest)


def test_find_cli_returns_none_when_nothing_is_there(tmp_path):
    assert cc.find_cli(system="Darwin", home=str(tmp_path), path_dirs=[str(tmp_path / "empty")], processes=[]) is None
    assert cc.find_cli(system="Windows", home=str(tmp_path), path_dirs=[], processes=[]) is None


def test_find_cli_on_windows_reads_the_process_list(tmp_path):
    exe = fake_cli(tmp_path / "AppData/Local/Programs/claude-code/1.0/abc/claude.exe")
    line = f"{exe} --output-format stream-json"
    assert cc.find_cli(system="Windows", home=str(tmp_path), path_dirs=[], processes=[line]) == str(exe)


def run_script(args, extra):
    merged = {**os.environ, **extra}
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=merged, timeout=60)


def test_script_prints_cli_or_cli_missing(tmp_path):
    extra = {"PATH": str(tmp_path / "nothing"), "SETUP_CLAUDE_HOME": str(tmp_path), "SETUP_CLAUDE_PS": ""}
    p = run_script([], extra)
    assert p.returncode == 3 and p.stdout.strip() == "CLI_MISSING", p.stdout + p.stderr
    fake_cli(tmp_path / "bin" / "claude")
    extra["PATH"] = str(tmp_path / "bin")
    p = run_script([], extra)
    assert p.returncode == 0 and p.stdout.strip() == f"CLI {tmp_path / 'bin' / 'claude'}", p.stdout + p.stderr


def test_script_runs_the_cli_with_the_session_variables_unset(tmp_path):
    # the fake CLI reports which of the three session variables reached it, then exits 7
    body = "#!/bin/sh\necho \"args: $*\"\n" + "".join(f'echo "{v}=${{{v}:-unset}}"\n' for v in SESSION_VARS) + "exit 7\n"
    fake_cli(tmp_path / "bin" / "claude", body)
    extra = {"PATH": str(tmp_path / "bin"), "SETUP_CLAUDE_HOME": str(tmp_path), "SETUP_CLAUDE_PS": "",
             SESSION_VARS[0]: "1", SESSION_VARS[1]: "sdk", SESSION_VARS[2]: "x"}
    p = run_script(["--", "plugin", "list"], extra)
    assert p.returncode == 7, p.stdout + p.stderr           # the CLI's own exit code comes back
    assert "args: plugin list" in p.stdout
    for v in SESSION_VARS:
        assert f"{v}=unset" in p.stdout, p.stdout


def test_find_cli_ignores_a_process_whose_binary_is_not_the_users_own(tmp_path):
    """ps can list another account's processes on a shared Mac; a path owned by someone else is never run."""
    other = fake_cli(tmp_path / "elsewhere/claude-code/9.9.9/x/claude.app/Contents/MacOS/claude")
    line = f"{other} --output-format stream-json"
    assert cc.find_cli(system="Darwin", home=str(tmp_path), path_dirs=[], processes=[line], is_mine=lambda p: False) is None
    assert cc.find_cli(system="Darwin", home=str(tmp_path), path_dirs=[], processes=[line], is_mine=lambda p: True) == str(other)


def test_process_listing_is_limited_to_the_current_user():
    assert "-xo" in cc.ps_command("Darwin") and "-axo" not in cc.ps_command("Darwin")


def test_find_cli_applies_the_ownership_check_to_a_path_candidate_too(tmp_path):
    shared = fake_cli(tmp_path / "shared-bin" / "claude")
    dirs = [str(tmp_path / "shared-bin")]
    assert cc.find_cli(system="Darwin", home=str(tmp_path), path_dirs=dirs, processes=[], is_mine=lambda p: False) is None
    assert cc.find_cli(system="Darwin", home=str(tmp_path), path_dirs=dirs, processes=[], is_mine=lambda p: True) == str(shared)


def test_is_mine_accepts_the_users_own_file_and_rejects_a_missing_one(tmp_path):
    own = fake_cli(tmp_path / "bin" / "claude")
    assert cc.is_mine(str(own))
    assert not cc.is_mine(str(tmp_path / "nope"))


def test_under_home_is_component_aware(tmp_path):
    """The Windows fallback (no uid): a sibling folder that merely starts with the home name is outside it."""
    home = tmp_path / "Users" / "alice"
    assert cc.under_home(str(home / "AppData" / "claude.exe"), str(home))
    assert not cc.under_home(str(tmp_path / "Users" / "alice-elsewhere" / "claude.exe"), str(home))
    assert not cc.under_home(str(tmp_path / "Users"), str(home))
