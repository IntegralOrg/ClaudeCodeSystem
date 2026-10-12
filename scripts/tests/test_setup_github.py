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
    if a[:1] == ["--version"]:
        print("gh version 9.9.9"); sys.exit(0)
    if a[:2] == ["auth", "status"]:
        sys.exit(0 if s.get("signed_in") else 1)
    if a[:2] == ["auth", "login"]:
        if s.get("no_code"):
            time.sleep(60); sys.exit(1)
        print("! First copy your one-time code: ABCD-1234", flush=True)
        print("Open this URL to continue in your web browser: https://github.com/login/device", flush=True)
        time.sleep(1); s["signed_in"] = True; json.dump(s, open(st, "w")); sys.exit(0)
    if a[:2] == ["api", "user"]:
        print("pat"); sys.exit(0)
    if a[:2] == ["repo", "view"]:
        r = s.get("repos", {}).get(a[2], s.get("remote_repo") if a[2] == "pat/brain" else None)
        if not r: sys.exit(1)
        print(json.dumps({"isEmpty": r["empty"], "visibility": r["visibility"]})); sys.exit(0)
    if a[:2] == ["repo", "create"]:
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
    assert json.loads(world["state"].read_text())["created"] == "brain-2"


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
