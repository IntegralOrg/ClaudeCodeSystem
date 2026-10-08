# Monthly Review

A full tune-up of the user's vault and agent. You audit, you **repair**, you rebuild the
knowledge graph, and only at the very end do you talk to the user.

**Run this on the last workday of each month.**

## How this command works

Phases 1 through 5 run **automatically with no questions asked**. Do not stop to ask
permission, do not present findings mid-run, do not say "would you like me to fix this?"
Fix it. The user's time is the scarcest resource in this process, and the vault is backed
up in git before anything destructive happens (Phase 0 guarantees this).

There are exactly **three** moments where you speak to the user, and no others:

1. **Phase 0**, once, and only when the vault is not already backed up: consent to make the
   backup.
2. **Phase 6**, the coaching conversation.
3. **Phase 7a**, approval of testimonial quotes before they are written down. Attributing a
   quote to a real client by name is not a vault edit and is never done unattended.

Phase 6 is the only phase that is interactive end to end.

**Assume the user is not technical.** They may not know what a "commit" is, what a
"knowledge graph" is, or why file size matters. Never use a technical term in output to the
user without a plain-language explanation beside it. Never show them a command and expect
them to understand it.

**The goal of this command is to make itself unnecessary.** A user who relies on the monthly
review to keep their vault healthy has a broken daily loop. Phase 6 exists to fix the daily
loop, not to schedule another cleanup.

**The vault is a Git repository.** Read a file, modify it, write it back with Edit or Write.

---

## Pre-Flight: Keys Check

Run `python3 scripts/check-keys.py --routine monthly-review`. Record the result (missing key names, or "none"). If the script exits 1, note it in the findings. If this run's keys check exits 0, then in `System/Routines.md`, under this routine's `## <title>` heading, if the first bullet reads `- live_since: not live` (or is missing), change that same bullet to `- live_since: <today's date>`; never add a second live_since bullet. Proceed to Phase 0.

---

## Phase 0: Safety Gate (BLOCKING)

**Nothing gets deleted, merged, or moved until the vault is confirmed saved to a remote
backup.** Run this check first, every time, with no exceptions.

### 0a: Check the backup state

Run these in order and record the result of each:

1. `git rev-parse --is-inside-work-tree` -- is this a git repository at all?
2. `git remote -v` -- is a remote backup configured?
3. `git branch --show-current` -- what branch are we on?
4. `git status --porcelain` -- is there unsaved work?
5. `git rev-parse --abbrev-ref --symbolic-full-name @{upstream}` -- which remote branch does
   this branch actually track? **Do not assume `origin/<branch>`.** A vault may track a
   different remote, and a branch with no upstream at all will make the next check fail.
   If this command errors, there is no upstream: go to **SAFE MODE**.
6. `git rev-list --count <upstream>..HEAD`, using the value from check 5 -- are there saved
   changes that have not been uploaded to the backup yet?

**If any of these commands errors, treat the result as "not backed up" and go to SAFE MODE.**
Never read a failed command as a zero. A zero means verified-safe, and only a command that
actually ran can mean that.

### 0b: Decide the mode

| What you found | What to do |
|---|---|
| Repo, remote configured, nothing unsaved, nothing un-uploaded | **FULL MODE.** Everything is backed up. Proceed to Phase 1. |
| Unsaved work or un-uploaded changes | Go to 0c. |
| No remote backup configured | **SAFE MODE.** Go to 0d. |
| Remote exists but the branch tracks no upstream (check 5 errored) | **SAFE MODE.** Go to 0d. Nothing can confirm the backup is current. |
| Any check errored for any other reason | **SAFE MODE.** Go to 0d. |
| Not a git repository | **SAFE MODE.** Go to 0d. |

### 0c: Offer to make the backup

Ask the user exactly once, in plain language. Do not explain git. Say something like:

> "Before I clean anything up, I want to save a backup of your vault so nothing can be
> lost. Want me to do that now? It takes a few seconds."

If they say yes:
1. `git add -A`
2. **Inspect what got staged before committing:** `git diff --cached --name-only`. If that
   list contains `.env`, anything ending in `.key` or `.pem`, anything named like
   `credentials` or `secrets`, or any other file that plausibly holds a password or API key,
   **unstage it** (`git restore --staged <file>`) and add it to `.gitignore` before
   continuing. This push uploads to a remote server, and **a secret pushed once must be
   treated as leaked even if it is deleted afterward.** The vault's
   `.gitignore` lists `.env` for exactly this reason, but never assume it is still intact.
3. `git commit -m "Backup before monthly review <today's date>"`
4. `git push`
5. **Re-run check 6 from Phase 0a.** A push can report success and still leave commits
   behind. If the count is not zero, the backup did NOT work. Drop to SAFE MODE and tell the
   user the backup failed, in plain language, without a wall of git output.

