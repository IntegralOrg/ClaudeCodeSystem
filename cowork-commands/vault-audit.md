---
name: vault-audit
description: Nightly self-healing vault hygiene -- fixes misfiled files, backfills frontmatter, self-amends its own schema, embeds docs to detect same-subject forks, and proposes merges to a human review queue. Never asks for approval mid-run.
---

# Vault Audit: Daily Self-Healing Hygiene

Keeps the vault matching its own design contract (`_generated/vault-hygiene/vault-schema.md`) and keeps the canonical/superseded convention honest. Fully autonomous: it fixes what it finds, stages removals into `_generated/vault-hygiene/audit-trash/` (never deletes), proposes same-subject merges to a human review queue (never merges on its own judgment), and never asks for approval mid-run.

**Why this exists:** vaults drift. Files land in the wrong folder, near-duplicate notes pile up, frontmatter goes missing, half-written stubs sit untouched for weeks, and two documents about the same thing quietly fork so a search returns the stale one. A monthly cleanup only catches this after months of decay have already made the vault harder to search and the agent's answers less reliable. This command catches the same drift every night, in minutes, by splitting the work two ways: a small deterministic script handles structure (walking the tree, hashing files, staging removals, embedding docs, generating candidate pairs, the invariant check) and Claude handles judgment (does this file's content match its folder, are these two files versions of one document, is the schema itself wrong). Neither one is safe alone: the script has no idea what a file means, and free-form judgment without a script drifts just as fast as the vault it's supposed to fix.

Modes:
- **Default (nightly)**: the steps below. Run standalone anytime, or as EOD Phase 5.5.
- **`init`**: one-time bootstrap for a vault with no schema/index yet. See the Init section.

Hard rules:
- Never touch anything under a `protected` path or a non-markdown file.
- Never `rm` a vault file: removals go through the `stage` subcommand.
- Records (files under `no_merge` folders) are never merged, split, or have their body rewritten. A pair with a record on either side is never folded: it downgrades to a label-only supersession (confirm-keep), which may add a `canonical`/`superseded_by` marker to the record's frontmatter but never touches its body.
- Only Step 4b item 5 (`apply`) ever folds, merges, or stamps canonical/superseded markers on an authored doc, and only on a block a human has decided. (Step 2's deterministic fixes -- refiling, frontmatter backfill, stub expansion, link repointing -- also edit the vault, exactly as the structural audit always has.) The embedding subcommands other than `apply` write only under `_generated/vault-hygiene/`.
- **Invariant violations fail loud, never auto-fix.** A contradictory canonical/superseded marker is reported and counted, not silently repaired.
- This command never runs git itself. In vaults using the EOD pipeline, `/eod` makes a pre-audit checkpoint commit right before invoking this command (see its Phase 5.5), so every edit this run makes to the live vault is trivially revertible. If you're running this standalone outside `/eod`, commit your own checkpoint first.
- **The trash purge is the one exception to that revertibility.** `scan` permanently deletes `_generated/vault-hygiene/audit-trash/` day-folders older than 7 days (files staged by EARLIER runs, which no pre-audit checkpoint of the current run can restore). Recovery window: a staged file sits under `_generated/vault-hygiene/audit-trash/YYYY-MM-DD/` for 7 days and can be restored by moving it back out; after purge it is gone (vaults that commit `_generated/` can still recover it from git history). Every purge is recorded in the receipt (Step 6 `trash_purged`).

**Why these files live in `_generated/vault-hygiene/` and not `.claude/`:** on Claude Code on the web, `acceptEdits` auto-approves Edit/Write everywhere in the working dir EXCEPT under `.claude/` (that dir holds settings/hooks/commands, which can escalate the session, so every write there prompts even in the cloud). A scheduled cloud routine that writes its schema/index/log under `.claude/` stalls on a permission prompt every run. `_generated/vault-hygiene/` is both audit-protected (never swept) and auto-approved, so writes flow silently. Do not move these files into `.claude/`.

## Setup

0. If `scripts/vault-audit.py` or `scripts/vault-embed.py` is missing in this vault, stop and tell the user: this vault is the repository they created from the template, and both scripts ship with it, so something removed them (restoring them from the template repository fixes it). They live side by side; `vault-embed.py` imports `vault-audit.py`.
1. `date` for today (`TODAY`).
2. `VAULT` = vault root (directory containing CLAUDE.md). `AUDIT="python3 \"$VAULT/scripts/vault-audit.py\""`, `EMBED="python3 \"$VAULT/scripts/vault-embed.py\""`.
3. If `_generated/vault-hygiene/vault-schema.md` is missing, stop and run Init instead.

## Step 1: Script pass

Run `scan --vault "$VAULT"` and read the JSON work order. It already purged old trash and refreshed the index (added/changed files are marked stale). The order also carries two fail-loud signals:
- `invariant_violations`: canonical/superseded markers that contradict each other (a dangling or chained `superseded_by`, a doc that is both canonical and superseded, a confirmed cluster with more than one canonical). **Never auto-fix these.** Report them in the receipt and stop stamping if any appear; they mean a prior decision is now inconsistent.
- `stale_canonical`: docs stamped `canonical: true` whose content hash has not changed in the staleness window (default 180 days; report-only, see Step 4b item 6).

## Step 2: Deterministic fixes

Work the order. A move or rename ALWAYS requires checking inbound links via the `links` subcommand, never just when the basename changes: many vaults use path-qualified wiki-links (`[[Resources/Reference/Server Logins]]`, `[[Reference/Server Logins]]`), and any of those forms breaks when the file's path changes even if the basename stays the same. `links` matches both the bare basename and any path-qualified suffix ending at the stem, so it will surface these. Repoint any link whose target no longer resolves, fixing both the basename and the path portion of the link as needed (edit each `[[Old Path/Old Name]]` or `[[Old Name]]` to the file's new location).

