import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "land-local.sh"
CRED = ".env"
STAMPED = re.compile(r"^\d{4}-\d{2}-\d{2} \d\d:\d\d:\d\d ")


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


def make_world(tmp_path, union=True):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(origin)], check=True)
    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", "-q", str(origin), str(seed)], check=True)
    git(seed, "config", "user.email", "t@example.com"); git(seed, "config", "user.name", "t")
    (seed / "README.md").write_text("# brain\n")
    (seed / ".gitignore").write_text(CRED + "\n_generated/landing.log\n")
    if union:
        (seed / ".gitattributes").write_text("*.md merge=union\n")
    git(seed, "add", "-A"); git(seed, "commit", "-q", "-m", "seed"); git(seed, "push", "-q", "origin", "main")
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        subprocess.run(["git", "clone", "-q", str(origin), str(d)], check=True)
        git(d, "config", "user.email", "t@example.com"); git(d, "config", "user.name", "t")
    return {"origin": origin, "a": a, "b": b, "state": tmp_path / "state"}


@pytest.fixture
def world(tmp_path):
    return make_world(tmp_path)


def land(w, clone, *args, sid="sid12345678", stdin_sid=None, extra_env=None):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    if sid:
        env["CLAUDE_CODE_SESSION_ID"] = sid
    env.update(CLAUDE_PROJECT_DIR=str(clone), LAND_LOCAL_STATE=str(w["state"] / clone.name), LAND_LOCAL_FORCE_LOCAL="1")
    env.update(extra_env or {})
    payload = json.dumps({"session_id": stdin_sid} if stdin_sid else {})
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, input=payload, timeout=60)


def landed(clone):
    return git(clone, "ls-tree", "-r", "--name-only", "origin/main") if git(clone, "fetch", "-q", "origin") == "" else ""


def origin_tip(w):
    return git(w["origin"], "rev-parse", "main")


def test_first_local_landing_from_clean_clone(world):
    a = world["a"]; (a / "Notes.md").write_text("hello\n")
    p = land(world, a, "--final")
    assert p.returncode == 0 and p.stdout == ""
    assert "Notes.md" in landed(a) and git(a, "rev-parse", "HEAD") == git(a, "rev-parse", "origin/main")
    assert "Session sid12345" in git(a, "log", "-1", "--format=%s")
    assert not any(n.startswith("_generated/") for n in landed(a).splitlines())  # the landing logs never land


def test_session_id_from_stdin_then_env_then_local(world):
    a = world["a"]
    (a / "s1.md").write_text("1\n"); land(world, a, "--final", sid="envid000", stdin_sid="stdinid00")
    assert "Session stdinid0" in git(a, "log", "-1", "--format=%s")
    (a / "s2.md").write_text("2\n"); land(world, a, "--final", sid=None)
    assert "Session local" in git(a, "log", "-1", "--format=%s")


def test_ignored_files_never_land(world):
    a = world["a"]; (a / CRED).write_text("SECRET=1\n"); (a / "x.md").write_text("x\n")
    land(world, a, "--final")
    assert CRED not in landed(a) and "x.md" in landed(a)


def test_pulls_other_machines_changes_first(world):
    a, b = world["a"], world["b"]
    (b / "FromB.md").write_text("b\n"); land(world, b, "--final")
    (a / "FromA.md").write_text("a\n"); land(world, a, "--final")
    names = landed(a); assert "FromA.md" in names and "FromB.md" in names
    assert git(a, "rev-parse", "HEAD") == git(a, "rev-parse", "origin/main")


def test_markdown_conflict_union_merges(world):
    a, b = world["a"], world["b"]
    (b / "README.md").write_text("# brain\nfrom b\n"); land(world, b, "--final")
    (a / "README.md").write_text("# brain\nfrom a\n"); p = land(world, a, "--final")
    assert p.returncode == 0 and p.stdout == ""
    git(a, "fetch", "-q", "origin"); text = git(a, "show", "origin/main:README.md")
    assert "from a" in text and "from b" in text


