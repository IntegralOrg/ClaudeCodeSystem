import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ["Setup Procedure", "How This Works", "Connecting Tools", "Routines", "Adding Your Computer", "Company GitHub Organization",
        "Getting Help", "Updating", "Start", "Who Decides"]


def read(name):
    return (ROOT / "System" / f"{name}.md").read_text(encoding="utf-8")


def has(text, *needles):
    low = text.lower()
    missing = [n for n in needles if n.lower() not in low]
    assert not missing, missing


def test_all_system_docs_exist_with_frontmatter():
    for name in DOCS:
        p = ROOT / "System" / f"{name}.md"
        assert p.is_file(), name
        head = p.read_text(encoding="utf-8").splitlines()[:6]
        assert head and head[0] == "---" and any(l.startswith("type:") for l in head), name


def test_setup_procedure_covers_every_step():
    text = read("Setup Procedure")
    has(text, "AskUserQuestion", "prepared brief", "three rounds", "CLAUDE.md", "System/routines", "check-keys.py", "SETUP_PENDING",
        "Adding Your Computer", "first win", "your call with Dean finishes those", "cloud session", "local session",
        "not live", "first run", "environment")
    for line in text.splitlines():
        if "check-keys.py" in line:
            assert ".env" not in line, line


def test_setup_procedure_matches_the_hooks_and_routine_tools():
    text = read("Setup Procedure")
    has(text, "create_trigger", "persist_session", "## Owner", "email:", "Setup completed", "live_since: not live",
        "Work/Daily/", "Claude GitHub app")
    step3 = text[text.index("## 4. Create the routines"):text.index("## 5. Keys")]
    has(step3, "repository", "get_trigger", "delete_trigger", "connectors", "created or reused")
    assert "scheduled-tasks" not in text
    # nowhere may the agent be told to open, read, cat, or print the credentials file
    bad = re.compile(r"\b(read|cat|print|echo|source|grep)\b[^.\n]{0,25}(\.env\b|credentials file)", re.I)
    for name in DOCS:
        for line in read(name).splitlines():
            m = bad.search(line)
            assert not m or "never" in line.lower(), (name, line)


def test_claude_md_support_rule_present():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    has(text, "Answering questions about this system", "System/", "what it is", "our recommendation", "the steps",
        "what changes afterwards", "drive the screen", "only when the session is local", "never improvise")
    has(text, "## Owner", "email:")
    assert "Setup repo check" not in text
    assert "ClaudeCodeSystem-Original" not in text


def test_connecting_tools_sections():
    text = read("Connecting Tools")
    for h in ["## The table", "## How a connector gets connected", "## Keys, for a tool with no good connector",
              "## When End of Day reports connector-missing", "## Claude plugins", "## Final check",
              "## Appendix: the full control way for Google (Cloud Console)"]:
        assert h in text, h
    assert not re.search(r"(?<![\w/])/" + "connect\\b", text) and "AskUserQuestion" not in text   # no retired slash command (the claude.ai/customize/connectors URL is fine)
    assert "check-keys.py" in text


def test_connect_steps_doc_is_gone_and_unreferenced():
    assert not (ROOT / "docs" / "connect-steps.md").exists()
    for p in [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]:
        assert "connect-steps" not in p.read_text(encoding="utf-8"), p.name


def test_adding_your_computer_order_and_content():
    text = read("Adding Your Computer")
    i_desktop = text.find("Claude Desktop"); i_ghd = text.find("GitHub Desktop"); i_open = text.find("Open the folder")
    assert 0 < i_desktop < i_ghd < i_open
    has(text, "~/Brain", "iCloud", "OneDrive", "Dropbox", "git --version", "Wispr Flow", "install.sh --vault",
        "Python 3", "Accessibility", "Screen Recording", "Superpowers", "Plugins", "~/.claude/settings.json", "claude -p")


