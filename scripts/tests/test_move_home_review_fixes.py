"""Final-review fixes for move-home.sh: absolute destinations, marker-first copy, no overwrite of a ready home."""
import os
import subprocess

from test_move_home import make_download, run


def test_tilde_and_relative_destinations_resolve_under_home(tmp_path):
    dl, home = make_download(tmp_path), tmp_path / "home"
    home.mkdir()
    rc, out = run(dl, home, "--dest", "~/Brain-2")
    assert rc == 0 and f"HOME_READY {home / 'Brain-2'}" in out, out
    rc, out = run(dl, home, "--dest", "Brain-3")
    assert rc == 0 and f"HOME_READY {home / 'Brain-3'}" in out, out
    assert not any("~" in p.name for p in dl.rglob("*"))


def test_destination_inside_the_download_is_refused(tmp_path):
    dl, home = make_download(tmp_path), tmp_path / "home"
    home.mkdir()
    rc, out = run(dl, home, "--dest", str(dl / "inner"))
    assert rc == 2 and out.startswith("USAGE") and not (dl / "inner").exists()


def test_crash_mid_copy_resumes_because_the_marker_goes_first(tmp_path):
    dl, home = make_download(tmp_path), tmp_path / "home"
    home.mkdir()
    shim = tmp_path / "shim"
    shim.mkdir()
    # A cp that copies the marker for real but dies after one other file: a crash halfway through the copy.
    (shim / "cp").write_text(
        "#!/bin/bash\n"
        'case "$*" in *SETUP_PENDING*) exec /bin/cp "$@" ;; esac\n'
        'dest="${@: -1}"; /bin/cp "' + str(dl / "README.md") + '" "$dest"; exit 1\n')
    (shim / "cp").chmod(0o755)
    env = {**os.environ, "HOME": str(home), "PATH": f"{shim}:{os.environ['PATH']}"}
    p = subprocess.run(["bash", str(dl / "scripts" / "setup" / "move-home.sh"), "--name", "Pat",
                        "--email", "p@e.com", "--no-open"], capture_output=True, text=True, env=env)
    assert p.returncode == 7, p.stdout
    rc, out = run(dl, home)
    assert rc == 0, out


def test_rerun_after_home_is_ready_never_overwrites_the_home(tmp_path):
    dl, home = make_download(tmp_path), tmp_path / "home"
    home.mkdir()
    assert run(dl, home)[0] == 0
    (home / "Brain" / "README.md").write_text("edited in part B\n")
    rc, out = run(dl, home)
    assert rc == 0 and (home / "Brain" / "README.md").read_text() == "edited in part B\n"


def test_home_inside_another_git_repo_still_gets_a_full_copy(tmp_path):
    dl, home = make_download(tmp_path), tmp_path / "home"
    home.mkdir()
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "d@e.com"], ["config", "user.name", "d"]):
        subprocess.run(["git", "-C", str(home), *args], check=True)
    (home / "dotfile").write_text("x")
    subprocess.run(["git", "-C", str(home), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(home), "commit", "-q", "-m", "dotfiles"], check=True)
    rc, out = run(dl, home)
    assert rc == 0, out
    assert (home / "Brain" / "README.md").is_file() and (home / "Brain" / ".git").is_dir()
