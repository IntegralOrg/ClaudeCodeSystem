import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "setup" / "github.py"
sys.path.insert(0, str(SCRIPT.parent))
import github as gh  # noqa: E402

FAKE_GH = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, subprocess, sys, time
    st = os.environ["FAKE_STATE"]
    def load():
        return json.load(open(st)) if os.path.exists(st) else {}
    s, a = load(), sys.argv[1:]
    with open(st + ".calls", "a") as f: f.write(json.dumps(a) + "\n")
    if a[:1] == ["--version"]:
        print("gh version 9.9.9"); sys.exit(0)
    if a[:2] == ["auth", "status"]:
        if not s.get("signed_in"): sys.exit(1)
        if s.get("auth_status_text"): print(s["auth_status_text"])
        print("  - Token scopes: " + ", ".join("'%s'" % x for x in s.get("scopes", ["gist", "read:org", "repo", "workflow"])))
        sys.exit(0)
    if a[:2] == ["auth", "refresh"]:
        s["refresh_argv"] = a; json.dump(s, open(st, "w"))
        print("! First copy your one-time code: WXYZ-5678", flush=True)
        print("Open this URL to continue in your web browser: https://github.com/login/device", flush=True)
        time.sleep(1); s["scopes"] = s.get("scopes", []) + ["workflow"]; json.dump(s, open(st, "w")); sys.exit(0)
    if a[:2] == ["auth", "logout"]:
        if not s.get("signed_in"):
            print("not logged in to any hosts", file=sys.stderr); sys.exit(1)
        s["signed_in"] = False; json.dump(s, open(st, "w")); sys.exit(0)
    if a[:2] == ["auth", "login"]:
        if s.get("no_code"):
            time.sleep(60); sys.exit(1)
        s["login_argv"] = a; json.dump(s, open(st, "w"))
        print("! First copy your one-time code: ABCD-1234", flush=True)
        print("Open this URL to continue in your web browser: https://github.com/login/device", flush=True)
        time.sleep(1); s["signed_in"] = True; json.dump(s, open(st, "w")); sys.exit(0)
    if a[:2] == ["api", "user/orgs"]:
        if s.get("orgs_error"):
            print("HTTP 401: Bad credentials", file=sys.stderr); sys.exit(1)
        for o in s.get("orgs", []): print(o)
        sys.exit(0)
    if a[:2] == ["api", "user"]:
        if s.get("api_user_fails"): sys.exit(1)
        print("pat"); sys.exit(0)
    if a[:2] == ["repo", "view"]:
        r = s.get("repos", {}).get(a[2], s.get("remote_repo") if a[2] == "pat/brain" else None)
        if not r: sys.exit(1)
        print(json.dumps({"isEmpty": r["empty"], "visibility": r["visibility"]})); sys.exit(0)
    if a[:2] == ["repo", "create"]:
        if s.get("create_error"):
            print(s["create_error"], file=sys.stderr); sys.exit(1)
        bare, src = s["bare"], a[a.index("--source") + 1]   # always act on --source, never on the cwd
        s["created"] = a[2]; json.dump(s, open(st, "w"))
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", bare], check=True)
        subprocess.run(["git", "-C", src, "remote", "add", "origin", bare], check=True)
        subprocess.run(["git", "-C", src, "push", "-q", "-u", "origin", "main"], check=True)
        print("https://github.com/pat/brain"); sys.exit(0)
    sys.exit(9)