def test_how_this_works_states_the_brakes_and_gaps():
    text = read("How This Works")
    has(text, "Bash", "guard", "merge=union", "`/update`", "System/Updating.md", "landing.log")
    has(text, "landing_health", "routine_health", "on branch")


def test_routines_doc_has_the_manual_path():
    text = read("Routines")
    has(text, "Create a routine by hand", "environment", "GitHub app", "not live")
    has(text, "create_trigger", "persist_session")
    by_hand = text[text.index("## Create a routine by hand"):text.index("## If a routine is stale")]
    has(by_hand, "Repository: choose `brain`")
    has(text, "get_trigger", "connectors")
    for title in ("End of Day", "Vault Hygiene"):
        assert f"## {title}\n- live_since: not live" in text, title


def test_public_repo_clean_of_internal_names():
    for name in DOCS:
        text = read(name).replace("github.com/IntegralOrg/ClaudeCodeSystem", "").replace("githubusercontent.com/IntegralOrg/ClaudeCodeSystem", "")  # the public template's addresses
        assert "Stephen" not in text and "Integral/" not in text, name
        if name != "Getting Help":
            assert "Integral" not in text, name
        if name != "Getting Help" and name != "Setup Procedure":
            assert "Dean" not in text, name
        assert "Eva" not in text, name


def test_go_live_flip_edits_the_first_bullet_never_adds_one():
    for folder in (".claude/commands", "cowork-commands"):
        for name in ("eod", "vault-audit"):
            text = (ROOT / folder / f"{name}.md").read_text(encoding="utf-8")
            assert "has no `live_since`" not in text, (folder, name)
            has(text, "change that same bullet", "never add a second live_since bullet")
    for p in (ROOT / "System" / "routines").glob("*.md"):
        text = p.read_text(encoding="utf-8")
        assert "has no `live_since`" not in text, p.name
        has(text, "never add a second live_since bullet")


def test_setup_procedure_is_safe_to_re_run():
    text = read("Setup Procedure")
    has(text, "list_triggers", "reuse it", "instead of creating a duplicate", "in place",
        "Create a routine by hand", "connector-missing", "persist_session: false",
        "Delete `SETUP_PENDING` now, so an interrupted hand-off never restarts setup")
    # order after the keys step: completion line, then marker deletion, then landing, then the first win
    keys = text.index("## 5. Keys")
    done = text.index("Setup completed <date>")
    gone = text.index("Delete `SETUP_PENDING` now")
    land = text.index("land-local.sh --final")
    demo = text.index("Local session: the first win")
    assert keys < done < gone < land < demo
    assert text.count("Delete `SETUP_PENDING`") == 1


def test_credentials_file_is_named_only_to_the_agent():
    # the person never hears the file's name: the pop-up writes it; the format line is for the agent, in the Appendix
    ct = read("Connecting Tools")
    has(ct, "the agent never opens, reads, or names to the person", "the agent never opens it")
    has(read("Setup Procedure"), "never open or name the file the script writes")
    has(read("Adding Your Computer"), "opens a box on your screen", "never in the chat")
    has(ct, "update_trigger", "connector path")
    assert "nothing after the `=`" in ct[ct.index("## Appendix"):]
    assert "never edits MCP server configuration" not in read("Connecting Tools")


def test_connecting_tools_keeps_the_google_walkthrough_in_the_appendix():
    # the per-tool sections are replaced by the table; the Cloud Console walkthrough moved, verbatim, to the Appendix
    text = read("Connecting Tools")
    appendix = text[text.index("## Appendix"):]
    has(appendix, "Download JSON", "already have a project", "organization policy", "gws", "oauthplayground",
        "gmail.modify", "GOOGLE_REFRESH_TOKEN", "If it lists upcoming events")
    has(text, "Direct Connections", "Tools That Need Login Credentials", "Rize", "ClickUp")


