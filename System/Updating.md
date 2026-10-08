---
type: reference
created: 2026-10-08
updated: 2026-10-08
---
# Updating

**What it is.** How this vault takes in a new version of the system from the template repository it was created from, without losing anything the owner has built.

**Our recommendation.** Take the update. Apply it in full, in one go, and report afterwards; do not stop to ask the owner which parts to take. The owner cannot judge a hook or a script change, and every update that is skipped makes the next one harder. The update is one commit, so it is easy to undo.

## The two rules

1. **Adopt by default.** A newer template file replaces the vault's copy. Hesitating is the failure mode here, not changing too much: "the vault's version is different" or "this might matter" is never a reason to skip.
2. **Never destroy the owner's work.** Notes, client files, daily notes, `_generated/`, the credentials file, anything the template never shipped, and every customization the owner made stay.

Keep the vault's version of a file over the template's only when you can name, in one line, one of these:

- **The vault is ahead:** it does something the template's version does not (a step, a check, an integration the owner added). Then merge: take the template's version and carry the owner's addition into it. Keep the vault's version whole only when the two cannot be combined.
- **It would break something the owner relies on:** a named routine, command, hook, or integration stops working. Then keep it and say what would break.

Anything else is adopted.

## Steps

1. **Get the template fresh.** Clone it into a new, empty folder outside the vault: `TPL="$(mktemp -d)/ccs-template" && git clone --quiet https://github.com/IntegralOrg/ClaudeCodeSystem "$TPL"` (on Windows, make a new empty folder under the temp directory and use its path as `TPL`). Never reuse a folder from an earlier run: a clone into a folder that already exists fails, and that is a local collision, not a GitHub problem. Use `$TPL` for every step below. Follow this file from that clone, not the vault's copy, which may be older.
2. **Read what changed.** In the clone's `CHANGELOG.md`, read every entry above the one whose `## [` heading matches the top entry of the vault's `CHANGELOG.md` (all of them if the vault has none or no heading matches). Note each `### In an existing vault` list; those are steps you do in step 4.
3. **Sort the files.** Run `python3 "$TPL/scripts/template-diff.py" --template "$TPL" --vault .` from the vault root. It lists each file in a group:
   - `add`, `take`, `retire`: apply as listed (copy in, replace, delete). No judgment needed; the owner never edited these.
   - `changed`: the owner edited a file the template also changed. Compare both against the two rules above. Usually that means taking the template's version and re-applying the owner's edit on top of it.
   - `retire-changed`: the template removed a file the owner edited. Delete it unless the vault is ahead or something relies on it; then keep it and say so.
   - `owned` (`CLAUDE.md`, `System/Routines.md`, `System/routines/*.md`, the local routines registry): the owner's files. Change them only where a CHANGELOG entry from step 2 says to, and keep everything else in them, including the owner's settings such as `timezone:` and `live_since:`.
   - Files the script does not list exist only in the vault: leave them.
4. **Do the CHANGELOG steps** from step 2, in order, oldest entry first. A step that deletes a file applies only to a file the sort put in `retire`; a file in `retire-changed` follows step 3's judgment, and anything the owner added to it is moved somewhere it still serves them before the file goes. A step that needs the owner (a connector, a key, a routine in their Claude account) goes in the report instead, as one plain sentence.
5. **Check.** Run `python3 -m compileall -q scripts` (silent means every script still parses) and confirm `.claude/settings.json` is valid JSON. A failure means a merge in step 3 broke a file; fix it. Then remove the clone (`rm -rf "$TPL"`).
6. **Save once.** Commit everything as one commit, `Update from the template (<date of the newest CHANGELOG entry>)`, and land it the way this vault always saves (see Git in `CLAUDE.md`).
7. **Report** in at most ten lines, in plain language: what is new for the owner (from the CHANGELOG), what was merged, what was kept and the one-line reason for each, and anything the owner has to do. Never list the files that were simply taken.

## What changes afterwards

The vault matches the template except where the report says otherwise, and its `CHANGELOG.md` top entry is the version it now has, which the next update starts from.
