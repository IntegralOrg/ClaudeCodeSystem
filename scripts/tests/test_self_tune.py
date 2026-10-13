"""Nightly self-tuning (`/vault-audit` Step 5b): `scripts/self-tune.py` reads the week's System Journal,
groups repeated friction by root cause, and hands the command step a work order. Tier 1 patterns are
applied the same night and recorded; Tier 2 patterns are reported as names and counts, and no file
outside the tuning outputs is ever touched."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "self-tune.py"
TODAY = "2026-10-13"
SECRET_A = "sk-" + "abcdefghijklmnopqrstuvwxyz0123456789"
SECRET_B = "supersecretvalue" + "98765"
OUTPUTS = {"_generated/vault-hygiene/tuning-order.json", "_generated/vault-hygiene/tuning.json", "_generated/Themes.md"}


def line(sid, day, complaints=(), failures=(), systems=("tasks",), private=False, slash=(), why="no rule says so",
         project="cloud:Brain"):
    rec = {"session_id": sid, "project": project, "started": f"{day}T10:00:00Z", "ended": f"{day}T11:00:00Z",
           "title": "t", "user_turns": 3, "slash_commands": list(slash), "tool_error_count": 0, "files_touched": [],
           "ask": "do the thing", "outcome": "done", "failures": list(failures), "complaints": list(complaints),
           "systems": list(systems), "topics": [], "why": why, "distilled_at": f"{day}T12:00:00Z"}
    if private:
        rec.update({"private": True, "ask": "[private session]", "outcome": "private", "systems": ["vent"]})
    return rec


def evidence(sid, day, tools, private=False, cwd="/home/u/Brain"):
    rec = {"schema": "evidence/2", "session_id": sid, "project": "p", "cwd": cwd, "started": f"{day}T10:00:00Z",
           "ended": f"{day}T11:00:00Z", "models": {"m": 1},
           "turns": [{"i": 0, "t": f"{day}T10:30:00Z", "role": "assistant", "tools": tools}],
           "tokens_by_model": {"m": {"input": 1, "output": 1, "cache_read": 0, "cache_creation": 0}}}
    if private:
        rec["private"] = True
    return rec


def make_vault(tmp_path, lines, evidences=(), tuning=None):
    v = tmp_path / "vault"
    (v / ".claude" / "commands").mkdir(parents=True)
    (v / "cowork-commands").mkdir()
    (v / "scripts" / "hooks").mkdir(parents=True)
    (v / "System").mkdir()
    (v / "CLAUDE.md").write_text("# Brain\n\n## Assistant Guidelines\n\n1. Be useful.\n")
    (v / ".claude" / "commands" / "eod.md").write_text("# EOD\n")
    (v / "cowork-commands" / "eod.md").write_text("---\nname: eod\ndescription: d\n---\n\n# EOD\n")
    (v / ".claude" / "settings.json").write_text("{}\n")
    (v / "scripts" / "hooks" / "guard.py").write_text("print('guard')\n")
    (v / "System" / "Routines.md").write_text("# Routines\n")
    sj = v / "_generated" / "system-journal"
    (sj / "cloud").mkdir(parents=True)
    with open(sj / "2026-10.mac.jsonl", "w") as f:
        for rec in lines:
            f.write(json.dumps(rec) + "\n")
    for ev in evidences:
        d = sj / "evidence" / ev["ended"][:7]
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{ev['session_id']}.json").write_text(json.dumps(ev))
    if tuning is not None:
        (v / "_generated" / "vault-hygiene").mkdir(parents=True, exist_ok=True)
        (v / "_generated" / "vault-hygiene" / "tuning.json").write_text(json.dumps(tuning))
    return v


def run(v, *args, check=True):
    r = subprocess.run([sys.executable, str(SCRIPT), args[0], "--vault", str(v), "--today", TODAY, *args[1:]],
                       capture_output=True, text=True)
    if check:
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    return r


def plan(v):
    run(v, "plan")
    return json.loads((v / "_generated" / "vault-hygiene" / "tuning-order.json").read_text())


def snapshot(v):
    out = {}
    for p in sorted(v.rglob("*")):
        if p.is_file():
            out[p.relative_to(v).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def complaint_week(extra=()):
    return [line("aaaa1111", "2026-10-08", complaints=["it forgot my time zone again"]),
            line("bbbb2222", "2026-10-10", complaints=["wrong time zone on the task"]),
            line("cccc3333", "2026-10-12", complaints=["time zone is wrong again"]),
            *extra]


AUDIT_TUNED = re.compile(r"^- tuned (journal|telemetry):[^ ]+ in [^:]+: .+ \(why: .+; \d+ sessions, \d{4}-\d\d-\d\d to \d{4}-\d\d-\d\d\)$")
AUDIT_REPORTED = re.compile(r"^- reported (journal|telemetry):[^ ]+ to your contact \(.+\): .+ x\d+, \d{4}-\d\d-\d\d to \d{4}-\d\d-\d\d$")


# --- Tier 1: applied the same night ---------------------------------------------------------------

def test_tier1_complaint_pattern_is_ordered_applied_and_recorded(tmp_path):
    v = make_vault(tmp_path, complaint_week())
    order = plan(v)
    assert order["status"] == "ok" and order["sessions_in_window"] == 3
    [p] = [p for p in order["patterns"] if p["key"] == "journal:tasks"]
    assert p["tier"] == 1 and p["target"] == "CLAUDE.md" and p["sessions"] == 3
    assert p["first"] == "2026-10-08" and p["last"] == "2026-10-12"
    assert any("time zone" in s for s in p["samples"])
    # The command step checks the change is allowed, applies it with Edit/Write (simulated here), then records it.
    dry = run(v, "record", "--key", "journal:tasks", "--tier", "1", "--target", "CLAUDE.md", "--change", "c", "--why", "w", "--dry-run")
    assert AUDIT_TUNED.match(dry.stdout.strip())
    assert not (v / "_generated" / "vault-hygiene" / "tuning.json").exists()
    claude = v / "CLAUDE.md"
    claude.write_text(claude.read_text() + "2. Always state times in the owner's time zone.\n")
    r = run(v, "record", "--key", "journal:tasks", "--tier", "1", "--target", "CLAUDE.md",
            "--change", "added a rule to always use the owner's time zone", "--why", "it kept forgetting the time zone")
    out = r.stdout.strip().splitlines()
    assert len(out) == 1 and AUDIT_TUNED.match(out[0]), out
    assert "journal:tasks" in out[0] and "why:" in out[0]
    state = json.loads((v / "_generated" / "vault-hygiene" / "tuning.json").read_text())
    assert state["patterns"]["journal:tasks"]["tuned_at"] == TODAY
    assert state["patterns"]["journal:tasks"]["tier"] == 1
    summary = run(v, "summary").stdout
    assert "Tuned 1 thing this week: added a rule to always use the owner's time zone" in summary


def test_tier1_command_pattern_targets_the_command_and_its_mirror(tmp_path):
    lines = [line(s, d, complaints=["the end of day note missed my meetings"], systems=["routines"], slash=["/eod"])
             for s, d in (("aaaa1111", "2026-10-08"), ("bbbb2222", "2026-10-09"), ("cccc3333", "2026-10-11"))]
    order = plan(make_vault(tmp_path, lines))
    [p] = order["patterns"]
    assert p["tier"] == 1
    assert p["target"] == ".claude/commands/eod.md" and p["mirror"] == "cowork-commands/eod.md"


def test_one_change_per_pattern_per_night(tmp_path):
    v = make_vault(tmp_path, complaint_week())
    plan(v)
    args = ("record", "--key", "journal:tasks", "--tier", "1", "--target", "CLAUDE.md", "--change", "a rule", "--why", "w")
    run(v, *args)
    again = run(v, *args, check=False)
    assert again.returncode == 2 and "already" in again.stderr


# --- Tier 2: reported, never edited ---------------------------------------------------------------

def test_tier2_hook_pattern_is_reported_and_no_file_is_edited(tmp_path):
    blocked = [{"name": "Bash", "input": "x", "ok": False, "ms": 5, "error_class": "hook_blocked"}]
    evs = [evidence(s, d, blocked) for s, d in (("aaaa1111", "2026-10-08"), ("bbbb2222", "2026-10-10"), ("cccc3333", "2026-10-12"))]
    lines = [line(s, d, complaints=["it forgot my time zone"]) for s, d in (("aaaa1111", "2026-10-08"), ("bbbb2222", "2026-10-10"), ("cccc3333", "2026-10-12"))]
    v = make_vault(tmp_path, lines, evs)
    before = snapshot(v)
    order = plan(v)
    assert any(x["key"] == "journal:tasks" and x["tier"] == 1 for x in order["patterns"])   # so the target guard below is reached
    [p] = [p for p in order["patterns"] if p["source"] == "telemetry"]
    assert p["key"] == "telemetry:Bash:hook_blocked" and p["tier"] == 2
    assert p["error_class"] == "hook_blocked" and p["calls"] == 3 and p["sessions"] == 3
    assert p["first"] == "2026-10-08" and p["last"] == "2026-10-12"
    # A Tier 1 record of a Tier 2 pattern, or a Tier 1 edit aimed at a script, hook or settings file, is refused.
    bad = run(v, "record", "--key", p["key"], "--tier", "1", "--target", "CLAUDE.md", "--change", "c", "--why", "w", check=False)
    assert bad.returncode == 2
    for target in ("scripts/hooks/guard.py", ".claude/settings.json", ".mcp.json"):
        bad = run(v, "record", "--key", "journal:tasks", "--tier", "1", "--target", target, "--change", "c", "--why", "w", check=False)
        assert bad.returncode == 2, target
        assert "plain-words file" in bad.stderr, (target, bad.stderr)
    r = run(v, "record", "--key", p["key"], "--tier", "2", "--target", "Inbox/2026-10-13 report for your contact.md",
            "--change", "reported", "--why", "guard blocks recur")
    assert AUDIT_REPORTED.match(r.stdout.strip()), r.stdout
    run(v, "themes")
    after = snapshot(v)
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert changed <= OUTPUTS, changed - OUTPUTS


def test_package_lists_only_vault_relative_paths(tmp_path):
    lines = [dict(line(s, d, failures=["hook blocked the script"], systems=["hooks"]),
                  files_touched=["scripts/x.py", "/home/someone/secret-place/y.md", "~/z.md", "Personal/Journal/a.md"])
             for s, d in (("aaaa1111", "2026-10-08"), ("bbbb2222", "2026-10-10"), ("cccc3333", "2026-10-12"))]
    v = make_vault(tmp_path, lines)
    plan(v)
    pkg = run(v, "package").stdout
    assert "scripts/x.py" in pkg
    assert "someone" not in pkg and "~/z.md" not in pkg and "Personal/" not in pkg


def test_tier2_report_package_is_names_and_counts(tmp_path):
    blocked = [{"name": "Bash", "input": "cat " + SECRET_A, "ok": False, "ms": 5, "error_class": "permission_denied"}]
    evs = [evidence(s, d, blocked) for s, d in (("aaaa1111", "2026-10-08"), ("bbbb2222", "2026-10-10"), ("cccc3333", "2026-10-12"))]
    lines = [line(s, d) for s, d in (("aaaa1111", "2026-10-08"), ("bbbb2222", "2026-10-10"), ("cccc3333", "2026-10-12"))]
    v = make_vault(tmp_path, lines, evs)
    plan(v)
    pkg = run(v, "package").stdout
    assert "telemetry:Bash:permission_denied" in pkg and "x3" in pkg and "2026-10-08" in pkg
    assert "cat " not in pkg and SECRET_A not in pkg
    only = run(v, "package", "--key", "journal:nothing").stdout
    assert "telemetry:Bash" not in only and "No reports tonight." in only


# --- What is never read --------------------------------------------------------------------------

def test_private_session_is_ignored(tmp_path):
    blocked = [{"name": "Bash", "input": "x", "ok": False, "ms": 5, "error_class": "hook_blocked"}]
    lines = [line("aaaa1111", "2026-10-08", complaints=["it forgot my time zone"]),
             line("bbbb2222", "2026-10-10", complaints=["time zone wrong"]),
             line("dddd4444", "2026-10-11"),
             line("pppp9999", "2026-10-12", complaints=["time zone private words"], private=True)]
    evs = [evidence("aaaa1111", "2026-10-08", blocked), evidence("bbbb2222", "2026-10-10", blocked),
           evidence("pppp9999", "2026-10-12", blocked, private=True)]
    v = make_vault(tmp_path, lines, evs)
    order = plan(v)
    assert order["sessions_in_window"] == 3                       # the private session is not counted
    assert order["patterns"] == []                                # 2 public sessions each: under the bar
    run(v, "themes")
    for rel in OUTPUTS:
        p = v / rel
        if p.exists():
            text = p.read_text()
            assert "pppp9999" not in text and "pppp" not in text and "private words" not in text, rel


def test_sensitive_lines_are_skipped(tmp_path):
    lines = [line(s, d, complaints=["my workout plan is wrong"], systems=["health"])
             for s, d in (("aaaa1111", "2026-10-08"), ("bbbb2222", "2026-10-10"), ("cccc3333", "2026-10-12"))]
    lines += [line(s, d) for s, d in (("eeee5555", "2026-10-09"), ("ffff6666", "2026-10-11"), ("gggg7777", "2026-10-12"))]
    order = plan(make_vault(tmp_path, lines))
    assert order["patterns"] == [] and order["skipped_sensitive"] == 3


def test_script_never_reads_personal(tmp_path):
    src = SCRIPT.read_text(encoding="utf-8")
    # The only directory walked is the journal; Personal/ is named only to drop file paths that point there.
    for m in re.finditer(r"glob\.glob\(([^)]*)\)", src):
        assert "root" in m.group(1), m.group(0)
    for ln in src.splitlines():
        if "Personal/" in ln:
            assert "startswith" in ln or ln.lstrip().startswith(("#", "\"", "'")) or "never" in ln, ln
    v = make_vault(tmp_path, complaint_week())
    (v / "Personal" / "Journal").mkdir(parents=True)
    (v / "Personal" / "Journal" / "2026-10-12.md").write_text("private phrase zebra-lantern")
    (v / "Personal" / "2026-10.mac.jsonl").write_text(json.dumps(line("zzzz0000", "2026-10-12", complaints=["zebra-lantern"])) + "\n")
    plan(v)
    run(v, "themes")
    for rel in OUTPUTS:
        assert "zebra-lantern" not in (v / rel).read_text() and "zzzz" not in (v / rel).read_text(), rel


# --- Cooldown and thresholds ---------------------------------------------------------------------

def test_pattern_inside_cooldown_is_skipped(tmp_path):
    tuning = {"patterns": {"journal:tasks": {"tuned_at": "2026-10-05", "tier": 1, "target": "CLAUDE.md", "change": "a rule"}}}
    order = plan(make_vault(tmp_path, complaint_week(), tuning=tuning))
    assert [p["key"] for p in order["patterns"]] == []
    assert order["skipped_cooldown"] == [{"key": "journal:tasks", "tuned_at": "2026-10-05", "until": "2026-10-19"}]


def test_pattern_after_cooldown_returns_with_its_previous_fix(tmp_path):
    tuning = {"patterns": {"journal:tasks": {"tuned_at": "2026-09-20", "tier": 1, "target": "CLAUDE.md", "change": "a rule"}}}
    order = plan(make_vault(tmp_path, complaint_week(), tuning=tuning))
    [p] = order["patterns"]
    assert p["previous"]["change"] == "a rule" and p["previous"]["tuned_at"] == "2026-09-20"


def test_window_with_two_sessions_applies_nothing(tmp_path):
    lines = [line("aaaa1111", "2026-10-10", complaints=["time zone"]), line("bbbb2222", "2026-10-12", complaints=["time zone"])]
    v = make_vault(tmp_path, lines)
    order = plan(v)
    assert order["status"] == "not_enough_sessions" and order["patterns"] == []
    assert order["audit_line"] == "tuning: not enough sessions yet (2 sessions in the last 7 days)"
    r = run(v, "record", "--key", "journal:tasks", "--tier", "1", "--target", "CLAUDE.md", "--change", "c", "--why", "w", check=False)
    assert r.returncode == 2
    run(v, "themes")
    assert not (v / "_generated" / "Themes.md").exists()


def test_two_sessions_fourteen_days_apart_qualify(tmp_path):
    lines = [line("oooo0000", "2026-09-20", complaints=["the proposal used the old price"], systems=["proposals"]),
             line("aaaa1111", "2026-10-12", complaints=["old price in the proposal again"], systems=["proposals"]),
             line("bbbb2222", "2026-10-09"), line("cccc3333", "2026-10-10")]
    order = plan(make_vault(tmp_path, lines))
    [p] = order["patterns"]
    assert p["key"] == "journal:proposals" and p["sessions"] == 2 and p["first"] == "2026-09-20"


def test_technical_failures_are_tier2(tmp_path):
    lines = [line(s, d, failures=["hook blocked the script that reads settings.json"], systems=["hooks"])
             for s, d in (("aaaa1111", "2026-10-08"), ("bbbb2222", "2026-10-10"), ("cccc3333", "2026-10-12"))]
    [p] = plan(make_vault(tmp_path, lines))["patterns"]
    assert p["tier"] == 2


# --- Themes ---------------------------------------------------------------------------------------

def test_themes_are_written_capped_and_expire(tmp_path):
    tuning = {"themes": {"journal:old": {"title": "Old friction", "first": "2026-09-01", "last": "2026-09-25", "sessions": 3,
                                         "root": "r", "evidence": ["x"], "projects": ["Brain"], "ask": "a"}}}
    v = make_vault(tmp_path, complaint_week(), tuning=tuning)
    plan(v)
    run(v, "record", "--key", "journal:tasks", "--tier", "1", "--target", "CLAUDE.md", "--change", "added a time zone rule",
        "--why", "no rule names the owner's time zone", "--title", "Time zone keeps slipping")
    run(v, "themes")
    text = (v / "_generated" / "Themes.md").read_text()
    assert len(text.splitlines()) <= 40
    assert "## Time zone keeps slipping  (3 sessions, first 2026-10-08, last 2026-10-12)" in text
    assert "Root: no rule names the owner's time zone" in text
    for field in ("Root:", "Evidence:", "Ask:", "Projects:"):
        assert re.search(rf"(?m)^{field} ", text), field
    assert "added a time zone rule" in text
    assert "Old friction" not in text                              # not seen for 14+ days: dropped
    assert "Projects: Brain" in text


# --- Outputs never carry a secret ----------------------------------------------------------------

def test_no_secret_looking_value_in_any_output(tmp_path):
    lines = [line("aaaa1111", "2026-10-08", complaints=[f"it printed {SECRET_A} again"], why=f"API_KEY={SECRET_B} leaked"),
             line("bbbb2222", "2026-10-10", complaints=[f"token {SECRET_A} shown"]),
             line("cccc3333", "2026-10-12", complaints=[f"API_KEY={SECRET_B} in the log"])]
    v = make_vault(tmp_path, lines)
    outs = [run(v, "plan").stdout]
    outs.append(run(v, "record", "--key", "journal:tasks", "--tier", "1", "--target", "CLAUDE.md",
                    "--change", f"never print {SECRET_A}", "--why", f"API_KEY={SECRET_B}").stdout)
    outs += [run(v, "themes").stdout, run(v, "summary").stdout, run(v, "package").stdout]
    for rel in OUTPUTS:
        outs.append((v / rel).read_text())
    blob = "\n".join(outs)
    assert SECRET_A not in blob and SECRET_B not in blob


def test_no_em_dashes_in_the_script_or_its_outputs(tmp_path):
    assert chr(0x2014) not in SCRIPT.read_text(encoding="utf-8")
    v = make_vault(tmp_path, complaint_week())
    plan(v)
    run(v, "record", "--key", "journal:tasks", "--tier", "1", "--target", "CLAUDE.md", "--change", "a rule " + chr(0x2014) + " here", "--why", "w")
    run(v, "themes")
    for rel in OUTPUTS:
        assert chr(0x2014) not in (v / rel).read_text(), rel


def test_fails_open_on_a_broken_journal(tmp_path):
    v = make_vault(tmp_path, complaint_week())
    with open(v / "_generated" / "system-journal" / "2026-10.mac.jsonl", "a") as f:
        f.write("{not json\n")
    (v / "_generated" / "system-journal" / "cloud" / "2026-10-11.zzzz.json").write_text("garbage")
    order = plan(v)
    assert order["status"] == "ok" and order["patterns"]
