---
name: handoff
description: Save current work state to a named file for a new session to resume later.
---

# Handoff

Hand off the current conversation to a fresh Claude Code session (new window, post-clear, after context compaction, or a brand-new cloud session). Writes a self-contained briefing to `.handoffs/<name>.md` that a new agent can read cold and continue the work without losing momentum.

**Cloud rule: a handoff that is not pushed does not exist.** Each cloud session runs in a temporary workspace that starts from a fresh clone of the vault repository. The next session can only read this handoff if it was committed and pushed (Step 3.5). The same goes for any other unsaved work sitting in the workspace.

**Required argument:** a short name for the handoff (e.g., `/handoff trussi-workflow-fix`). This becomes the filename. Use kebab-case or short descriptive words. Spaces are converted to hyphens automatically.

**If no name is provided, stop and ask for one.** Do not infer a name or proceed without one. The name is how the user finds this handoff later across multiple projects.

Name: $ARGUMENTS

---

## Principles

The handoff file is written **to the next Claude**, not to the user. It should read like a briefing for a smart colleague who just walked in: they haven't seen this conversation, don't know what's been tried, don't know why this matters. Be specific. Include file paths with line numbers, exact commands, and the reasoning behind decisions, not just the decisions themselves.

**Never delegate understanding.** Don't write "figure out what needs to happen next." Write what specifically needs to happen next, with enough context that the next agent can make judgment calls.

---

## Step 0: Validate the Name

Check that `$ARGUMENTS` is not empty.

- **If empty:** Tell the user: `Please provide a name for this handoff. Example: /handoff trussi-workflow-fix` and stop. Do not proceed.
- **If provided:** Sanitize the name: lowercase, replace spaces with hyphens, strip special characters except hyphens and underscores. This becomes `HANDOFF_NAME`.

Set the handoff path: `.handoffs/HANDOFF_NAME.md` (relative to the current working directory).

Create the `.handoffs/` directory if it does not exist.

**If a file with that name already exists**, tell the user and ask:

AskUserQuestion: "A handoff named '[HANDOFF_NAME]' already exists (written [date from file]). What should I do?"
Options:
- Overwrite it with a fresh handoff
- Pick a different name
- Read the existing one instead (run /pickup)

---

## Step 1: Synthesize Current State

Before writing anything, silently review the conversation and answer these questions for yourself:

1. **What is the goal?** One sentence. What is the user actually trying to accomplish? Not the immediate task, the underlying objective.
2. **What have we done so far?** Concrete actions: files edited, commands run, things discovered, decisions made. Include file paths and line numbers where relevant.
3. **What was tried and rejected?** Dead ends the next agent should not re-explore. Include *why* each was rejected.
4. **What is the current state of the work?** Is code half-written? Are there uncommitted changes? Is something running in the background? Are there open questions waiting on the user?
5. **What are the next concrete steps?** Not "continue the work," the actual next 1-3 actions. If blocked, what is it blocked on?
6. **What context does the next agent need to pull?** Specific files to read, memory entries to check, git state to inspect, external systems to query. Give exact paths and commands.
7. **What gotchas or constraints apply?** Decisions the user made, approaches they rejected, things that look simple but aren't, things already verified so they don't need re-verifying.

If any of these are unclear, **ask the user before writing the handoff**. A vague handoff is worse than no handoff; it wastes the next session's context budget on re-discovery.

## Step 2: Verify Current Environment State

Run these in parallel and include relevant output in the handoff:

- `date` -- timestamp the handoff
- `pwd` -- capture the current working directory so the next session knows where to operate
- `git status` and `git log --oneline -5` -- if relevant files are in a git repo, capture uncommitted state and recent commits
- Check for any running background processes (builds, dev servers, long-running tasks). A new session does NOT inherit them -- the workspace is torn down between sessions -- so record what was running and how to restart it, not just that it exists
- If work touches a specific file, note its current length and any in-progress edits

## Step 3: Write the Handoff File

Write to `.handoffs/HANDOFF_NAME.md` in the current working directory. Use this structure:

```markdown
# Handoff -- [Topic] -- [YYYY-MM-DD HH:MM ET]

> **For the next Claude reading this:** The user cleared context, opened a new window, or started a new cloud session. You are continuing work mid-stream. Read this entire file before taking any action. Then pull the context listed in "Load This Context" before responding. Do not ask the user to re-explain what is already documented here.

**Working directory:** `[cwd from pwd]`
**Project context:** [e.g., "Brain vault", "DevProjects/agent-browser", "none"]

## The Goal

[One or two sentences. Why this work matters, what success looks like.]

## Where We Are Right Now

[Concrete state: what's been done, what's in-progress, what's blocked. File paths and line numbers. If code is half-written, say exactly where. If something is running in the background, say so. If waiting on the user to decide something, say what.]

## What Has Been Tried (and Rejected)

[Dead ends with reasons. "Tried X, didn't work because Y." "Considered Z, rejected because user wants W." Skip this section if nothing was rejected.]

## Decisions Made This Session

[Non-obvious choices the user approved. Things the next agent should NOT re-litigate. Include the why.]

## Next Steps

1. [First concrete action]
2. [Second concrete action]
3. [Third concrete action, or "then check in with the user before proceeding"]

## Load This Context Before Responding

Run these reads/commands in parallel at the start of your response, before saying anything:

- Read: `[path]` -- [why: what you'll learn from it]
- Read: `[path]:[lineStart]-[lineEnd]` -- [why]
- Bash: `git status` in `[dir]` -- [why]
- Bash: `[any other command]` -- [why]
- Check memory: `[memory filename]` -- [why]

[Only list context actually needed. Don't pad. The next agent has a fresh context budget; spend it on what matters.]

## Gotchas and Constraints

- [Things that look simple but aren't]
- [Things already verified so you don't need to re-verify]
- [User's preferences specific to this work]
- [External state that might change (someone else editing a file, a cron about to fire, etc.)]

## Open Questions

[If there are questions waiting on the user that blocked progress, list them here so the next session can raise them immediately. If none, omit this section.]

---

*Handoff written [timestamp]. Session topic: [topic]. If this file is older than a few hours when you read it, verify it's still current before acting on it; state may have changed.*
```

## Step 3.5: Persist the Handoff (required)

The handoff must reach the vault's Git remote, or the next session will never see it:

1. `git add .handoffs/HANDOFF_NAME.md`
2. `git commit -m "Handoff: HANDOFF_NAME"`
3. `git push` -- if the push is rejected because the remote moved, run `git pull --rebase`, then push again

Then check `git status` for **other** uncommitted changes. If there are any, tell the user plainly: uncommitted work will not survive this session. Offer to commit and push it too. Finished work belongs in the same push; half-done changes the user does not want on the main branch can go on a WIP branch (`git checkout -b wip/HANDOFF_NAME`, commit, `git push -u origin wip/HANDOFF_NAME`) -- and record that branch name in the handoff's "Where We Are Right Now" section. Do not silently leave unpushed changes behind.

If the push fails after a retry, say so explicitly: the handoff exists only in this temporary workspace until a push succeeds.

## Step 4: Confirm With the User

After writing and pushing the file, show a compact summary. **The last thing in your reply is always the exact resume command, on its own, in a fenced code block, with the real name filled in**, so the user can copy it straight into the next session instead of typing it:

```text
Handoff saved and pushed: .handoffs/HANDOFF_NAME.md

  Goal: [one line]
  Next steps: [1-line summary of first next action]
  Context to pull: [count] files, [count] commands
```

Then end the reply with exactly this block (substitute the real name, never the placeholder):

```
/pickup HANDOFF_NAME
```

Rules for the resume command:
- It is the final line of the reply, after any other text (including warnings, a failed-push notice, or open questions you raise). Nothing follows it.
- Use the sanitized `HANDOFF_NAME` exactly as saved, so it matches the filename.
- If you edit or re-save the handoff later in the same conversation, output the command again at the end of that reply too.

Do not dump the full file content into the chat. The user can read it if they want to verify. The point is the file exists and is ready for the next session.

---

## Notes on Using This

- **When to run**: Before `/clear`, before ending a cloud session mid-task, before closing a window, or when context is getting long and you want a checkpoint before compaction.
- **Named and persistent**: Each handoff gets its own file in `.handoffs/`. You can have many active handoffs across different workstreams. Old handoffs stick around until manually deleted.
- **Not a replacement for EOD**: This is for mid-stream work handoffs, not end-of-day wrap-ups. Your `/eod` still routes items to your task inboxes and builds tomorrow's plan.
- **Not a replacement for tasks**: Ongoing project state belongs in your task manager or client inbox files. Handoff is for the immediate thread of work the current session is in the middle of.
- **Cleanup**: Periodically review `.handoffs/` and delete stale handoffs that are no longer relevant.
