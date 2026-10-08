"""The cloud hooks run in any cloud session on a repo with committed settings, including the
template itself. They must refuse to land or journal when origin is the template repository."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD_FORMS = [
    "https://github.com/IntegralOrg/ClaudeCodeSystem.git",
    "https://github.com/integralorg/claudecodesystem",
    "git@github.com:IntegralOrg/ClaudeCodeSystem-Cloud.git",
    "https://github.com/StackDev223/ClaudeCodeSystem.git/",
]


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


def make_repo(tmp_path, origin_url):
    repo = tmp_path / "repo"
    (repo / "scripts" / "system-journal").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "cloud-land.sh", repo / "scripts" / "cloud-land.sh")
    shutil.copy(ROOT / "scripts" / "system-journal" / "cloud-journal.sh", repo / "scripts" / "system-journal" / "cloud-journal.sh")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "user.email", "t@example.com"); git(repo, "config", "user.name", "t")
    (repo / "note.md").write_text("hello\n")
    git(repo, "add", "-A"); git(repo, "commit", "-q", "-m", "seed")
    git(repo, "remote", "add", "origin", origin_url)
    return repo


def run(script, repo, tmp_path, var):
    env = {k: v for k, v in os.environ.items() if k not in ("CLOUD_LAND_TEST_DIR", "CLOUD_JOURNAL_TEST_DIR")}
    env.update(CLAUDE_CODE_SESSION_ID="sid12345678", **{var: str(tmp_path / "state")})
    return subprocess.run(["bash", str(repo / script), "--final"], capture_output=True, text=True, env=env, input="{}", timeout=60)


def log_text(tmp_path, sub):
    p = tmp_path / "state" / sub / "hook.log"
    return p.read_text() if p.exists() else ""


@pytest.mark.parametrize("url", GUARD_FORMS)
def test_cloud_land_disabled_on_template(tmp_path, url):
    repo = make_repo(tmp_path, url)
    (repo / "new.md").write_text("new\n")
    p = run("scripts/cloud-land.sh", repo, tmp_path, "CLOUD_LAND_TEST_DIR")
    assert p.returncode == 0 and p.stdout == ""
    log = log_text(tmp_path, ".cloud-land")
    assert "origin is the template repository; landing disabled" in log
    assert "cloud-land start" not in log and "landed on main" not in log


@pytest.mark.parametrize("url", GUARD_FORMS)
def test_cloud_journal_disabled_on_template(tmp_path, url):
    repo = make_repo(tmp_path, url)
    p = run("scripts/system-journal/cloud-journal.sh", repo, tmp_path, "CLOUD_JOURNAL_TEST_DIR")
    assert p.returncode == 0 and p.stdout == ""
    log = log_text(tmp_path, ".system-journal")
    assert "origin is the template repository; journal disabled" in log
    assert "cloud-journal start" not in log
    assert not (repo / "_generated").exists()  # nothing created in the template


def test_cloud_land_non_template_passes_the_guard(tmp_path):
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(bare)], check=True)
    repo = make_repo(tmp_path, str(bare))
    git(repo, "push", "-q", "origin", "main")
    (repo / "new.md").write_text("new\n")
    p = run("scripts/cloud-land.sh", repo, tmp_path, "CLOUD_LAND_TEST_DIR")
    assert p.returncode == 0
    log = log_text(tmp_path, ".cloud-land")
    assert "template repository" not in log and "cloud-land start" in log


def test_cloud_journal_non_template_passes_the_guard(tmp_path):
    repo = make_repo(tmp_path, "https://github.com/someone/ClaudeCodeSystem-Foo.git")
    p = run("scripts/system-journal/cloud-journal.sh", repo, tmp_path, "CLOUD_JOURNAL_TEST_DIR")
    assert p.returncode == 0
    assert "template repository" not in log_text(tmp_path, ".system-journal")
