import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import importlib
pc = importlib.import_module("profile-convert")

SRC = """---
type: client-profile
client: Acme
status: active
---
# Company Profile: Acme

## Recent Activity
- **2026-10-02** — Dev lead handed to Diego. -- [source](Transcripts/a.md)
- **2026-09-29** — Reclassified non-build; offer moves to $1,500/mo coaching.

## Overview
Acme does things.

## Engagement
- **Recurring (from 2026-09-02):** $5k/mo fractional partnership.

### Recent Activity
- **2026-09-25** — Dean is PM.

## Related
- [[Work/Clients/Acme/Company Profile|Acme]]
"""

def test_converts_losslessly():
    out, rep = pc.convert(SRC, today="2026-10-06", engagement="maintenance", last_change="2026-10-02")
    assert rep["log_entries"] == 3 and rep["removed_sections"] == ["Recent Activity", "Recent Activity"]
    assert out.count("## Current State") == 1 and out.count("## Log") == 1
    assert "Recent Activity" not in out
    # every original bullet text survives verbatim
    for frag in ["Dev lead handed to Diego. -- [source](Transcripts/a.md)", "Reclassified non-build; offer moves to $1,500/mo coaching.", "Dean is PM."]:
        assert frag in out
    log = out.split("## Log")[1]
    assert log.index("(2026-10-02)") < log.index("(2026-09-29)") < log.index("(2026-09-25)")
    assert "- **Engagement status** (2026-10-06): maintenance" in out
    assert "- **Engagement** (2026-10-02): $5k/mo fractional partnership. (verify)" in out
    assert "engagement: maintenance" in out.split("---")[1]
    assert "## Overview\nAcme does things." in out and "## Related" in out

def test_current_state_sits_right_after_title():
    out, _ = pc.convert(SRC, today="2026-10-06", engagement=None, last_change="2026-10-02")
    assert out.index("# Company Profile: Acme") < out.index("## Current State") < out.index("## Overview")

def test_refuses_already_converted():
    out, _ = pc.convert(SRC, today="2026-10-06", engagement=None, last_change="2026-10-02")
    import pytest
    with pytest.raises(pc.AlreadyConverted):
        pc.convert(out, today="2026-10-06", engagement=None, last_change="2026-10-02")

def test_converted_output_passes_state_guard():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
    import guard_state_writes as gsw
    out, _ = pc.convert(SRC, today="2026-10-06", engagement="active", last_change="2026-10-02")
    assert gsw.check_content("/v/Work/Clients/Acme/Company Profile.md", out) is None

NESTED = """# Company Profile: Beta

## Recent Activity

### 2026-08-17 - Call (phone)
- **Rec**: switch to Quo.
-- [source](Transcripts/x.md)

### 2026-08-03 - Other call
- Did a thing.

## Overview
Beta.
"""

def test_nested_subheadings_move_into_log():
    out, rep = pc.convert(NESTED, today="2026-10-06", engagement=None, last_change="2026-10-02")
    assert rep["log_entries"] == 2 and "Recent Activity" not in out
    for frag in ["- **Rec**: switch to Quo.", "-- [source](Transcripts/x.md)", "- Did a thing.", "Call (phone)"]:
        assert frag in out
    log = out.split("## Log")[1]
    assert log.index("(2026-08-17)") < log.index("(2026-08-03)")
    assert "## Overview\nBeta." in out and "###" not in out


def _log_lines(out):
    return out.split("## Log")[1].splitlines()

MIXED = """---
type: client-profile
---
# Company Profile: Gamma

## Recent Activity

### 2026-07-01 - Connect call
- Priority pivot.
-- [source](Transcripts/y.md)

- **2026-06-29**: Locked.
- **2026-06-22**: Rollout.
"""

def test_dated_bullets_under_subheading_are_top_level():
    out, rep = pc.convert(MIXED, today="2026-10-06", engagement=None, last_change="2026-10-02")
    lines = _log_lines(out)
    top = [l for l in lines if l.startswith("- (")]
    assert top[0].startswith("- (2026-07-01)") and top[1].startswith("- (2026-06-29)") and top[2].startswith("- (2026-06-22)")
    assert "  - Priority pivot." in lines and "  -- [source](Transcripts/y.md)" in lines
    assert rep["log_entries"] == 3

def test_no_git_date_skips_engagement_seed(capsys):
    out, rep = pc.convert(SRC, today="2026-10-06", engagement="active", last_change=None)
    assert rep["seeded"] == ["Engagement status"]
    assert "(verify)" not in out and "warning" in capsys.readouterr().err

def test_junk_engagement_seed_skipped():
    for junk in ["December 28, 2025", "2026-09-02", "dual-platform.", "12345 67890 123"]:
        src = f"# T\n\n## Engagement\n- {junk}\n"
        out, rep = pc.convert(src, today="2026-10-06", engagement="active", last_change="2026-10-02")
        assert rep["seeded"] == ["Engagement status"], junk

def test_subheading_colon_and_date_separators():
    src = "# T\n\n## Recent Activity\n\n### 2026-08-17: Title\n- x\n\n- **2026-09-30:** Done\n- 2026-09-01 - 2026-09-30 range\n"
    out, _ = pc.convert(src, today="2026-10-06", engagement=None, last_change="2026-10-02")
    assert "- (2026-08-17) Title" in out and "- (2026-09-30) Done" in out and "- (2026-09-01) 2026-09-30 range" in out

def test_refuses_existing_log_and_no_frontmatter_gets_engagement():
    import pytest
    with pytest.raises(pc.AlreadyConverted):
        pc.convert("# T\n\n## Log\n- x\n", today="2026-10-06", engagement=None, last_change=None)
    out, _ = pc.convert("# T\n\nBody\n", today="2026-10-06", engagement="active", last_change=None)
    assert out.startswith("---\nengagement: active\n---")


def test_today_git_date_skips_engagement_seed(capsys):
    out, rep = pc.convert(SRC, today="2026-10-06", engagement="active", last_change="2026-10-06")
    assert rep["seeded"] == ["Engagement status"] and "(verify)" not in out
    assert "warning" in capsys.readouterr().err

def test_cli_exits_1_on_already_converted(tmp_path):
    import subprocess
    out, _ = pc.convert(SRC, today="2026-10-06", engagement=None, last_change="2026-10-02")
    f = tmp_path / "Company Profile.md"
    f.write_text(out, encoding="utf-8")
    r = subprocess.run([sys.executable, str(Path(pc.__file__)), str(f)], capture_output=True, text=True)
    assert r.returncode == 1 and "Traceback" not in r.stderr and r.stderr.startswith("error:")
