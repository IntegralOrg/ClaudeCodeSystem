import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "bump_updated.py"
TODAY = "2026-10-09"

NOTE = "---\ntype: note\nupdated: 2025-01-01\ntags: []\n---\n\n# Title\n\nBody text.\n"


def run_hook(project, payload_or_raw, today=TODAY):
    """Run the hook as a subprocess against a temp project dir (a plain dir is not the template repo)."""
    raw = payload_or_raw if isinstance(payload_or_raw, str) else json.dumps(payload_or_raw)
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project), BUMP_UPDATED_TODAY=today)
    return subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True, text=True, env=env)


def edit(path, tool="Edit"):
    return {"session_id": "t", "hook_event_name": "PostToolUse", "tool_name": tool,
            "tool_input": {"file_path": str(path)}}


def make(project, rel, data, binary=False):
    p = project / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        p.write_bytes(data)
    else:
        p.write_text(data, encoding="utf-8")
    return p


def assert_silent(p):
    assert p.returncode == 0
    assert p.stdout == "" and p.stderr == ""


def test_bumps_an_old_date(tmp_path):
    f = make(tmp_path, "Work/note.md", NOTE)
    assert_silent(run_hook(tmp_path, edit(f)))
    assert f.read_text() == NOTE.replace("2025-01-01", TODAY)


def test_multiedit_payload_works(tmp_path):
    f = make(tmp_path, "note.md", NOTE)
    payload = edit(f, tool="MultiEdit")
    payload["tool_input"]["edits"] = [{"old_string": "a", "new_string": "b"}]
    assert_silent(run_hook(tmp_path, payload))
    assert f"updated: {TODAY}" in f.read_text()


def test_write_payload_with_relative_path(tmp_path):
    f = make(tmp_path, "note.md", NOTE)
    payload = {"tool_name": "Write", "tool_input": {"file_path": "note.md", "content": "x"}}
    assert_silent(run_hook(tmp_path, payload))
    assert f"updated: {TODAY}" in f.read_text()


def test_noop_when_already_today_keeps_mtime(tmp_path):
    f = make(tmp_path, "note.md", NOTE.replace("2025-01-01", TODAY))
    os.utime(f, (1_000_000_000, 1_000_000_000))
    before = f.stat().st_mtime_ns
    assert_silent(run_hook(tmp_path, edit(f)))
    assert f.stat().st_mtime_ns == before


def test_noop_when_quoted_today(tmp_path):
    body = NOTE.replace("2025-01-01", '"%s"' % TODAY)
    f = make(tmp_path, "note.md", body)
    os.utime(f, (1_000_000_000, 1_000_000_000))
    assert_silent(run_hook(tmp_path, edit(f)))
    assert f.read_text() == body
    assert f.stat().st_mtime_ns == 1_000_000_000 * 10**9


def test_quoted_value_becomes_bare_date(tmp_path):
    f = make(tmp_path, "note.md", NOTE.replace("2025-01-01", "'2025-01-01'"))
    run_hook(tmp_path, edit(f))
    assert f.read_text() == NOTE.replace("2025-01-01", TODAY)


def test_never_adds_a_missing_key(tmp_path):
    body = "---\ntype: note\n---\n\nBody\n"
    f = make(tmp_path, "note.md", body)
    assert_silent(run_hook(tmp_path, edit(f)))
    assert f.read_text() == body


def test_ignores_file_without_frontmatter(tmp_path):
    body = "# Title\n\nupdated: 2001-01-01\n"
    f = make(tmp_path, "note.md", body)
    assert_silent(run_hook(tmp_path, edit(f)))
    assert f.read_text() == body


def test_ignores_unclosed_frontmatter(tmp_path):
    body = "---\nupdated: 2001-01-01\n" + "x: y\n" * 80
    f = make(tmp_path, "note.md", body)
    run_hook(tmp_path, edit(f))
    assert f.read_text() == body


def test_ignores_non_markdown(tmp_path):
    f = make(tmp_path, "note.txt", NOTE)
    assert_silent(run_hook(tmp_path, edit(f)))
    assert f.read_text() == NOTE


def test_ignores_file_outside_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside = make(tmp_path, "elsewhere/note.md", NOTE)
    assert_silent(run_hook(project, edit(outside)))
    assert outside.read_text() == NOTE


def test_ignores_excluded_directories(tmp_path):
    for d in ("_generated/x", ".claude/commands", ".git/hooks", "node_modules/pkg", ".superpowers/s", ".handoffs"):
        f = make(tmp_path, d + "/note.md", NOTE)
        assert_silent(run_hook(tmp_path, edit(f)))
        assert f.read_text() == NOTE, d


