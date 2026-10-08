import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "land-local.sh"
CRED = ".env"


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


def test_first_local_landing_from_clean_clone(world):
    a = world["a"]; (a / "Notes.md").write_text("hello\n")
    p = land(world, a, "--final")
    assert p.returncode == 0 and p.stdout == ""
    assert "Notes.md" in landed(a) and git(a, "rev-parse", "HEAD") == git(a, "rev-parse", "origin/main")
    assert "Session sid12345" in git(a, "log", "-1", "--format=%s")


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
    assert p.returncode == 0
    git(a, "fetch", "-q", "origin"); text = git(a, "show", "origin/main:README.md")
    assert "from a" in text and "from b" in text


def test_non_markdown_conflict_is_logged_and_left(tmp_path):
    w = make_world(tmp_path, union=False)
    a, b = w["a"], w["b"]
    (b / "data.json").write_text('{"v": 1}\n'); land(w, b, "--final")
    (a / "data.json").write_text('{"v": 2}\n'); p = land(w, a, "--final")
    assert p.returncode == 0
    assert "conflict" in (a / "_generated" / "landing.log").read_text()
    assert (a / "data.json").read_text() == '{"v": 2}\n'
    assert not (a / ".git" / "rebase-merge").exists() and not (a / ".git" / "rebase-apply").exists()


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