''').lstrip()


@pytest.fixture
def world(tmp_path):
    fake = tmp_path / "gh"
    fake.write_text(FAKE_GH); fake.chmod(0o755)
    vault = tmp_path / "Brain"; vault.mkdir()
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(vault), *args], check=True)
    (vault / "README.md").write_text("x")
    subprocess.run(["git", "-C", str(vault), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(vault), "commit", "-q", "-m", "s"], check=True)
    state = tmp_path / "state.json"
    env = {**os.environ, "SETUP_GH": str(fake), "SETUP_NO_UI": "1", "FAKE_STATE": str(state),
           "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"), "SETUP_BIN_DIR": str(tmp_path / "bin")}
    return {"tmp": tmp_path, "vault": vault, "state": state, "env": env}


def run(w, *args):
    p = subprocess.run([sys.executable, str(SCRIPT), *args, "--vault", str(w["vault"])],
                       capture_output=True, text=True, env=w["env"], timeout=120)
    return p.returncode, p.stdout


def setstate(w, **kw):
    s = json.loads(w["state"].read_text()) if w["state"].exists() else {}
    s.update(kw); w["state"].write_text(json.dumps(s))


def calls(w):
    f = Path(str(w["state"]) + ".calls")
    return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


@pytest.mark.parametrize("system,machine,want", [
    ("Darwin", "arm64", "gh_2.1.0_macOS_arm64.zip"), ("Darwin", "x86_64", "gh_2.1.0_macOS_amd64.zip"),
    ("Windows", "AMD64", "gh_2.1.0_windows_amd64.zip"), ("Windows", "ARM64", "gh_2.1.0_windows_arm64.zip"),
    ("Linux", "aarch64", "gh_2.1.0_linux_arm64.tar.gz")])
def test_asset_name(system, machine, want):
    assert gh.asset_name("2.1.0", system, machine) == want


def test_helper_value_uses_absolute_forward_slash_path():
    assert gh.helper_value(r"C:\Users\Pat\AppData\Local\Programs\gh\gh.exe") == \
        "!'C:/Users/Pat/AppData/Local/Programs/gh/gh.exe' auth git-credential"


def test_login_start_prints_code_and_one_sentence(world):
    rc, out = run(world, "login-start", "--timeout", "15")
    assert rc == 0, out
    assert "CODE ABCD-1234" in out
    say = next(l for l in out.splitlines() if l.startswith("SAY "))
    assert "gh" not in say.split() and "Authorize" in say


def test_login_start_times_out_without_code(world):
    setstate(world, no_code=True)
    rc, out = run(world, "login-start", "--timeout", "3")
    assert rc == 1 and out.startswith("LOGIN_NO_CODE")


def test_login_wait_reports_signed_in(world):
    setstate(world, signed_in=True)
    rc, out = run(world, "login-wait", "--timeout", "5")
    assert rc == 0 and "SIGNED_IN pat" in out


def test_login_wait_falls_back_to_auth_status_when_api_user_fails(world):
    setstate(world, signed_in=True, api_user_fails=True,
             auth_status_text="github.com\n  Logged in to github.com account patty (keyring)")
    rc, out = run(world, "login-wait", "--timeout", "5")
    assert rc == 0 and "SIGNED_IN patty" in out


def test_logout_names_the_host_and_the_user(world):
    setstate(world, signed_in=True)
    rc, out = run(world, "logout")
    assert rc == 0 and out.startswith("SIGNED_OUT")
    assert ["auth", "logout", "-h", "github.com", "-u", "pat"] in calls(world)


def test_connect_creates_private_repo_and_sets_helper(world):
    setstate(world, signed_in=True, bare=str(world["tmp"] / "remote.git"))
    rc, out = run(world, "connect")
    assert rc == 0, out
    assert out.splitlines()[-1].startswith("CONNECTED")
    helpers = subprocess.run(["git", "config", "--global", "--get-all", "credential.https://github.com.helper"],
                             capture_output=True, text=True, env=world["env"]).stdout.splitlines()
    assert helpers[0] == "" and helpers[1].endswith("auth git-credential") and "/gh'" in helpers[1]


def test_connect_reuses_empty_repo(world):
    bare = world["tmp"] / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    setstate(world, signed_in=True, remote_repo={"empty": True, "visibility": "PRIVATE"})
    world["env"]["SETUP_REMOTE_URL"] = str(bare)          # tests point "github.com/pat/brain" at a local bare repo
    rc, out = run(world, "connect")
    assert rc == 0, out
    assert subprocess.run(["git", "-C", str(bare), "rev-parse", "main"], capture_output=True).returncode == 0


def test_connect_stops_on_nonempty_repo(world):
    setstate(world, signed_in=True, remote_repo={"empty": False, "visibility": "PRIVATE"})
    rc, out = run(world, "connect")
    assert rc == 3 and out.startswith("REPO_EXISTS")


def test_connect_stops_on_public_repo(world):
    setstate(world, signed_in=True, remote_repo={"empty": True, "visibility": "PUBLIC"})
    rc, out = run(world, "connect")
    assert rc == 3 and out.startswith("REPO_NOT_PRIVATE")


def test_verify_unreachable_without_origin(world):
    rc, out = run(world, "verify")
    assert rc == 1 and out.startswith("UNREACHABLE")


def test_helper_value_survives_an_apostrophe_in_the_path():
    assert gh.helper_value("C:\\Users\\O'Brien\\gh.exe") == "!'C:/Users/O'\\''Brien/gh.exe' auth git-credential"


def test_connect_can_use_another_name_after_repo_exists(world):
    setstate(world, signed_in=True, bare=str(world["tmp"] / "remote2.git"),
             repos={"pat/brain": {"empty": False, "visibility": "PRIVATE"}})
    rc, out = run(world, "connect", "--name", "brain-2")
    assert rc == 0, out
    assert json.loads(world["state"].read_text())["created"] == "pat/brain-2"


def _set_origin(w, url):
    subprocess.run(["git", "-C", str(w["vault"]), "remote", "add", "origin", url], check=True)


def test_connect_refuses_an_existing_public_origin(world):
    _set_origin(world, "https://github.com/pat/open-notes")
    setstate(world, signed_in=True, repos={"https://github.com/pat/open-notes": {"empty": False, "visibility": "PUBLIC"}})
    rc, out = run(world, "connect")
    assert rc == 3 and out.startswith("REPO_NOT_PRIVATE")


def test_connect_refuses_an_origin_it_cannot_verify(world):
    _set_origin(world, "https://github.com/someone-else/brain")
    setstate(world, signed_in=True)
    rc, out = run(world, "connect")
    assert rc == 3 and out.startswith("ORIGIN_UNVERIFIED")


def test_connect_rerun_pushes_to_its_own_private_origin(world):
    bare = world["tmp"] / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    _set_origin(world, str(bare))
    setstate(world, signed_in=True, repos={str(bare): {"empty": False, "visibility": "PRIVATE"}})
    rc, out = run(world, "connect")
    assert rc == 0 and out.splitlines()[-1].startswith("CONNECTED"), out


def test_connect_stops_on_an_organization_policy_without_retrying(world):
    setstate(world, signed_in=True, bare=str(world["tmp"] / "bare.git"),
             create_error="HTTP 403: Repository creation is restricted by organization policy")
    rc, out = run(world, "connect")
    assert rc == 3 and out.startswith("ORG_POLICY"), out
    assert "PUSH_FAILED" not in out
    assert not (world["tmp"] / "bare.git").exists()        # nothing was created or pushed


def test_orgs_lists_the_organizations_the_account_belongs_to(world):
    setstate(world, signed_in=True, orgs=["acme", "acme-labs"])
    rc, out = run(world, "orgs")
    assert rc == 0 and out.strip() == "ORGS acme acme-labs", out


def test_orgs_prints_the_bare_token_when_there_are_none(world):
    setstate(world, signed_in=True)
    rc, out = run(world, "orgs")
    assert rc == 0 and out.strip() == "ORGS", out


def test_orgs_reports_a_failed_lookup_instead_of_no_organizations(world):
    setstate(world, signed_in=True, orgs=["acme"], orgs_error=True)
    rc, out = run(world, "orgs")
    assert rc == 1 and out.startswith("ORGS_UNKNOWN"), out


@pytest.mark.parametrize("bad", ["acme", "/x", "x/", "acme/brain/extra", "-f/x", "acme/-x"])
def test_retarget_rejects_malformed_targets_before_touching_anything(world, bad):
    setstate(world, signed_in=True)
    rc, out = run(world, "retarget", f"--to={bad}")       # = form, so argparse passes a leading dash through
    assert rc == 2 and out.startswith("USAGE"), (bad, out)
    assert subprocess.run(["git", "-C", str(world["vault"]), "remote", "get-url", "origin"],
                          capture_output=True).returncode != 0


def test_connect_owner_creates_in_the_organization_with_a_per_person_name(world):
    setstate(world, signed_in=True, bare=str(world["tmp"] / "remote.git"))
    rc, out = run(world, "connect", "--owner", "acme")
    assert rc == 0 and out.splitlines()[-1].startswith("CONNECTED"), out
    assert json.loads(world["state"].read_text())["created"] == "acme/brain-pat"


def test_connect_owner_keeps_an_explicit_name(world):
    setstate(world, signed_in=True, bare=str(world["tmp"] / "remote.git"))
    rc, out = run(world, "connect", "--owner", "acme", "--name", "pat-vault")
    assert rc == 0, out
    assert json.loads(world["state"].read_text())["created"] == "acme/pat-vault"


def test_connect_owner_reuses_an_empty_repo_the_admin_created(world):
    bare = world["tmp"] / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    setstate(world, signed_in=True, repos={"acme/brain-pat": {"empty": True, "visibility": "PRIVATE"}})
    world["env"]["SETUP_REMOTE_URL"] = str(bare)
    rc, out = run(world, "connect", "--owner", "acme")
    assert rc == 0, out
    assert "created" not in json.loads(world["state"].read_text())
    assert subprocess.run(["git", "-C", str(bare), "rev-parse", "main"], capture_output=True).returncode == 0


def test_connect_owner_stops_on_an_organization_policy(world):
    setstate(world, signed_in=True, bare=str(world["tmp"] / "bare.git"),
             create_error="HTTP 403: Resource not accessible by integration")
    rc, out = run(world, "connect", "--owner", "acme")
    assert rc == 3 and out.startswith("ORG_POLICY"), out
    assert not (world["tmp"] / "bare.git").exists()


def test_retarget_points_origin_at_a_private_repo_in_the_organization(world):
    old = world["tmp"] / "old.git"; new = world["tmp"] / "new.git"
    for b in (old, new):
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(b)], check=True)
    _set_origin(world, str(old))
    setstate(world, signed_in=True, repos={"acme/brain-pat": {"empty": True, "visibility": "PRIVATE"}})
    world["env"]["SETUP_REMOTE_URL"] = str(new)
    rc, out = run(world, "retarget", "--to", "acme/brain-pat")
    assert rc == 0 and out.startswith("RETARGETED"), out
    origin = subprocess.run(["git", "-C", str(world["vault"]), "remote", "get-url", "origin"],
                            capture_output=True, text=True).stdout.strip()
    assert origin == str(new)


def test_retarget_refuses_a_public_or_unknown_repo_and_keeps_origin(world):
    old = world["tmp"] / "old.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(old)], check=True)
    _set_origin(world, str(old))
    setstate(world, signed_in=True, repos={"acme/open": {"empty": True, "visibility": "PUBLIC"}})
    rc, out = run(world, "retarget", "--to", "acme/open")
    assert rc == 3 and out.startswith("REPO_NOT_PRIVATE"), out
    rc, out = run(world, "retarget", "--to", "acme/missing")
    assert rc == 3 and out.startswith("ORIGIN_UNVERIFIED"), out
    origin = subprocess.run(["git", "-C", str(world["vault"]), "remote", "get-url", "origin"],
                            capture_output=True, text=True).stdout.strip()
    assert origin == str(old)


def test_is_org_policy_matches_the_known_messages_only():
    for msg in ("GraphQL: Resource not accessible by integration",
                "HTTP 403: SAML enforcement: you must re-authorize",
                "repository creation is restricted by organization policy"):
        assert gh.is_org_policy(msg), msg
    for msg in ("remote: Repository not found.", "could not resolve host github.com", ""):
        assert not gh.is_org_policy(msg), msg


def test_login_start_asks_for_the_workflow_scope(world):
    """The first push carries .github/workflows/vault-autosync.yml, which GitHub refuses without the workflow scope."""
    rc, out = run(world, "login-start", "--timeout", "15")
    assert rc == 0, out
    argv = json.loads(world["state"].read_text())["login_argv"]
    assert "-s" in argv and argv[argv.index("-s") + 1] == "workflow", argv


def test_logout_signs_the_wrong_account_out_so_login_start_can_run_again(world):
    setstate(world, signed_in=True)
    rc, out = run(world, "logout")
    assert rc == 0 and out.startswith("SIGNED_OUT"), out
    assert not json.loads(world["state"].read_text()).get("signed_in")
    rc, out = run(world, "logout")                 # nothing to sign out of: still fine, still re-runnable
    assert rc == 0 and out.startswith("SIGNED_OUT"), out


def test_login_start_adds_the_workflow_scope_to_an_existing_sign_in(world):
    """gh was signed in before setup (or by an older setup) without the workflow scope: the first push would be rejected."""
    setstate(world, signed_in=True, scopes=["gist", "read:org", "repo"])
    rc, out = run(world, "login-start", "--timeout", "15")
    assert rc == 0, out
    assert "CODE WXYZ-5678" in out and "SAY " in out          # one more device-code approval, same words
    argv = json.loads(world["state"].read_text())["refresh_argv"]
    assert argv[:2] == ["auth", "refresh"] and "-s" in argv and argv[argv.index("-s") + 1] == "workflow", argv
    rc, out = run(world, "login-wait", "--timeout", "5")
    assert rc == 0 and "SIGNED_IN pat" in out
    assert "workflow" in json.loads(world["state"].read_text())["scopes"]


def test_login_wait_does_not_finish_on_a_sign_in_that_still_lacks_the_workflow_scope(world):
    """The refresh is pending: the old sign-in answers auth status, but the push would still be rejected."""
    setstate(world, signed_in=True, scopes=["gist", "read:org", "repo"])
    rc, out = run(world, "login-wait", "--timeout", "4")
    assert rc == 1 and out.startswith("LOGIN_TIMEOUT"), out


def test_login_start_leaves_a_sign_in_that_already_has_the_scope_alone(world):
    setstate(world, signed_in=True, scopes=["repo", "workflow"])
    rc, out = run(world, "login-start", "--timeout", "15")
    assert rc == 0 and out.strip() == "SIGNED_IN pat", out
    assert "refresh_argv" not in json.loads(world["state"].read_text())