If they say no: drop to SAFE MODE.

### 0d: SAFE MODE rules

SAFE MODE is not an abort. The run continues and does almost everything.

**Still runs normally:** every audit, the CLAUDE.md size repair, adding missing information,
the graph rebuild, the personalization audit, and the coaching phase.

**Does not run:** deleting any file, merging two files into one, moving a file to a
different folder, removing a folder.

**This ban is global and applies to every phase, not just Phase 3.** It covers deleting an
unwanted skill in Phase 6d, archiving dead weight, pruning empty folders, and any other
destructive action anywhere in this command, **including actions the user explicitly approves
during Phase 6.** Approval is not a backup. If the user approves a deletion while in SAFE
MODE, record it in the pending list, tell them it will happen once the vault is backed up,
and do not perform it.

Everything that would have been destructive gets collected into a "Waiting on your backup"
list and shown in the Phase 7 report instead.

**Announce SAFE MODE at the start of the run, not just at the end.** One sentence:

> "Heads up: your vault isn't safely backed up right now, so I'm going to skip anything that
> deletes or moves files. I'll still do the rest, and I'll show you what I'd have cleaned up.
> We can sort out the backup at the end."

Word it that way rather than "isn't backed up anywhere," because SAFE MODE also triggers when
a remote exists but the backup was declined, failed, or could not be verified.

---

## Phase 1: Silent Audit (automatic, no output)

Gather everything before reporting anything. **Produce no user-facing output during this
phase.** Later phases consume this findings list.

### 1a: Integrations

For every integration CLAUDE.md claims exists:
- If it is an MCP connection, make one small call (list workspaces, list recent events) to
  confirm it actually responds.
- If it uses an API key, confirm the variable exists in `.env` and is not still a
  placeholder value (`your_...`, `xxx`, `changeme`, or empty).

Record drift in **both** directions: things CLAUDE.md claims but are dead, and things that
work but CLAUDE.md never mentions. The second kind is more common and more damaging, because
the agent does not know it has the tool.

### 1b: Scripts

Every script path CLAUDE.md references must exist on disk. Every script in `scripts/` should
be documented. Record both directions.

### 1c: Folder structure

`ls` the vault root, then one level into each documented subfolder. Compare against the
Folder Structure section of CLAUDE.md. Record folders documented but missing, and folders
present but undocumented.

### 1d: Skills

List every `.md` in `.claude/commands/`. Compare against skills CLAUDE.md references.
Record:
- **Phantom skills**: referenced in CLAUDE.md, missing from disk.
- **Orphan skills**: on disk, never mentioned anywhere the user would see them.

For each orphan, also check whether the user has ever actually run it (look for its output
artifacts, generated files, or log entries). An unused skill is a Phase 5 signal.

### 1e: Context size

Count characters in CLAUDE.md (`wc -c`) and lines in the memory file.

**Targets: CLAUDE.md between 25,000 and 30,000 characters. Memory index under 200 lines.**

Why this matters, in the user's language: CLAUDE.md is loaded into the agent's head at the
start of every single conversation. When it gets too long, the agent starts skimming it
instead of reading it, and follows instructions less reliably.

### 1f: Misplaced agent files

Search **outside** the vault for `memory.md`, a `CLAUDE.md`, or a memory folder that belongs
inside it. Check the home directory, the desktop, and the default agent config location.

This is a real and common failure: a user works with their agent daily for months while its
memory file sits somewhere they have never looked, so they cannot see, edit, or back up
anything the agent has learned. Record the exact path if found.

### 1g: Duplicates

Three passes, cheapest first.

**Exact duplicates.** Hash every markdown file in the vault:
```sh
find . -name "*.md" -not -path "./.git/*" -not -path "./.claude/*" -exec shasum -a 256 {} \;
```
Group by hash. Any group with more than one file is a set of true duplicates.

If `shasum` is unavailable on the user's platform, fall back to a **full byte-for-byte
comparison** (`cmp -s fileA fileB`). Never fall back to comparing file size plus the first N
characters: vault notes routinely share an identical frontmatter header and a similar length,
so a prefix comparison produces false matches, and a false match here **deletes a file the
user wanted to keep**.

**Near duplicates.** Same or nearly-same filename, or the same H1 title, in different
folders. Common causes: a file was copied instead of moved, or the same note was created
twice under slightly different names.

**Topical duplicates.** The same operational fact stated in three or more files. This is the
expensive pass and the one that matters most. Hashing cannot find it. Look for the same
tool, process, credential location, or rule explained repeatedly across CLAUDE.md, memory,
and reference files. This is exactly the drift that degrades an agent over time, because the
copies fall out of sync with each other and the agent gets contradictory instructions.

### 1h: Dead weight

