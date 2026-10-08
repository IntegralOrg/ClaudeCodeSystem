import json
import os
import subprocess
import sys
from pathlib import Path

# Import parse_frontmatter for direct testing
import importlib.util
spec = importlib.util.spec_from_file_location("check_keys", Path(__file__).resolve().parents[1] / "check-keys.py")
check_keys = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_keys)
parse_frontmatter = check_keys.parse_frontmatter

SCRIPT = Path(__file__).resolve().parents[1] / "check-keys.py"
CRED = ".env"


def make_vault(tmp_path, keys=("ALPHA_KEY", "BETA_TOKEN"), optional=("GAMMA_KEY",)):
    (tmp_path / "System" / "routines").mkdir(parents=True)
    (tmp_path / "System" / "routines" / "eod.md").write_text(
        "---\nname: eod\ntitle: End of Day\nschedule: \"0 23 * * 1-5\"\nprompt: /eod\nconnectors: [Gmail]\n"
        f"keys: [{', '.join(keys)}]\noptional_keys: [{', '.join(optional)}]\n---\n# EOD\n")
    (tmp_path / "System" / "routines" / "vault-hygiene.md").write_text(
        "---\nname: vault-hygiene\ntitle: Vault Hygiene\nschedule: \"0 1 * * *\"\nprompt: /vault-audit\nkeys: []\n---\n")
    (tmp_path / (CRED + ".example")).write_text("# Alpha: get it at alpha.example\nALPHA_KEY=\n# Beta\nBETA_TOKEN=\nGAMMA_KEY=\n")
    return tmp_path


def run(vault, *args, env_extra=None):
    env = {k: v for k, v in os.environ.items() if not k.endswith(("_KEY", "_TOKEN"))}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(SCRIPT), "--vault", str(vault), *args], capture_output=True, text=True, env=env)


def test_init_creates_env_from_example_only_when_missing(tmp_path):
    v = make_vault(tmp_path)
    run(v, "--init")
    f = v / CRED
    assert f.is_file() and f.read_text() == (v / (CRED + ".example")).read_text()
    f.write_text("ALPHA_KEY=secret-value\n")
    p = run(v, "--init")
    assert f.read_text() == "ALPHA_KEY=secret-value\n"
    assert "secret-value" not in p.stdout + p.stderr


def test_missing_key_named_never_valued(tmp_path):
    v = make_vault(tmp_path)
    (v / CRED).write_text("ALPHA_KEY=secret-value\nBETA_TOKEN=\n")
    p = run(v, "--routine", "eod")
    assert p.returncode == 1
    assert "missing: BETA_TOKEN" in p.stdout and "present: ALPHA_KEY" in p.stdout
    assert "secret-value" not in p.stdout + p.stderr
    assert "GAMMA_KEY (optional)" in p.stdout


def test_exported_env_wins_and_all_present_exits_zero(tmp_path):
    v = make_vault(tmp_path)
    p = run(v, "--routine", "eod", env_extra={"ALPHA_KEY": "a", "BETA_TOKEN": "b"})
    assert p.returncode == 0 and "missing: none" in p.stdout


def test_all_routines_and_json(tmp_path):
    v = make_vault(tmp_path)
    p = run(v, "--json")
    out = json.loads(p.stdout)
    assert out["routines"]["eod"]["missing"] == ["ALPHA_KEY", "BETA_TOKEN"]
    assert out["routines"]["vault-hygiene"]["missing"] == []
    assert p.returncode == 1


def test_unknown_routine_is_usage_error(tmp_path):
    assert run(make_vault(tmp_path), "--routine", "nope").returncode == 2


def test_documented_invocations_never_name_the_credentials_file():
    root = SCRIPT.parents[1]
    for doc in ["System/Setup Procedure.md", ".claude/commands/eod.md", ".claude/commands/vault-audit.md"]:
        p = root / doc
        if p.exists():
            for line in p.read_text().splitlines():
                if "check-keys.py" in line:
                    assert CRED not in line, line


def test_crlf_frontmatter_normalized_before_parsing(tmp_path):
    # Direct test of parse_frontmatter with CRLF line endings
    text_with_crlf = "---\r\nname: test\r\nkeys: [KEY1, KEY2]\r\n---\r\nbody"
    fm = parse_frontmatter(text_with_crlf)
    assert fm is not None
    assert fm.get("name") == "test"
    assert fm.get("keys") == ["KEY1", "KEY2"]


def test_keys_as_bare_scalar_exits_2(tmp_path):
    v = make_vault(tmp_path)
    # Overwrite eod.md with bare scalar keys (not a list)
    (v / "System" / "routines" / "eod.md").write_text(
        "---\nname: eod\ntitle: End of Day\nschedule: \"0 23 * * 1-5\"\nprompt: /eod\nconnectors: [Gmail]\n"
        "keys: ALPHA_KEY\noptional_keys: [GAMMA_KEY]\n---\n# EOD\n")
    p = run(v, "--routine", "eod")
    assert p.returncode == 2
    assert "keys must be a list" in p.stderr


def test_export_with_extra_spaces_counts_as_present(tmp_path):
    v = make_vault(tmp_path)
    (v / CRED).write_text("export  ALPHA_KEY=secret\nBETA_TOKEN=value\n")
    p = run(v, "--routine", "eod")
    assert p.returncode == 0
    assert "missing: none" in p.stdout


def test_block_style_yaml_list_parsing(tmp_path):
    v = make_vault(tmp_path)
    # Overwrite eod.md with block-style list format
    (v / "System" / "routines" / "eod.md").write_text(
        "---\nname: eod\ntitle: End of Day\nschedule: \"0 23 * * 1-5\"\nprompt: /eod\nconnectors: [Gmail]\n"
        "keys:\n- ALPHA_KEY\n- BETA_TOKEN\noptional_keys: [GAMMA_KEY]\n---\n# EOD\n")
    (v / CRED).write_text("ALPHA_KEY=secret\nBETA_TOKEN=value\n")
    p = run(v, "--routine", "eod")
    assert p.returncode == 0
    assert "missing: none" in p.stdout
    assert "present: ALPHA_KEY, BETA_TOKEN" in p.stdout


def test_indented_block_list_items_are_parsed(tmp_path):
    v = make_vault(tmp_path)
    (v / "System" / "routines" / "eod.md").write_text(
        "---\nname: eod\ntitle: End of Day\nschedule: \"0 23 * * 1-5\"\nprompt: /eod\nconnectors: [Gmail]\n"
        "keys:\n  - ALPHA_KEY\n  - BETA_TOKEN\noptional_keys: [GAMMA_KEY]\n---\n# EOD\n")
    p = run(v, "--routine", "eod")
    assert p.returncode == 1
    assert "missing: ALPHA_KEY, BETA_TOKEN" in p.stdout


def test_other_routine_malformed_does_not_abort_when_routine_specified(tmp_path):
    v = make_vault(tmp_path)
    # Make vault-hygiene malformed
    (v / "System" / "routines" / "vault-hygiene.md").write_text(
        "---\nname: vault-hygiene\ntitle: Vault Hygiene\nschedule: \"0 1 * * *\"\nprompt: /vault-audit\n"
        "keys: MALFORMED\n---\n")
    # When we specify --routine eod, the malformed vault-hygiene should not abort
    (v / CRED).write_text("ALPHA_KEY=secret\nBETA_TOKEN=value\n")
    p = run(v, "--routine", "eod")
    assert p.returncode == 0
    assert "missing: none" in p.stdout