**If you rename or move a file or folder that the embedding layer tracks** (anything in the index, not a record), re-key the loop state so nothing re-embeds or re-judges: `$EMBED migrate --vault "$VAULT" --rename "<old rel>" "<new rel>"` (do the `mv` first, then migrate; `--dry-run` reports the re-key counts). It re-keys the index rows, the vector cache, the judgment cache (and the pair id derived from the paths, keeping `renamed_from_pair_id`), the watched clusters, and the golden set.

Collision rule for EVERY `mv` (moves from `root_clutter`/`unknown_folder`/`belongs:` verdicts, renames from `naming_violations`): check whether the destination path already exists before moving, and never overwrite an existing note with a bare `mv`. If the destination file is byte-identical to the incoming one, handle the pair under the `exact_duplicates` rule instead; if it differs, keep both by moving the incoming file under a distinguishing name (e.g. `Name (from Notes).md`), note the collision for Step 5, and let Step 4/4b's merge bar decide whether they become one file.

- `root_clutter` and `unknown_folder`: read the file (skim is fine), pick the destination from the schema's folder purposes, `mkdir -p` if needed, `mv` it. If no folder fits, the closest general-purpose folder wins (e.g., `Resources/Reference/`); note the mismatch for Step 5.
- `exact_duplicates`: keep the copy whose folder the schema endorses (tie-break: most recently modified); `stage` the rest. When both copies sit in the SAME folder, mtime lies (the stray copy is usually newer): keep the one whose name the index or inbound links already know, falling back to git creation date. Repoint links from staged copies to the keeper. The script already excludes `no_merge` records from duplicate candidates (a record is never staged, merged, or repointed), so nothing under a `no_merge` folder appears here.
- `empty_stubs`: read each before acting. `stage` only the genuinely contentless (template header only, no information). A tiny body that carries real information (an ID, a number, a link) is content, not a stub: keep the file and expand it minimally (frontmatter plus a one-line context sentence) so it stops flagging. The script already excludes `no_merge` records from this list.
- `missing_frontmatter`: add minimal frontmatter (`type` per the folder's content, `created` from the file's git or mtime date). Follow CLAUDE.md's frontmatter schema if one is documented; otherwise use `type`/`created` at minimum. The script already excludes `no_merge` records from this list.
- `naming_violations`: rename to satisfy the pattern (derive the date from frontmatter/content), repoint links.

## Step 3: Semantic re-index

For each rel path in `stale`:
- If it falls under a `no_merge_paths` pattern: derive the row from path + filename + first 20 lines only (records are indexed for navigation, not merging).
- Otherwise read the file and write a row: `concept` = one line, `<entity>: <what this file is>`, max 120 chars; `entities` = the people/companies/projects it is about; `verdict` = `ok`, or `belongs:<folder>` when the CONTENT says it lives elsewhere even though the folder is schema-legal.

