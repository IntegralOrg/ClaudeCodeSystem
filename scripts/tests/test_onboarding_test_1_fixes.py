"""Fixes from the first live onboarding test (PR A): docs the agent follows during setup."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(name):
    return (ROOT / "System" / f"{name}.md").read_text(encoding="utf-8")


def has(text, *needles):
    low = text.lower()
    missing = [n for n in needles if n.lower() not in low]
    assert not missing, missing


def part_b():
    text = read("Setup Procedure")
    return text[text.index("## Part B"):text.index("## 1. Open, then learn")]


# G4: GitHub sign-in

def test_b3_confirms_the_signed_in_github_user_before_creating_the_repo():
    b3 = part_b()[part_b().index("**B3."):part_b().index("**B4.")]
    has(b3, "signed in to GitHub as **<login>**", "Is that the account you want your vault on?", "github.py logout",
        "login-start")
    # identity card comes after SIGNED_IN and before the organization question
    assert b3.index("SIGNED_IN") < b3.index("Is that the account") < b3.index("Where the vault lives")
    has(b3, "already belongs to an account, sign in to that account instead")


def test_every_did_you_do_it_card_has_an_it_did_not_work_option():
    text = read("Setup Procedure")
    has(text, "**It did not work**")
    rule = [l for l in text.splitlines() if "It did not work" in l and "When a step fails" in l]
    assert rule, "the second option must route to 'When a step fails'"
    b4 = part_b()[part_b().index("**B4."):]
    has(b4, "It did not work")


def test_claude_comes_back_to_the_front_after_each_browser_step():
    text = read("Setup Procedure")
    has(text, "handback", "com.anthropic.claudefordesktop", "looking at Claude")
    pb = part_b()
    assert pb.count("bring Claude back") >= 1 or pb.count("Claude back to the front") >= 1


def test_browser_sign_in_warning_is_said_once_before_the_first_claude_page():
    b4 = part_b()[part_b().index("**B4."):]
    has(b4, "Your browser will ask you to sign in to Claude once; use the same email as the app.")


# G3: routines

def test_routine_files_carry_a_model_and_an_off_the_hour_schedule():
    eod = (ROOT / "System" / "routines" / "eod.md").read_text(encoding="utf-8")
    hyg = (ROOT / "System" / "routines" / "vault-hygiene.md").read_text(encoding="utf-8")
    assert re.search(r"^model: claude-opus-5-5$", eod, re.M)
    assert re.search(r"^model: claude-sonnet-5-5$", hyg, re.M)   # a bare value: check-keys.py and setup pass it to the API as is
    assert re.search(r'^schedule: "7 23 \* \* 1-5"$', eod, re.M)
    assert re.search(r'^schedule: "7 1 \* \* \*"$', hyg, re.M)
    has(eod, "11:07 PM")
    has(hyg, "1:07 AM", "open decision")
    assert "0 23 * * 1-5" not in eod and "0 1 * * *" not in hyg


def test_setup_section_3_writes_the_local_remotetrigger_path_first():
    text = read("Setup Procedure")
    step3 = text[text.index("## 3. Create the routines"):text.index("## 4. Keys")]
    has(step3, "`/schedule`", "RemoteTrigger", "`list`", "`create`", "`get`", "`update`", "cron_expression",
        "persist_session", "job_config", "environment_id", "session_context", "model", "sources", "git_repository",
        "events", "7 3 * * 2-6", "7 4 * * 2-6", "11:07 PM")
    assert step3.index("RemoteTrigger") < step3.index("mcp__Claude_Code_Remote__create_trigger")
    has(step3, "model` from the routine's file", "verify")
    assert "0 3 * * 2-6" not in step3 and "0 4 * * 2-6" not in step3
    has(step3, "- model: claude-opus-5-5")
    has(step3, "Routines (the sidebar may say Scheduled)")


def test_routines_doc_records_the_model_and_the_07_schedules():
    text = read("Routines")
    has(text, "## End of Day\n- live_since: not live", "## Vault Hygiene\n- live_since: not live")
    eod = text[text.index("## End of Day"):text.index("## Vault Hygiene")]
    hyg = text[text.index("## Vault Hygiene"):text.index("## How setup creates them")]
    has(eod, "- model: claude-opus-5-5", "7 23 * * 1-5", "11:07 PM", "7 3 * * 2-6")
    has(hyg, "- model: claude-sonnet-5-5", "7 1 * * *", "1:07 AM")
    has(text, "7 4 * * 2-6", "Routines (the sidebar may say Scheduled)", "RemoteTrigger", "`/schedule`",
        "start minutes late")
    by_hand = text[text.index("## Create a routine by hand"):text.index("## If a routine is stale")]
    has(by_hand, "Model:", "model:` line")
    assert "0 23 * * 1-5" not in text and "0 1 * * *" not in text and "0 3 * * 2-6" not in text
    assert text.count("sidebar may say Scheduled") == 1


def test_how_this_works_table_matches_the_new_times():
    has(read("How This Works"), "11:07 PM", "1:07 AM")


# G6: bundled CLI

def test_superpowers_install_finds_the_bundled_cli_before_any_screen_drive():
    adding = read("Adding Your Computer")
    line = [l for l in adding.splitlines() if "Installs the **Superpowers**" in l][0]
    has(line, "scripts/setup/claude_cli.py", "CLI_MISSING", "before")
    assert line.index("claude_cli.py") < line.index("Settings, Plugins")
    setup = read("Setup Procedure")
    sec7 = setup[setup.index("## 7. Show it working"):setup.index("## Ask the person only when")]
    has(sec7, "scripts/setup/claude_cli.py", "CLI_MISSING", "superpowers@superpowers-marketplace")


# G7: section 7 and section 2

def test_first_computer_checks_list_connectors_and_disclose_the_paid_call():
    setup = read("Setup Procedure")
    sec7 = setup[setup.index("## 7. Show it working"):setup.index("## Ask the person only when")]
    has(sec7, "connectors", "missing", "paid", "`claude -p`", "skip it", "session journal")
    adding = read("Adding Your Computer")
    step4 = adding[adding.index("## 4."):adding.index("## 5.")]
    has(step4, "paid call", "says so in one sentence", "skips it", "names the missing ones")


def test_build_the_vault_replaces_every_placeholder_and_rewrites_the_schedule_rules():
    setup = read("Setup Procedure")
    sec2 = setup[setup.index("## 2. Build the vault"):setup.index("## 3. Create the routines")]
    has(sec2, "`[Your Name]`", "`[YourCompany]`", "every", "no bracketed placeholder", "rule 12", "rule 13",
        "Meeting Window", "Daily Schedule Skeleton", "week shape", "planning day")


def test_round_3_offers_process_automation_and_a_quiet_planning_default():
    setup = read("Setup Procedure")
    sec1 = setup[setup.index("## 1. Open, then learn"):setup.index("## 2. Build the vault")]
    has(sec1, "Process automation", "I do not plan the week", "quiet default")
    jobs = [l for l in sec1.splitlines() if "What should this system carry for you first?" in l][0]
    assert jobs.count(";") == 3, jobs      # four options: the question tool holds no more


# G5: the allow prompts

def test_start_welcome_warns_about_the_allow_prompts():
    t = (ROOT / "System" / "Start.md").read_text(encoding="utf-8")
    welcome = t[t.index("## 1."):t.index("## 2.")]
    has(welcome, "Your Mac will ask a few times whether Claude may do something: click **Allow** each time.")


def test_plan_requirement_is_pro_or_max():
    for rel in ("README.md", "docs/index.html"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "Claude Pro or Max plan" in text, rel
        assert "Claude Max plan" not in text, rel


# G9: a flagged turn

def test_message_flagged_has_words_in_getting_help_and_when_a_step_fails():
    has(read("Getting Help"), "**Message flagged**", "Continue setup", "new session", "skips it")
    setup = read("Setup Procedure")
    fails = setup[setup.index("## When a step fails"):]
    has(fails, "**Message flagged**", "Continue setup")
    has(read("Getting Help"), "usage", "expected")


# G11: the hand-off sentence before the link

def test_start_says_the_hand_off_sentence_then_waits_before_opening_the_link():
    t = (ROOT / "System" / "Start.md").read_text(encoding="utf-8")
    home = t[t.index("## 5."):t.index("## When a step fails")]
    item2 = [l for l in home.splitlines() if l.startswith("2.")][0]
    has(item2, "wait two seconds")
    assert item2.index("I'm opening your Brain") < item2.index("wait two seconds") < item2.index("claude://code/new")


def test_no_em_dashes_in_the_touched_docs():
    for name in ("Setup Procedure", "Routines", "Adding Your Computer", "Start", "Getting Help", "How This Works"):
        assert chr(0x2014) not in read(name), name
    for p in (ROOT / "System" / "routines").glob("*.md"):
        assert chr(0x2014) not in p.read_text(encoding="utf-8"), p.name
    assert chr(0x2014) not in (ROOT / "scripts" / "setup" / "claude_cli.py").read_text(encoding="utf-8")
