import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PS1 = ROOT / "scripts" / "setup" / "move-home.ps1"
SH = ROOT / "scripts" / "setup" / "move-home.sh"
TOKENS = ["HOME_READY", "OPEN_URL", "ALREADY_HOME", "DEST_NOT_EMPTY", "SYNCED_PATH", "NOT_A_DOWNLOAD",
          "GIT_MISSING", "COPY_FAILED", "GIT_FAILED"]
CODES = {"DEST_NOT_EMPTY": 3, "SYNCED_PATH": 4, "NOT_A_DOWNLOAD": 5, "GIT_MISSING": 6, "COPY_FAILED": 7,
         "GIT_FAILED": 8}


def test_ps1_matches_the_sh_contract():
    ps, sh = PS1.read_text(encoding="utf-8"), SH.read_text(encoding="utf-8")
    for t in TOKENS:
        assert t in ps and t in sh, t
    for token, code in CODES.items():
        assert re.search(rf"Stop-With '{token}' .+ {code}\s*(\}}|$)", ps, re.M), token
        assert re.search(rf"{token}.*exit {code}", sh), token
    assert "claude://code/new?folder=" in ps and "[uri]::EscapeDataString" in ps
    assert "Programs\\Git\\cmd\\git.exe" in ps          # git installed this session is not on PATH yet
    assert "OneDrive" in ps and "-Force" in ps


@pytest.mark.skipif(os.name != "nt", reason="needs Windows (robocopy, Windows PowerShell); proven in the Windows proof run")
def test_ps1_moves_and_commits(tmp_path):
    dl = tmp_path / "dl"
    (dl / "scripts" / "setup").mkdir(parents=True)
    shutil.copy(PS1, dl / "scripts" / "setup" / "move-home.ps1")
    (dl / "SETUP_PENDING").write_text("x"); (dl / ".gitignore").write_text("*.log\n")
    dest = tmp_path / "home" / "Brain"
    p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(dl / "scripts" / "setup" / "move-home.ps1"),
                        "-Name", "Pat", "-Email", "pat@example.com", "-Dest", str(dest), "-NoOpen"],
                       capture_output=True, text=True, env={**os.environ, "USERPROFILE": str(tmp_path / "home")})
    assert p.returncode == 0, p.stdout + p.stderr
    assert "HOME_READY" in p.stdout and (dest / ".gitignore").is_file() and (dest / ".git").is_dir()


def test_ps1_has_the_review_fixes():
    ps = PS1.read_text(encoding="utf-8")
    assert "[IO.Path]::GetFullPath" in ps and "StartsWith($Src + '\\'" in ps       # absolute, never inside the download
    i_marker = ps.index("Copy-Item -LiteralPath (Join-Path $Src 'SETUP_PENDING')")
    i_robo = ps.index("robocopy $Src $Dest")
    i_head = ps.index("$homeDone")
    assert i_head < i_marker < i_robo                                               # finished home skipped; marker first
    assert ps.count("if ($LASTEXITCODE -ne 0) { Stop-With 'GIT_FAILED' 'git config failed' 8 }") == 2