Batch the writes: build a JSON array `[{"file":..., "concept":..., "entities":[...], "verdict":"ok"}, ...]` in a scratch file and run `bulk-update --json <file>` (use `update-row` for one-offs). Then act on any `belongs:` verdicts as moves (Step 2 rules). Ordering rule whenever YOU edit a file's content: run `scan` first (so the index picks up the new hash), THEN `update-row`; the reverse order leaves a stale hash that re-flags the file next run.

## Step 4: Fragmentation sweep (feeder only; never merges)

Read a concepts-only projection of `_generated/vault-hygiene/vault-index.json` (path, concept, entities, verdict per row), e.g. via a python one-liner, rather than the raw JSON. Also re-examine every `watched_clusters` entry.

Find clusters: 2+ non-record files whose concepts describe the same thing about the same entity. For each cluster that clears the bar (same concept AND same entity AND same purpose), run `$AUDIT watch --vault "$VAULT" <file> <file> ...`. That is the whole action. This step never merges, stages, or repoints on its own judgment: measured merge precision on a bad guess is roughly one in three, and a wrong merge hides a document from retrieval. Step 4b turns every watched cluster into candidate pairs that bypass the similarity gate, the comparator judges them, survivorship picks a winner, and the proposal lands in the review queue for a human decision. Exact byte duplicates are Step 2's job and stay autonomous. A watched cluster that a later night no longer sees as a cluster is left alone (the script drops clusters whose files disappear). Report `watched: N clusters (M new this run)` in the receipt; `merged:` is always `none` here.

## Step 4b: Canonical judgment (semantic layer; only item 5 modifies a doc, and only on a decided block)

Runs every night. `$EMBED` is stdlib-only for every subcommand except `report` (which needs the embedder).

0. `$EMBED report --vault "$VAULT" --install`. Embeds changed in-scope docs (local, in-process `bge-small` embeddings: no data leaves the machine except a one-time model-weights download; hash-gated, so a full vault is about a minute and a normal night is seconds) and rewrites `canonical-candidates.json` + `embed-candidate-report.md`. `--install` pip-installs `fastembed` + `numpy` at run start when they are missing (on the web runner: ~10 s, no setup step needed). If the install or import fails (e.g. a local machine whose `python3` has no onnxruntime wheels), the command logs `embedding: skipped`, leaves the previous candidate list untouched, exits 0, and this step continues with whatever candidates already exist. Never let this step break the run; a skip is logged in the receipt as `candidates: (embedding skipped)`. Locally, a real embed run is `uv run --python 3.12 --with fastembed,numpy "$VAULT/scripts/vault-embed.py" report --vault "$VAULT"`.

1. `$EMBED pending --vault "$VAULT" --limit 25 --with-text --max-chars 6000`. The JSON lists unjudged candidate pairs with both docs' text (`meta.pending` is the backlog; 25 per night bounds the cost). Pairs already judged are never re-emitted unless a doc's content hash changed.
2. For each pair, read both texts and classify on one dimension (the escape hatch is `distinct-purpose`):
   - `version-fork`: the two docs are versions of the same document (one evolved from the other, or both from a common ancestor); a reader should only ever land on one of them.
   - `duplicate`: same content and same purpose, both current (a copy/paste, an export, the same doc filed twice).
   - `distinct-purpose`: they legitimately coexist (different audience, different stage of one pipeline, a record of an event vs a living doc, a person profile vs a sales-lead note, a talk track vs a plan, two sessions of one series). **When unsure, answer `distinct-purpose`**: a wrong fork/duplicate call is the costly error (it can hide a doc from retrieval later); a missed one just resurfaces.
   - A "Supersedes:" line, a "canonical version" line naming the other doc, or a "consolidated rewrite of" note is strong fork evidence. A draft or `_Originals/` path is NOT by itself: a pre-cleanup source with the same skeleton as the living doc is a fork; a raw scribble or meeting fragment whose facts were folded into a living doc is a record (distinct-purpose). Sharing a client, a template, or a topic is not fork evidence.
   - `confidence` in [0, 1]. `reason`: one line, no em dashes, naming the concrete tell.
