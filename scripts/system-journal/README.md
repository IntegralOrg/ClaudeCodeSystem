# System Journal (capture)

Turn every Claude Code session into two durable records so a later review can spot what keeps
coming back across sessions, and so any claim can be checked against what was actually said.

- **Evidence record** (deterministic, kept forever): the user's words verbatim, the agent's
  visible words capped, the agent's actions (tool names and capped inputs, files touched),
  every tool error, and identity/timing. It is produced by code, not a model, so the same
  transcript always yields the same bytes.
- **Journal line** (one per session, distilled by a model from the evidence): what was asked,
  what happened, what failed, what the user complained about, what shipped, what was decided,
  what was left open, which systems it touched, and a first "why."

This template ships the **capture** half only. There is no reflection command and no Themes
writer yet; the audit tier is generated locally but is not shipped anywhere. `themes-inject.py`
is included but stays inert until a `_generated/Themes.md` exists (nothing here writes one).
Today every session is recorded and `/opportunity-scan` answers what change would have
prevented a bad session; automatic self-tuning from repeated friction is planned as a step
inside the nightly Vault Hygiene run.

## The read rule (entropy guard)

| Tier | Who reads it | Where |
|------|--------------|-------|
| Evidence (deterministic, per session) | A human or agent checking or re-deriving a line | `_generated/system-journal/evidence/<YYYY-MM>/<session_id>.json` |
| Journal (distilled, one line per session) | A review step, whole, never a working session | `_generated/system-journal/<YYYY-MM>.<host>.jsonl` (local) and `cloud/<date>.<sid8>.json` (containers) |
| Themes (capped render) | Every session at startup (once a reflection step writes it) | `_generated/Themes.md` |

A working session never loads the journal or the evidence at startup. When a session needs
history on a topic, it reads Themes (once that exists), then follows the session ids listed
there. This keeps the journal from becoming one more pile of context that may or may not get
considered.

## Storage decision

**Full transcripts are not stored anywhere.** Git history never shrinks, so a transcript
archive in the vault would bloat the repo within months. And a transcript is about 88% tool
output and attachments nobody re-reads; the user's words are roughly 5% and the agent's words
2%.

**The evidence record keeps that ~7% deterministically.** It is code, not a model: the same
transcript always yields the same bytes. A future, better distiller re-reads the same evidence
instead of re-summarizing a summary (no layering of model error over time), and every claim in
a journal line can be checked against the user's actual words. One file per session, sharded by
month, so git stores each once and a resumed session rewrites only its own file. In practice
the evidence files are small (single-digit KB median; tens of KB at p95).

**What is given up, plainly:** tool outputs. If a journal line says "the query returned zero
rows" and someone later doubts it, the evidence shows the query the agent ran and what it said
next, not the rows. Full transcripts remain on the producing machine only for Claude Code's own
retention window (30 days by default, `cleanupPeriodDays`), which is Claude Code's behavior, not
this tool's; in a cloud container there is no window at all (see Cloud).

## Pipeline

```
~/.claude/projects/*/<session>.jsonl              (Claude Code's own transcript; deleted by Claude Code
        |                                          after ~30 days locally, gone with the container in the cloud)
        |  extract.py   deterministic, no LLM, byte-stable; runs on Stop (live session, throttled 15 min),
        |               at SessionEnd (final), and on the 30-minute idle sweep
        v
_generated/system-journal/evidence/<YYYY-MM>/<sid>.json     (KEPT FOREVER; the only input to everything below)
        |  distill.py   `claude -p` (Sonnet by default), one JSON line per session, ~$0.09 each,
        |               only for FINAL sessions (ended or idle); never a live one
        v
_generated/system-journal/<YYYY-MM>.<host>.jsonl            (one line per session; replaced when the session grows)
```

**Triggers (local).** Three hooks in the USER-level `~/.claude/settings.json` (not the vault's
project settings, so they fire for every Claude Code session on this machine regardless of
directory, and never ship to cloud containers via the repo). `install.sh --write-hooks` writes
them:

- `Stop` -> `run.sh --stop-hook`: after every turn, throttled to once per 15 minutes per
  session, extracts the live session inline (a few hundred milliseconds, no model call). A
  crash, a closed laptop, or a week-long session never leaves the evidence more than 15 minutes
  stale. Never distills.
- `SessionEnd` -> `run.sh --hook`: reads the session id from the hook's stdin JSON *before*
  detaching (a backgrounded job loses stdin), then re-launches itself in the background to
  extract that session as FINAL and distill it. Every run also sweeps any session idle for 30+
  minutes that was never processed. Single-flight lock in `~/.system-journal/run.lock`.
- `SessionStart` -> `themes-inject.py`: the read side for non-vault directories. It injects any
  Themes whose `Projects:` line matches a path component of the session's cwd. Inert until a
  reflection step writes `_generated/Themes.md`; silent in the vault, in temp dirs, and on any
  error.

