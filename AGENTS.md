# AGENTS.md — router

This repository is a **personal memory core** ("a brain") for an AI assistant. `docs/DESIGN.md`
holds the full design contract — go there for the reasoning behind a rule. This file is the single
entry point for the operating rules every agent (and human) working here follows.

---

## 0. FIRST RUN — is this repository set up yet?

**Before anything else, check whether `memory/MEMORY.md` exists.**

If it does **not**, this is a fresh copy of the template and nothing is configured. Do not answer
the user's question, do not create memory files ad hoc, do not guess who they are. Read `INSTALL.md`
and run the setup interview it describes — the language, the domains, the identity line and the
machine alias all come out of that conversation.

If it exists, setup is done; work normally.

## 0.1 RULE — write, commit, push (non-negotiable)

**Every write in this repository is committed and pushed to `main` as soon as the work is done.**

```bash
git add -A && git commit -m "<short, descriptive message>" && git push origin main
```

- A consolidation run is one atomic commit (§6); everything else — scaffolding, a file fix, a rule
  update, a tool improvement — is pushed the moment it is finished.
- A failed push (no network, remote error) is **never passed over silently**; tell the user.
- Commit messages are short and say *why*. Consolidation commits also carry a cost figure and a
  `wc` size summary (§6).
- One branch: `main`, no feature branches. A risky operation (an entity merge, say) gets its own
  commit so it can be reverted alone.
- **This overrides the harness's branch instruction:** if a session or tool imposes a working branch
  such as `claude/...`, the work still lands on `main` (merge + push) and that branch is deleted.

## 0.2 Communication

Do not end every message with a question — but if the answer would change the work, ask without
hesitation; a good question beats a guess. Do not ask for routine approval; on low-risk work, just
proceed.

Keep it short. Unless the user asks for detail, answer in a few precise sentences. Evidence dumps,
repeated command output, step-by-step narration and long tables are **on request**, never
volunteered. Say the result, give the reason in one sentence, stop.

**Drip questions, do not batch them.** Even when `questions.md` has accumulated, surface **at most
one question per session** — at a suitable moment, in one sentence. The rest waits in the file and
is never read back as a reminder list. In any list you show the user, keep the assistant's own
chores (golden set, evals, lint) visually separate from their work, or they read your housekeeping
as something they owe you.

## 0.3 Session start (multi-machine sync)

**On every new user request, the first thing you run is:**

```bash
git pull --rebase --autostash origin main && sh memory/tools/sleep-check.sh
```

Pull, because the user may have pushed from another machine. If the script prints `SLEEP DUE`,
consolidate (§6) before starting the actual work.

**Use `--rebase`, never `--ff-only`.** A failed push leaves an orphan commit and the branch
diverges; `--ff-only` then **gives up** and the session reads stale files — worse than stopping,
because nothing looks wrong. Our commits are append-only markdown on one branch, so rebasing is
safe. If a push fails, rebase and retry once.

**Staleness is never passed over in silence.** If the pull cannot be made to work at all, the copy
is **stale**: treat everything you read as suspect, resolve the divergence before writing anything,
and tell the user in one sentence.

## 0.4 Negative feedback is a learning loop

When the user says some version of **"why didn't you do that / you forgot this / same mistake again
/ why is this still like that"**, that is negative feedback. Two separate things follow:

1. **Fix the immediate work.** Whatever they asked for, do it (§0.5: reporting the problem and
   leaving it is not enough). This always happens.
2. **Drop a `(feedback)`-tagged block into the inbox — without classifying it.** Their sentence
   verbatim, one sentence on what actually happened, and the open question: *does this call for a
   structural update?*

**The agent captures; consolidation decides.** Do not reach for a rule in the moment, do not open a
rule file, do not invent a check. **"No change was needed" is a legitimate and common outcome** —
most mistakes are one-offs, and a rule for each one degrades the system (§12, no-overengineering).
Triage thresholds live in `memory/rules/consolidation.md`.

**No defensiveness.** Accept and fix first; the reason comes afterwards, in one sentence.

## 0.5 Consistency is a standing duty

