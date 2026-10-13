"""cloud-land.sh must land what the SESSION changed, never what the container's working tree
happens to differ from main by. A container restored from a stale environment snapshot has a
working tree older than main; without a start-of-session snapshot the old script read that as
"the agent deleted and reverted everything newer" and pushed it (2026-10-13: 101 deletions,
109 reverts from a 13-second read-only session). These tests pin the guard."""
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SID = "sid1234567890abcdef"
SID8 = SID[:8]
REFUSALS = "_generated/landing/cloud-refusals"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


def commit_all(repo, msg):
    git(repo, "add", "-A"); git(repo, "commit", "-q", "-m", msg); return git(repo, "rev-parse", "HEAD")


def make_repos(tmp_path, nfiles=0):
    """bare origin + a clone whose HEAD and origin/main are the NEWER commit. Returns (repo, bare, seed, newer)."""
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(bare)], check=True)
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "cloud-land.sh", repo / "scripts" / "cloud-land.sh")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "user.email", "t@example.com"); git(repo, "config", "user.name", "t")
    git(repo, "remote", "add", "origin", str(bare))
    (repo / "a.md").write_text("a v1\n"); (repo / "b.md").write_text("b v1\n"); (repo / "old.md").write_text("old\n")
    for i in range(nfiles):
        (repo / f"f{i:02d}.md").write_text(f"f{i} v1\n")
    seed = commit_all(repo, "seed")
    (repo / "a.md").write_text("a v2\n"); (repo / "new-on-main.md").write_text("added on main\n")
    for i in range(nfiles):
        (repo / f"f{i:02d}.md").write_text(f"f{i} v2\n")
    newer = commit_all(repo, "newer")
    git(repo, "push", "-q", "origin", "main")
    return repo, bare, seed, newer


def make_stale(repo, seed):
    """Working tree and index back to the seed snapshot while HEAD stays at the newer commit."""
    git(repo, "read-tree", "--reset", "-u", seed)
    assert (repo / "a.md").read_text() == "a v1\n" and not (repo / "new-on-main.md").exists()


def run(repo, tmp_path, *args):
    env = dict(os.environ, CLAUDE_CODE_SESSION_ID=SID, CLOUD_LAND_TEST_DIR=str(tmp_path / "state"))
    p = subprocess.run(["bash", str(repo / "scripts" / "cloud-land.sh"), *args], capture_output=True, text=True, env=env, input="{}", timeout=60)
    assert p.returncode == 0 and p.stdout == "", p.stderr
    return p


def log(tmp_path):
    p = tmp_path / "state" / ".cloud-land" / "hook.log"
    return p.read_text() if p.exists() else ""


def main_files(bare):
    return set(git(bare, "ls-tree", "-r", "--name-only", "main").splitlines())


def main_file(bare, path):
    return subprocess.run(["git", "-C", str(bare), "show", f"main:{path}"], capture_output=True, text=True).stdout


def markers(bare):
    return sorted(f for f in main_files(bare) if f.startswith(REFUSALS))


def test_start_snapshots_the_tree_and_counts_stale_files(tmp_path):
    repo, bare, seed, newer = make_repos(tmp_path)
    make_stale(repo, seed)
    run(repo, tmp_path, "--start")
    text = log(tmp_path)
    assert "start snapshot" in text and "stale at start: 2 file(s)" in text  # a.md reverted, new-on-main.md missing
    assert (tmp_path / "state" / ".cloud-land" / "start-tree").read_text().strip()
    assert git(bare, "rev-parse", "main") == newer  # --start never lands anything


def test_stale_tree_lands_nothing_when_the_session_touched_nothing(tmp_path):
    repo, bare, seed, newer = make_repos(tmp_path)
    make_stale(repo, seed)
    run(repo, tmp_path, "--start")
    run(repo, tmp_path)
    run(repo, tmp_path, "--final")
    assert git(bare, "rev-parse", "main") == newer
    assert "nothing to land" in log(tmp_path) and "landed on main" not in log(tmp_path)


def test_edits_after_the_snapshot_land_exactly_even_on_a_stale_tree(tmp_path):
    repo, bare, seed, newer = make_repos(tmp_path)
    make_stale(repo, seed)
    run(repo, tmp_path, "--start")
    (repo / "new.md").write_text("by the agent\n")
    (repo / "b.md").write_text("b by the agent\n")
    (repo / "old.md").unlink()
    run(repo, tmp_path, "--final")
    files = main_files(bare)
    assert "new.md" in files and "old.md" not in files
    assert main_file(bare, "b.md") == "b by the agent\n"
    assert main_file(bare, "a.md") == "a v2\n"            # the stale copy of a.md was NOT landed as a revert
    assert "new-on-main.md" in files                      # the file missing from the stale tree was NOT deleted
    assert markers(bare) == []
    assert "landed on main (attempt 1): +2 -1" in log(tmp_path)


