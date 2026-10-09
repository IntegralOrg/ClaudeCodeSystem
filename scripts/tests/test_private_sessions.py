# scripts/tests/test_private_sessions.py
# A private session (/vent) is recorded as metadata only: no user words in the evidence record,
# no model call in distill, a stub journal line that keeps the same keys.
import json
import sys
from pathlib import Path

SJ = Path(__file__).resolve().parents[1] / "system-journal"
sys.path.insert(0, str(SJ))
import distill  # noqa: E402
import extract  # noqa: E402

SECRET = "my private words about my day"
WITHHELD = "[withheld: private session]"
USAGE = {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 4}


def write(tmp_path, entries):
    p = tmp_path / "s1.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return str(p)


def user(ts, text):
    return {"type": "user", "timestamp": ts, "sessionId": "s1", "isSidechain": False, "message": {"content": text}}


def assistant(ts, mid, tools, text="I hear you, that sounds hard"):
    content = [{"type": "text", "text": text}]
    content += [{"type": "tool_use", "id": tid, "name": name, "input": inp} for tid, name, inp in tools]
    return {"type": "assistant", "timestamp": ts, "sessionId": "s1", "cwd": "/Users/x/Brain", "gitBranch": "main",
            "isSidechain": False, "message": {"id": mid, "model": "claude-opus-5-5", "content": content, "usage": dict(USAGE)}}


def result(ts, tid, is_error=False, text="file contents"):
    return {"type": "user", "timestamp": ts, "sessionId": "s1", "isSidechain": False,
            "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "is_error": is_error, "content": text}]}}


def session(first_user, tools):
    return [
        {"type": "ai-title", "aiTitle": "Venting about my boss"},
        user("2026-10-09T15:00:00.000Z", first_user),
        user("2026-10-09T15:00:01.000Z", SECRET),
        assistant("2026-10-09T15:00:02.000Z", "m1", tools),
        result("2026-10-09T15:00:03.000Z", "t1"),
    ]


def assert_private(rec):
    assert rec["private"] is True
    assert SECRET not in json.dumps(rec) and "boss" not in json.dumps(rec) and "hear you" not in json.dumps(rec)
    for turn in rec["turns"]:
        if "text" in turn:
            assert turn["text"] == WITHHELD
        for tl in turn.get("tools", []):
            assert set(tl) <= {"name", "ok", "ms", "error_class"}
    assert rec["final"] == WITHHELD and rec["files_touched"] == [] and rec["pr_refs"] == []
    # metadata survives
    assert rec["session_id"] == "s1" and rec["started"] and rec["ended"]
    assert rec["user_turns"] >= 1 and rec["assistant_turns"] == 1
    assert rec["tool_counts"] and rec["tokens_by_model"]["claude-opus-5-5"]["output"] == 2


def test_slash_vent_is_private(tmp_path):
    entries = session("<command-name>/vent</command-name>", [("t1", "Read", {"file_path": "/a/notes.md"})])
    rec = extract.extract_session(write(tmp_path, entries))
    assert_private(rec)
    assert rec["slash_commands"] == ["/vent"]
    (tl,) = [t for turn in rec["turns"] for t in turn.get("tools", [])]
    assert tl == {"name": "Read", "ok": True, "ms": 1000}


def test_skill_tool_use_vent_is_private(tmp_path):
    entries = session("let me get something off my chest", [("t1", "Skill", {"skill": "vent"})])
    assert_private(extract.extract_session(write(tmp_path, entries)))


def test_write_under_journal_prefix_is_private(tmp_path):
    entries = session("let me get something off my chest",
                      [("t1", "Write", {"file_path": "/Users/x/Brain/Personal/Journal/Raw/2026-10-09.md", "content": SECRET})])
    assert_private(extract.extract_session(write(tmp_path, entries)))


def test_normal_session_is_unchanged(tmp_path):
    entries = session("fix the build", [("t1", "Edit", {"file_path": "/Users/x/Brain/Work/a.md"})])
    rec = extract.extract_session(write(tmp_path, entries))
    assert "private" not in rec
    assert rec["turns"][1]["text"] == SECRET
    assert rec["title"] == "Venting about my boss"
    assert rec["files_touched"] == ["/Users/x/Brain/Work/a.md"]


def test_mentioning_the_prefix_in_a_command_is_not_private(tmp_path):
    entries = session("audit hygiene", [("t1", "Bash", {"command": "grep -r Personal/Journal/ ."})])
    assert "private" not in extract.extract_session(write(tmp_path, entries))


def test_rules_come_from_vocab_json(tmp_path):
    (tmp_path / "scripts" / "system-journal").mkdir(parents=True)
    (tmp_path / "scripts" / "system-journal" / "vocab.json").write_text(
        json.dumps({"private_commands": ["diary"], "private_path_prefixes": ["Me/Notes/"]}))
    rules = extract.load_private_rules(str(tmp_path))
    assert rules == {"private_commands": ["diary"], "private_path_prefixes": ["Me/Notes/"]}
    assert extract.session_is_private(["/diary"], [], [], rules)
    assert extract.session_is_private([], [], ["/v/Me/Notes/a.md"], rules)
    assert not extract.session_is_private(["/vent"], [], ["/v/Personal/Journal/a.md"], rules)
    assert extract.load_private_rules(str(tmp_path / "missing")) == {
        "private_commands": ["vent"], "private_path_prefixes": ["Personal/Journal/"]}


def test_shipped_vocab_and_builtin_default_agree():
    vocab = json.loads((SJ / "vocab.json").read_text(encoding="utf-8"))
    for v in (vocab, distill._GENERIC_VOCAB):
        assert v["private_commands"] == ["vent"] and v["private_path_prefixes"] == ["Personal/Journal/"]


def run_distill(tmp_path, monkeypatch, raw):
    vault = tmp_path / "vault"
    ev = vault / "_generated" / "system-journal" / "evidence" / "2026-10" / "s1.json"
    ev.parent.mkdir(parents=True)
    ev.write_text(json.dumps(raw))
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "state.json").write_text(json.dumps(
        {"s1": {"evidence": str(ev.relative_to(vault)), "final": True, "distilled": False, "mtime": 1}}))
    monkeypatch.setattr(distill, "STATE_DIR", str(state_dir))
    monkeypatch.setattr(distill, "STATE_FILE", str(state_dir / "state.json"))
    monkeypatch.setattr(distill, "STATE_LOCK", str(state_dir / "state.lock"))
    monkeypatch.setattr(distill, "ERR_LOG", str(state_dir / "errors.log"))
    calls = []

    def fake_claude(raw, model, prompt_text):
        calls.append(raw)
        return ({"ask": "fix the build", "outcome": "done", "outcome_note": "fixed", "failures": [], "complaints": [],
                 "shipped": [], "decisions": [], "open_loop": "", "systems": ["testing"], "topics": [], "why": "x"}, 0.01)

    monkeypatch.setattr(distill, "call_claude", fake_claude)
    monkeypatch.setattr(sys, "argv", ["distill.py", "--vault", str(vault), "--workers", "1"])
    assert distill.main() == 0
    lines = [json.loads(x) for p in (vault / "_generated" / "system-journal").glob("*.jsonl") for x in p.read_text().splitlines()]
    audit = list((vault / "_generated" / "system-journal" / "audit").glob("*.audit.jsonl"))
    log = [json.loads(x) for x in (vault / "_generated" / "system-journal" / "audit" / "sanitization-log.jsonl").read_text().splitlines()]
    return calls, lines, audit, log


