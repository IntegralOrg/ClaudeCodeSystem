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
> **Internal process and SOP work belongs in the Brain vault** (`Integral/SOPs/`), never here. This
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

**Skills with scripts live in `.claude/skills/<name>/`** (a `SKILL.md` plus `scripts/` and `references/`). They have no CoWork mirror: their scripts run on the user's own machine, which CoWork and Claude Code on the web do not have. The folder ships with the template as is. Keep each one's upstream license file in its folder.

**`System/` holds the setup procedure and the guidance the agent answers from** (`Setup Procedure.md`, `How This Works.md`, `Connecting Tools.md`, `Routines.md`, `Adding Your Computer.md`, `Getting Help.md`), plus the routine definitions in `System/routines/`. It is maintained here, in the template, and ships to every new vault as is. A client's copy does not update itself: a refresh mechanism (pulling newer `System/` files from the template into an existing vault) is a known gap, and for now a client asks the agent to fetch `System/` from the template. Keep these files client-neutral: they are public and are shipped as the client's own instructions.

**There is exactly one folder of Code commands: `.claude/commands/`.** (The old `examples/commands/` folder was removed -- it created the illusion that some commands were optional examples, so some commands never reached users. All commands are first-class and shipped.)

**To add a new command:**
1. Create the Code version in `.claude/commands/`
2. Copy it to `cowork-commands/` and prepend the YAML frontmatter

That is it. **You do not need to register the command anywhere.** A client's vault is a repository created from this template, so every `.md` in `.claude/commands/` is already in it, and `cowork-commands/` comes along as upload-ready mirrors the user adds through Cowork's **Customize** section. Any command you add to those folders ships to every new vault automatically. There is deliberately no hand-maintained install list.

**To modify an existing command:**
1. Edit the Code version (the source of truth)
2. Copy the changes to the matching file in `cowork-commands/` (preserve the YAML frontmatter)

---

## Developing THIS repo (maintainers, not vault users)

Everything above is for a maintainer changing this template. The engineering playbook (branching, review, the CodeRabbit loop) does **not** live in this repo: it is kept in one internal copy and linked from here by maintainers' own notes, so that copies never drift. Do not add a second copy of it here; vault-setup tooling is not where an engineering playbook belongs.
