# Developing the ClaudeCodeSystem template

> ## THIS REPOSITORY IS PUBLIC AND SHIPS TO CLIENTS
>
> Everything committed here is world-readable and lands in client hands. Verify with
> `gh repo view IntegralOrg/ClaudeCodeSystem --json visibility` before doubting it.
>
> **Never write into this repo:** client names paired with their systems or security posture, PR
> numbers or their findings, vulnerabilities, credentials, plan or billing state, developer names,
> internal headcount or revenue plans, or any Integral internal process document.
>
> **Internal process and SOP work belongs in your internal process repository**, never here. This
> holds even if a handoff or a previous session names this repo as "the canonical home" for a
> document. A recorded decision is not evidence of visibility.
>
> `docs/superpowers/` is gitignored here as a backstop, because `brainstorming` and `writing-plans`
> write client-specific specs and plans into that path by default.
>
> Only generic, portable, client-facing methodology belongs in this repo.

The repo root is the vault a client receives via "Use this template": `CLAUDE.md`, `.claude/`, `scripts/`, `Templates/`, `Resources/` and the rest at the root are what a client's vault starts with. This file (`docs/DEVELOPING.md`) holds the maintainer notes and is not part of the client skeleton.

## Dual-Format Slash Commands (Code vs CoWork)

Slash commands exist in **two formats** to support both Claude Code and Claude CoWork:

| Format | Location | Frontmatter | How Users Get Them |
|--------|----------|-------------|-------------------|
| Claude Code | `.claude/commands/` | None needed | Auto-discovered by Claude Code; a client's vault is created from this repo, so it already has them |
| Claude CoWork | `cowork-commands/` | YAML `---` block with `name:` and `description:` | Manually uploaded by user through the **Customize** section in CoWork settings |

**Maintenance rule: when you create or modify a slash command, you MUST update both versions.** The CoWork version is identical to the Code version except for the YAML frontmatter block at the top of the file:

```yaml
---
name: command-name
description: One-line description of what the command does.
---
```

The `name` field should match the filename (without `.md`). The `description` should be a clear one-liner that helps the user understand when to use the command.

**Skills with scripts live in `.claude/skills/<name>/`** (a `SKILL.md` plus `scripts/` and `references/`). They have no CoWork mirror: their scripts run on the user's own machine, which CoWork and Claude Code on the web do not have. The folder ships with the template as is. Keep each one's upstream license file in its folder. A skill with no scripts (Vent) is the exception: it has no machine dependency, so it also gets a `cowork-commands/<name>.md` mirror (same body, `name:` and `description:` frontmatter), kept in step with the skill.

**`System/` holds the setup procedure and the guidance the agent answers from** (`Setup Procedure.md`, `How This Works.md`, `Connecting Tools.md`, `Routines.md`, `Adding Your Computer.md`, `Company GitHub Organization.md`, `Getting Help.md`, `Updating.md`), plus the routine definitions in `System/routines/`. It is maintained here, in the template, and ships to every new vault as is. A client's vault takes newer versions with `/update` (or the prompt in the README), which follows `System/Updating.md` from a fresh clone of the template and sorts files with `scripts/template-diff.py`. **When you remove or rename something a vault already has, or change a file the owner fills in (`CLAUDE.md`, `System/Routines.md`, `System/routines/*.md`), add a `### In an existing vault` list to the CHANGELOG entry:** it is the only instruction an update follows for those. Keep these files client-neutral: they are public and are shipped as the client's own instructions.

**There is exactly one folder of Code commands: `.claude/commands/`.** (The old `examples/commands/` folder was removed -- it created the illusion that some commands were optional examples, so some commands never reached users. All commands are first-class and shipped.)

**To add a new command:**
1. Create the Code version in `.claude/commands/`
2. Copy it to `cowork-commands/` and prepend the YAML frontmatter

That is it. **You do not need to register the command anywhere.** A client's vault is a repository created from this template, so every `.md` in `.claude/commands/` is already in it, and `cowork-commands/` comes along as upload-ready mirrors the user adds through Cowork's **Customize** section. Any command you add to those folders ships to every new vault automatically. There is deliberately no hand-maintained install list.

**To modify an existing command:**
1. Edit the Code version (the source of truth)
2. Copy the changes to the matching file in `cowork-commands/` (preserve the YAML frontmatter)

---

## Decision tiers

Who decides what in a client's system. The client-facing version is `System/Who Decides.md`; this section is the rule the builds cite. Two pieces implement it inside the nightly Vault Hygiene run: a tuning step (`/vault-audit` Step 5b, `scripts/self-tune.py`: reads the week's System Journal, applies Tier 1, reports Tier 2) and a system check (confirms the next night whether a fix held). Both ship: the system check runs as `/vault-audit` Step 0b (`scripts/system-check.py`) and the tuning step as Step 5b; a pattern that comes back after its 14-day cooldown is tuned again with its earlier fix in view. The intention: the owner of a vault is non-technical, so the system makes as many decisions as it can, routes what it must not decide to the people who maintain the template, and never routes anything to the owner as a decision.

- **The client is never the approver.** No approve/skip, no cards, no queue. At most one plain line in the daily note or at the end of a run ("Fixed: it kept forgetting your time zone").
- **Tier 1, the system decides and applies on its own:** rules in the vault's `CLAUDE.md`, memory files, wording in `.claude/commands/*.md` (and the `cowork-commands/` mirror), `System/` guide pages, and its own `_generated/Themes.md`. Every change is logged with its reason in `_generated/vault-hygiene/audit-log.md`, one undoable change each (the landing commit is the undo). Tier 1 is apply-and-log, never propose-and-wait: a proposal nobody applies is the failure mode, not an over-eager change. The next nightly run is what confirms a fix held; there is no Done button.
- **Tier 2, the system must not decide alone, and it goes to the template maintainers, never the client:** scripts, hooks, guard rules, credentials, routines, `.claude/settings.json`, `.mcp.json`, and anything that looks like a bug in the template. Packaged as names and counts only.
- **Tier 2 that is generic** (the same bug in every vault) is fixed once in the template and reaches every vault through `/update`. The maintainers fix the product; they never review one vault's system on a schedule.

**The Tier 2 package format** (nothing else, ever): routine name, error class, count, first and last date, file paths. Never note content, never anything from a session marked `"private": true` in the System Journal (skip those records entirely), never a value that looks like a key.

**The channel (decided 2026-10-13): a Markdown file the owner sends on.** Write the package into `Inbox/<date> report for your contact.md` through `scripts/setup/help_report.py` (it masks anything that looks like a key) and put one plain line in the daily note and in the run's closing summary telling the owner to reach out to their contact for support with that file. The owner knows who their contact is; the system never names an address, never emails anyone, and never calls a support service. Dedupe through `_generated/routine-alerts.json`, once per reason per 7 days, so the same problem is not written up every night. This works in every vault with no setup and no credential; `System/Getting Help.md` describes it to the owner.

**The surfacing rule:** every run that changes something ends with a numbered list of at most six plain lines saying what just happened. `/update` already does this; the nightly system check and the nightly tuning step do it for their runs.

---

## Developing THIS repo (maintainers, not vault users)

Everything above is for a maintainer changing this template. The engineering playbook (branching, review, the CodeRabbit loop) does **not** live in this repo: it is kept in one internal copy and linked from here by maintainers' own notes, so that copies never drift. Do not add a second copy of it here; vault-setup tooling is not where an engineering playbook belongs.

After editing a setup document, run `python3 scripts/setup/script-doc.py`; the test fails when `docs/setup-script.md` is stale.