def test_distill_writes_stub_without_calling_the_model(tmp_path, monkeypatch):
    entries = session("<command-name>/vent</command-name>", [("t1", "Read", {"file_path": "/a/notes.md"})])
    rec = extract.extract_session(write(tmp_path, entries))
    calls, lines, audit, log = run_distill(tmp_path, monkeypatch, rec)
    assert calls == []
    (line,) = lines
    assert line["session_id"] == "s1" and line["private"] is True
    assert (line["ask"], line["outcome"], line["outcome_note"]) == ("[private session]", "private", "")
    for k in ("failures", "complaints", "shipped", "decisions", "topics"):
        assert line[k] == []
    assert (line["open_loop"], line["why"], line["systems"]) == ("", "", ["vent"])
    assert line["title"] == "[private session]" and line["files_touched"] == [] and line["user_turns"] == 1
    assert SECRET not in json.dumps(line)
    assert audit == [] or "s1" not in audit[0].read_text()
    assert [d["action"] for d in log] == ["dropped"]


def test_distill_normal_session_still_calls_the_model(tmp_path, monkeypatch):
    rec = extract.extract_session(write(tmp_path, session("fix the build", [("t1", "Read", {"file_path": "/a/b.md"})])))
    calls, lines, _, _ = run_distill(tmp_path, monkeypatch, rec)
    assert len(calls) == 1
    assert lines[0]["ask"] == "fix the build" and "private" not in lines[0]


def test_distill_covers_an_older_unflagged_record(tmp_path, monkeypatch):
    old = {"session_id": "s1", "started": "2026-10-09T15:00:00Z", "slash_commands": ["/vent"], "files_touched": [],
           "user_turns": 1, "turns": [{"i": 0, "role": "user", "text": SECRET}]}
    calls, lines, _, _ = run_distill(tmp_path, monkeypatch, old)
    assert calls == [] and lines[0]["private"] is True and SECRET not in json.dumps(lines[0])
