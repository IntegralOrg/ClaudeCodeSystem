import importlib.util
import json
import sys
from pathlib import Path

SJ = Path(__file__).resolve().parents[1] / "system-journal"
sys.path.insert(0, str(SJ))
spec = importlib.util.spec_from_file_location("telemetry_stats", SJ / "telemetry-stats.py")
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)

NOW = "2026-10-07T20:00:00+00:00"


def rec(sid, ended, tools, schema="evidence/2", cwd="/Users/x/Brain", tokens=None, model="m"):
    r = {"schema": schema, "session_id": sid, "project": "p", "cwd": cwd, "started": ended, "ended": ended,
         "models": {model: 1}, "turns": [{"i": 0, "t": ended, "role": "assistant", "tools": tools}]}
    if schema == "evidence/2":
        r["tokens_by_model"] = tokens or {model: {"input": 1, "output": 2, "cache_read": 3, "cache_creation": 4}}
    return r


def write_vault(tmp_path, records):
    for r in records:
        d = tmp_path / "_generated" / "system-journal" / "evidence" / r["ended"][:7]
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{r['session_id']}.json").write_text(json.dumps(r))
    return str(tmp_path)


RECORDS = [
    rec("s1", "2026-10-07T15:00:00.000Z", [
        {"name": "Bash", "input": "git status", "ok": True, "ms": 100},
        {"name": "Bash", "input": "cat x", "ok": False, "ms": 300, "error_class": "hook_blocked"},
        {"name": "Bash", "input": "sleep", },                                   # pending
    ]),
    rec("s2", "2026-10-07T03:30:00.000Z", [{"name": "Read", "input": "/a", "ok": True}], cwd="/Users/x/Other"),
    rec("s0", "2026-09-01T12:00:00.000Z", [{"name": "Bash", "input": "old", "ok": True}]),   # outside window
    rec("s9", "2026-10-06T12:00:00.000Z", [{"name": "Grep", "input": "x"}], schema="evidence/1"),  # old schema
]


def test_window_filters_by_ended(tmp_path):
    v = write_vault(tmp_path, RECORDS)
    assert sorted(r["session_id"] for r in ts.load_records(v, 7, NOW)) == ["s1", "s2", "s9"]


def test_group_by_tool_with_pending_excluded_from_error_rate(tmp_path):
    groups = ts.summarize(ts.load_records(write_vault(tmp_path, RECORDS), 7, NOW), "tool", "America/New_York")
    bash = next(g for g in groups if g["key"] == "Bash")
    assert bash["calls"] == 3 and bash["answered"] == 2 and bash["errors"] == 1 and bash["pending"] == 1
    assert bash["error_rate"] == 0.5 and bash["p50_ms"] == 100 and bash["p95_ms"] == 300
    assert bash["top_error_classes"] == {"hook_blocked": 1} and bash["tokens"] is None


def test_mixed_schemas(tmp_path):
    groups = ts.summarize(ts.load_records(write_vault(tmp_path, RECORDS), 7, NOW), "tool", "America/New_York")
    grep = next(g for g in groups if g["key"] == "Grep")
    assert grep == {"key": "Grep", "calls": 1, "answered": 0, "errors": 0, "pending": 0, "unknown": 1,
                    "error_rate": None, "p50_ms": None, "p95_ms": None, "sessions": 1,
                    "top_error_classes": {}, "tokens": None}


def test_group_by_repo_sums_tokens_once_per_session(tmp_path):
    groups = ts.summarize(ts.load_records(write_vault(tmp_path, RECORDS), 7, NOW), "repo", "America/New_York")
    brain = next(g for g in groups if g["key"] == "Brain")
    assert brain["sessions"] == 2 and brain["calls"] == 4
    assert brain["tokens"] == {"input": 1, "output": 2, "cache_read": 3, "cache_creation": 4}  # s9 is evidence/1: no tokens


def test_group_by_day_in_eastern(tmp_path):
    keys = sorted(g["key"] for g in ts.summarize(ts.load_records(write_vault(tmp_path, RECORDS), 7, NOW), "day", "America/New_York"))
    assert keys == ["2026-10-06", "2026-10-07"]   # s2 at 03:30Z is 23:30 ET on the 6th


def test_group_by_model_tokens_exact(tmp_path):
    groups = ts.summarize(ts.load_records(write_vault(tmp_path, RECORDS), 7, NOW), "model", "America/New_York")
    m = next(g for g in groups if g["key"] == "m")
    assert m["tokens"]["input"] == 2   # s1 + s2; s9 has no tokens_by_model


def test_session_detail(tmp_path):
    v = write_vault(tmp_path, RECORDS)
    d = ts.session_detail(next(r for r in ts.load_records(v, 7, NOW) if r["session_id"] == "s1"))
    assert d["calls"] == 3 and d["errors"] == [{"name": "Bash", "input": "cat x", "ms": 300, "error_class": "hook_blocked"}]
    assert d["slowest"][0]["ms"] == 300 and d["pending"] == 1


