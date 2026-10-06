# ClaudeCodeSystem Setup Repo

> ## THIS REPOSITORY IS PUBLIC AND SHIPS TO CLIENTS
>
> Everything committed here is world-readable and lands in client hands. Verify with
> `gh repo view IntegralOrg/ClaudeCodeSystem-Cloud --json visibility` before doubting it.
>
> **Never write into this repo:** client names paired with their systems or security posture, PR
> numbers or their findings, vulnerabilities, credentials, plan or billing state, developer names,
> internal headcount or revenue plans, or any Integral internal process document.
>
> **Internal process and SOP work belongs in the Brain vault** (`Integral/SOPs/`), never here. This
> holds even if a handoff or a previous session names this repo as "the canonical home" for a
> document. A recorded decision is not evidence of visibility.
>
> `docs/superpowers/` is gitignored here as a backstop, because `brainstorming` and `writing-plans`
> write client-specific specs and plans into that path by default.
>
> Only generic, portable, client-facing methodology belongs in this repo.

This is the setup repository for the Claude Code Personal Assistant System. It is NOT a vault -- it contains the templates, examples, and setup commands used to build a vault.

## If the user opens Claude Code in this folder

Guide them to type `/onboard` to begin setup. The skills are in `.claude/commands/` and are ready to use.

## If this folder is nested inside an existing vault (bootstrap mode)

The user may have added this repo inside their existing vault. Detect this by checking:
1. Does a parent directory look like a vault (contains a `CLAUDE.md` with vault content, `Inbox/`, `Work/`, or similar vault files)?
2. Is this folder nested (e.g., `Brain/ClaudeCodeSystem-main/` or `Brain/ClaudeCodeSystem/`)?

If yes, **bootstrap automatically**:

1. Identify the vault root (the nearest parent that looks like a vault root).
2. Copy all files from this repo's `.claude/commands/` to the vault root's `.claude/commands/`:
   ```
   mkdir -p <vault_root>/.claude/commands/
   cp .claude/commands/*.md <vault_root>/.claude/commands/
   ```
3. Tell the user: "I found the setup files and copied the commands to your vault. You can now type `/onboard` to begin, or I can start it for you."
4. Offer to start `/onboard` immediately.

## If the user just says "set me up" or "help me get started"

Read `.claude/commands/onboard.md` from this repo and execute it directly. The user does not need to know about skills to get started.

## Dual-Format Slash Commands (Code vs CoWork)

Slash commands exist in **two formats** to support both Claude Code and Claude CoWork:

| Format | Location | Frontmatter | How Users Get Them |
|--------|----------|-------------|-------------------|
| Claude Code | `.claude/commands/` | None needed | Auto-discovered by Claude Code; copied to vault during `/onboard` Phase 6E |
| Claude CoWork | `cowork-commands/` | YAML `---` block with `name:` and `description:` | Manually uploaded by user through the **Customize** section in CoWork settings |

**Maintenance rule: when you create or modify a slash command, you MUST update both versions.** The CoWork version is identical to the Code version except for the YAML frontmatter block at the top of the file:

```yaml
---
name: command-name
description: One-line description of what the command does.
---
```

The `name` field should match the filename (without `.md`). The `description` should be a clear one-liner that helps the user understand when to use the command.

**Skills with scripts live in `.claude/skills/<name>/`** (a `SKILL.md` plus `scripts/` and `references/`). They have no CoWork mirror: their scripts run on the user's own machine, which CoWork and Claude Code on the web do not have. Onboarding Phase 6E copies the whole folder. Keep each one's upstream license file in its folder.

**There is exactly one folder of Code commands: `.claude/commands/`.** (The old `examples/commands/` folder was removed -- it created the illusion that some commands were optional examples, which is how they kept getting dropped during onboarding. All commands are first-class and shipped.)

**To add a new command:**
1. Create the Code version in `.claude/commands/`
2. Copy it to `cowork-commands/` and prepend the YAML frontmatter

That is it. **You do NOT need to register the command anywhere in `onboard.md`.** Phase 6E installs *every* `.md` from `.claude/commands/` with an unconditional glob copy (and copies all of `cowork-commands/` into the vault for users who also use Cowork -- those files are upload-ready mirrors the user adds through Cowork's **Customize** section). Any command you add to those folders ships to every user automatically. There is deliberately no hand-maintained install list, because that list is what kept dropping commands during onboarding.

**To modify an existing command:**
1. Edit the Code version (the source of truth)
2. Copy the changes to the matching file in `cowork-commands/` (preserve the YAML frontmatter)

## After setup is complete

This repo is no longer needed. Everything gets copied into the user's vault during `/onboard`. The `/finish` command offers to archive this folder.

---

## Developing THIS repo (Integral team, not vault users)

Everything above is for a user setting up their vault. If you are an Integral developer changing this repo, follow the **Integral development playbook**. It does **not** live here:

> **`How We Ship`** — Brain vault, `Work/Engineering/Developer Guide - How We Ship.md`,
> published company-wide to the **Integral Brain** shared drive under `Engineering/`.

That is the single copy for every Integral repo. Repos link to it and must not hold their own: it used to be duplicated around, the copies drifted, and the drift silently broke the CodeRabbit loop for months. This repo held one of those copies at `docs/guides/development-process.md` until 2026-08-05 — it is gone, because vault-setup tooling is not where an engineering playbook belongs.