def test_adding_your_computer_final_fix_content():
    text = read("Adding Your Computer")
    has(text, "Microsoft Store", "python3 -c", "xcode-select --install", "~/Documents/GitHub", "choose `~/Brain`",
        "GIT_TERMINAL_PROMPT=0 git ls-remote origin", "Git Credential Manager", "gh auth login --web && gh auth setup-git",
        "land-local.sh --final", "landed on main", "nothing to push", "worktree")
    assert "python.org installer does not provide" in text
    # the screen-driving consent comes before the Superpowers install; the landing auth check before the landing
    assert text.index("drive the screen for anything") < text.index("Installs the **Superpowers**")
    assert text.index("ls-remote origin") < text.index("land-local.sh --final")
    assert "python.org and tick" not in text


def test_routine_schedules_are_utc_and_environment_choice_is_simple():
    setup, routines = read("Setup Procedure"), read("Routines")
    has(setup, "UTC", "7 3 * * 2-6", "7 4 * * 2-6", "America/New_York", "without naming an environment")
    has(routines, "UTC", "7 3 * * 2-6", "7 4 * * 2-6", "daylight-saving")
    assert "find the environment id other routines use" not in setup
    for folder in (".claude/commands", "cowork-commands"):
        eod = (ROOT / folder / "eod.md").read_text(encoding="utf-8")
        has(eod, "TZ=<that zone> date +%F")
        assert "[Your Timezone])" not in eod


def test_skeleton_has_the_sections_setup_fills_and_the_maintainer_and_local_notes():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    first = text.split("\n\n")[1]
    has(first, "IntegralOrg/ClaudeCodeSystem", "docs/DEVELOPING.md", "maintaining the template")
    for h in ("## Owner", "## Company", "## Tools I live in", "## The shape of my week", "## First jobs for this system"):
        assert h in text, h
        has(read("Setup Procedure"), h)
    has(text, "scripts/land-local.sh", "do not pull, rebase, or push by hand", "_generated/landing.log")