Temp-dir transcripts are never extracted or journaled. Every headless `claude -p` distill call
is itself a session and fires the hooks, so bursts of "skipped: another run holds the lock"
during a sweep are normal.

**State.** `~/.system-journal/state.json` (per machine) records, per session: transcript size
and mtime, the evidence path, `final` (ended or idle, so eligible to distill), `distilled`, the
journal path, and `distill_count`. Every writer merges its own session's keys under a file lock,
never writes a whole in-memory copy back, so two concurrent writers never clobber each other.

**Files.** Canonical source is this folder in the vault. Because a cloud-synced folder (iCloud
Drive, Dropbox) can block direct script execution on macOS, `install.sh` copies the scripts to
`~/scripts/system-journal/`. Re-run `install.sh` after any edit.

```
bash scripts/system-journal/install.sh --vault <path>          # first-time setup (records the vault)
bash scripts/system-journal/install.sh                         # after editing (re-copy)
bash ~/scripts/system-journal/run.sh                           # sweep now (extract idle sessions + distill pending)
bash ~/scripts/system-journal/run.sh --force                   # re-extract every transcript still on disk, KEEPS journal lines
bash ~/scripts/system-journal/run.sh --force --redistill       # re-extract AND re-distill everything (~$0.09 x sessions; ask first)
bash ~/scripts/system-journal/run.sh --redistill-session <sid> # one new journal line from the evidence file alone (no transcript needed)
python3 ~/scripts/system-journal/distill.py --dry-run | tail -1 # the pending COUNT; read it before any bulk operation
tail ~/.system-journal/run.log ~/.system-journal/errors.log
```

**Cost guard.** `state.json` is the only thing standing between a sweep and a paid re-distill of
every session. `--force` keeps journal lines unless `--redistill` is also passed; a live session
is never distilled (the Stop hook does not set `final`); and before any bulk operation the check
is the pending count from `distill.py --dry-run | tail -1`. Run that first, always.

**Fail loud.** A distill failure is logged to `~/.system-journal/errors.log` and the session
stays pending, so it is retried next run and never silently dropped.

## Configuration (portability)

The scripts carry no hardcoded owner identity; everything resolves at runtime.

- **Vault path.** `extract.py`, `distill.py`, and `themes-inject.py` resolve the vault in this
  order: (1) env `SYSTEM_JOURNAL_VAULT`; (2) `~/.system-journal/config.json` key `vault`
  (written by `install.sh --vault`); (3) a script-relative fallback (three levels up, i.e. the
  vault root when the scripts sit at `<vault>/scripts/system-journal/`). The installed copies
  under `~/scripts/system-journal/` are not inside the vault, so **run `install.sh --vault
  <path>` once** or export `SYSTEM_JOURNAL_VAULT`. `cloud-journal.sh` ignores all of this and
  uses the repo root it runs in.
- **Vocabulary.** The `systems` controlled list and the sensitivity rules live in
  `scripts/system-journal/vocab.json` (keys `systems`, `sensitive_tags`,
  `sensitive_path_prefixes`). `distill.py` loads it from `<vault>/scripts/system-journal/vocab.json`;
  when the file is absent it falls back to a built-in generic default (still routes personal
  lines out of the audit tier). Edit `vocab.json` to extend the vocabulary; no code change
  needed.
- **install.sh flags.**
  - `install.sh` (no flags): copy the scripts to `~/scripts/system-journal/` and print the hook
    lines.
  - `install.sh --vault <path>`: merge `{"vault": "<path>"}` into `~/.system-journal/config.json`
    (preserves any other keys).
  - `install.sh --write-hooks`: merge the three hooks into `~/.claude/settings.json`, only when
    an identical command is not already present; everything else in the file is preserved.
    `--settings <path>` targets a different file (for testing against a copy).
- **Distiller model.** `SYSTEM_JOURNAL_MODEL` overrides the default (`claude-sonnet-5`). Cost is
  roughly nine cents per session on Sonnet.
- **Cloud git identity.** `cloud-journal.sh` and `cloud-land.sh` commit as the env
  `SYSTEM_JOURNAL_GIT_NAME` / `SYSTEM_JOURNAL_GIT_EMAIL`, then the repo's existing git identity,
  then a neutral placeholder bot identity.

## Cloud (containers)

A cloud container has a transcript only while it lives. Containers are torn down on idle
timeout, SessionEnd does not fire on that teardown, and a resume gets a fresh container with the
same session id and the full history. So the cloud cannot be swept; it must capture while alive.
`cloud-journal.sh` runs as a repo-level `Stop` hook (`.claude/settings.json` in the repo, so it
ships to every container that clones it; hooks bypass the permission classifier and cannot stall
a run) and as `SessionEnd --final`:

- **Every Stop (60 s throttle):** extract the container's own session as FINAL into
  `_generated/system-journal/evidence/`, and land it on the repo's `main` from a throwaway
  worktree of `origin/main` (never the agent's branch). This write is the durable copy; a
  container that dies has lost at most one interval.
- **Every 15 minutes, and always on `--final`:** distill, writing
  `_generated/system-journal/cloud/<date>.<sid8>.json`, landed the same way.

A cloud-only person therefore needs only the hook block and the scripts in their repo plus push
access from their cloud environment, nothing on any machine. Sessions started outside a repo
that carries the hook block are not captured. Cloud files carry `project: "cloud:<repo dir>"`.

## Evidence record schema (`evidence/2`; `evidence/1` files are kept as written)

Deterministic; no extraction timestamp inside the file, so an unchanged transcript never dirties
git.

- Identity: `session_id`, `project`, `cwd`, `git_branch`, `title`, `started`, `ended`, `models`
  (model id -> assistant turns), `user_turns`, `assistant_turns`, `subagent_runs`,
  `slash_commands`, `tool_counts`, `tool_error_count`, `files_touched`, `pr_refs`.
- `turns[]`, in order, each with `i`, `t` (timestamp), `role`:
  - `user`: `text`, the user's words verbatim, capped at 8,000 chars with a `…[+N chars]` marker
    (`truncated: true`) only for pasted documents. System-injected turns (`<system-reminder>`,
    command output, task notifications) are dropped.
  - `assistant`: `text` (visible words, capped 1,000 chars per turn, no thinking), `tools[]`
    (`name`, `input` capped 200 chars: the command, file path, pattern, query or URL; `file` for
    edits and writes), `errors[]` (tool errors that came back, capped 400 chars each). No tool
    outputs.
  - evidence/2 (2026-10-07) adds to each `tools[]` entry: `ok` (the result came back; absent while a call is still pending), `ms` (assistant entry to result entry), and `error_class` on failure (`hook_blocked`, `permission_denied`, `exit_<n>`, `<Name>Error`, `HTTP <nnn>`, else `tool_error`; never the error text). `input` is passed through the guard hooks' secret masker. Per record: `tokens_by_model` (model id -> input / output / cache_read / cache_creation, summed once per model message).
- `final`: the last assistant message, capped 3,000 chars.

## Journal line schema

Deterministic (copied from the evidence): `session_id`, `project`, `started`, `ended`, `title`,
`user_turns`, `slash_commands`, `tool_error_count`, `files_touched`, `pr_refs`, `session_models`,
`evidence` (path of the record the line was distilled from). Distilled: `ask`, `outcome` (done |
partial | failed | abandoned | unknown), `outcome_note`, `failures[]`, `complaints[]` (the user's
words), `shipped[]`, `decisions[]`, `open_loop`, `systems[]` (**controlled vocabulary** from
`vocab.json`, plus `client:<slug>`; off-list tags move to `topics`), `topics[]` (free-form),
`why`. Plus `distilled_at` and `model` (the **distiller**, never the session's model, which is
`session_models`).

## Telemetry (`telemetry-stats.py`)

Aggregates the evidence files; no transcript, no network, same script in every vault built from the template. `python3 scripts/system-journal/telemetry-stats.py --since-days 7 --group-by tool|repo|session|model|day [--json]` or `--session <id>` for one session (errors, ten slowest calls, tokens). `evidence/1` calls count as `unknown`; a call whose result has not arrived is `pending` and excluded from the error rate. Growth is sized, not archived: git history keeps every blob, so the fields were kept to about 25 to 45 bytes per call and 200 bytes per session, and old files are never re-extracted. The extractor loads its secret masker from `scripts/hooks/log_tool_use.py` (the vault path first, then script-relative); when none loads, every stored tool input becomes `[input withheld: secret masker not found]` with one warning in `run.log`. Evidence bytes therefore depend on the masker version, which qualifies "deterministic": the same transcript plus the same masker gives the same bytes. `ms` runs from the tool call to its result and includes any time a human spent approving the call. Reader: `/opportunity-scan`.

## Audit tier

`distill.py` routes every line through `sensitivity()` after writing the private line. A line
whose `systems` tags or `files_touched` paths touch a sensitive area (from `vocab.json`) is
dropped whole from `_generated/system-journal/audit/<month>.<host>.audit.jsonl`; kept lines are
projected to work-only fields. Every decision, kept or dropped, is appended to
`audit/sanitization-log.jsonl`. In this template the audit tier is generated **locally only** and
is not shipped anywhere; a central store and a consent flow are not part of the template. Pass
`distill.py --no-audit` to skip it, or `--reaudit` to re-route existing lines without any model
calls.