def test_cli_json(tmp_path, capsys):
    v = write_vault(tmp_path, RECORDS)
    assert ts.main(["--vault", v, "--now", NOW, "--since-days", "7", "--group-by", "tool", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["total_calls"] == 5 and out["sessions"] == 3 and out["group_by"] == "tool"


def test_cli_text_and_missing_session(tmp_path, capsys):
    v = write_vault(tmp_path, RECORDS)
    assert ts.main(["--vault", v, "--now", NOW]) == 0
    assert "Bash" in capsys.readouterr().out
    assert ts.main(["--vault", v, "--now", NOW, "--session", "nope"]) == 1


def test_chat_only_session_appears_in_repo_and_day(tmp_path):
    chat_rec = rec("s_chat", "2026-10-07T15:00:00.000Z", [], tokens={"m": {"input": 9, "output": 0, "cache_read": 0, "cache_creation": 0}})
    recs = RECORDS + [chat_rec]
    groups_repo = ts.summarize(ts.load_records(write_vault(tmp_path, recs), 7, NOW), "repo", "America/New_York")
    brain = next(g for g in groups_repo if g["key"] == "Brain")
    assert brain["sessions"] == 3 and brain["calls"] == 4 and brain["tokens"]["input"] == 10
    groups_day = ts.summarize(ts.load_records(write_vault(tmp_path, recs), 7, NOW), "day", "America/New_York")
    day_0707 = next(g for g in groups_day if g["key"] == "2026-10-07")
    assert day_0707["sessions"] == 2 and day_0707["tokens"]["input"] == 10


def test_multiday_session_tokens_once_on_ended_day(tmp_path):
    multiday_rec = {
        "schema": "evidence/2",
        "session_id": "s_multi",
        "project": "p",
        "cwd": "/Users/x/Brain",
        "started": "2026-10-07T20:00:00.000Z",
        "ended": "2026-10-08T16:00:00.000Z",
        "models": {"m": 1},
        "tokens_by_model": {"m": {"input": 5, "output": 5, "cache_read": 0, "cache_creation": 0}},
        "turns": [
            {"i": 0, "t": "2026-10-07T20:00:00.000Z", "role": "assistant", "tools": [{"name": "Bash", "input": "x", "ok": True, "ms": 50}]},
            {"i": 1, "t": "2026-10-08T15:00:00.000Z", "role": "assistant", "tools": [{"name": "Bash", "input": "y", "ok": True, "ms": 60}]},
        ]
    }
    d = tmp_path / "_generated" / "system-journal" / "evidence" / "2026-10"
    d.mkdir(parents=True, exist_ok=True)
    (d / "s_multi.json").write_text(json.dumps(multiday_rec))
    groups_day = ts.summarize(ts.load_records(str(tmp_path), 7, NOW), "day", "America/New_York")
    day_0708 = next((g for g in groups_day if g["key"] == "2026-10-08"), None)
    assert day_0708 is not None and day_0708["calls"] == 2 and day_0708["tokens"]["input"] == 5
    day_0707 = next((g for g in groups_day if g["key"] == "2026-10-07"), None)
    assert day_0707 is None


def test_cli_session_json(tmp_path, capsys):
    v = write_vault(tmp_path, RECORDS)
    assert ts.main(["--vault", v, "--now", NOW, "--session", "s1", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["session_id"] == "s1" and out["calls"] == 3 and out["errors"][0]["error_class"] == "hook_blocked" and "unknown" in out


def test_error_without_error_class_defaults_to_tool_error(tmp_path, capsys):
    no_class_rec = rec("s_noclass", "2026-10-07T15:00:00.000Z", [
        {"name": "Bash", "input": "fail", "ok": False, "ms": 100},
        {"input": "slow", "ok": True, "ms": 200},
    ])
    v = write_vault(tmp_path, [no_class_rec])
    assert ts.main(["--vault", v, "--now", NOW, "--session", "s_noclass"]) == 0
    out = capsys.readouterr().out
    assert "tool_error" in out and "?" in out


def test_load_records_counts_and_reports_skipped_files(tmp_path, capsys):
    v = write_vault(tmp_path, RECORDS)
    d = tmp_path / "_generated" / "system-journal" / "evidence" / "2026-10"
    (d / "corrupt.json").write_text('{"schema": "evidence/2", "session_id": "bad", "ended": ')
    (d / "nosid.json").write_text(json.dumps({"schema": "evidence/2"}))
    (d / "list.json").write_text("[1, 2]")
    got = ts.load_records(v, 7, NOW)
    assert sorted(r["session_id"] for r in got) == ["s1", "s2", "s9"]
    assert capsys.readouterr().err.strip() == "telemetry-stats: skipped 3 unreadable or malformed evidence file(s)"


def test_load_records_is_silent_when_nothing_is_skipped(tmp_path, capsys):
    ts.load_records(write_vault(tmp_path, RECORDS), 7, NOW)
    assert capsys.readouterr().err == ""


def test_model_without_v2_data_reports_no_tokens(tmp_path):
    old = rec("s_old", "2026-10-07T15:00:00.000Z", [{"name": "Read", "input": "/a"}], schema="evidence/1", model="legacy-model")
    groups = ts.summarize(ts.load_records(write_vault(tmp_path, RECORDS + [old]), 7, NOW), "model", "America/New_York")
    legacy = next(g for g in groups if g["key"] == "legacy-model")
    assert legacy["tokens"] is None and legacy["calls"] == 1
    assert next(g for g in groups if g["key"] == "m")["tokens"]["input"] == 2


def test_tz_accepts_name_or_tzinfo_object(tmp_path):
    from datetime import timedelta, timezone
    recs = ts.load_records(write_vault(tmp_path, RECORDS), 7, NOW)
    by_name = sorted(g["key"] for g in ts.summarize(recs, "day", "America/New_York"))
    assert by_name == ["2026-10-06", "2026-10-07"]
    utc = sorted(g["key"] for g in ts.summarize(recs, "day", timezone.utc))
    assert utc == ["2026-10-06", "2026-10-07"] and utc == by_name
    far_east = sorted(g["key"] for g in ts.summarize(recs, "day", timezone(timedelta(hours=14))))
    assert far_east == ["2026-10-07", "2026-10-08"]   # s1 15:00Z is 05:00 on the 8th; s2 and s9 land on the 7th
    assert ts._tz(timezone.utc) is timezone.utc


def test_default_tz_is_local_unless_env_names_one():
    assert ts.DEFAULT_TZ is None or isinstance(ts.DEFAULT_TZ, str)


def test_malformed_record_structure_is_skipped_not_fatal(tmp_path, capsys):
    v = write_vault(tmp_path, RECORDS)
    d = tmp_path / "_generated" / "system-journal" / "evidence" / "2026-10"
    base = {"schema": "evidence/2", "ended": "2026-10-07T15:00:00.000Z"}
    (d / "bad_turns.json").write_text(json.dumps(dict(base, session_id="b1", turns=["bad"])))
    (d / "bad_tools.json").write_text(json.dumps(dict(base, session_id="b2", turns=[{"role": "assistant", "tools": ["x"]}])))
    (d / "bad_tokens.json").write_text(json.dumps(dict(base, session_id="b3", tokens_by_model={"m": 5})))
    (d / "bad_models.json").write_text(json.dumps(dict(base, session_id="b4", models=["m"])))
    got = ts.load_records(v, 7, NOW)
    assert sorted(r["session_id"] for r in got) == ["s1", "s2", "s9"]
    assert "skipped 4 unreadable or malformed" in capsys.readouterr().err
    ts.summarize(got, "tool")   # does not raise


def test_non_numeric_token_values_and_bad_names_are_skipped(tmp_path, capsys):
    v = write_vault(tmp_path, RECORDS)
    d = tmp_path / "_generated" / "system-journal" / "evidence" / "2026-10"
    base = {"schema": "evidence/2", "ended": "2026-10-07T15:00:00.000Z"}
    (d / "bad_n.json").write_text(json.dumps(dict(base, session_id="n1", tokens_by_model={"m": {"input": "n/a"}})))
    (d / "bad_bool.json").write_text(json.dumps(dict(base, session_id="n2", tokens_by_model={"m": {"output": True}})))
    (d / "bad_name.json").write_text(json.dumps(dict(base, session_id="n3", turns=[{"role": "assistant", "tools": [{"name": ["x"]}]}])))
    (d / "bad_class.json").write_text(json.dumps(dict(base, session_id="n4", turns=[{"role": "assistant", "tools": [{"name": "Bash", "ok": False, "error_class": {"a": 1}}]}])))
    got = ts.load_records(v, 7, NOW)
    assert sorted(r["session_id"] for r in got) == ["s1", "s2", "s9"]
    assert "skipped 4 unreadable or malformed" in capsys.readouterr().err
    for group_by in ("tool", "repo", "model", "day"):
        ts.summarize(got, group_by, "America/New_York")   # does not raise


def test_default_zone_is_local_per_timestamp_across_dst(tmp_path, monkeypatch):
    import time
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    try:
        # 04:30Z on Nov 1 2026 is 00:30 EDT on Nov 1 (before the 06:00Z fall-back). A fixed current
        # offset (EST, -5) would call it 23:30 on Oct 31.
        r = rec("s_dst", "2026-11-01T04:30:00.000Z", [{"name": "Bash", "input": "x", "ok": True}])
        now = "2026-11-03T00:00:00+00:00"
        recs = ts.load_records(write_vault(tmp_path, [r]), 7, now)
        assert ts._tz(None) is None
        assert [g["key"] for g in ts.summarize(recs, "day", None)] == ["2026-11-01"]
    finally:
        monkeypatch.undo()   # put TZ back to its original value (or unset) first,
        time.tzset()         # then make the process zone match it