def test_a_second_turn_does_not_reland_or_clobber(tmp_path):
    repo, bare, seed, newer = make_repos(tmp_path)
    run(repo, tmp_path, "--start")
    (repo / "new.md").write_text("turn 1\n")
    run(repo, tmp_path)
    # someone else edits new.md on main between turns; the next turn must not clobber it with turn 1's content
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True)
    git(other, "config", "user.email", "o@example.com"); git(other, "config", "user.name", "o")
    (other / "new.md").write_text("edited elsewhere\n"); commit_all(other, "elsewhere"); git(other, "push", "-q", "origin", "main")
    (repo / "b.md").write_text("turn 2\n")
    run(repo, tmp_path, "--final")
    assert main_file(bare, "new.md") == "edited elsewhere\n" and main_file(bare, "b.md") == "turn 2\n"


def test_start_after_a_failed_landing_retains_the_snapshot(tmp_path):
    """/clear runs SessionStart again in the same container. If the last landing failed, a fresh
    snapshot would make the unlanded edits look untouched; the existing snapshot must be kept."""
    repo, bare, seed, newer = make_repos(tmp_path)
    run(repo, tmp_path, "--start")
    first = (tmp_path / "state" / ".cloud-land" / "start-tree").read_text()
    (repo / "new.md").write_text("unlanded edit\n")
    git(repo, "remote", "set-url", "origin", str(tmp_path / "nowhere.git"))   # the landing cannot reach origin
    run(repo, tmp_path)
    assert "fetch failed" in log(tmp_path) and git(bare, "rev-parse", "main") == newer
    run(repo, tmp_path, "--start")                                             # /clear
    assert (tmp_path / "state" / ".cloud-land" / "start-tree").read_text() == first
    assert "retaining start snapshot" in log(tmp_path)
    git(repo, "remote", "set-url", "origin", str(bare))
    run(repo, tmp_path, "--final")
    assert main_file(bare, "new.md") == "unlanded edit\n"


def test_start_after_a_successful_landing_keeps_the_relanded_baseline(tmp_path):
    repo, bare, seed, newer = make_repos(tmp_path)
    run(repo, tmp_path, "--start")
    (repo / "new.md").write_text("turn 1\n")
    run(repo, tmp_path)
    landed = (tmp_path / "state" / ".cloud-land" / "start-tree").read_text()
    run(repo, tmp_path, "--start")                                             # /clear after a clean landing
    assert (tmp_path / "state" / ".cloud-land" / "start-tree").read_text() == landed
    run(repo, tmp_path, "--final")
    assert log(tmp_path).splitlines()[-1].endswith("nothing to land")
    assert git(bare, "log", "--oneline", "main").count("\n") == 2            # seed, newer, turn 1: nothing re-landed


def test_without_a_snapshot_deletions_are_refused_and_recorded(tmp_path):
    repo, bare, seed, newer = make_repos(tmp_path)
    (repo / "new.md").write_text("by the agent\n")
    (repo / "old.md").unlink()
    run(repo, tmp_path, "--final")
    files = main_files(bare)
    assert "new.md" in files and "old.md" in files        # the add lands, the deletion does not
    assert len(markers(bare)) == 1 and markers(bare)[0].endswith(f"-{SID8}.json")
    rec = json.loads(main_file(bare, markers(bare)[0]))
    assert rec["session_id"] == SID and rec["refused_deletions"] == 1 and "old.md" in rec["sample"]
    assert "no start snapshot" in rec["reason"]
    assert "refused 1 deletion(s)" in log(tmp_path)


def test_without_a_snapshot_a_large_delta_is_refused_entirely(tmp_path):
    repo, bare, seed, newer = make_repos(tmp_path, nfiles=30)
    make_stale(repo, seed)                                  # 31 reverts + 1 deletion, no snapshot
    run(repo, tmp_path, "--final")
    assert main_file(bare, "f00.md") == "f0 v2\n" and main_file(bare, "a.md") == "a v2\n"
    assert "new-on-main.md" in main_files(bare)
    assert len(markers(bare)) == 1
    rec = json.loads(main_file(bare, markers(bare)[0]))
    assert rec["refused_changes"] == 31 and rec["refused_deletions"] == 1 and "exceeds" in rec["reason"]
    # only the marker was added to main
    assert main_files(bare) - {markers(bare)[0]} == set(git(bare, "ls-tree", "-r", "--name-only", newer).splitlines())


def test_small_delta_without_a_snapshot_still_lands(tmp_path):
    repo, bare, seed, newer = make_repos(tmp_path)
    (repo / "b.md").write_text("b by the agent\n")
    run(repo, tmp_path, "--final")
    assert main_file(bare, "b.md") == "b by the agent\n" and markers(bare) == []
