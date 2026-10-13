"""cloud-journal.sh lands only ITS OWN session's journal and evidence files. Copying every
evidence file from the container let a stale container overwrite fresh records on main."""
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SID = "aaaa1111-2222-3333-4444-555566667777"
SID8 = SID[:8]
OTHER = "bbbb9999-2222-3333-4444-555566667777"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


def test_journal_lands_only_its_own_session_files(tmp_path):
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(bare)], check=True)
    repo = tmp_path / "repo"
    sj = repo / "scripts" / "system-journal"
    sj.mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "system-journal" / "cloud-journal.sh", sj / "cloud-journal.sh")
    # Stubs: extract.py writes this session's evidence AND leaves a stale copy of another session's
    # evidence in the container; distill.py writes this session's journal line and a stray other one.
    (sj / "extract.py").write_text(
        "import os,sys\n"
        "v=sys.argv[sys.argv.index('--vault')+1]; d=os.path.join(v,'_generated/system-journal/evidence/2026-10'); os.makedirs(d,exist_ok=True)\n"
        f"open(os.path.join(d,'{SID}.json'),'w').write('{{\"own\": true}}\\n')\n"
        f"open(os.path.join(d,'{OTHER}.json'),'w').write('{{\"stale\": true}}\\n')\n")
    (sj / "distill.py").write_text(
        "import os,sys\n"
        "d=sys.argv[sys.argv.index('--cloud-dir')+1]; os.makedirs(d,exist_ok=True)\n"
        f"open(os.path.join(d,'2026-10-13.{SID8}.json'),'w').write('{{\"own\": true}}\\n')\n"
        f"open(os.path.join(d,'2026-10-13.{OTHER[:8]}.json'),'w').write('{{\"stray\": true}}\\n')\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "user.email", "t@example.com"); git(repo, "config", "user.name", "t")
    git(repo, "remote", "add", "origin", str(bare))
    fresh = repo / "_generated" / "system-journal" / "evidence" / "2026-10"
    fresh.mkdir(parents=True)
    (fresh / f"{OTHER}.json").write_text('{"fresh": true}\n')
    git(repo, "add", "-A"); git(repo, "commit", "-q", "-m", "seed"); git(repo, "push", "-q", "origin", "main")
    # a stub `claude` so the script's `command -v claude` passes without calling anything
    binstub = tmp_path / "bin"; binstub.mkdir()
    (binstub / "claude").write_text("#!/bin/sh\nexit 0\n"); (binstub / "claude").chmod(0o755)
    env = dict(os.environ, CLAUDE_CODE_SESSION_ID=SID, CLOUD_JOURNAL_TEST_DIR=str(tmp_path / "state"))
    env["PATH"] = f"{binstub}:{env.get('PATH', '')}"
    p = subprocess.run(["bash", str(sj / "cloud-journal.sh"), "--final"], capture_output=True, text=True, env=env, input="{}", timeout=60)
    assert p.returncode == 0 and p.stdout == ""
    log = (tmp_path / "state" / ".system-journal" / "hook.log").read_text()
    assert "landed on main" in log, log
    files = set(git(bare, "ls-tree", "-r", "--name-only", "main").splitlines())
    assert f"_generated/system-journal/cloud/2026-10-13.{SID8}.json" in files
    assert f"_generated/system-journal/evidence/2026-10/{SID}.json" in files
    assert f"_generated/system-journal/cloud/2026-10-13.{OTHER[:8]}.json" not in files
    stale_on_main = subprocess.run(["git", "-C", str(bare), "show", f"main:_generated/system-journal/evidence/2026-10/{OTHER}.json"], capture_output=True, text=True).stdout
    assert stale_on_main == '{"fresh": true}\n'   # the container's stale copy did not overwrite main