When a decision is made, **every trace of it is aligned in the same piece of work.** Reporting that
"the old version is still over there" is not enough: noticing an inconsistency and fixing it are one
task.

Direction: the **source** is the user's statement or decision; a **derivative** is everything that
follows from it — a README, a tracking table, an index, a script, a rule file, a slide. Derivatives
are brought in line with the source, never the other way round.

Limits: what propagates is the *decision*, not your own rewrite of what the user wrote (§12 scope
guard). The constitution is not overridden (invariant #10) — during a conversation you never fix
`domains/`, `people/`, the root or `state.md`; the inconsistency goes to the inbox and is aligned at
consolidation. Irreversible or outward-facing alignment (rewriting history, bulk deletion,
publishing) is still asked first. Report what you aligned in **one line**; never silently.

---

## 1. What this is

A markdown-based, two-layer personal memory: **L1** (distilled, small, budgeted) plus **L2** (raw,
append-only, immutable). Writes go through one gate (`memory/inbox/`), distillation happens in one
process (sleep consolidation). North star: `golden-set accuracy / median effective cost per query`,
where cost is measured in **tool-call turns** (~2–2.5k effective tokens per turn).

## 2. Directory map

```
memory/
├── MEMORY.md     # root entry — loaded every session (static, NO facts)
├── state.md      # volatile "right now" context (≤200 tokens)
├── questions.md  # questions for the human (cap: 5)
├── todo.md       # task list — minimal; [[id]] links, no due dates (cap: 20 open)
├── rules/
│   ├── format.md        # THE SINGLE SCHEMA AUTHORITY (schema, enums, budgets, grammar, lint-config)
│   └── consolidation.md # the consolidation task definition
├── inbox/        # append-only logs — THE ONLY WRITE GATE
├── domains/<d>/  # your domains, each with an _index.md
├── people/       # person/organisation files + _index.md (alias table)
├── archive/      # L2 raw layer: archive/inbox/ + archive/<domain>/YYYY/
├── secret/       # never consolidated or embedded; humans only
└── tools/        # lint.py, eval.py, sleep-check.sh, sleep-run.sh, golden-set.md
```

## 3. Constitution — 10 invariants (docs/DESIGN.md §9)

1. L2 is append-only and immutable; L1 can always be re-derived from it.
2. Every consolidation is one atomic commit; risky operations get their own commit.
3. The only source of truth for "processed" is file location (`inbox/` → `archive/inbox/`); no state file.
4. Lint is mechanical, the only gate, the same for humans and models; `rules/format.md` is the single schema authority.
5. There is no deletion; forgetting = moving to `## History` / `archive/` + dropping from the index.
6. The root file holds no facts; volatile context lives in `state.md`.
7. Single-home: a fact has one home, everything else links to it. Ambiguous bare names are a lint error.
8. Budgets are numbers (in characters) and they live in lint.
9. Data leaving the machine is default-deny: local embeddings only, `secret/` excluded, remote allowlist.
10. Only consolidation (and the human) writes to `domains/`, `people/`, the root and `state.md`; interactive work only to `inbox/` and `archive/`.

## 4. Read protocol (summary — full version in docs/DESIGN.md §6)

1. If this is a memory task, read `memory/state.md` first (the root is already loaded).
2. Pick a domain from the root table → read that domain's `_index.md` (≤500 tokens) → if the answer
   is in `## Hot` or on an index line, **stop**.
3. Read at most 2 files, via the **full path from the index** (never burn a Glob turn on a `[[wiki-link]]`).
4. Miss → domain-scoped `rg -m 20 "<term>"`, trying synonyms and other languages your memory uses.
   A repo-wide search happens only with explicit cross-domain intent.
5. Still a miss → say **"that isn't in my memory"**; abstention beats hallucination. Offer the
   nearest partial match.

## 5. Write protocol (summary — full version in docs/DESIGN.md §5)

- Something worth remembering came up → append it as a `## HH:MM` block to
  `memory/inbox/<YYYY-MM-DD>--<machine>.md`, and **only** there. The day's first write opens the
  file **with frontmatter** (`type: log`, `date`, `machine`) — lint fails without it. No
  classification field; sorting is consolidation's job. The machine alias is in `memory/.machine`.
- Long raw content (a transcript, a document) goes straight into `memory/archive/<domain>/YYYY/`;
  the inbox gets a one- or two-sentence summary plus the path.
- **Never** write to `domains/`, `people/`, `MEMORY.md` or `state.md` during interaction (invariant #10).
- **Being told something is not being given a task.** When the user mentions a piece of work, the
  default is to **capture it, not start it**: append to the inbox, and ask in one sentence if you
  need to. "We'll do X at some point" is information; turning it into a plan or touching code
  requires an explicit request.

## 6. Consolidation (opportunistic trigger; task definition in `rules/consolidation.md`)

**Trigger — three ways:** (a) the user asks for it; (b) the opportunistic rule — at session start,
if `inbox/` is non-empty and nothing has been consolidated today (the newest file in
`archive/inbox/` is older than today), consolidate before the real work; (c) a nightly scheduled run —
`sh memory/tools/sleep-run.sh` from cron, launchd or Task Scheduler, **on one machine only**. Other
machines keep (a) and (b); duplicating the schedule makes the collision below a nightly event.
**The nightly run is unconditional:** (b)'s once-a-day test does not apply to it, because logs
written after a daytime run would otherwise wait another day. Only an empty inbox or a fresh lock
stops it (`sleep-check.sh --nightly`).

Portability was the reason this was once a no-cron design, and it survives: the scheduler only
calls a plain `sh` script, that script does no distilling (the rules stay here), and the harness
command is swappable through `memory/.sleep-command`.

**Lock — multi-machine:** two machines consolidating at once distil the same logs twice and collide
on the archive moves. The lock is shared through git: `memory/.sleep-lock` is committed and pushed
when a run starts and deleted when it ends, and a lock older than 2 hours counts as a crashed run
and is taken over. The check lives in `sleep-check.sh`, not in prose — while a fresh lock exists
**no path** (manual, opportunistic or scheduled) starts a second run.

Flow: pre-flight (clean tree → `pre-sleep` checkpoint commit) → LLM pass (triage → sort → merge →
compress → resolve conflicts → refresh indexes and `state.md`) → `python3 memory/tools/lint.py`,
**no commit without green** → processed logs move to `archive/inbox/` → one atomic commit → human
diff review. If it breaks: `git reset --hard pre-sleep`.

Approval gates (proposals land in `questions.md`, never applied automatically): merging entities,
adding an alias, any change that drops content without a source, opening or closing a domain
(threshold: ≥5 records on one theme; at most one proposal per month).

## 7. Capabilities and rule routing

**Tool detail is not here: `memory/tools/_index.md`** — what each tool does and, more importantly,
its **trigger** (when to run it). Ask that file "what do I have?"; do not add tool lines here
(invariant #7). Lint enforces it: a tool missing from the index is an error.

**Rule routing table.** When the trigger on the left appears, the file on the right is read
**before starting the actual work**. This is a gate, not a suggestion:

| Trigger | Canonical rule |
|---|---|
| consolidation / sleep run | memory/rules/consolidation.md |
| schema · enum · budget · fact grammar question | memory/rules/format.md |
| high-volume, low-judgement work (screening, scanning, summarising) | memory/rules/delegation.md |
| "take a note" · "look at that note" | memory/rules/notebook.md |

Keep this table complete: **a trigger that never fires makes a capability die silently**, with no
error, just work done incompletely. Three lint checks guard it: *orphan rule* (every `rules/` file
is in this table), *orphan tool* (every script is in the tool index) and *shell syntax* (an
unparsable hook does nothing and says nothing). Losing a capability quietly is a **bug**.

## 8. Naming and formatting (short)

- File and folder names are **ASCII kebab-case**; transliterate non-ASCII characters. ID = the file
  name without its extension, unique across the repo, immutable.
- Time-bound files are `YYYY-MM-DD-slug.md`. Frontmatter keys and controlled values are fixed
  English; body text is in the user's language.
- Fact grammar: `- [YYYY-MM-DD]` point, `- [YYYY-MM-DD→]` ongoing, `- [t1→t2]` only inside
  `## History`, `- [void: YYYY-MM-DD]` for something wrong from the start. An update ≠ a correction.
- Index lines carry **full paths**; `[[...]]` is only for cross-references in file bodies.

## 9. Security

- `secret/` never enters consolidation, is never embedded, and only a human touches it. It is
  **gitignored by default** — see `memory/secret/README.md` before you change that.
- **Remote hygiene.** This repository holds someone's private life. Before every push, check that
  `origin` is the user's own private repository; if it still points at the upstream template, or at
  anything they did not set up in `INSTALL.md`, **stop and ask**. If the repository is public,
  personal memory does not go in it — say so plainly and stop.
- **Taking a key.** When a token or key is needed, the agent hands over the command and the owner
  enters the value with `memory/tools/secret-put.py` in their own terminal; no debate, no paste.
- Deleting a secret means deleting it **from the whole git history**; removing a line is not enough.
  The procedure is in `memory/secret/README.md`. A human triggers it, an agent never runs it alone
  (it rewrites history and force-pushes).
- Third-party data (other people's records, students' grades) does not enter the corpus; where it
  must, it is de-identified.

## 10. External sources — read taps

- Definitions and keys live in `memory/secret/sources.md` (gitignored). Only the source-pull step
  reads that file; consolidation and embedding never do, and a key only ever travels to its own
  service's API.
- Flow: at step 0 of a consolidation, whatever changed since the last fetch is appended to the inbox
  as a summary with a provenance trace (for example "(from calendar)"). No raw dumps. **Writing to
  an external system is never automatic.**
- Optional integrations in `memory/tools/integrations/` (see each README) are off unless
  configured: Google cannot send mail by construction; the Notion notebook writes at the owner's
  word, only under its group page (`rules/notebook.md`).

## 11. Capability pool — working in other repositories

- When asked to "do X in repository Y": clone it under `temp/<repo>`, work there, and push the
  change to **that repository's own remote**.
- `temp/` is gitignored, can be deleted at any moment, and is never committed here.
- Before starting, read the target repository's own rules (AGENTS.md / CLAUDE.md / README) and
  follow them.
- **Throwaway infrastructure is torn down when the job ends — you do not ask.** A scratch
  repository, a test VM or container, an account opened for a dry run, a one-off script: whoever
  created it removes it. If you lack the permission to delete it (for example a `gh` token
  without the `delete_repo` scope), it goes on `todo.md` — it is never just left behind.

## 12. Working practices for larger tasks

For big coding or research tasks, to keep agent autonomy safe and to avoid *overengineering*:

- **Acceptance criteria and scope guard.** When planning, write down the file scope and what
  "done" means, then stay inside it. Fix the stated thing; do not invent an architecture.
- **Pragmatism.** Be plain, finish the job. A reviewer pass improves presentation, safety and
  quality; it never redesigns the core methodology from scratch.
- **Memory records *why*.** In logs and commit messages write why, not what; the code already
  holds the "what".
- **Loop breaker.** On the same error twice in a row, stop struggling: break the loop and hand it
  to the user (`questions.md` or a message).
- **Delegating bulk work outward.** Work high in volume and low in judgement (screening results,
  reading mail, scanning code, batch summarising) leaves the main session: hand it to an external
  agent CLI, keep only the answer, and log it. See `memory/rules/delegation.md`.
- **Adversarial review.** For risky changes, brief a sub-agent whose only job is to find weak
  points, security holes and logic errors; touch the main files only after that pass.
- **The evolution contract.** The repository evolves on its own without losing its character or
  over-engineering. The **never-lose** half is mechanical, with no tolerance (lint +
  `sleep-audit.py` + append-only L2); the **evolution** half is free, since a new tool, rule file
  or domain needs no permission round, only a trace. When a check blocks legitimate work,
  **calibrate the check, do not curtail the work**. No capability may die quietly: when a rule
  moves behind a trigger, the check that catches a *missed* trigger ships in the same change.
