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


def make_probe_vault(tmp_path):
    (tmp_path / "System" / "routines").mkdir(parents=True)
    (tmp_path / "System" / "routines" / "eod.md").write_text(
        "---\nname: eod\ntitle: End of Day\nschedule: \"7 23 * * 1-5\"\nprompt: /eod\nconnectors: [Gmail]\nkeys: []\n"
        "optional_keys:\n"
        "  - name: FATHOM_API_KEY\n    probe_url: https://api.fathom.ai/external/v1/meetings?limit=1\n    header: X-Api-Key\n    header_prefix: \"\"\n"
        "  - SLACK_TOKEN_WORKSPACE_A\n---\n# EOD\n")
    (tmp_path / (CRED + ".example")).write_text("FATHOM_API_KEY=\nSLACK_TOKEN_WORKSPACE_A=\n")
    return tmp_path


def run_probe(vault, results, *args):
    return run(vault, *args, env_extra={"CHECK_KEYS_PROBE_RESULTS": json.dumps(results)})


def test_object_and_bare_keys_mix_in_one_list(tmp_path):
    v = make_probe_vault(tmp_path)
    p = run_probe(v, {"https://api.fathom.ai/external/v1/meetings?limit=1": 401}, "--json")
    rep = json.loads(p.stdout)["routines"]["eod"]
    assert "FATHOM_API_KEY" in rep["optional_missing"] and "SLACK_TOKEN_WORKSPACE_A" in rep["optional_missing"]


def test_probe_200_means_present_even_with_no_variable(tmp_path):
    v = make_probe_vault(tmp_path)   # the cloud case: a network secret, nothing in the environment
    p = run_probe(v, {"https://api.fathom.ai/external/v1/meetings?limit=1": 200}, "--json")
    rep = json.loads(p.stdout)["routines"]["eod"]
    assert "FATHOM_API_KEY" in rep["present"] and "FATHOM_API_KEY" not in rep["optional_missing"]


def test_probe_error_is_unverified_not_missing(tmp_path):
    v = make_probe_vault(tmp_path)
    p = run_probe(v, {"https://api.fathom.ai/external/v1/meetings?limit=1": "error"}, "--json")
    rep = json.loads(p.stdout)["routines"]["eod"]
    assert rep["unverified"] == ["FATHOM_API_KEY"] and "FATHOM_API_KEY" not in rep["optional_missing"]
    assert p.returncode == 0


def test_probe_sends_the_header_only_when_the_variable_is_set(tmp_path, monkeypatch):
    seen = {}
    def fake_open(req, timeout):
        seen["headers"] = dict(req.header_items())
        class R:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()
    monkeypatch.setattr(check_keys._opener, "open", fake_open)
    spec = {"name": "FATHOM_API_KEY", "probe_url": "https://api.fathom.ai/x", "header": "X-Api-Key", "header_prefix": ""}
    assert check_keys.probe_key(spec, "") == "present"
    assert "X-api-key" not in seen["headers"] and "X-Api-Key" not in seen["headers"]
    assert check_keys.probe_key(spec, "abc") == "present"
    assert seen["headers"].get("X-api-key") == "abc"


def test_probe_2xx_with_ok_false_body_is_missing(monkeypatch):
    # Slack's auth.test answers 200 with {"ok": false} when no token reaches it.
    def fake_open(req, timeout):
        class R:
            status = 200
            def read(self, n=-1): return b'{"ok":false,"error":"not_authed"}'
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()
    monkeypatch.setattr(check_keys._opener, "open", fake_open)
    spec = {"name": "SLACK_TOKEN_WORKSPACE_A", "probe_url": "https://slack.com/api/auth.test",
            "header": "Authorization", "header_prefix": "Bearer "}
    assert check_keys.probe_key(spec, "") == "missing"


def test_where_names_both_places_and_never_the_value(tmp_path):
    v = make_probe_vault(tmp_path)
    (v / "System" / "Routines.md").write_text("## End of Day\n- live_since: not live\n- environment id: env_123\n")
    p = run_probe(v, {"https://api.fathom.ai/external/v1/meetings?limit=1": 401}, "--where")
    assert "FATHOM_API_KEY (optional): on this computer run python3 scripts/set-key.py FATHOM_API_KEY" in p.stdout
    assert "network secret" in p.stdout and "api.fathom.ai" in p.stdout and "X-Api-Key" in p.stdout and "env_123" in p.stdout
    assert ".env" not in p.stdout


def test_where_marks_only_optional_keys(tmp_path):
    v = make_vault(tmp_path, keys=("ALPHA_KEY",), optional=("GAMMA_KEY",))
    p = run(v, "--where")
    assert "ALPHA_KEY: on this computer run" in p.stdout
    assert "GAMMA_KEY (optional): on this computer run" in p.stdout
    assert "ALPHA_KEY (optional)" not in p.stdout


def test_probe_never_follows_a_redirect():
    # a 302 to another URL that would answer 200: the probe stops at the 302 and reports "could not check"
    import http.server
    import threading

    hits = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append((self.path, self.headers.get("X-Api-Key")))
            if self.path == "/start":
                self.send_response(302)
                self.send_header("Location", "/elsewhere")
            else:
                self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        spec = {"name": "SOME_KEY", "probe_url": f"http://127.0.0.1:{srv.server_port}/start",
                "header": "X-Api-Key", "header_prefix": ""}
        assert check_keys.probe_key(spec, "secret") == "unknown"
        assert [h[0] for h in hits] == ["/start"]
    finally:
        srv.shutdown()


def test_nameless_object_key_is_skipped_with_a_note(tmp_path):
    v = make_vault(tmp_path)
    r = v / "System" / "routines" / "eod.md"
    r.write_text(r.read_text().replace("keys: [ALPHA_KEY, BETA_TOKEN]", "keys:\n  - probe_url: https://x.example/ok\n  - ALPHA_KEY"))
    out = json.loads(run(v, "--json").stdout)
    assert "eod: a key declaration has no name" in out["notes"]
    rep = out["routines"]["eod"]
    assert "" not in rep["present"] + rep["missing"] + rep["unverified"] and "ALPHA_KEY" in rep["missing"]
