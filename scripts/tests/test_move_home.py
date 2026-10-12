import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "setup" / "move-home.sh"


def make_download(tmp_path):
    d = tmp_path / "Downloads" / "ClaudeCodeSystem-main"
    (d / "scripts" / "setup").mkdir(parents=True)
    shutil.copy(SCRIPT, d / "scripts" / "setup" / "move-home.sh")
    (d / "SETUP_PENDING").write_text("not set up\n")
    (d / "README.md").write_text("# brain\n")
    (d / ".gitignore").write_text("*.log\n")
    return d


def run(download, home, *args):
    env = {**os.environ, "HOME": str(home)}
    env.pop("GIT_DIR", None)
    p = subprocess.run(["bash", str(download / "scripts" / "setup" / "move-home.sh"),
                        "--name", "Pat Example", "--email", "pat@example.com", "--no-open", *args],
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stdout


def git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, text=True).stdout.strip()


def test_moves_copies_hidden_files_and_commits(tmp_path):
    dl, home = make_download(tmp_path), tmp_path / "home"
    home.mkdir()
    rc, out = run(dl, home)
    dest = home / "Brain"
    assert rc == 0, out
    assert f"HOME_READY {dest}" in out
    assert (dest / ".gitignore").is_file() and (dest / "SETUP_PENDING").is_file()
    assert git(dest, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert git(dest, "log", "--format=%an <%ae>") == "Pat Example <pat@example.com>"
    assert git(dest, "config", "user.email") == "pat@example.com"


def test_open_url_is_encoded(tmp_path):
    dl, home = make_download(tmp_path), tmp_path / "home dir"
    home.mkdir()
    rc, out = run(dl, home)
    url = next(l for l in out.splitlines() if l.startswith("OPEN_URL "))[len("OPEN_URL "):]
    assert url.startswith("claude://code/new?folder=")
    assert "%20" in url and " " not in url and url.endswith("&q=Continue%20setup")


def test_refuses_nonempty_destination(tmp_path):
    dl, home = make_download(tmp_path), tmp_path / "home"
    (home / "Brain").mkdir(parents=True); (home / "Brain" / "notes.md").write_text("mine")
    rc, out = run(dl, home)
    assert rc == 3 and out.startswith("DEST_NOT_EMPTY")
    assert (home / "Brain" / "notes.md").read_text() == "mine"


@pytest.mark.parametrize("sub", ["Library/Mobile Documents/com~apple~CloudDocs/Brain", "Dropbox/Brain",
                                 "OneDrive/Brain", "Documents/Brain", "Desktop/Brain"])
def test_refuses_synced_destinations(tmp_path, sub):
    dl, home = make_download(tmp_path), tmp_path / "home"
    home.mkdir()
    rc, out = run(dl, home, "--dest", str(home / sub))
    assert rc == 4 and out.startswith("SYNCED_PATH")


def test_rerun_resumes_a_partial_copy(tmp_path):
    dl, home = make_download(tmp_path), tmp_path / "home"
    (home / "Brain").mkdir(parents=True)
    shutil.copy(dl / "SETUP_PENDING", home / "Brain" / "SETUP_PENDING")   # a copy that died early
    rc, out = run(dl, home)
    assert rc == 0, out
    rc2, out2 = run(dl, home)
    assert rc2 == 0, out2
    assert git(home / "Brain", "rev-list", "--count", "HEAD") == "1"


def test_already_home_is_a_no_op(tmp_path):
    dl, home = make_download(tmp_path), tmp_path / "home"
    home.mkdir()
    rc, out = run(dl, home, "--dest", str(dl))
    assert rc == 0 and out.startswith("ALREADY_HOME")


def test_not_a_download_without_marker(tmp_path):
    dl, home = make_download(tmp_path), tmp_path / "home"
    home.mkdir(); (dl / "SETUP_PENDING").unlink()
    rc, out = run(dl, home)
    assert rc == 5 and out.startswith("NOT_A_DOWNLOAD")


def test_usage_requires_name_and_email(tmp_path):
    dl = make_download(tmp_path)
    p = subprocess.run(["bash", str(dl / "scripts" / "setup" / "move-home.sh"), "--no-open"],
                       capture_output=True, text=True)
    assert p.returncode == 2 and p.stdout.startswith("USAGE")