3. Write `[{"pair_id": ..., "verdict": ..., "confidence": ..., "reason": ...}, ...]` to a scratch file with the Write tool (never a shell heredoc: the cloud runner stalls on it), then `$EMBED judge --vault "$VAULT" --json <scratch> --model <the model id running this session>`. Exit 2 means a verdict was rejected (`unknown_pair`, `bad_verdict`, `bad_confidence`, `missing_reason`, `confirmed_locked`): fix and re-submit only those. Verdicts for already-judged pairs are replayed, never overwritten.
4. `$EMBED survivorship --vault "$VAULT"`. Deterministic winner for every new fork/duplicate judgment (existing `canonical: true` > type/folder priority > most recent `updated`/mtime > `tie`), written to the judgment, then `_generated/vault-hygiene/pending-supersession-review.md` is regenerated: one block per open proposal with an editable `decision:` line (`pending | confirm | confirm-keep | reject | swap`). **The review is file mode:** the human opens that file and sets each `decision:` line; their edits survive regeneration; never set a `decision:` line yourself. The JSON output's `queue.open` is the receipt's `proposals_open`.
5. `$EMBED apply --vault "$VAULT" --dry-run --today "$TODAY"`. Applies nothing; prints (stderr) one block per decided proposal: the exact frontmatter diff for winner and loser, the files whose links repoint, the trash destination, and for `confirm`/`swap` the loser's unique lines (verbatim check). A block reported `STALE: stale:<path>` means that document changed after the comparator judged it (or `changed_during_batch:<path>` on a real run): the judgment is closed as `stale`, leaves the queue, and the pair returns as a fresh candidate next run; never hand-edit or re-submit it. If a confirm block is reported `SKIP: fold_missing`, read BOTH docs in full and write the fold: every unique fact from the loser that the winner lacks, in the loser's words where possible, as markdown (bullets or short paragraphs; no em dashes). Put it in a scratch JSON with the Write tool (never a heredoc): `{"<pair_id>": "<fold markdown>"}`; an empty string declares the loser a strict subset (only when every unique line is formatting, not a fact). Re-run the dry-run with `--folds <scratch>` and read the diff once more. Then the real apply: `$EMBED apply --vault "$VAULT" --folds <scratch> --today "$TODAY"`. On a `confirm`: the winner gets `canonical: true` (and `status: active` if it had none) plus a `## Folded from <loser> (date)` section; the loser gets `status: superseded` + `superseded_by` (path-qualified wikilink) + `superseded_at` + `superseded_reason`; inbound links repoint to the winner; the loser is staged to `audit-trash/<date>/`; the judgment is cached (`status: confirmed`, `outcome: folded`, `decided_by: human`); the block leaves the queue; an `## <date> (apply)` receipt is appended to `audit-log.md`. `confirm-keep` stamps both and leaves the loser in place. `reject` needs no fold: the verdict becomes `distinct-purpose`. A pair with a `no_merge` record on either side is downgraded to `confirm-keep`. A decided block whose winner or loser no longer exists is closed as `withdrawn`. Exit 3 means the invariant check found a violation after apply: stop and report it. `applied` goes in the receipt.
6. **Staleness (report-only).** From the Step 1 scan output, list `stale_canonical` (canonical docs whose hash has not changed in the window). Do not edit them. Put the count in the receipt and name the docs in `notes:` when above 0, so a later review notices a canonical doc may have drifted from reality. (Calibrating the comparator against a golden set, `$EMBED calibrate`, is a local, on-demand run, not part of the nightly.)

## Step 5: Schema feedback

Read the last 3 run entries in `_generated/vault-hygiene/audit-log.md`, including each entry's `violations` line (written by Step 6). Group entries by their `kind:folder-or-path:destination-or-rule` tuple: if the same tuple recurs in the same direction across 3+ runs, the schema is wrong, not the vault's content: amend the YAML core (add the folder, adjust the rule) AND append one line to the schema's Amendment Changelog: `- YYYY-MM-DD: <change>. Why: <the recurring pattern>.` Never amend to bless junk (recurring genuine clutter is just fixed again), and never touch `protected` this way. After amending the schema, re-run scan to confirm it still parses before proceeding.

## Step 6: Receipt

Append to `_generated/vault-hygiene/audit-log.md` **using the Edit/Write tool** (read the file, add the new entry at the end). Do NOT shell this out with `cat >>`, `echo >>`, `tee`, or a heredoc: shell write-redirects are not in the cloud runner's auto-approved set, so a scheduled routine stalls on a permission prompt, whereas an Edit/Write tool call is auto-approved. Same rule for the Step 5 Amendment Changelog line and any other file this command writes.