- Files containing nothing beyond a template header.
- Files whose content refers to dates, projects, or engagements that have concluded.
- Empty folders.

### 1i: Frontmatter gaps

Files missing the YAML metadata block at the top. Prioritize the folders the user actually
navigates over deep archives.

---

## Phase 2: CLAUDE.md Repair (automatic)

### 2a: Size

Report the current character count against the 25,000 to 30,000 target.

**If over 30,000 characters:** find the largest sections that are *reference detail* rather
than *rules*. Move each one to a file under `Resources/Reference/` and replace it in
CLAUDE.md with a single pointer line. Re-count and record the before and after numbers.

**Never extract a guideline, rule, or preference.** Those only work when they are loaded
into every conversation. Only reference material moves out: tool usage instructions, API
endpoint lists, command flags, long examples, historical changelogs.

**If between 25,000 and 30,000:** do not extract anything. Note which sections are growing
fastest and name the extraction candidates for next month.

**If under 25,000:** say so and move on. A short CLAUDE.md is not a problem to solve.

### 2b: Accuracy

Apply every finding from 1a through 1d directly:
- Remove entries for tools and scripts that no longer exist.
- Add entries for tools that work but are undocumented.
- Correct the folder structure block to match reality.
- Remove references to phantom skills, and document orphan skills the user should know about.

---

## Phase 3: Duplicate and Structure Repair (automatic)

**Skip every action in this phase if in SAFE MODE.** Collect them into the pending list
instead.

### 3a: Resolve duplicates

For each group found in 1g:

**Byte-identical files:** keep the copy in the correct folder, delete the rest.

**Same topic, different content, and the two agree:** merge into one canonical file,
**preserving every unique fact from both versions**. Replace the other copies with a link to
the canonical file. Nothing is lost, which is what makes this safe to do without asking.

**Same topic, but the two contradict each other** (different values for the same setting,
different locations for the same file, incompatible steps for the same process): **do not
merge, and do not pick a winner.** Leave both files in place and carry the conflict into
Phase 6 for the user to resolve.

Merging contradictory statements would produce exactly the failure this pass exists to
prevent: an agent holding two incompatible instructions with no way to choose between them.
Say plainly which files disagree and what they disagree about. Resolving a contradiction
requires knowing which version is true, and only the user knows that.

**Stated in three or more files:** apply the same agreement test as above, across **every**
file in the group, before consolidating anything. If they all agree, consolidate into one
canonical home and leave pointers in the others.

**If any two of them contradict each other, defer the entire group to Phase 6.** Do not
consolidate the agreeing subset and leave the conflicting files behind: that buries the
disagreement inside a file the user now trusts as canonical, which is worse than leaving the
conflict visible where they can see it.

**Choosing the canonical location**, in priority order:
1. The folder the documented structure says it belongs in.
2. The copy with richer, more complete content.
3. The more recently modified copy.

### 3b: Fix structure

- Move misfiled files to the folder their type and content dictate.
- Move any misplaced agent file found in 1f **into** the vault. Tell the user in Phase 7
  where it was, where it went, and why it was invisible to them before.
- Archive files with history worth keeping. Delete genuinely empty ones.
- Remove empty folders.

---

## Phase 4: Rebuild the Knowledge Graph (automatic, every run)

Run the full `/graph-sync` process: frontmatter backfill, wiki-link pass, entity registry
rebuild, and Maps of Content refresh.

**This runs every time, not on request.**

**Run it after Phase 3, never before.** Syncing the graph first would index files that Phase
3 is about to merge or delete, and leave broken links pointing at them.

Record the result: files indexed, links added, entities registered, and **orphan count**
(files connected to nothing else).

Orphan count is the headline number. In the user's language: a vault where every note
connects to related notes is one the agent can actually navigate. A vault of disconnected
files is a pile, not a brain. Compare against last month's orphan count when a previous
review recorded one.

---

## Phase 5: Personalization Audit (automatic)

Phases 2 through 4 are generic hygiene. This phase asks a different question: **what would
make this vault better for this specific person?**

### 5a: Skill usage

For every skill on disk, determine whether this user has ever actually run it. Then diagnose:

- **Never run, but the work still happens manually** (you can see evidence of the task being
  done by hand in notes, daily entries, or task history): the skill is **undiscovered**.
  This is a teaching problem. Carry it into Phase 6 and show them.
- **Never run, and the work never happens at all**: the skill is **unwanted**. Offer to
  delete it in Phase 6. Do not delete it automatically.

Do not skip this for the monthly review command itself. If the user is running this for the
first time after many months, that is the single most important finding of the run.

### 5b: Folder gravity

Which folders grow, and which have not been touched in months? A folder that is documented
in CLAUDE.md but never used is pure overhead: it costs the agent context on every
conversation and returns nothing.

