#!/usr/bin/env python3
"""GitHub for a new vault, with one browser approval from the person and no app to install.

Each step checks first, so any step can be re-run:
  status       one JSON line: gh path, signed in, origin, reachable
  install-gh   download the GitHub CLI into the user's own folder (no admin rights)
  login-start  start the browser sign-in in the background, copy the one-time code, open the page
  login-wait   wait until the sign-in finishes
  connect      make Git use gh for github.com, create the private repo `brain` (or reuse an empty one), push
  verify       GIT_TERMINAL_PROMPT=0 git ls-remote origin
Stdout: the first token is stable (GH_READY, CODE, SAY, SIGNED_IN, CONNECTED, REACHABLE, or a failure token).
Exit: 0 ok, 1 failed, 2 usage, 3 needs the person.
Test hooks: SETUP_NO_UI=1 (no clipboard, no browser), SETUP_GH, SETUP_BIN_DIR, SETUP_REMOTE_URL.
"""
import argparse
import io
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile

PINNED_VERSION = "2.102.0"
DEVICE_URL = "https://github.com/login/device"
CODE_RE = re.compile(r"\b([A-Z0-9]{4}-[A-Z0-9]{4})\b")
SAY_LOGIN = ("SAY The code is already copied. On the GitHub page that just opened, paste it, click Continue, "
             "then click the green Authorize button. Come back here when GitHub says you are done.")


def out(token, msg=""):
    print(f"{token} {msg}".rstrip(), flush=True)


def fail(token, msg, code=1):
    out(token, msg)
    sys.exit(code)


def asset_name(version, system, machine):
    m = machine.lower()
    arch = "arm64" if m in ("arm64", "aarch64") else "amd64"
    if system == "Darwin":
        return f"gh_{version}_macOS_{arch}.zip"
    if system == "Windows":
        return f"gh_{version}_windows_{arch}.zip"
    return f"gh_{version}_linux_{arch}.tar.gz"


def helper_value(gh_path):
    # Git runs the helper through sh: forward slashes, and an apostrophe (C:/Users/O'Brien) closed and re-opened.
    return "!'" + gh_path.replace("\\", "/").replace("'", "'\\''") + "' auth git-credential"


def bin_dir():
    if os.environ.get("SETUP_BIN_DIR"):
        return os.environ["SETUP_BIN_DIR"]
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", "gh")
    return os.path.expanduser("~/.local/bin")


def gh_path():
    if os.environ.get("SETUP_GH"):
        return os.environ["SETUP_GH"]
    exe = "gh.exe" if platform.system() == "Windows" else "gh"
    local = os.path.join(bin_dir(), exe)
    return local if os.path.isfile(local) else shutil.which("gh")


def run(cmd, cwd=None, timeout=120, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def git(vault, *args, timeout=120):
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return run(["git", "-C", vault, *args], timeout=timeout, env=env)


def ui_copy(text):
    if os.environ.get("SETUP_NO_UI"):
        return
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["pbcopy"], input=text.encode(), check=False)
    elif system == "Windows":
        subprocess.run(["clip"], input=text.encode("ascii", "ignore"), check=False)   # the code is ASCII
    elif shutil.which("xclip"):
        subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=False)


def ui_open(url):
    if os.environ.get("SETUP_NO_UI"):
        return
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", url], check=False)
    elif system == "Windows":
        os.startfile(url)  # noqa: S606 - opening the GitHub sign-in page is the point
    else:
        subprocess.run(["xdg-open", url], check=False)


def latest_version():
    try:
        with urllib.request.urlopen("https://api.github.com/repos/cli/cli/releases/latest", timeout=15) as r:
            return json.load(r)["tag_name"].lstrip("v")
    except Exception:
        return PINNED_VERSION


def cmd_install_gh(a):
    existing = gh_path()
    if existing and run([existing, "--version"]).returncode == 0:
        return out("GH_READY", existing)
    version = latest_version()
    name = asset_name(version, platform.system(), platform.machine())
    url = f"https://github.com/cli/cli/releases/download/v{version}/{name}"
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
    except Exception as e:
        fail("GH_INSTALL_FAILED", f"could not download {url}: {e}")
    exe = "gh.exe" if platform.system() == "Windows" else "gh"
    with tempfile.TemporaryDirectory() as tmp:
        if name.endswith(".zip"):
            zipfile.ZipFile(io.BytesIO(data)).extractall(tmp)
        else:
            tarfile.open(fileobj=io.BytesIO(data)).extractall(tmp)
        found = [os.path.join(d, exe) for d, _, files in os.walk(tmp) if exe in files and os.path.basename(d) == "bin"]
        if not found:
            fail("GH_INSTALL_FAILED", f"{exe} not found inside {name}")
        os.makedirs(bin_dir(), exist_ok=True)
        dest = os.path.join(bin_dir(), exe)
        shutil.copy2(found[0], dest)
        os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if run([dest, "--version"]).returncode != 0:
        fail("GH_INSTALL_FAILED", f"{dest} does not run")
    out("GH_READY", dest)


def need_gh():
    p = gh_path()
    if not p:
        fail("GH_MISSING", "run install-gh first")
    return p


def signed_in(gh):
    return run([gh, "auth", "status", "-h", "github.com"]).returncode == 0


