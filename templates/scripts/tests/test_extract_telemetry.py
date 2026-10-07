# scripts/tests/test_extract_telemetry.py
import json
import sys
from pathlib import Path

SJ = Path(__file__).resolve().parents[1] / "system-journal"
sys.path.insert(0, str(SJ))
import extract  # noqa: E402

USAGE = {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 4}


def write(tmp_path, entries, tail=""):
    p = tmp_path / "s1.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n" + tail)
    return str(p)


def assistant(ts, mid, tools, model="claude-opus-5-5", text=None, sidechain=False):
    content = [{"type": "text", "text": text}] if text else []
    content += [{"type": "tool_use", "id": tid, "name": name, "input": inp} for tid, name, inp in tools]
    return {"type": "assistant", "timestamp": ts, "sessionId": "s1", "cwd": "/Users/x/Brain", "gitBranch": "main",
            "isSidechain": sidechain, "message": {"id": mid, "model": model, "content": content, "usage": dict(USAGE)}}


def result(ts, tid, is_error=False, text="ok"):
    return {"type": "user", "timestamp": ts, "sessionId": "s1", "isSidechain": False,
            "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "is_error": is_error, "content": text}]}}


def user(ts, text):
    return {"type": "user", "timestamp": ts, "sessionId": "s1", "isSidechain": False, "message": {"content": text}}


def tools_of(rec):
    return [t for turn in rec["turns"] if turn["role"] == "assistant" for t in turn.get("tools", [])]


def test_schema_is_evidence_2(tmp_path):
    rec = extract.extract_session(write(tmp_path, [user("2026-10-07T15:00:00.000Z", "hi")]))
    assert rec["schema"] == "evidence/2"


def test_ok_duration_and_error_class(tmp_path):
    rec = extract.extract_session(write(tmp_path, [
        user("2026-10-07T15:00:00.000Z", "go"),
        assistant("2026-10-07T15:00:01.000Z", "m1", [("t1", "Bash", {"command": "git status"}),
                                                   ("t2", "Read", {"file_path": "/a"})]),
        result("2026-10-07T15:00:03.500Z", "t1"),
        result("2026-10-07T15:00:04.000Z", "t2", is_error=True, text="FileNotFoundError: /a"),
    ]))
    t1, t2 = tools_of(rec)
    assert (t1["ok"], t1["ms"]) == (True, 2500) and "error_class" not in t1
    assert (t2["ok"], t2["ms"], t2["error_class"]) == (False, 3000, "FileNotFoundError")
    assert rec["tool_error_count"] == 1


def test_pending_call_has_no_ok(tmp_path):
    rec = extract.extract_session(write(tmp_path, [
        assistant("2026-10-07T15:00:01.000Z", "m1", [("t1", "Bash", {"command": "sleep 99"})], text="running"),
    ]))
    (t1,) = tools_of(rec)
    assert "ok" not in t1 and "ms" not in t1


def test_truncated_line_is_skipped(tmp_path):
    rec = extract.extract_session(write(tmp_path, [
        assistant("2026-10-07T15:00:01.000Z", "m1", [("t1", "Bash", {"command": "ls"})], text="ok"),
        result("2026-10-07T15:00:02.000Z", "t1"),
    ], tail='{"type": "assistant", "timest'))
    assert [t["ok"] for t in tools_of(rec)] == [True]


def test_tool_input_is_masked(tmp_path):
    rec = extract.extract_session(write(tmp_path, [
        assistant("2026-10-07T15:00:01.000Z", "m1",
                  [("t1", "Bash", {"command": "curl -H 'X-Api-Key: abc123' https://x"})], text="ok"),
        result("2026-10-07T15:00:02.000Z", "t1"),
    ]))
    (t1,) = tools_of(rec)
    assert "abc123" not in t1["input"] and "X-Api-Key" in t1["input"]


def test_tokens_once_per_message(tmp_path):
    rec = extract.extract_session(write(tmp_path, [
        assistant("2026-10-07T15:00:01.000Z", "m1", [], text="thinking"),
        assistant("2026-10-07T15:00:01.100Z", "m1", [("t1", "Read", {"file_path": "/a"})]),
        result("2026-10-07T15:00:01.200Z", "t1"),
        assistant("2026-10-07T15:00:02.000Z", "m2", [], text="done", model="claude-sonnet-5-5"),
    ]))
    assert rec["tokens_by_model"] == {
        "claude-opus-5-5": {"input": 1, "output": 2, "cache_read": 3, "cache_creation": 4},
        "claude-sonnet-5-5": {"input": 1, "output": 2, "cache_read": 3, "cache_creation": 4},
    }


def test_sidechain_ignored_for_tokens_and_tools(tmp_path):
    rec = extract.extract_session(write(tmp_path, [
        assistant("2026-10-07T15:00:01.000Z", "m9", [("t9", "Bash", {"command": "ls"})], sidechain=True),
        assistant("2026-10-07T15:00:02.000Z", "m1", [("t1", "Read", {"file_path": "/a"})], text="ok"),
        result("2026-10-07T15:00:03.000Z", "t1"),
    ]))
    assert [t["name"] for t in tools_of(rec)] == ["Read"]
    assert list(rec["tokens_by_model"]) == ["claude-opus-5-5"] and rec["tokens_by_model"]["claude-opus-5-5"]["input"] == 1


def test_error_classes():
    ec = extract.error_class
    assert ec("PreToolUse:Bash hook error: [python3 x]: BLOCKED: access to credentials") == "hook_blocked"
    assert ec("Permission for this action was denied by the Claude Code auto mode classifier") == "permission_denied"
    assert ec("The user doesn't want to proceed with this tool use.") == "permission_denied"
    assert ec("Exit code 129\nerror: unknown option") == "exit_129"
    assert ec("FileNotFoundError: no such file") == "FileNotFoundError"
    assert ec("request failed HTTP 500") == "HTTP 500"
    assert ec("something odd") == "tool_error"


def test_no_error_text_is_stored_on_the_tool_entry(tmp_path):
    rec = extract.extract_session(write(tmp_path, [
        assistant("2026-10-07T15:00:01.000Z", "m1", [("t1", "Bash", {"command": "x"})], text="ok"),
        result("2026-10-07T15:00:02.000Z", "t1", is_error=True, text="SECRET OUTPUT TEXT HTTP 500"),
    ]))
    (t1,) = tools_of(rec)
    assert "SECRET OUTPUT TEXT" not in json.dumps(t1) and t1["error_class"] == "HTTP 500"


def test_hooks_candidates_vault_path_first():
    cands = extract.HOOKS_CANDIDATES
    assert cands[0] == str(Path(extract.DEFAULT_VAULT) / "scripts" / "hooks")
    assert Path(cands[1]).resolve() == (SJ.parent / "hooks").resolve()


def test_load_masker_uses_first_candidate_that_has_it(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (b / "log_tool_use.py").write_text("def _mask(t):\n    return t.replace('S3CR3T', 'B***')\n")
    (a / "log_tool_use.py").write_text("def _mask(t):\n    return t.replace('S3CR3T', 'A***')\n")
    assert extract.load_masker([str(tmp_path / "missing"), str(a), str(b)])("x S3CR3T") == "x A***"
    assert extract.load_masker([str(tmp_path / "missing"), str(b)])("x S3CR3T") == "x B***"
    assert extract.load_masker([str(tmp_path / "missing")]) is None


def test_masking_happens_before_the_cap(monkeypatch):
    monkeypatch.setattr(extract, "mask_input", lambda t: t.replace("Q" * 100, ""))
    out = extract.tool_input_summary("Bash", {"command": "A" * 150 + "Q" * 100 + "TAILMARK"})
    assert out.endswith("TAILMARK")
