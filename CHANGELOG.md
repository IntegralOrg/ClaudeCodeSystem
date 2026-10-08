# Changelog

All notable changes to the ClaudeCodeSystem project are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [2026-10-08] - Cloud-first onboarding: the template is the vault, setup runs itself

### Added
- **Self-running setup** -- `SETUP_PENDING` at the root plus `scripts/hooks/setup_pending.py` start setup from `System/Setup Procedure.md` in the first session; no command to type. Silent in the template repository itself.
- **`System/`** -- the system explains itself: How This Works, Connecting Tools (including Claude plugins), Routines, Adding Your Computer, Getting Help; `CLAUDE.md` answers system questions only from these, in a fixed shape.
- **`System/routines/*.md` and `scripts/check-keys.py`** -- routine definitions declare the key names they need; the script reports present/missing by name, never a value; `--init` creates the credentials file from the example once (local sessions only).
- **Push channel** -- EOD ends with a status line and reaches the owner by email (Gmail connector) or an all-day calendar event when Vault Hygiene is stale or a key or connector is missing.
- **`scripts/land-local.sh` and `scripts/hooks/landing_health.py`** -- every local session lands on `main` from the Stop hook (ff-only pull, commit, push; throttle; lock; never force); repeated landing failures are announced at the next session start.
- **`scripts/hooks/guard_vault_path.py`** -- warns every session while the vault sits in iCloud, OneDrive, Dropbox, or Google Drive.
- **`docs/index.html`** -- the front door on GitHub Pages: Use this template, then open in Claude.
- **Tests** -- repo layout and autosync guard, retired commands, editor-trace gate, setup hooks, check-keys, land-local, landing health, System docs, front door.
- **`scripts/hooks/routine_health.py`** -- at session start, says when End of Day, Vault Hygiene, or Monthly Review has not run, or a routine is still not live; the connector-free push channel.

### Changed
- **The repository root is the vault root** -- `scripts/`, `.claude/settings.json`, `CLAUDE.md` (client skeleton), `Templates/`, `.env.example`, and `.github/workflows/vault-autosync.yml` (guarded so it never runs on the template) live at the root; maintainer notes moved to `docs/DEVELOPING.md`.
- **EOD** -- starts with the keys check and a connector listing; writes a "Routine health" section into the daily note.
- **Repository renamed** -- `IntegralOrg/ClaudeCodeSystem-Cloud` is now `IntegralOrg/ClaudeCodeSystem`; the separate Mac edition is being archived.
- **Monthly Review** -- writes `Work/Monthly/YYYY-MM-DD Monthly Review.md`, which the health hook reads.

### Removed
- **`/onboard`, `/train`, `/connect`, `/finish`** (both command folders), `docs/onboarding-guide.md`, Wispr Flow from setup, every reference to the previous note editor, `examples/settings.json` and `examples/cloud-hooks.settings.json` (now `.claude/settings.json`).

### Known gaps
- `System/` guidance does not refresh itself from the template; ask the agent to fetch it.
- Markdown union merges can duplicate a frontmatter line on a true conflict. The autosync workflow repairs it on branch merges only; a duplicate left by a local rebase is reported by Vault Hygiene's frontmatter check and fixed by hand.
- Human steps on the white-glove onboarding call (connectors, keys, installs, permission grants) are logged by hand in the facilitator's checklist, not by the system.
- The previous note editor's state folder is no longer excluded from hygiene and graph scans; delete it from a vault if one exists.

---

## [2026-09-30] - /handoff always ends with the copy-ready /pickup command

`/handoff` printed "To resume: /pickup NAME" inside its summary, mixed in with the other lines. In practice the name got lost in the summary or dropped when the reply carried extra warnings, and the user had to retype it in the next session.

### Changed
- **`/handoff` Step 4** (`.claude/commands/handoff.md` + `cowork-commands/handoff.md`) -- the reply now always ends with the exact resume command, alone in its own fenced code block, with the real handoff name filled in (for example `/pickup client-onboarding-fix`). It is the final line of the reply, after any warnings or open questions, and it is printed again whenever the handoff is re-saved in the same conversation. The name matches the saved filename exactly, so a single copy and paste resumes the work.

---

## [2026-10-06] - drive-screen skill: the agent can take the keyboard when a step must be clicked through

Some steps have no API and no connector: an OAuth consent screen, an installer, a settings page in a desktop app. The template told the agent to never touch a browser and to stop, so those steps always fell back to the human. Installing a headless browser by default is the wrong fix (a blank browser with no logins, and a large dependency most vaults never need).