```
## YYYY-MM-DD
moved: <list or none>
renamed: <list or none>
merged: none
staged: <list or none>
trash_purged: <day-folder count from the scan output, or 0>
frontmatter: <count>
watched: <N clusters (M new this run), or none>
amendments: <list or none>
violations: <kind:folder-or-path:destination-or-rule, ... or none>
candidates: <meta.candidates from Step 4b's pending output; append " (embedding skipped)" when item 0 skipped embedding, since pending still reads the prior candidate list>
judged: <verdicts accepted in Step 4b this run> (backlog: <meta.pending after judging>)
proposals_open: <queue.open from the survivorship output, or 0 when skipped>
applied: <receipt.applied from the apply step, or 0> (folded N, kept N, rejected N)
invariant_violations: <count from the scan output, or 0>
stale_canonical: <count from the scan output, or 0>
```

`violations` is the identity record Step 5 compares across runs: one entry per `root_clutter`, `unknown_folder`, `naming_violations`, `empty_stubs`, or `missing_frontmatter` finding acted on this run, written as `kind:folder-or-path:destination-or-rule` -- e.g. `unknown_folder:Notes/:Resources/Reference/` for a file routed to the closest general-purpose folder, or `missing_frontmatter:Resources/Health/:added` for a frontmatter fix. Reuse the exact same tuple wording when the same violation recurs so Step 5 can match it; do not paraphrase run to run.

Then report ONE line: `Vault audit: N moved, N merged, N staged, N amendments, N proposals open`. In EOD, that line is the phase status; standalone, print it plus anything surprising.

## Init (one time per vault)

1. `mkdir -p "$VAULT/_generated/vault-hygiene"` first (the schema, index, log, and trash state all live under it; keep them OUT of `.claude/` so a scheduled cloud routine never stalls on a permission prompt). Then draft `_generated/vault-hygiene/vault-schema.md` from CLAUDE.md's folder-structure block plus the real tree (`ls` root and one level down). Include `root_whitelist`, `protected`, `folders` with purposes, `naming` for dated records, `no_merge: true` for records, `frontmatter_required`, and an `embedding:` config block (below). Also create an empty `_generated/vault-hygiene/audit-log.md` so Step 5/6 have a file to read and append to.

2. **Derive `protected` by convention, do not ask for it.** Default protected paths: generated-output folders (always include `_generated/`, which holds this audit's own state), `Archive/`, `Attachments/`, `Templates/`, `.claude/` and any other dot-folder, `.handoffs/`. This is a non-technical user's vault; a raw "which paths should I protect" question is a technical question they can't answer well. Instead, ask **at most one** plain-language question:

   > "Are there folders I should never reorganize, like a private journal? I will still keep them tidy if you want, just never merge or rewrite them."

   Map the answer: "keep tidy but never rewrite" -> mark that folder `no_merge: true` (a record folder: filed and indexed, never merged or rewritten). "Never touch it at all" -> add it to `protected` (skipped entirely). Everything else self-corrects later through Step 5.

3. **Mark record folders `no_merge`, including batch/generated output.** Any folder of one-file-per-item output that a tool or a fan-out produced (extraction runs, generated reports, call transcripts, daily notes, journals) is a record, not mergeable authored content. Mark it `no_merge: true`: that both keeps the audit from rewriting it AND excludes it from embedding, so a dated batch of near-identical siblings never floods the candidate list. If a tight cluster of numbered or dated siblings from one folder ever shows up in `embed-candidate-report.md`, that folder is the thing to mark `no_merge` (do not try to widen a filename regex to chase it; the durable fix is classifying the whole folder as a record).

4. **Add the `embedding:` config block** to the schema so the semantic layer is tuned per vault, not in code:

   ```yaml
   embedding:
     owners: []                 # the vault owner's name, and the owning company's name,
                                 # as they appear in `entities`. These are dropped before
                                 # measuring entity overlap (a shared owner/company entity
                                 # is not a real linking signal). Leave [] for a personal
                                 # vault with no single company.
     gate_high: 0.86            # cosine gate when two docs share a non-owner entity
     gate_fallback: 0.90        # single-signal gate (entity-less or disjoint docs)
     stale_days: 180            # a canonical doc unchanged this long is flagged (report-only)
     canonical_home_dirs: [Resources/Reference]  # folders whose live docs win survivorship
   ```

5. Run `scan` (everything shows as added/stale). Build the first index with Step 3's procedure in batches of about 40 files per bulk-update. This is the one expensive run.

6. Run Steps 4 through 6 normally. The invariant check runs from the first `scan` and fails loud if a canonical/superseded marker is ever dangling, chained, or contradictory, so the convention stays honest without anyone having to remember it. Done: the vault is now under nightly audit; wire Phase 5.5 into `/eod` if not already present.