def test_non_markdown_conflict_is_logged_and_left(tmp_path):
    w = make_world(tmp_path, union=False)
    a, b = w["a"], w["b"]
    (b / "data.json").write_text('{"v": 1}\n'); land(w, b, "--final")
    (a / "data.json").write_text('{"v": 2}\n'); p = land(w, a, "--final")
    assert p.returncode == 0 and p.stdout == ""
    log = (a / "_generated" / "landing.log").read_text()
    assert "conflict" in log
    assert all(STAMPED.match(l) for l in log.splitlines())  # raw git output never reaches landing.log
    assert (a / "_generated" / "landing-git.log").is_file()
    assert (a / "data.json").read_text() == '{"v": 2}\n'
    assert not (a / ".git" / "rebase-merge").exists() and not (a / ".git" / "rebase-apply").exists()


def test_mid_merge_never_commits_conflict_markers(tmp_path):
    w = make_world(tmp_path, union=False)
    a, b = w["a"], w["b"]
    (b / "data.json").write_text('{"v": 1}\n'); land(w, b, "--final")
    (a / "data.json").write_text('{"v": 2}\n'); git(a, "add", "data.json"); git(a, "commit", "-q", "-m", "local")
    subprocess.run(["git", "-C", str(a), "pull", "--no-rebase", "-q", "origin", "main"], capture_output=True, text=True)
    assert (a / ".git" / "MERGE_HEAD").exists() and git(a, "ls-files", "-u")
    before = origin_tip(w)
    p = land(w, a, "--final")
    assert p.returncode == 0 and p.stdout == ""
    assert origin_tip(w) == before
    assert "skipped: repository is mid-merge/rebase/cherry-pick/revert" in (a / "_generated" / "landing.log").read_text()
    assert (a / ".git" / "MERGE_HEAD").exists() and "<<<<<<<" in (a / "data.json").read_text()


@pytest.mark.parametrize("marker", ["CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"])
def test_other_in_progress_operations_skip(world, marker):
    a = world["a"]; (a / "n.md").write_text("n\n")
    path = a / ".git" / marker
    path.mkdir() if marker.startswith("rebase") else path.write_text("x\n")
    before = origin_tip(world)
    p = land(world, a, "--final")
    assert p.returncode == 0 and origin_tip(world) == before
    assert "mid-merge/rebase/cherry-pick/revert" in (a / "_generated" / "landing.log").read_text()


def test_throttle_skips_rapid_stops_but_final_bypasses(world):
    a = world["a"]
    (a / "one.md").write_text("1\n"); land(world, a)
    (a / "two.md").write_text("2\n"); land(world, a)
    assert "throttled" in (a / "_generated" / "landing.log").read_text()
    land(world, a, "--final"); assert "two.md" in landed(a)


def test_lock_prevents_concurrent_landing(world):
    a = world["a"]; (a / "n.md").write_text("n\n")
    state = world["state"] / a.name; state.mkdir(parents=True); (state / "lock").mkdir()
    p = land(world, a, "--final")
    assert p.returncode == 0 and "locked" in (a / "_generated" / "landing.log").read_text()
    assert "n.md" not in landed(a)


def test_stale_lock_is_removed_and_landing_proceeds(world):
    a = world["a"]; (a / "n.md").write_text("n\n")
    state = world["state"] / a.name; state.mkdir(parents=True); lock = state / "lock"; lock.mkdir()
    old = time.time() - 3600; os.utime(lock, (old, old))
    p = land(world, a, "--final")
    log = (a / "_generated" / "landing.log").read_text()
    assert p.returncode == 0 and "stale lock removed" in log and "landed on main" in log
    assert "n.md" in landed(a) and not lock.exists()