def test_no_false_repair_promise_for_duplicate_frontmatter():
    for text in (read("How This Works"), (ROOT / "System" / "routines" / "vault-hygiene.md").read_text(encoding="utf-8"), (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")):
        assert "Vault Hygiene repairs the duplicates" not in text and "Vault Hygiene repairs it nightly" not in text
        assert "also repairs duplicated frontmatter" not in text
    has(read("How This Works"), "autosync workflow repairs", "by hand")


def test_vault_audit_init_seeds_the_template_root_files():
    for folder in (".claude/commands", "cowork-commands"):
        text = (ROOT / folder / "vault-audit.md").read_text(encoding="utf-8")
        has(text, "README.md", "CHANGELOG.md", "LICENSE", "SETUP_PENDING", ".env.example", ".gitattributes", "`docs`", "`System`", "`Templates`",
            "duplicate_frontmatter_keys")


def test_vent_skill_ships_in_every_system_and_is_generic():
    skill = (ROOT / ".claude" / "skills" / "vent" / "SKILL.md").read_text(encoding="utf-8")
    head = skill.split("---")[1]
    assert re.search(r"^name: vent$", head, re.M) and re.search(r"^description: .+", head, re.M)
    has(skill, "Personal/Journal/", "988", "Don't decide today")
    assert ("ob" + "sidian") not in skill.lower() and chr(0x2014) not in skill
    # a skill with no scripts is mirrored for CoWork, body identical
    mirror = (ROOT / "cowork-commands" / "vent.md").read_text(encoding="utf-8")
    assert mirror == skill
    assert not (ROOT / ".claude" / "skills" / "vent" / "home.txt").exists()
    has(read("How This Works"), "/vent", "Personal/Journal/", "never decides anything for you")
    has((ROOT / "README.md").read_text(encoding="utf-8"), "/vent")


def test_journal_folder_is_a_record_folder_by_default():
    for folder in (".claude/commands", "cowork-commands"):
        text = (ROOT / folder / "vault-audit.md").read_text(encoding="utf-8")
        has(text, "Personal/Journal", "no_merge: true", "/vent")


def test_vent_sessions_stay_out_of_the_audit_tier():
    import importlib.util, json
    spec = importlib.util.spec_from_file_location("distill_for_vent_test", ROOT / "scripts" / "system-journal" / "distill.py")
    distill = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(distill)
    vocab = json.loads((ROOT / "scripts" / "system-journal" / "vocab.json").read_text(encoding="utf-8"))
    for v in (vocab, distill._GENERIC_VOCAB):
        assert "vent" in v["sensitive_tags"] and "vent" in v["systems"]
        assert "Personal/Journal/" in v["sensitive_path_prefixes"]
        tags, prefixes = set(v["sensitive_tags"]), tuple(v["sensitive_path_prefixes"])
        by_tag = {"systems": ["vent"], "files_touched": []}
        by_path = {"systems": ["documentation"], "files_touched": [str(ROOT / "Personal/Journal/Log.md")]}
        assert distill.sensitivity(by_tag, str(ROOT), tags, prefixes)[0]
        assert distill.sensitivity(by_path, str(ROOT), tags, prefixes)[0]


def test_setup_opens_without_eva_and_asks_with_the_picker():
    text = read("Setup Procedure")
    step1 = text[text.index("## 1."):text.index("## 2. Build the vault")]
    has(step1, "Whatever the person's first message says", "Never ask whether they have a brief",
        "up to four questions per call", "two to four options", "(Recommended)", "multi-select",
        "readlink /etc/localtime", "IANA", "not available in this session", "plain text")
    assert "transcript" not in step1.lower() and "Do you have" not in step1


def test_kickoff_tells_people_to_send_a_message():
    for rel in ("SETUP_PENDING", "README.md", "docs/index.html"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "starts by itself" not in text and "start by itself" not in text, rel
        has(text, "send any message")
    hook = (ROOT / "scripts" / "hooks" / "setup_pending.py").read_text(encoding="utf-8")
    has(hook, "whatever the first message says", "pasted brief")
    for rel in ("README.md", "docs/index.html"):
        assert "interview transcript" not in (ROOT / rel).read_text(encoding="utf-8"), rel


def test_mac_permissions_name_the_claude_code_helper_and_the_hand_back():
    text = read("Adding Your Computer")
    has(text, "**Claude Code**", "not Claude", "System Events", "screenctl.py request", "screenctl.py doctor",
        "start a new session", "brings you back to the Claude window")
    assert "give Claude Desktop **Accessibility**" not in text
    has((ROOT / "docs" / "index.html").read_text(encoding="utf-8"), "Claude Code")
    help_text = read("Getting Help")
    has(help_text, "when the agent cannot fix it", "Inbox/", "which setup step")


def test_drive_screen_hands_back_and_requests_permissions():
    skill = ROOT / ".claude" / "skills" / "drive-screen"
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    has(text, "Every drive ends with `handback`", "back to this window and", "Say yes to start", "handback --quiet",
        "screenctl.py request", "permissions_belong_to", "Claude Code", "CoreGraphics")
    src = (skill / "scripts" / "screenctl.py").read_text(encoding="utf-8")
    has(src, '"request", "handback"', "def bring_claude_forward", "def notify", "CGPreflightPostEventAccess",
        "responsibility_get_pid_responsible_for_pid", "com.anthropic.claudefordesktop")
    ref = (skill / "references" / "driving-agents.md").read_text(encoding="utf-8")
    has(ref, "Claude Code", "Nothing to install")


def test_claude_md_carries_the_setup_trigger_for_a_clean_machine():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    paras = text.split("\n\n")
    assert "maintaining the template" in paras[1]          # maintainer paragraph stays first
    trigger = paras[2]
    has(trigger, "SETUP_PENDING", "System/Setup Procedure.md", "## 0. Where you are",
        "whatever the first message says", "hooks may not run")


def test_setup_procedure_routes_and_runs_both_sessions():
    text = read("Setup Procedure")
    i0, ia, ib, i1 = (text.index("## 0. Where you are"), text.index("## Part A"),
                      text.index("## Part B"), text.index("## 1. Open, then learn"))
    assert i0 < ia < ib < i1
    part_a, part_b = text[ia:ib], text[ib:i1]
    has(part_a, "xcode-select --install", "winget install --id Git.Git -e --scope user", "9PNRBTZXMB4Z",
        "move-home.sh", "move-home.ps1", "screenctl.py request", "_generated/setup/answers.md",
        "Click Trust, then press Enter", "Downloads", "in the background", "while")
    has(part_b, "github.py install-gh", "github.py login-start", "github.py login-wait", "github.py connect",
        "github.py verify", "REPO_EXISTS", "scripts/land-local.sh", "Claude GitHub app", "Trash")
    assert "land-local.sh --final" not in part_a + part_b     # keeps the existing order test meaningful
    for t in ("DEST_NOT_EMPTY", "SYNCED_PATH", "GIT_MISSING"):
        assert t in part_a, t
    fails = text[text.index("## When a step fails"):]
    has(fails, "help_report.py", "once", "keep going", "handback", "onboarding contact")
    assert "gh auth" not in part_a + part_b      # the person never sees gh commands; the agent uses github.py


def test_adding_your_computer_points_desktop_starters_back():
    has(read("Adding Your Computer"), "If you started on your computer", "already")


def test_setup_parts_skip_the_second_welcome_and_can_rename_the_repo():
    text = read("Setup Procedure")
    part_a = text[text.index("## Part A"):text.index("## Part B")]
    part_b = text[text.index("## Part B"):text.index("## 1. Open, then learn")]
    has(part_a, "skip its opening line")
    has(part_b, "skip its opening line", "connect --name")


def test_setup_procedure_routes_a_vaultless_session_to_start():
    text = read("Setup Procedure")
    sec0 = text[text.index("## 0. Where you are"):text.index("## Part A")]
    first_bullet = [l for l in sec0.splitlines() if l.startswith("- ")][0]
    has(first_bullet, "no vault", "System/Start.md")
    has(sec0, "cloud session", "downloaded copy", "vault's home")


def test_setup_procedure_says_when_to_ask_the_person():
    text = read("Setup Procedure")
    ask = text[text.index("## Ask the person only when"):text.index("## When a step fails")]
    has(ask, "permission only they can grant", "sign-in", "consent", "administrator", "failed twice",
        "missing from their workspace", "Everything else", "why it is needed")


def test_setup_procedure_stops_on_an_organization_policy():
    text = read("Setup Procedure")
    part_b = text[text.index("## Part B"):text.index("## 1. Open, then learn")]
    has(part_b, "ORG_POLICY", "personal GitHub account", "ask your admin")
    line = [l for l in part_b.splitlines() if "ORG_POLICY" in l][0]
    assert "do not retry" in line.lower()
    has(line, "--owner", "third-party access", "Company GitHub Organization")   # two messages: org blocked vs managed account


def test_setup_procedure_offers_the_company_organization_only_when_the_account_has_one():
    text = read("Setup Procedure")
    part_b = text[text.index("## Part B"):text.index("## 1. Open, then learn")]
    has(part_b, "github.py orgs", "github owner", "Where should your vault live on GitHub?", "connect --owner",
        "brain-<their GitHub username>", "ask nothing", "ORGS_UNKNOWN", "more than three", "plain text")
    b4 = part_b[part_b.index("**B4."):]
    has(b4, "organization", "request", "owner approves")
    sec1 = text[text.index("## 1. Open, then learn"):text.index("## 2. Build the vault")]
    has(sec1, "github owner", "prepared brief", "never asked here")


def test_company_github_organization_doc_covers_setup_move_and_offboarding():
    text = read("Company GitHub Organization")
    has(text, "What it is", "Our recommendation", "Team plan", "Exactly two", "Two-factor", "No permission", "Admin",
        "third-party access", "GitHub CLI", "Claude GitHub app", "No branch protection", "brain-<GitHub username>",
        "Transfer ownership", "retarget --to", "land-local.sh --final", "When someone leaves", "only `origin`",
        "Enterprise Cloud", "create each person's vault yourself", "gitleaks git . --redact", "--name-only")
    assert "git log -p" not in text          # the pre-transfer scan never prints a credential into the conversation
    assert "install the Claude GitHub app on it themselves" not in text   # repo admins cannot; owners install it


def test_wispr_flow_is_offered_by_name_after_the_demo():
    setup = read("Setup Procedure")
    sec7 = setup[setup.index("## 8. Show it working"):setup.index("## Ask the person only when")]
    has(sec7, "Wispr Flow", "wisprflow.ai", "drive", "on yes")
    adding = read("Adding Your Computer")
    step4 = adding[adding.index("## 4."):adding.index("## 5.")]
    has(step4, "Wispr Flow", "offers")


def test_superpowers_installs_without_asking():
    text = read("Adding Your Computer")
    line = [l for l in text.splitlines() if "Installs the **Superpowers**" in l][0]
    has(line, "without asking", "claude plugin marketplace add obra/superpowers-marketplace",
        "claude plugin install superpowers@superpowers-marketplace", "Settings, Plugins", "one sentence")
    assert "install-or-skip" not in text and "whether to install" not in text
    has(read("Connecting Tools"), "Setup installs it for you")


def test_update_ends_with_a_numbered_summary():
    for rel in (".claude/commands/update.md", "cowork-commands/update.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        has(text, "What changed:", "numbered", "plain language", "at most six")
    updating = read("Updating")
    step7 = updating[updating.index("7. **Report**"):updating.index("## What changes afterwards")]
    has(step7, "What changed:", "numbered", "at most six", "last message")
    code = (ROOT / ".claude" / "commands" / "update.md").read_text(encoding="utf-8")
    cowork = (ROOT / "cowork-commands" / "update.md").read_text(encoding="utf-8")
    assert cowork.split("---", 2)[2].strip() == code.strip()      # the mirror's body matches the Code version


def test_drive_screen_names_the_pre_python_driver_and_the_changelog_ships_it():
    skill = (ROOT / ".claude" / "skills" / "drive-screen" / "SKILL.md").read_text(encoding="utf-8")
    has(skill, "screenctl.js", "before python3 exists", "osascript -l JavaScript", "six commands", "`screenctl.py` takes over")
    assert (ROOT / ".claude" / "skills" / "drive-screen" / "scripts" / "screenctl.js").is_file()
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = log.split("## [2026-10-12]")[1].split("\n## [")[0]
    has(entry, "System/Start.md", "screenctl.js", "Start in Claude", "ORG_POLICY", "Superpowers", "Wispr Flow", "What changed:",
        "### In an existing vault")


def test_who_decides_page_is_plain_and_names_the_records():
    text = read("Who Decides")
    has(text, "**What it is.**", "**Our recommendation.**", "## What your system fixes on its own", "## What it sends to your contact",
        "## What it never asks you", "_generated/vault-hygiene/audit-log.md", "Work/Daily/", "names and counts",
        "## What changes afterwards")
    low = text.lower()
    assert "tier 1" not in low and "tier 2" not in low          # tiers are internal vocabulary, never on the client page
    has(text, "never the approver", "never asks you to approve", "never shows you a queue")
    assert "skip" not in low
    assert chr(0x2014) not in text


def test_developing_has_the_decision_tiers_section():
    text = (ROOT / "docs" / "DEVELOPING.md").read_text(encoding="utf-8")
    sec = text[text.index("## Decision tiers"):]
    has(sec, "The client is never the approver", "Tier 1", "Tier 2", "apply-and-log", "never propose-and-wait",
        "audit-log.md", "routine", "error class", "count", "first and last date", "file paths",
        "help_report.py", "routine-alerts.json", "once per reason per 7 days", "`/update`",
        "numbered list of at most six plain lines", "System/Who Decides.md",
        "a Markdown file the owner sends on", "never emails anyone", "never names an address")
    assert "not yet chosen" not in sec and "Gmail" not in sec
    has(read("Who Decides"), "reach out to your contact", "never emails anyone")
    for rel in (".claude/commands/vault-audit.md", "cowork-commands/vault-audit.md"):
        assert "not chosen yet" not in (ROOT / rel).read_text(encoding="utf-8"), rel
    assert chr(0x2014) not in sec


def test_claude_md_and_guides_point_at_who_decides():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    about = text[text.index("### How I Work"):text.index("### Git Autopilot")]
    has(about, "System/Who Decides.md", "fixes", "your contact")
    has(read("How This Works"), "System/Who Decides.md")
    has((ROOT / "README.md").read_text(encoding="utf-8"), "Who%20Decides.md")
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = log.split("## [2026-10-13] - Who decides")[1].split("\n## [")[0]
    has(entry, "System/Who Decides.md", "### In an existing vault", "Decision tiers")


def test_vault_audit_tunes_from_the_week():
    code = (ROOT / ".claude" / "commands" / "vault-audit.md").read_text(encoding="utf-8")
    cowork = (ROOT / "cowork-commands" / "vault-audit.md").read_text(encoding="utf-8")
    assert cowork.split("---", 2)[2].strip() == code.strip()      # the mirror's body matches the Code version
    step = code[code.index("## Step 5b: Tune from the week"):code.index("## Step 6: Receipt")]
    has(step, "scripts/self-tune.py", "plan", "record", "--dry-run", "themes", "package", "Decision tiers",
        "\"private\": true", "Personal/", "3+ sessions", "14+ days apart", "root cause", "not enough sessions yet",
        "Tier 1", "Tier 2", "tonight", "Edit/Write", "help_report.py",
        "--report", "routine-alerts.json", "fewer than 7 days", "_generated/Themes.md", "audit-log.md",
        "never edits a script", "one change per pattern", "previous", "permission prompt")
    has(code[code.index("## Step 6: Receipt"):], "tuning:", "- tuned", "- reported", "What just happened:", "at most six")
    assert chr(0x2014) not in code


def test_tuning_reaches_the_daily_note_and_the_guides():
    for rel in (".claude/commands/eod-note.md", "cowork-commands/eod-note.md"):
        has((ROOT / rel).read_text(encoding="utf-8"), "Tuning:", "self-tune.py summary", "Tuned 2 things this week")
    readme = (ROOT / "scripts" / "system-journal" / "README.md").read_text(encoding="utf-8")
    assert "capture half only" not in readme
    has(readme, "Step 5b", "self-tune.py", "rolling 7-day window", "Tier 1", "Tier 2", "\"private\": true")
    line = "tunes the system from the week's sessions"
    has((ROOT / "README.md").read_text(encoding="utf-8"), line)
    has(read("How This Works"), line)
    has(read("Routines"), line)
    has((ROOT / "CLAUDE.md").read_text(encoding="utf-8"), "_generated/Themes.md")
    dev = (ROOT / "docs" / "DEVELOPING.md").read_text(encoding="utf-8")
    assert "Until both have shipped" not in dev
    has(dev, "Step 5b", "scripts/self-tune.py")
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = log.split("## [2026-10-13] - Nightly self-tuning")[1].split("\n## [")[0]
    has(entry, "Step 5b", "scripts/self-tune.py", "Decision tiers", "### In an existing vault", "System/Routines.md", "Startup Checklist")


def test_system_check_is_documented():
    has(read("How This Works"), "/system-check", "_generated/system-check/")
    has((ROOT / "README.md").read_text(encoding="utf-8"), "/system-check", "scripts/system-check.py")
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = log.split("## [2026-10-13] - System check")[1].split("\n## [")[0]
    has(entry, "scripts/system-check.py", "Decision tiers", "### In an existing vault", "setup: N problems", "names and counts")
    assert chr(0x2014) not in entry
