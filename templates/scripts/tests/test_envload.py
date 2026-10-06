import os, subprocess, sys
from pathlib import Path
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import envload

def test_load_sets_missing_and_keeps_existing(tmp_path, monkeypatch):
    (tmp_path / "CLAUDE.md").write_text("")
    (tmp_path / ".env").write_text('A=1\nexport B="two"\n# c\nC=\'3\'\n')
    monkeypatch.setenv("A", "already")
    monkeypatch.setenv("B", "x"); monkeypatch.delenv("B")
    monkeypatch.setenv("C", "x"); monkeypatch.delenv("C")
    used = envload.load(tmp_path / "sub")
    assert used == tmp_path / ".env"
    assert os.environ["A"] == "already" and os.environ["B"] == "two" and os.environ["C"] == "3"

def test_load_returns_none_without_env(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("")
    assert envload.load(tmp_path) is None

def test_with_env_execs_command(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("")
    (tmp_path / ".env").write_text("WITH_ENV_T=hello\n")
    env = {k: v for k, v in os.environ.items() if k != "WITH_ENV_T"}
    p = subprocess.run([sys.executable, str(SCRIPTS / "with-env.py"), "--", sys.executable, "-c",
                        "import os;print(os.environ.get('WITH_ENV_T'))"],
                       cwd=tmp_path, env=env, capture_output=True, text=True)
    assert p.stdout.strip() == "hello" and p.returncode == 0

def test_with_env_propagates_exit_code(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("")
    p = subprocess.run([sys.executable, str(SCRIPTS / "with-env.py"), "--", sys.executable, "-c",
                        "import sys;sys.exit(7)"], cwd=tmp_path, capture_output=True, text=True)
    assert p.returncode == 7

def test_with_env_usage_error(tmp_path):
    p = subprocess.run([sys.executable, str(SCRIPTS / "with-env.py"), "--"],
                       cwd=tmp_path, capture_output=True, text=True)
    assert p.returncode == 64

def test_parse_handles_edge_cases():
    out = envload.parse('X=a=b\n  export Y = "q"\nbad line\n#Z=1\nW=\n')
    assert out["X"] == "a=b" and out["Y"] == "q" and out["W"] == "" and "Z" not in out

def test_local_file_overrides_base_and_exported_wins(tmp_path, monkeypatch):
    (tmp_path / "CLAUDE.md").write_text("")
    (tmp_path / ".env").write_text("OVL_K=base\nOVL_ONLY_BASE=b\nOVL_EXP=base\n")
    (tmp_path / (".env" + ".local")).write_text("OVL_K=local\nOVL_EXP=local\n")
    for k in ("OVL_K", "OVL_ONLY_BASE"):
        monkeypatch.setenv(k, "x"); monkeypatch.delenv(k)
    monkeypatch.setenv("OVL_EXP", "exported")
    assert envload.load(tmp_path) == tmp_path / ".env"
    assert os.environ["OVL_K"] == "local" and os.environ["OVL_ONLY_BASE"] == "b"
    assert os.environ["OVL_EXP"] == "exported"

def test_only_local_file_returns_env_path(tmp_path, monkeypatch):
    (tmp_path / "CLAUDE.md").write_text("")
    (tmp_path / (".env" + ".local")).write_text("OVL_L=1\n")
    monkeypatch.setenv("OVL_L", "x"); monkeypatch.delenv("OVL_L")
    assert envload.load(tmp_path) == tmp_path / ".env"
    assert os.environ["OVL_L"] == "1"

def test_parse_skips_empty_key():
    assert envload.parse("=x\nexport =y\nK=v\n") == {"K": "v"}

def test_with_env_command_not_found(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("")
    p = subprocess.run([sys.executable, str(SCRIPTS / "with-env.py"), "--", "no-such-cmd-xyz"],
                       cwd=tmp_path, capture_output=True, text=True)
    assert p.returncode == 127 and "command not found: no-such-cmd-xyz" in p.stderr

def test_with_env_falls_back_to_script_repo(tmp_path):
    # cwd has no CLAUDE.md/.git anywhere above; falls back to the script's repo root.
    repo = tmp_path / "repo"; (repo / "scripts").mkdir(parents=True)
    (repo / "CLAUDE.md").write_text("")
    (repo / ".env").write_text("FALLBACK_T=viaroot\n")
    for n in ("with-env.py", "envload.py"):
        (repo / "scripts" / n).write_text((SCRIPTS / n).read_text())
    elsewhere = tmp_path / "elsewhere"; elsewhere.mkdir()
    env = {k: v for k, v in os.environ.items() if k != "FALLBACK_T"}
    # tmp_path lives under a system temp dir with no markers above it
    p = subprocess.run([sys.executable, str(repo / "scripts" / "with-env.py"), "--", sys.executable, "-c",
                        "import os;print(os.environ.get('FALLBACK_T'))"],
                       cwd=elsewhere, env=env, capture_output=True, text=True)
    assert p.stdout.strip() == "viaroot"

def test_fathom_env_file_does_not_override_exported(tmp_path, monkeypatch):
    import importlib.util
    import pytest
    if not (SCRIPTS / "fathom-fetch.py").exists():
        pytest.skip("fathom-fetch.py is not part of the template")
    spec = importlib.util.spec_from_file_location("ff", SCRIPTS / "fathom-fetch.py")
    ff = importlib.util.module_from_spec(spec); spec.loader.exec_module(ff)
    f = tmp_path / "x.env"; f.write_text("DUMMY_EXPORTED=fromfile\nDUMMY_NEW=fromfile\n")
    monkeypatch.setenv("DUMMY_EXPORTED", "exported"); monkeypatch.setenv("DUMMY_NEW", "t"); monkeypatch.delenv("DUMMY_NEW")
    ff.apply_env_file(str(f))
    assert os.environ["DUMMY_EXPORTED"] == "exported" and os.environ["DUMMY_NEW"] == "fromfile"