def test_landing_log_is_capped(world):
    a = world["a"]; (a / "n.md").write_text("n\n")
    (a / "_generated").mkdir()
    (a / "_generated" / "landing.log").write_text("".join(f"2026-01-01 00:00:00 filler {i}\n" for i in range(4500)))
    land(world, a, "--final")
    lines = (a / "_generated" / "landing.log").read_text().splitlines()
    assert len(lines) < 2100 and "landed on main" in lines[-1]
    assert not (a / "_generated" / "landing.tmp.log").exists()


def test_landing_git_log_is_capped(world):
    a = world["a"]; (a / "n.md").write_text("n\n")
    (a / "_generated").mkdir()
    (a / "_generated" / "landing-git.log").write_text("".join(f"raw git output {i}\n" for i in range(4500)))
    land(world, a, "--final")
    lines = (a / "_generated" / "landing-git.log").read_text().splitlines()
    assert len(lines) < 2200
    assert not (a / "_generated" / "landing.tmp.log").exists()


def test_credential_files_never_land_even_if_the_ignore_file_forgets_them(world):
    a = world["a"]
    (a / ".gitignore").write_text("_generated/landing.log\n")  # no credentials line
    (a / CRED).write_text("SECRET=1\n"); (a / (CRED + ".local")).write_text("SECRET=2\n")
    (a / "sub").mkdir(); (a / "sub" / CRED).write_text("SECRET=3\n")
    (a / "tls.pem").write_text("pem\n"); (a / "sub" / "id.key").write_text("key\n"); (a / "AuthKey.p8").write_text("p8\n")
    (a / "ok.md").write_text("ok\n")
    land(world, a, "--final")
    names = landed(a).splitlines()
    assert "ok.md" in names
    for bad in (CRED, CRED + ".local", "sub/" + CRED, "tls.pem", "sub/id.key", "AuthKey.p8"):
        assert bad not in names, bad


def test_exits_silently_inside_a_cloud_container(world):
    a = world["a"]; (a / "c.md").write_text("c\n")
    p = land(world, a, "--final", extra_env={"LAND_LOCAL_FORCE_LOCAL": "", "LAND_LOCAL_FORCE_CLOUD": "1"})
    assert p.returncode == 0 and not (a / "_generated" / "landing.log").exists() and "c.md" not in landed(a)


def test_template_origin_never_lands(tmp_path, world):
    a = world["a"]; git(a, "remote", "set-url", "origin", "https://github.com/IntegralOrg/ClaudeCodeSystem.git")
    (a / "t.md").write_text("t\n"); p = land(world, a, "--final")
    assert p.returncode == 0 and "template repository" in (a / "_generated" / "landing.log").read_text()


def test_template_origin_forms_never_land(world):
    a = world["a"]
    for i, url in enumerate(("git@github.com:IntegralOrg/ClaudeCodeSystem-Cloud.git", "https://github.com/StackDev223/ClaudeCodeSystem",
                             "https://user:tok@github.com/INTEGRALORG/claudecodesystem.git/")):
        git(a, "remote", "set-url", "origin", url)
        (a / f"t{i}.md").write_text("t\n"); p = land(world, a, "--final")
        assert p.returncode == 0, url
    assert (a / "_generated" / "landing.log").read_text().count("template repository") == 3


def test_lookalike_origin_is_not_the_template(world, tmp_path):
    a = world["a"]
    clone = tmp_path / "IntegralOrg" / "ClaudeCodeSystem-Foo.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(world["origin"]), str(clone)], check=True)
    git(a, "remote", "set-url", "origin", str(clone))
    (a / "f.md").write_text("f\n"); land(world, a, "--final")
    log = (a / "_generated" / "landing.log").read_text()
    assert "template repository" not in log and "landed on main" in log


def test_no_origin_means_no_op(world, tmp_path):
    lone = tmp_path / "lone"; subprocess.run(["git", "init", "-q", "-b", "main", str(lone)], check=True)
    (lone / "a.md").write_text("a\n"); p = land(world, lone, "--final")
    assert p.returncode == 0 and "no origin" in (lone / "_generated" / "landing.log").read_text()