### Added
- **`.claude/skills/drive-screen/`** (MIT, from [coleam00/skills](https://github.com/coleam00/skills)). Window discovery, focus, typing, pasting, keys, clicks, scrolling and screenshots on Windows, macOS and Linux, plus steering a Claude Code session in another terminal. It tries a command or scripting surface before the screen, verifies focus before every send, and starts only after the user hands over the keyboard in the current session. Per-OS first-run setup is in its `references/driving-agents.md`.
- **Onboarding Phase 6E step 3a** copies `.claude/skills/` into the vault, whole folder, same golden rule as the commands.

### Changed
- **Template CLAUDE.md, guideline 17**: the browser rule now forbids *installing* browser automation to work around a missing API, and tells the agent to offer the `drive-screen` skill when a step can only be clicked through.
- `.gitignore` keeps `.claude/skills/` in the repo (everything else under `.claude/` stays ignored).

---

## [2026-10-07] - System Journal per-call telemetry

### Added
- **System Journal** -- evidence/2 adds per-call `ok` / `ms` / `error_class` and per-session `tokens_by_model` (additive; evidence/1 files are read as `unknown`). `templates/scripts/system-journal/telemetry-stats.py` aggregates them (stdlib only, no network). `/opportunity-scan` reads one session and names the one durable change that would have prevented its friction. Stored tool inputs now pass through the guard hooks' secret masker.

---

## [2026-10-07] - Guard hooks, credential isolation, Current State / Log profile shape

### Added
- **`templates/scripts/hooks/`** -- `guard_secrets.py` (blocks reading, printing, or searching the credentials file and environment), `log_tool_use.py` (masked JSONL action log under `_generated/agent-actions/`), `guard_state_writes.py` (one `## Current State`, append-only `## Log`), `session_context.py` (session start context), plus a README with two proof commands. Wired into `examples/settings.json`.
- **`templates/scripts/{envload,with-env,sanitize_ingest,profile-convert}.py`** with tests in `templates/scripts/tests/`.
- **`templates/Client Note.md`** -- the client profile skeleton (`engagement: prospect`, five-key Current State, Log).

### Changed
- **Commands** (both command folders) -- no step sources the credentials file any more; helpers run through `python3 scripts/with-env.py -- ...`. `/graph-daily` Phase 4 writes takeaways to the Log and replaces changed Current State lines.
- **`templates/CLAUDE.md`** -- credential guideline rewritten, new write-path guideline, and the logins-file explanation for non-technical users.
- **`/onboard`** installs the hooks and scripts into the vault, and creates client profiles from `templates/Client Note.md`.

---

## [2026-10-06] - System Journal capture + metadata-rendered knowledge graph

Two portable building blocks land in the template. The **System Journal** turns every Claude Code session into a deterministic evidence record plus one distilled journal line, so a later review can spot what keeps coming back. The **knowledge graph** stops being hand-linked: `Graph/index.md` and the MOCs are now rendered from frontmatter, and the inline "link every first mention" pass is retired.

### Added
- **`templates/scripts/system-journal/`** -- capture pipeline (`extract.py`, `distill.py`, `run.sh`, `cloud-journal.sh`, `install.sh`, `themes-inject.py`, a generic `vocab.json`, and a README). In the cloud, repo-level `Stop`/`SessionEnd` hooks capture while the container is alive; locally, hooks install via `install.sh --vault <path> --write-hooks`. About nine cents per finished session with the default Sonnet distiller. Capture only: no reflection command and no Themes writer yet; the audit tier is generated locally and shipped nowhere.
- **`templates/scripts/cloud-land.sh`** plus the hook block merged into **`examples/settings.json`** (and a standalone copy in **`examples/cloud-hooks.settings.json`**) -- repo-level hooks that land a cloud session's file edits and journal on `main` without the agent running git, bypassing the permission classifier so an unattended cloud run never stalls.
- **`templates/scripts/graph-render.py`** -- deterministic, stdlib-only renderer for `Graph/index.md` and the MOCs, from frontmatter plus the concept index. Private top-level folders (`graph_private_top:`) and the internal/company folder (`graph_company_folder:`) are configurable in the vault schema YAML; `--schema` sets the schema path. Includes `templates/scripts/test_graph_render.py`.

### Changed
- **`/graph-daily` and `/graph-sync`** (both command folders) -- no inline wiki-link pass; structural edges only (a `## Related` line to a hub on new docs, entity-registry rows), and the renderer regenerates index/MOCs. No orphan report.
- **`templates/CLAUDE.md` Graph Navigation guideline** -- Graph files are rendered, not hand-edited; links are structural, path-qualified; do not link every mention in prose.

## [2026-10-06] - Embedding + canonical detection ported into `/vault-audit`

The nightly hygiene run now has a semantic layer: it detects same-subject document forks and proposes merges to a human review queue, instead of letting duplicates quietly accumulate.

### Added
- **`templates/scripts/vault-embed.py`**: local, in-process embeddings (`bge-small`, no data egress), same-subject candidate generation, a deterministic survivorship rule, a file-mode review queue, and fold-and-retire `apply` (only ever modifies a doc on a human-decided block). Thresholds, the owner/company exclusion list, the staleness window, and canonical-home folders are config in the schema's `embedding:` block (CLI flags override). A `migrate --rename` subcommand re-keys the saved state (index, vectors, judgments, watched clusters, golden set) after a rename.
- **`templates/scripts/tests/`**: stdlib-only unit tests for both scripts (run with `cd templates/scripts/tests && python3 -m unittest discover`).
- **`/vault-audit` Step 4b**: the nightly canonical-judgment pass (embed, judge, survivorship, dry-run, apply) plus a fail-loud invariant check on canonical/superseded markers. On the web runner, `report --install` self-installs the embedder at run start, so the scheduled routine needs no setup step.

### Changed
- **`templates/scripts/vault-audit.py`** refreshed to the current version (the invariant check, `hash_since`, and a report-only `stale_canonical` flag).
- **`templates/CLAUDE.md`** documents the canonical-marker frontmatter fields (`canonical`, `status: superseded`, `superseded_by`, `superseded_at`, `superseded_reason`).
- **`/onboard`** copies `vault-embed.py` alongside `vault-audit.py` and writes the schema `embedding:` block.

---

## [2026-10-05] - Completion check moves into EOD; /morning-precheck retired

`/morning-precheck` ran as its own scheduled morning job to find tasks that were already done. In practice it re-read the same day `/eod` had just read a few hours earlier, needed its own scheduled run and credentials, and existed only to serve task tracking, which not every vault uses.

### Changed
- **`/eod-gather` gains Section 5: Completion Check** (`.claude/commands/` and `cowork-commands/`). It checks open tasks against what the run already read plus up to 30 targeted thread lookups, checks off tasks with clear evidence, and records uncertain ones as `CONFIRM` rows. It runs only when the vault has open task lists; a vault not used for task management skips it entirely.
- **`/eod-today`** lists `CONFIRM` rows in `Today.md` under `## Possibly Done` for `/morning` to settle.

### Removed
- **`/morning-precheck`** (both command folders). If you scheduled it as a routine or a local job, delete that schedule.

---

## [2026-10-04] - Recall and source trust order

Asked to "find context" on a topic, the agent searched only the vault and its memory, answered from partial notes, and missed detail that existed in an earlier chat session. Nothing told it that past session transcripts are a recall source, or how to weigh a past chat against a vault doc.

### Added
- **Assistant Guideline "Recall and source trust order"** in `templates/CLAUDE.md` -- when a recall ask comes up thin in the vault, run a targeted search of past session transcripts (search only, never loaded at startup or read whole). Trust order for decisions and rules: canonical docs, vault notes, past session transcripts, built-in memory last. For changing facts the most recent dated source wins. Conflicts are shown with dates, never resolved silently; past chats are cited as dated leads; durable facts found only in a chat get filed into the vault; a "don't log" instruction in the matched session is honored.

---

## [2026-09-24] - Local routines are backed up in the vault

A Claude desktop LOCAL scheduled task lives only on the machine that created it (prompt on disk under `~/.claude/scheduled-tasks/`, schedule and approvals in app state that nothing exports, absent from the account's cloud routine list). A crashed or replaced computer lost them silently, and no rule told the agent to back them up.

### Added
- **`templates/scripts/local-routines-backup.sh`** -- mirrors every local task prompt into `Resources/Reference/Local Routines/<device>/` and prunes mirrors of deleted tasks; macOS and Linux.
- **`templates/Local Routines Registry.md`** -- the human-maintained half: one row per task with the settings the app does not export (schedule, folder, worktree, model, permissions, the exact always-allow command, deploy script to run first) plus the restore steps for a new computer.
- **Assistant Guideline "Local routines are backed up in the vault"** in `templates/CLAUDE.md`, a Quick Reference row, and an `/onboard` step (Code and CoWork variants) that copies both files into every new vault.

### Changed
- `docs/integration-architecture.md` scheduled-automation section explains the local-versus-cloud routine split and the backup rule.

---

## [2026-08-17] - Add /vault-audit: Nightly Self-Healing Vault Hygiene

`/monthly-review` catches structural drift once a month, after it has already made the vault harder to search. Nothing ran nightly, so a misfiled file or an unmerged duplicate could sit for weeks before the next full pass found it.

### Added
- **`/vault-audit`** (`.claude/commands/vault-audit.md` + `cowork-commands/vault-audit.md`) -- six-step nightly hygiene pass, fully autonomous: it fixes what it finds and never asks for approval mid-run. Splits the work deliberately: `templates/scripts/vault-audit.py` (stdlib-only Python, copied into the vault at `scripts/vault-audit.py`) owns everything deterministic -- walking the tree, hashing files for change detection, staging removals, purging week-old trash -- while Claude owns everything semantic -- does a file's content match its folder, do two files describe the same thing closely enough to merge, is the schema itself wrong. Neither is safe alone: a script has no notion of meaning, and free-form judgment without a script drifts as fast as the vault it's meant to fix.
- **`.claude/vault-schema.md`** -- the per-vault design contract the audit enforces: a machine-parsed YAML block (root whitelist, protected paths, folder purposes and naming patterns, `no_merge` record folders, required frontmatter) plus prose canonical-home rules. The audit can amend its own YAML when the same misfile recurs 3+ nights running, with every amendment logged to a changelog inside the file -- the schema self-corrects instead of needing a human to notice it's stale.
- **Removals are staged, never deleted.** Every file the audit would remove goes to `.claude/audit-trash/<date>/` first and is purged automatically after 7 days, so a bad call is a `mv` away from reversible, not a `git revert` away.
- **`/eod` Phase 5.5** -- runs the nightly audit after tomorrow's plan is built. Makes its own pre-audit checkpoint commit (`git commit -m "pre-audit checkpoint"`) immediately before invoking the command, so the audit itself never has to touch git and every change it makes in a session is trivially revertible.
- **`/onboard` Phase 6A** -- writes the vault's first `.claude/vault-schema.md` right after the folder structure is created, and copies `templates/scripts/vault-audit.py` into the new vault. Deliberately asks **at most one** plain-language question during setup ("Are there folders I should never reorganize, like a private journal?") -- protected paths are otherwise derived by convention (`Archive/`, `Attachments/`, `Templates/`, dot-folders, generated-output files), never interrogated out of a non-technical user one path at a time.

### Design notes
- Three refinements earned the hard way and worth calling out for anyone extending the command: the exact-duplicate tie-break falls back to the canonically-named file (not raw mtime) when both copies land in the same schema-endorsed folder, since a fresh accidental copy is usually the *newer* file, not the real one; empty-looking stubs get read in full before staging, because a two-line file can still carry a load-bearing fact (an ID, a date, a link); and any workflow that edits a file's content and then reindexes it must `scan` before `update-row`, never after, or the stored hash goes stale and the file re-flags on the very next run.

---

## [2026-07-28] - Monthly Review v2: The Command Now Repairs the Vault Instead of Reporting On It

`/monthly-review` was a four-question interview bolted to a permission-gated checklist. It asked the user for approval five separate times, marked problems for future attention instead of fixing them, and never touched the two things that actually degrade an agent over time: an unbounded `CLAUDE.md` and a vault whose files have drifted out of any coherent structure.

Field evidence (Beyond Braid "Agent Level Up" call, 2026-07-28, 29:47-32:59): a delivery lead walked a user through the `CLAUDE.md` character count live (31k against the 25k-30k target) and described the monthly review as the thing that "does a diagnostic of how your file's grown and been built over time" -- a diagnostic that did not exist in the shipped command. On the same call, one user had never run the review and another did not know it existed. A third had already hand-patched his own copy with folder-organization checks after a manual cleanup, framing the payoff as "your digital brain and the dots should be more connected versus a bunch of random dots sprawled everywhere." A fourth user's `memory.md` was sitting outside his vault, invisible through months of daily use. A user patching the skill himself is the clearest available signal that the shipped version is under-scoped.

The command is now 8 phases, only one of which is interactive.

### Added
- **Phase 0: Safety Gate (blocking).** No file is deleted, merged, or moved until the vault is confirmed present in a remote Git backup. Checks repo status, remote configuration, uncommitted work, and unpushed commits. On unsaved work it offers once, in plain language, to make the backup, then **re-verifies `git rev-list --count origin/<branch>..HEAD` after pushing** -- a push can report success and still leave commits behind, and treating the exit code as proof would defeat the entire gate.
- **SAFE MODE.** When there is no remote, or the user declines the backup, the run continues rather than aborting: every audit, the `CLAUDE.md` repair, the graph rebuild, the personalization audit, and the coaching phase all still run. Only destructive operations are withheld, collected into a "Waiting on your backup" list, and surfaced in the final report. A client with no remote configured must not get a dead command, because they will never run it again.
- **Phase 4: full knowledge-graph rebuild on every run**, not on request. Ordered deliberately **after** the merge phase; syncing first would index files about to be deleted and leave broken links pointing at them. Reports orphan count (files connected to nothing) as the headline metric, compared against last month.
- **Phase 5: Personalization Audit.** Asks what would improve this vault for this specific person rather than applying generic hygiene. Diagnoses each unused skill as **undiscovered** (the work still happens manually, so teach it) or **unwanted** (the work never happens, so offer to delete it), measures folder gravity, hunts repeated manual work as slash-command candidates, and checks structure fit -- where documentation and real filing behavior disagree, the documentation is treated as wrong, not the user.
- **Topical duplicate detection.** Beyond exact-hash and near-filename passes, a third pass finds the same operational fact restated across three or more files. Hashing cannot find this, and it is the drift that actually degrades an agent, because the copies fall out of sync and the agent starts receiving contradictory instructions.
- **Misplaced agent file detection (Phase 1f).** Searches outside the vault for a stray `memory.md`, `CLAUDE.md`, or memory directory, then explains where it was and why it was invisible. The detection always runs; the **move happens in FULL MODE only**, since relocating a file is a destructive operation and SAFE MODE defers it to the pending list.

### Changed
- **Phases 1 through 5 run with no questions asked.** The command no longer requests permission mid-run or presents findings for approval before acting. It fixes, then shows a receipt. There are exactly three remaining interaction points, documented at the top of the command: the one-time backup consent in Phase 0 (only when the vault is unsaved or unpushed), the Phase 6 coaching conversation, and approval of testimonial quotes in Phase 7a before a named client is quoted in writing. The backup gate is what makes the unattended repair in between safe.
- **The four feedback questions are cut to two and moved from the start of the run to the end.** Asked cold they produce shrugs; asked after the user has seen concrete findings they produce specifics. The "monthly 1-on-1 with your agent" framing is retained; the cold-open interrogation is not.
- **Phase 6 coaching replaces the old feedback step.** Root-causes the behavior rather than the symptom ("your instructions file grew 6,000 characters because every call added a guideline and nothing ever removed one," not "the file was too big"), teaches two or three concrete habits, then closes the loop by scheduling the preventive routines and building a slash command for the repeated manual work found in Phase 5, during the run. The command's stated goal is to make itself unnecessary: a user who depends on a monthly cleanup has a broken daily loop.
- **Written throughout for a non-technical reader.** No technical term appears in user-facing output without a plain-language explanation beside it.
- **Duplicate resolution defaults to merge-preserving-both-facts**, with byte-identical copies deleted outright. Nothing unique is lost, which is what makes the merge safe to perform unattended.

### Fixed
- **The `CLAUDE.md` growth diagnostic never existed.** Phase 2 now counts characters against the 25,000-30,000 target and, past 30,000, extracts oversized *reference detail* into `Resources/Reference/` files, leaving pointers, then reports before and after. **Guidelines, rules, and preferences are never extracted** -- an instruction that is not loaded into every conversation is not an instruction, so a size fix must not quietly gut the rules to hit a character target.
- **Nothing was ever actually repaired.** Every phase that previously produced a findings list to review now applies the fix in FULL MODE. In SAFE MODE the non-destructive repairs still apply and the destructive ones are deferred to the pending list rather than silently skipped.
- **Structural drift went unaddressed.** Duplicate files, misfiled notes, empty files and folders, and stale references to concluded work are now found and resolved in Phase 3.
- **Discovery.** Phase 5a explicitly checks whether the user has ever run the monthly review itself; a first run after many months is treated as the most important finding of the run and routed into coaching.

---

## [2026-07-24] - Add /morning-precheck and /reconcile

Two commands ported into the cloud edition, cloud-native from the start (no local-machine assumptions to strip).

### Added
- **`/morning-precheck`** (`.claude/commands/morning-precheck.md` + `cowork-commands/morning-precheck.md`) -- headless research pass that runs as a scheduled [Routine](https://code.claude.com/docs/en/routines) in Claude Code on the web (~6:30 AM weekdays), before the interactive `/morning`. Fans out parallel Task-tool subagents against Gmail, Slack, Calendar, and Fathom transcripts to verify what is actually still open; auto-marks HIGH-confidence completions in the client Inbox files; and writes `Inbox/Morning Precheck.md` for `/morning` to consume later that morning. Bakes in three hard-won rules: **done-by-anyone counts** (a teammate resolving the request is done for the user), **full-thread reading** (not just sender-side signals), and **exact-line matching instead of keyword matching** (keyword matches can wrongly check off the wrong task). `AskUserQuestion` is explicitly forbidden -- ambiguous items go to `## Confirm` for `/morning` to ask about later. Auto-retries the push on rejection (3 attempts, `git pull --rebase origin main` between each), since there is no user around to run the rebase manually in a headless Routine.
- **`/reconcile`** (`.claude/commands/reconcile.md` + `cowork-commands/reconcile.md`) -- interactive light EOD counterpart to `/eod`. Walks the day's time blocks and captures four states per block (done / carried / **skipped** / new-followup) so plan-adherence is honest -- silently dropping missed blocks inflates the metric and hides the pattern the user wants to see. Checks off the client Inbox files, patches Google Calendar with actuals prefixed `[done]` / `[carried]` / `[skipped]` so the calendar becomes a historical record of how time was actually spent, and upserts a row into `Work/Daily/Plan Adherence Log.md` for day-over-day trend visibility. Same 3-attempt push-retry loop, so a concurrent EOD Routine landing between the local commit and push cannot strand the reconcile.

### Design notes
- Both commands use inline `[YOUR_UTC_OFFSET]` and `[YOUR_IANA_TIMEZONE]` placeholders for timezone (not `.env` vars), matching the repo's existing `[Your Timezone]` / `[Client A]` / `[YourCompany]` customization pattern -- one-time swap when installing, not runtime config.
- `/morning-precheck` uses `zoneinfo.ZoneInfo(...)` for the Slack look-back timestamp so it resolves to 8:00 AM in the user's real timezone. The cloud container runs UTC by default, so a naive `time.mktime(...timetuple())` would have made "yesterday 8 AM" resolve five hours off for a US-East user.
- `/morning-precheck` runs `mkdir -p Inbox/` before writing the state file to protect a bare-fresh vault where `/onboard` has not yet created the folder.
- `/reconcile` is intentionally NOT a Routine candidate. It needs the user present to name exceptions ("which planned blocks did NOT happen?"); a headless variant would either auto-mark everything done (dishonest) or auto-mark everything skipped (useless).

---

## [2026-07-09] - Git Autopilot: Version Control Becomes Invisible to the User

Users of the cloud edition must never have to think about Git, GitHub, branches, pull requests, or merge conflicts. The biggest delivery risk was divergence: cloud sessions work on harness-assigned `claude/*` branches, stop to ask about PRs, or die without pushing, so changes never reach `main` and parallel sessions fork the vault. This release makes convergence on `main` continuous and self-healing, with three layers:

### Added
- **Git Autopilot section in `templates/CLAUDE.md`** (plus a rewritten persistence guideline #21). Standing, durable owner authorization that every session reads: `main` is the only branch that matters; sync (`git pull --rebase origin main`) at the start of every session and command; commit and push after every completed unit of work (never more than ~15 minutes unpushed); NEVER create a pull request or ask the user to review/approve/merge one; when the harness assigns a designated `claude/*` branch, push it and then also land the commits on `main` directly (`git push origin HEAD:main` after rebasing); resolve every merge conflict autonomously (Markdown: keep both sides; generated files like `Today.md`: newest wins; config: merge keys, newer value on collision); never surface Git mechanics to the user, except plainly reporting repeated push failures.
- **`templates/vault-autosync.yml`** -- a GitHub Actions safety net installed by `/onboard` at `.github/workflows/vault-autosync.yml` in the vault. Independent of any session's behavior, it merges every non-`main` branch into `main` (Markdown union-merges; other conflicts resolve toward the branch, which carries the newer work), pushes, and deletes the merged branch (which also closes any stray PR). Triggers: every side-branch push, PR opened/reopened, hourly sweep, manual dispatch. Serialized via a concurrency group; push retries with re-merge if `main` moves mid-run. So even a session that only pushed its designated `claude/*` branch and vanished converges within the hour.
- **`.gitattributes` in every new vault** (onboard 6A): `*.md merge=union`, so parallel sessions appending to the same Markdown files (inbox files, daily notes) merge cleanly on both the session side and the Action side instead of raising conflicts. Verified: concurrent edits to the same task file keep both sides' lines with no conflict stop.

### Changed
- **`onboard.md` (Code + CoWork copies)**: 6A now creates `.gitattributes` and installs the autosync workflow unconditionally (never ask the user about it); 7A gains a fallback for tokens that cannot push workflow files (`workflows` scope) -- create the file via the session's GitHub tools, or push everything else and log a TODO; 7A's confirmation wording now promises "you never need to touch GitHub yourself."

The first Cloud Edition pass changed the wording; this pass changes the behavior. The cloud workspace is temporary -- a fresh clone at session start, recycled at session end -- so anything the system wants to keep has to be pushed, and anything it wants in every session has to live in the repository (or the environment settings), not the workspace.

### Fixed
- **Nothing ever committed or pushed.** The docs called Git "the durability layer," but no command ran `git commit`/`git push`, so every EOD close-out, morning plan, and brain dump died with the workspace. Every writing command (`eod`, `morning`, `brain-dump`, `learn`, `graph-sync`, `graph-daily`, `handoff`) now ends with an explicit commit-and-push step, and `templates/CLAUDE.md` gains a global persistence guideline (#21) covering ad-hoc work.
- **`/handoff` + `/pickup` were broken across cloud sessions.** A handoff written to `.handoffs/` but never pushed could not reach the next session (which starts from a fresh clone). `/handoff` now commits and pushes the handoff (new Step 3.5) and warns about other unpushed changes; `/pickup` pulls first, treats old local-CLI memory paths (`~/.claude/projects/...`) as unavailable, and knows background processes never survive into a new session.
- **Onboarding built the vault on disposable disk.** Phase 6A offered `~/Documents/Brain` and `~/Desktop/Brain` -- paths that evaporate with the workspace. The vault now gets its own private GitHub repository (created during 6A), and a new Phase 7A pushes everything before wrap-up. Vault structure now includes a `.gitignore`.
- **Settings written to ephemeral locations.** Permissions went to `~/.claude/settings.json` (home folder of a temporary workspace) and `settings.local.json` (untracked). Durable permissions now live in the vault's **committed** `.claude/settings.json` (onboard 6D, `/connect`, onboarding guide); MCP servers move from home settings to the vault's committed `.mcp.json` with `${ENV_VAR}` placeholders instead of raw secrets. `examples/settings.json` drops the macOS-only `additionalDirectories` (`$HOME/Library/LaunchAgents`, etc.).
- **Secrets story.** `.env` is now documented everywhere as a session-local, untracked scratch copy; the permanent home for credentials is environment variables in the Claude Code environment settings (onboard 6C rewritten, `/connect` saves to both and verifies, glossary updated).

### Changed
- **Local scheduling replaced by cloud Routines.** Deleted `examples/scripts/eod-runner.sh`, `eod-cron.sh`, and `com.brain.eod-runner.plist` (macOS launchd/iCloud/Gatekeeper machinery, contradicting "nothing to install"). README FAQ, `docs/daily-workflow.md`, and `docs/integration-architecture.md` now describe scheduled Routines in Claude Code on the web (`/eod` on a weekday-night schedule, runs and pushes in the cloud). `md-to-gdoc.py` stays -- it runs fine in the workspace.
- **CoWork story made consistent.** Onboard 6E copies `cowork-commands/` into the vault for Cowork users (upload-ready, no walkthrough), and the repo `CLAUDE.md` maintenance notes match reality again. Remaining Desktop/CLI trichotomy references in `templates/CLAUDE.md` and `docs/integration-architecture.md` reframed for the single cloud runtime.
- `.gitignore`: dropped the leftover `.obsidian/` block.

---

## [2026-07-08] - Cloud Edition: Drop Obsidian and Local-Machine Framing

### Changed
- **The documentation no longer describes the system as "built on Obsidian" or as running on the user's local machine.** This is the cloud edition -- it runs in Claude Code on the web, and the vault is a Git repository of Markdown files that Claude reads and writes directly in a cloud workspace. The system is now described as **built on Claude Code and a Git-backed Markdown vault**.
- **`README.md`**: rewrote the tagline, "What you will need," and Get Started sections for the cloud edition; removed the Windows local-install section (Git Bash / Developer Mode / Virtual Machine Platform); relabeled the architecture diagram's "Obsidian Vault" box to "Git-Backed Vault (Markdown)"; replaced the iCloud atomic-write note; updated the Windows/Linux and cost FAQs.
- **`docs/onboarding-guide.md`**: dropped the "Pick Your Claude Interface" (Desktop vs CLI) step and the "Install Obsidian" step; reframed requirements, permission descriptions, the `/connect` and morning steps, and the glossary for the cloud edition.
- **`docs/vault-design-guide.md`**: retitled and rewrote "Why Obsidian?" as "Why a Git-backed Markdown vault?"; updated the core-idea, template-placeholder, atomic-writes, and "what makes this different" sections.
- **`docs/integration-architecture.md`**, **`docs/daily-workflow.md`**, **`templates/CLAUDE.md`**: relabeled the vault, dropped the Desktop/CoWork/CLI trichotomy and iCloud/Dropbox sync-race rationale, and reframed wiki-links as the graph convention (not "clickable in Obsidian").
- **Commands** (`onboard`, `train`, `finish`, `graph-sync`, `graph-daily`, `eod-gather`, `eod-sync`, `monthly-review`, `brain-dump`, `morning`) and their `cowork-commands/` mirrors: removed "Open Obsidian" instructions, the "nothing is in the cloud / on your machine" framing, `.obsidian/` exclusions, and the iCloud atomic-write rule.
- **Repo `CLAUDE.md`**: bootstrap detection no longer keys on `.obsidian/`; it now detects an existing vault by its contents (`CLAUDE.md`, `Inbox/`, `Work/`).

---

## [2026-06-18] - Single Command Folder: Removed examples/commands/, Unconditional Install

### Fixed
- **Commands were silently dropped during onboarding.** `onboard.md` Phase 6E used a hand-enumerated, conditional install list: `morning.md`/`eod.md`/`daily-note.md`/`brain-dump.md` only installed if the user picked the matching Phase 5 workflow preference, and the five EOD phase commands (`eod-gather`, `eod-sync`, `eod-time`, `eod-note`, `eod-today`) were never installed at all. Because `/eod` and its phase commands reference each other, a half-installed pipeline broke mid-run after the user invoked a slash command.

### Changed
- **Phase 6E now installs every command unconditionally** via a glob copy of `.claude/commands/*.md` (minus `onboard.md`), in both the CLI and CoWork paths. Workflow preferences only affect which command is *recommended* and how tool-specific ones are *customized*, never whether a file is installed. There is no longer any hand-maintained install list to fall out of sync.
- **Removed the `examples/commands/` folder.** Its 10 commands (`eod`, `eod-gather`, `eod-sync`, `eod-time`, `eod-note`, `eod-today`, `morning`, `monthly-review`, `brain-dump`, `daily-note`) moved into `.claude/commands/` via `git mv`. There is now exactly one source folder for Code commands. The "examples" framing was the root cause of the drift: it made shipped commands look optional. `examples/` retains only `settings*.json` and `scripts/`.
- **Docs updated**: repo `CLAUDE.md` (Dual-Format table + maintenance rule), `README.md` (repository-structure tree), `docs/vault-design-guide.md`, and `finish.md` (both Code + CoWork copies) no longer reference `examples/commands/`.

---

## [2026-06-10] - Handoffs Moved Out of .claude/ to .handoffs/

### Changed
- **Handoff storage moved from `.claude/handoffs/` to `.handoffs/` at the working-directory root** (`/handoff`, `/pickup`, `/onboard` Phase 6E, README — both `.claude/commands/` and `cowork-commands/` copies). Claude Code's hardcoded sensitive-file guard prompts on EVERY Write/Edit under `.claude/` directories and cannot be suppressed by permission allow rules, PreToolUse hooks, or PermissionRequest hooks (verified empirically; known open bug anthropics/claude-code#41615, including the dialog's non-persisting "always allow" option). Moving the directory out of `.claude/` is the only way to make handoff writes prompt-free.
- **`/pickup` legacy fallback extended**: if `.handoffs/` is missing or empty but `.claude/handoffs/` has files, read from there and suggest migrating them (covers projects not yet moved).

### Migration
- Per project: `mv .claude/handoffs .handoffs` and gitignore `.handoffs/` (keep the old `.claude/handoffs/` ignore line for stragglers).

---

## [2026-06-03] - Remove Legacy /resume Command

### Removed
- **`/resume` deleted** (`examples/commands/resume.md` + `cowork-commands/resume.md`) and dropped from the onboard Phase 6E install lists. It drove the obsolete single global `~/.claude/handoff.md` pattern that `/pickup`'s legacy note warns against. Use `/handoff` + `/pickup` (named, per-project, multiple active handoffs) instead.

---

## [2026-06-03] - Handoff/Pickup Promoted to the Standard Command Set

### Changed
- **`/handoff` and `/pickup` moved from `examples/commands/` into the standard set `.claude/commands/`.** They are now core commands every user receives during setup (like `/onboard`, `/strategy`, `/learn`), not optional examples. One source of truth per command.
- **`/pickup` updated to the latest functionality**: explicit "Step 0: Resolve Which Handoff to Read" (lists actual handoffs and asks rather than silently falling back), a legacy-note guard against stale root `handoff.md` orphans hijacking a resume, and split Read / Freshness-check steps.
- **`onboard.md` Phase 6E**: handoff/pickup now install from `.claude/commands/` under an "Always copy these session-continuity skills (every user gets these)" block, with rationale on why they exist (context + task management, hand off / pick up conversations, persistent track record in the vault).
- **`cowork-commands/handoff.md` and `pickup.md`** synced to the new bodies (YAML frontmatter preserved).
- **README**: added a "Session Continuity (`/handoff` and `/pickup`)" key-concept section and listed both in the repository-structure tree under `.claude/commands/`.

### Removed
- `examples/commands/handoff.md` and `examples/commands/pickup.md` (moved to the standard set; no longer duplicated in examples).

---

## [2026-04-28] - Brainstorming Skill + Local Handoff Files

### Added
- **Brainstorming community skill** installed during onboarding via `npx skills add https://github.com/obra/superpowers --skill brainstorming`
- Added `/brainstorming` to the strategy skills walkthrough in `train.md`

### Changed
- **Handoff/Pickup now write to the current working directory** instead of global `~/.claude/handoff.md`. Each project gets its own `handoff.md`, so multiple projects can have independent active handoffs.

---

## [2026-04-24] - Handoff and Pickup Improvements
`d1b93a3`

### Changed
- Revised `examples/commands/handoff.md` for improved clarity

### Added
- New `examples/commands/pickup.md` skill for resuming work across sessions

---

## [2026-04-15] - License Change
`d30f875`

### Changed
- **License switched from MIT to CC BY-NC-ND 4.0** — the project is no longer permissively licensed; commercial use, modifications, and derivatives are restricted
- README updated to reflect the new license

---

## [2026-04-11] - Task Management Refactor
`713fbad`

### Added
- `examples/commands/handoff.md` — new skill for session handoff documentation
- `examples/commands/resume.md` — new skill for resuming previous sessions

### Changed
- Restructured task management documentation across `daily-workflow.md`, `vault-design-guide.md`, and template `CLAUDE.md`
- Simplified `eod-sync.md` and `eod-gather.md` example skills
- Minor fixes to `finish.md`, `onboard.md`, `optimize.md`, and `monthly-review.md`

---

## [2026-04-10] - Knowledge Graph in Vault Docs
`b457201`

### Changed
- Added knowledge graph integration guidance to `docs/vault-design-guide.md` and `templates/CLAUDE.md`

---

## [2026-04-08] - Knowledge Management Skills
`8f33a98` / `cc7e9fe`

### Added
- **Six new skills moved to `.claude/commands/`** (previously in `examples/`):
  - `build-skill.md` — turn a successful task into a repeatable workflow
  - `graph-daily.md` — incremental daily knowledge graph sync
  - `graph-sync.md` — full vault knowledge graph rebuild
  - `learn.md` — capture and integrate new knowledge
  - `optimize.md` — audit and improve existing setup
  - `strategy.md` — structured problem-solving with Integral methodology
- `templates/integral-methodology.md` — Integral methodology reference document
- Enhanced `onboard.md` and `train.md` with knowledge graph and skill creation sections

---

## [2026-03-31] - Vault Path Fix
`6638d87`

### Changed
- Minor fix to `onboard.md` for vault path determination logic

---

## [2026-03-27] - "Slash Commands" Renamed to "Skills"
`084a77b`

### Changed
- **Terminology change across the entire project**: all references to "slash commands" replaced with "skills"
- Affected 12 files including all setup skills, README, docs, and templates
- This was a deliberate naming decision to improve clarity for non-technical users

---

## [2026-03-24] - Daily Workflow and Permissions
`d81222d` / `ef1bb8b` / `6d619e6`

### Added
- New permissions added to `examples/settings.json`

### Changed
- Expanded `docs/daily-workflow.md` with task management guidance
- Improved `eod-gather.md`, `eod-sync.md`, and `eod-today.md` example skills
- Enhanced `connect.md` and `onboard.md` setup skills with better instructions
- Updated `docs/onboarding-guide.md` and `docs/vault-design-guide.md`
- Refined `templates/CLAUDE.md`

---

## [2026-03-23] - Setup Commands and Example Skills
`4976cf6` / `449e415`

### Added
- **Core setup skills**: `connect.md`, `finish.md`, `train.md` in `.claude/commands/`
- **Project-level `CLAUDE.md`** with bootstrap detection and setup instructions
- **Eight new example skills**:
  - `brain-dump.md`, `daily-note.md`, `eod-note.md`, `eod-sync.md`
  - `eod-time.md`, `eod-today.md`, `eod.md`, `monthly-review.md`
- `examples/scripts/md-to-gdoc.py` — Markdown-to-Google-Doc conversion script

### Changed
- Major rewrite of `onboard.md` with improved flow and file path handling
- Simplified and restructured all four docs files
- Updated `templates/.env.example` and `templates/CLAUDE.md`
- Consolidated `README.md` with clearer project overview

---

## [2026-03-20] - Onboarding Skill and Docs
`e906471`

### Added
- `.claude/commands/onboard.md` — the first setup skill (385 lines)
- `docs/onboarding-guide.md` — step-by-step onboarding reference

### Changed
- README rewritten with onboarding instructions and system overview
- Expanded `docs/integration-architecture.md` with additional integration details
- Refined `docs/vault-design-guide.md` structure
- Updated `.gitignore` and example settings files

---

## [2026-03-19] - Initial Release
`7479fd7`

### Added
- **Project scaffolding**: `.gitignore`, MIT `LICENSE`, `README.md`
- **Core documentation**:
  - `docs/daily-workflow.md` — daily usage patterns
  - `docs/integration-architecture.md` — system architecture reference
  - `docs/vault-design-guide.md` — Obsidian vault structure guide
- **Example skills**: `eod-gather.md`, `morning.md`
- **Example scripts**: `eod-cron.sh`, `eod-runner.sh`, LaunchAgent plist
- **Example settings**: `settings.json`, `settings.local.json`
- **Templates**: `.env.example`, `CLAUDE.md` template