### 5c: Repeated manual work

Scan notes, daily entries, and task history for the same activity recurring with no skill
behind it. Every hit is a candidate for a new slash command. This is the highest-value
output of the entire run.

### 5d: Structure fit

Does the documented folder structure match how this user actually files things? **When it
does not, the structure is wrong, not the user.** Correct the documentation to match real
behavior rather than trying to correct the human.

### 5e: Routine gaps

Which recurring routines exist as skills but are not scheduled to run automatically?

### 5f: Apply the obvious ones

Fix anything unambiguously an improvement: delete the documented-but-dead folder reference,
correct the structure block, document the undocumented working tool. Carry every judgment
call into Phase 6.

---

## Phase 6: Coaching (the only interactive phase)

Written for a non-technical reader. Plain language throughout. State the purpose out loud:

> "The point of all this is that next month's review should find nothing. Here's what drifted
> and how to stop it."

### 6a: Root-cause the drift

Name the **behavior**, not the symptom.

Weak: "CLAUDE.md was too big."
Strong: "Your instructions file grew by about 6,000 characters this month. Every client call
added a new guideline and nothing ever removed one. That's why your agent started missing
things you'd told it."

Weak: "You had 14 duplicate files."
Strong: "You've been asking your agent to write notes without telling it where to put them,
so it creates a new file each time instead of adding to the one that already exists."

### 6b: Two questions

Ask these **now**, after showing findings, not at the start of the run. Answered cold they
produce shrugs. Answered after seeing real findings they produce specifics.

1. "Given what I just found, what felt clunkiest this month?"
2. "What do you wish your agent could do that it can't do today?"

Use AskUserQuestion. One at a time.

### 6c: Teach two or three habits

Only habits that would have prevented **this month's specific drift**. Concrete and small.

Good: "When you add a new guideline, delete one that's no longer true."
Good: "When you ask me to write something down, tell me which client it belongs to."
Bad: "Maintain good documentation hygiene."

Show, do not just tell. If the habit involves a command, run it once with them.

### 6d: Close the loop

Offer each of these, and perform the ones they approve **during this run**:

1. **Schedule the routines** that would have prevented the drift, including this review. A
   monthly review that depends on the user remembering to run it will not get run. This is
   the single most important offer in the phase.
2. **Build a slash command** for the repeated manual work found in 5c, right now, while they
   are watching.
3. **Teach the undiscovered skills** from 5a and delete the unwanted ones. **Deletion is a
   destructive action: in SAFE MODE, add it to the pending list instead of performing it,
   even though the user just approved it** (see Phase 0d).
4. **Route their answers** from 6b: new preferences into the Assistant Guidelines section of
   CLAUDE.md, tool and automation ideas into `Resources/Reference/System Improvements.md`.

---

## Phase 7: The Report

### 7a: Testimonial scan

Run this quietly before reporting. Find the last scan date, then search connected messaging
workspaces and vault transcripts since that date for positive client feedback ("thank",
"great job", "love", "amazing", "impressed", "saved us", "game changer"). Filter to clients,
not internal team.

**Present findings for approval before writing any of them down.** This is the third and last
interaction point (see the top of this file). Attributing a quote to a named client is not a
vault edit and must never happen unattended.

**Capture the minimum.** Record the quote itself, who said it, the date, and where it came
from. Do not copy the surrounding conversation into the vault. **Skip any quote whose meaning
depends on confidential context** (pricing, contract terms, staffing complaints, anything
about a third party), because such a quote cannot be used without leaking that context along
with it.

Append approved quotes to `[YourCompany]/Testimonials.md` with the quote, name, date, and
source. Update the scan date.

**Approval here means "record it internally." It does not mean the client has agreed to be
quoted publicly.** Say so when presenting the findings: using any of these externally, in
marketing or on a website, is a separate decision that may require asking the client.

### 7b: The receipt

Show every change made, grouped by phase, with real numbers:

- CLAUDE.md: characters before and after
- Files: total before and after
- Duplicates resolved
- Files moved or archived
- Graph: orphan count, and the change from last month
- Integrations and scripts corrected

If the run was in SAFE MODE, list the "Waiting on your backup" items separately and offer to
set up a backup now.

### 7c: Wrap up

1. Update the "Last Monthly Review" date in CLAUDE.md to today.
2. Log the run in `CHANGELOG.md`.
3. Write the findings and the coaching note to `Work/Monthly/YYYY-MM-DD Monthly Review.md` (today's full date). Vault health checks read that file to see that this review ran.
4. Close with the one number that matters:

> "Your vault is more connected than it was last month: 12 orphaned notes, down from 47."

And the one thing you want them to remember:

> "If you do nothing else this month, do [the single habit from 6c]. That's what caused most
> of what I just cleaned up."