def test_similarly_named_directory_is_not_excluded(tmp_path):
    f = make(tmp_path, "generated/note.md", NOTE)
    run_hook(tmp_path, edit(f))
    assert f"updated: {TODAY}" in f.read_text()


def test_duplicate_updated_lines_left_alone(tmp_path):
    body = "---\nupdated: 2025-01-01\ntype: note\nupdated: 2025-02-02\n---\n\nBody\n"
    f = make(tmp_path, "note.md", body)
    assert_silent(run_hook(tmp_path, edit(f)))
    assert f.read_text() == body


def test_keeps_crlf(tmp_path):
    body = NOTE.replace("\n", "\r\n").encode()
    f = make(tmp_path, "note.md", body)
    assert_silent(run_hook(tmp_path, edit(f)))
    assert f.read_bytes() == body.replace(b"2025-01-01", TODAY.encode())


def test_keeps_trailing_comment(tmp_path):
    body = NOTE.replace("updated: 2025-01-01", "updated: 2025-01-01  # bumped by hook")
    f = make(tmp_path, "note.md", body)
    run_hook(tmp_path, edit(f))
    assert f.read_text() == body.replace("2025-01-01", TODAY)


def test_body_text_with_updated_line_untouched(tmp_path):
    body = NOTE + "\nupdated: 2001-01-01\n\n---\nupdated: 2002-02-02\n---\n"
    f = make(tmp_path, "note.md", body)
    run_hook(tmp_path, edit(f))
    assert f.read_text() == body.replace("updated: 2025-01-01", "updated: " + TODAY, 1)
    assert "updated: 2001-01-01" in f.read_text()


def test_nested_updated_key_is_not_top_level(tmp_path):
    body = "---\ntype: note\nmeta:\n  updated: 2025-01-01\n---\n\nBody\n"
    f = make(tmp_path, "note.md", body)
    run_hook(tmp_path, edit(f))
    assert f.read_text() == body


def test_no_trailing_newline_and_unicode_body_preserved(tmp_path):
    body = "---\nupdated: 2025-01-01\n---\ncaf\u00e9 \u2192 na\u00efve"
    f = make(tmp_path, "note.md", body)
    run_hook(tmp_path, edit(f))
    assert f.read_text(encoding="utf-8") == body.replace("2025-01-01", TODAY)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows does not keep POSIX file modes")
def test_preserves_file_mode(tmp_path):
    f = make(tmp_path, "note.md", NOTE)
    f.chmod(0o640)
    run_hook(tmp_path, edit(f))
    assert (f.stat().st_mode & 0o777) == 0o640
    assert [p.name for p in tmp_path.iterdir()] == ["note.md"]


def test_falls_back_to_real_today_without_override(tmp_path):
    from datetime import date
    f = make(tmp_path, "note.md", NOTE)
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    env.pop("BUMP_UPDATED_TODAY", None)
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(edit(f)),
                       capture_output=True, text=True, env=env)
    assert_silent(p)
    assert f"updated: {date.today().isoformat()}" in f.read_text()


def test_skips_the_template_repository(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin",
                    "https://github.com/IntegralOrg/ClaudeCodeSystem.git"], check=True)
    f = make(tmp_path, "note.md", NOTE)
    assert_silent(run_hook(tmp_path, edit(f)))
    assert f.read_text() == NOTE


def test_acts_in_a_client_repository(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin",
                    "https://github.com/someone/their-brain.git"], check=True)
    f = make(tmp_path, "note.md", NOTE)
    run_hook(tmp_path, edit(f))
    assert f"updated: {TODAY}" in f.read_text()


def test_fails_open_on_malformed_payloads(tmp_path):
    f = make(tmp_path, "note.md", NOTE)
    for raw in ("not json", "", "[]", "null", json.dumps({"tool_input": "x"}),
                json.dumps({"tool_input": {"file_path": 5}}),
                json.dumps({"tool_input": {"file_path": str(tmp_path / "missing.md")}}),
                json.dumps({"tool_input": {"file_path": str(tmp_path)}})):
        assert_silent(run_hook(tmp_path, raw))
    assert f.read_text() == NOTE


def test_fails_open_on_non_utf8_file(tmp_path):
    data = b"---\nupdated: 2025-01-01\n---\n\xff\xfe\n"
    f = make(tmp_path, "note.md", data)
    assert_silent(run_hook(tmp_path, edit(f)))
    assert f.read_bytes() == data


def test_hash_without_space_is_part_of_the_value_not_a_comment(tmp_path):
    body = "---\nupdated: 2025-01-01#v2\n---\nbody\n"
    f = make(tmp_path, "note.md", body)
    run_hook(tmp_path, edit(f))
    assert f.read_text(encoding="utf-8") == body