def cmd_login_start(a):
    gh = need_gh()
    if signed_in(gh):
        return out("SIGNED_IN", run([gh, "api", "user", "--jq", ".login"]).stdout.strip())
    logdir = os.path.join(a.vault, "_generated", "setup")
    os.makedirs(logdir, exist_ok=True)
    log = os.path.join(logdir, "github-login.log")
    kw = {"stdin": subprocess.DEVNULL, "stdout": open(log, "w"), "stderr": subprocess.STDOUT}
    if platform.system() == "Windows":
        kw["creationflags"] = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen([gh, "auth", "login", "--web", "-h", "github.com", "-p", "https"], **kw)
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        with open(log, encoding="utf-8", errors="replace") as f:
            m = CODE_RE.search(f.read())
        if m:
            ui_copy(m.group(1))
            ui_open(DEVICE_URL)
            out("CODE", m.group(1))
            return print(SAY_LOGIN, flush=True)
        time.sleep(0.5)
    fail("LOGIN_NO_CODE", "GitHub did not answer; check the internet connection and run login-start again")


def cmd_login_wait(a):
    gh = need_gh()
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        if signed_in(gh):
            return out("SIGNED_IN", run([gh, "api", "user", "--jq", ".login"]).stdout.strip())
        time.sleep(3)
    fail("LOGIN_TIMEOUT", "the GitHub approval did not finish; run login-start again for a fresh code")


def configure_helper(gh):
    key = "credential.https://github.com.helper"
    run(["git", "config", "--global", "--unset-all", key])
    run(["git", "config", "--global", "--add", key, ""])
    r = run(["git", "config", "--global", "--add", key, helper_value(os.path.abspath(gh))])
    if r.returncode != 0:
        fail("PUSH_FAILED", "could not point Git at the GitHub sign-in: " + r.stderr.strip()[:200])


def cmd_connect(a):
    gh = need_gh()
    if not signed_in(gh):
        fail("LOGIN_NEEDED", "run login-start first", 3)
    configure_helper(gh)
    login = run([gh, "api", "user", "--jq", ".login"]).stdout.strip()
    origin = git(a.vault, "remote", "get-url", "origin")
    has_origin = origin.returncode == 0
    if has_origin:
        # A rerun reaches the private repository an earlier run created (it has files: that is fine). Anything
        # else is refused before a single byte is pushed: a public repository would publish the person's notes.
        url = origin.stdout.strip()
        view = run([gh, "repo", "view", url, "--json", "visibility"])
        if view.returncode != 0:
            fail("ORIGIN_UNVERIFIED", f"could not confirm {url} is this person's private repository", 3)
        if json.loads(view.stdout or "{}").get("visibility") != "PRIVATE":
            fail("REPO_NOT_PRIVATE", f"{url} is not private; nothing was pushed", 3)
    else:
        view = run([gh, "repo", "view", f"{login}/{a.name}", "--json", "isEmpty,visibility"])
        if view.returncode != 0:
            r = run([gh, "repo", "create", a.name, "--private", "--source", a.vault, "--remote", "origin", "--push"],
                    cwd=a.vault, timeout=300)
            if r.returncode != 0:
                fail("PUSH_FAILED", r.stderr.strip()[:300] or "creating the repository failed")
        else:
            info = json.loads(view.stdout or "{}")
            if info.get("visibility") != "PRIVATE":
                fail("REPO_NOT_PRIVATE", f"github.com/{login}/{a.name} exists and is not private", 3)
            if not info.get("isEmpty"):
                fail("REPO_EXISTS", f"github.com/{login}/{a.name} already has files; ask which name to use, "
                                    "then run connect --name <new name>", 3)
            url = os.environ.get("SETUP_REMOTE_URL") or f"https://github.com/{login}/{a.name}.git"
            git(a.vault, "remote", "add", "origin", url)
    push = git(a.vault, "push", "-u", "origin", "main", timeout=300)
    if push.returncode != 0:
        fail("PUSH_FAILED", push.stderr.strip()[:300])
    out("CONNECTED", git(a.vault, "remote", "get-url", "origin").stdout.strip())


def cmd_verify(a):
    r = git(a.vault, "ls-remote", "origin", timeout=60)
    if r.returncode != 0:
        fail("UNREACHABLE", (r.stderr.strip() or "no origin")[:300])
    out("REACHABLE")


def cmd_status(a):
    gh = gh_path()
    origin = git(a.vault, "remote", "get-url", "origin")
    print(json.dumps({"gh": gh, "signed_in": bool(gh) and signed_in(gh),
                      "origin": origin.stdout.strip() if origin.returncode == 0 else None,
                      "reachable": git(a.vault, "ls-remote", "origin", timeout=60).returncode == 0}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["status", "install-gh", "login-start", "login-wait", "connect", "verify"])
    ap.add_argument("--vault", default=os.getcwd())
    ap.add_argument("--timeout", type=float, default=None)
    ap.add_argument("--name", default="brain", help="connect: the repository name (default brain)")
    a = ap.parse_args()
    a.vault = os.path.abspath(a.vault)
    if a.timeout is None:
        a.timeout = 30 if a.step == "login-start" else 600
    {"status": cmd_status, "install-gh": cmd_install_gh, "login-start": cmd_login_start,
     "login-wait": cmd_login_wait, "connect": cmd_connect, "verify": cmd_verify}[a.step](a)


if __name__ == "__main__":
    main()
