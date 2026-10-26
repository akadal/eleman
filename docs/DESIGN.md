# eleman: design contract for a personal memory core

**Scope:** the core only — data structure, memory lifecycle, read protocol. No UI, no backend, no
service process.

---

## 1. Summary

A markdown-based, two-layer personal memory core, **consumed directly off the filesystem** by an
agent harness of the Claude Code class. The backbone is hierarchical (domain folders → isolation +
progressive disclosure), with a network layer laid over it (person/organisation files + cross
links). Writes go through one gate (an append-only inbox); distillation happens in one process
(sleep consolidation). The unit of token optimisation is not file size but the **tool-call turn**;
every part of the design serves one principle: *few turns, small files, index first*.

**One-sentence positioning:** a single-person memory core that takes the skeleton of the Claude
Code memory convention, dresses it in Zep's temporal-validity discipline and Mastra's append-only
capture plus sleep-consolidation lifecycle, and adds zero extra processes (with one exception: a
derived local vector index in v2).

### 1.1 Problem

- Heterogeneous personal data (family, work, projects, meetings, ideas) resists organisation;
  Notion-style manual filing is not sustainable for one person.
- LLM assistants run out of context; dumping everything into the prompt is expensive and — worse —
  **mixes subjects together** (context bleed, the number one fear).
- What is wanted: the best possible memory for the fewest tokens, without subjects bleeding, simple
  enough that one person can build and maintain it.

### 1.2 Definition of success (north star)

`golden-set accuracy / median effective cost per query` — the two numbers are always reported
together. Effective cost = tokens read **plus the number of tool-call turns** (each turn re-bills
the entire context accumulated so far, roughly 2–2.5k effective tokens per turn). Accuracy alone is
meaningless: you can inflate it to 100% by dumping the whole memory into context.

### 1.3 Non-goals (deliberately not built)

- No multi-user, no sharing, no authorisation. One person.
- No UI. The interface is the filesystem, the harness, and a text editor.
- No real-time sync. Sync is git; conflict resolution is human.
- The core is integration-agnostic: mail/calendar/drive connectors are not part of it. A harness's
  API connections may feed the inbox as **read sources** (rules in §13.1); writing to an external
  system is never automatic.
- No separate service process (one exception: the derived, disposable local vector index in v2).
- No instant consistency: the delay between writing and distilling is accepted; fresh information
  is grepped out of the inbox.
- No 100% recall target: when in doubt, "that isn't in my memory" beats making something up.
- Not a task manager: due dates and reminders are out of scope. This scope gate stays closed.

---

## 2. Conceptual model

### 2.1 Two layers

| Layer | Content | Character | Who writes |
|---|---|---|---|
| **L1 — distilled memory** | People, preferences, project and topic states, decisions, facts | Small, budgeted, human-readable, maintained | Consolidation only (+ the human) |
| **L2 — raw layer** | Inbox logs, transcripts, documents, long notes | Append-only, immutable, unbounded | Capture (+ the human) |

**The constitutional principle:** L2 is append-only and immutable; L1 is a view that can always be
re-derived from L2; git sits underneath everything and every consolidation is one atomic commit. As
long as those three hold, no mistake is ever *data loss* — it is only a corrupted derived view, and
`git revert` plus re-distillation undoes it.

**Mapping to human memory:** session context is working memory (transient); `inbox/` is short-term
memory (days); L1 is long-term memory. Consolidation is the **selective** transfer from short-term
to long-term: it decides what becomes permanent and what falls away undistilled. No persistence
decision is made at capture time at all — capture stays cheap, filing waits for sleep.

### 2.2 The hybrid decision: hierarchical backbone, networked veins

- **What the hierarchy carries:** domain isolation (a family question only ever walks the
  `domains/family/` path), progressive disclosure (root → domain index → file), and lifecycle
  boundaries (inbox / domains / archive are physically separate).
- **What the network carries:** person and organisation files are the hub for entities that span
  domains; links are the edges between files; backlink queries work with grep and no tooling.
- **The condition:** if the network layer goes undisciplined — bare-name links, copied facts, a
  root file full of facts — it silently punctures the hierarchy's isolation. That is why link
  discipline is wired to a mechanical linter (§10).

**The single-home principle:** every fact has exactly one home; everywhere else links to it and
never copies it. This is the structural antidote to context bleed: two copies of the same fact can
never exist.

**Deliberate simplifications (against the literature):** no knowledge graph or graph DB (wiki-links
plus grep are enough); no continuously running observer daemons (periodic consolidation is enough);
no embedding-driven automatic link generation (consolidation writes links explicitly); no
multi-phase NREM/REM sleep simulation (one consolidation pass is enough).

---

## 3. Data structure

### 3.1 Canonical directory tree (the single authority)

```
memory/
├── MEMORY.md                  # root entry — loaded every session (static; ≤800 tokens)
├── state.md                   # volatile "right now" context (≤200 tokens)
├── questions.md               # consolidation's questions and pending proposals (cap: 5)
├── todo.md                    # deliberately minimal task list (cap: 20 open)
├── rules/
│   ├── format.md              # THE SINGLE SCHEMA AUTHORITY: schemas, enums, budgets, grammar
│   └── consolidation.md       # the consolidation task definition (read only during a run)
├── inbox/
│   └── 2026-03-14--laptop.md  # today's append-only log (machine suffix in the file name)
├── domains/
│   ├── <d>/<sub>/             # sub-folder for parts of the same thing, e.g.
│   │                          #   learning/databases/overview.md + week03.md
│   │                          #   ID = <folder>-<file> (rules/format.md)
│   ├── personal/  _index.md, preferences.md
│   ├── family/    _index.md, house-move.md
│   ├── work/      _index.md, project-atlas.md
│   ├── projects/  _index.md, home-automation.md
│   └── ideas/     _index.md, 2026-02-08-memory-core-idea.md
├── people/                    # entity layer: people + organisations (no "concepts" — YAGNI)
│   ├── _index.md              # alias table: every person and org on one line each
│   ├── alex-rivera.md
│   └── northwind-co.md
├── archive/                   # L2 raw layer — append-only, immutable
│   ├── inbox/                 # processed inbox logs are MOVED here
│   └── <domain>/YYYY/         # the archive path carries a domain segment (required for the bleed filter)
│       └── 2026-02-20-atlas-kickoff-transcript.md
├── secret/                    # never enters consolidation or embeddings; humans only
├── tools/
│   ├── lint.py                # v1: 3 rule classes (§10.3)
│   └── eval.py                # v1: golden-set runner + cost logging
└── .index/                    # v2: derived vector index — gitignored
```

The domain list is a starting suggestion. Opening or closing a domain is cheap: a folder and an
index line.

### 3.2 File types (five of them)

| Type | `type` | Location | Target / ceiling (tokens)* |
|---|---|---|---|
| Root entry | — | `MEMORY.md` | 500 / 800 |
| Index | `index` | `domains/*/_index.md`, `people/_index.md` | 400 / 500 |
| Topic | `topic` | `domains/<d>/*.md` | 400 / 700 |
| Person/Org | `entity` | `people/*.md` | 250 / 400 |
| Log / Archive | `log` / `archive` | `inbox/`, `archive/` | free (raw) |

\* Lint checks characters, not tokens — mechanical, no tokeniser required. The conversion factor is
pinned in `rules/format.md`. An L1 file over its ceiling gets compressed or split at consolidation.

Types that were cut (YAGNI): a `concept` entity (no question in a personal memory wants a concept
file back), and a separate `decision` type (decisions live as lines under a topic file's
`## Decisions` heading, with an archive link where needed; git history keeps the record).

### 3.3 `MEMORY.md` — the root entry (a static contract)

The root carries content that does not change on a weekly timescale: identity (2–3 lines) + the
domain routing table + the protocol. **It may not contain facts, other people's names, or dated
status.** The root is the tax paid unconditionally on every session, and it is the most insidious
bleed vector there is. Volatile context lives in `state.md`.

Note that index tables carry **full paths**, not `[[wiki-links]]` — the harness does not resolve
`[[...]]`, so every link you follow that way costs one extra Glob turn. `[[...]]` is used only
inside file bodies, as a human-readable cross-reference (lint checks that the target exists).

### 3.4 The domain index — `_index.md`

A two-block contract: a **mechanically reproducible** `## Files` block plus a `## Hot` block
(≤5 items) curated by consolidation. Only `status: active` files are listed line by line; closed
ones collapse into a single count. Chronological records (meetings and the like) do not go in the
index at all — the date is in the file name and a date-grep finds them.

```markdown
---
type: index
domain: family
updated: 2026-03-11
---
# Family — index

Household: partner (→ memory/people/sam-okonkwo.md), one child (b. 2019).

## Hot
- [2026-03→] Moving house in October → memory/domains/family/house-move.md
- [2026-03-09] School registration completed → memory/domains/family/school-registration.md

## Files
- memory/domains/family/house-move.md — October 2026 move, mover quotes (active)
- closed: 1 file (school-registration)
```

### 3.5 The topic file (`topic`)

```markdown
---
id: project-atlas
type: topic
domain: work                # exactly ONE domain; multiple is forbidden
title: "Project Atlas — data platform migration"
summary: "Migration off the legacy warehouse; currently in the pilot phase."
status: active              # active | paused | closed
updated: 2026-03-08
---
# Project Atlas — data platform migration

Team: me (lead), [[alex-rivera]] (data engineering), [[jordan-lee]] (contractor).
Budget: 180k, internal. Not related to the Northwind grant.

## Current state
- [2026-01-10→] Phase 2: migration of historical data; target finish 2026-09-30
- [2026-03-05] Monthly review held; interim report is with Alex ←[[2026-03-05-atlas-review-transcript]]

## Decisions
- [2026-02-02] Embedding model: bge-m3 (over e5-large; recall 0.82 vs 0.61) ←[[2026-02-01-embedding-benchmark]]
- [2026-01-10] Target platform: managed Postgres, not the vendor's warehouse

## History
- [2026-01→2026-01-10] Phase 1: vendor evaluation (done; output: the platform decision above)
```

The `summary` field is critical: it lets a grep result be discarded without opening the file.

### 3.6 The person/organisation file (`entity`)

Carries no detail of its own: identity + at most five lines of context per domain + links. The same
person's two contexts live in one file under separate headings, with the details in the relevant
domain file. Because the file is small (**≤400 tokens**) it is read in full; there is no
section-targeted reading acrobatics.

```markdown
---
id: alex-rivera
type: entity
entity: person              # person | org
name: "Alex Rivera"
aliases: ["Alex", "A. Rivera"]
domains: [work, family]
updated: 2026-03-06
---
# Alex Rivera

- [2010→] Colleague since university; data engineering.

## Context: work
- Data engineering lead on Atlas → memory/domains/work/project-atlas.md
- [2026-03-05] Took over the September interim report

## Context: family
- Family friend; their partner and mine are close
```

**Namesake rule:** if a bare name collides, add a distinguishing suffix to the file name
(`alex-rivera-neighbour` vs `alex-rivera-colleague`); the real spelling lives in `name`/`aliases`.
The same alias appearing in two files is a **lint error**, not a warning. `people/_index.md` lists
every person and organisation on one line in the form `name — aliases — domains — path`;
consolidation catches namesakes using that small table.

### 3.7 The inbox log (`log`)

```markdown
---
type: log
date: 2026-03-14
machine: laptop
---
# 2026-03-14 (laptop)

## 09:14
Spoke with Jordan; the proposal defence moved to 15 September. Alex will be on the panel.

## 11:40
Mover X quoted 28,000; we thought it steep, we will get a quote from Y.
```

- Capture is one append. There is **no classification field** — asking for a type, a domain or an
  entity guess at capture time adds friction, and friction kills capture. Filing is consolidation's job.
- Long raw content (a transcript, a document) goes straight into `archive/<domain>/YYYY/`; the inbox
  gets a one- or two-sentence summary plus the path. The inbox never bloats.
- Multiple machines: the machine suffix in the file name eliminates conflicts as a class
  (append-only + disjoint files).
- **Processed = location:** when consolidation finishes, the log is moved to `archive/inbox/`. There
  is no separate state file; the single source of truth for processed-versus-unprocessed is where
  the file lives, and that is inside the atomic commit → it stays consistent even after a
  `git reset`, and silent data loss closes as a class. `inbox/` always holds only one or two days
  of unprocessed material → "what did I say yesterday" is a constant-small grep.

### 3.8 Naming, IDs, language, git

- File and folder names are **ASCII kebab-case**. The reason is mechanical: macOS (NFD) and Linux
  (NFC) normalise differently, which produces phantom git changes on non-ASCII names, and ASCII
  keeps grep patterns single.
- **ID = the file name without extension**, unique across the repo, immutable. Renaming is a last
  resort; if you must, `git mv` + link updates + adding the old name to `aliases`, all in one commit.
- Time-bound files are `YYYY-MM-DD-slug.md`; timeless ones are plain `slug.md`.
- Frontmatter keys and controlled values are fixed English; body text is in the user's language. The
  whole schema is defined in `rules/format.md`, and **lint is configured from that file** — schema
  and enforcement cannot drift apart.
- Git: one branch, no branching. Every consolidation is one atomic commit; a risky operation (a
  merge) gets its own commit so it can be reverted alone. `.index/` and large binaries stay out of
  the repository.

---

## 4. Temporality: the fact grammar

The markdown equivalent of Zep's `valid_from`/`invalid_at` pair — a stamp at the start of the line
plus the section it sits in:

```
- [YYYY-MM-DD]      Point fact (it happened that day).
- [YYYY-MM-DD→]     Ongoing state (still true).
- [t1→t2]           Closed interval — only inside ## History. (it was true across that span)
- [void: YYYY-MM-DD]  Correction — the fact was WRONG FROM THE START; it was never true.
```

- **An update is not a correction.** "About to move" → "moved" is a state transition: the line drops
  into `## History` with a closing date. A fact that was mis-distilled or misheard gets `[void: t]`
  instead — it does not settle into History as "once true", and it is **not used** in temporal
  reasoning. Without this distinction a memory turns its own errors into historical facts.
- An invalidated line is never deleted (the no-deletion rule). If `## History` grows past roughly a
  third of the file budget, consolidation reduces it to a single summarising paragraph and pushes
  the full record into `archive/`.
- Provenance: a fact distilled **from an archive document** carries `←[[archive-id]]` at the end of
  the line (human-readable, one link). For a fact distilled from the inbox, the date stamp is
  enough — the source is two steps away in `archive/inbox/YYYY-MM-DD*.md` via date plus grep. A
  mandatory record-ID apparatus on every line is **not built**: the token tax plus the risk of
  pushing the model to invent sources outweighs the benefit.
- Cut (YAGNI): `due:` dates and expiry sweeps (we are not a task manager), `last_verified` stamps
  (staleness detection is a grep for "updated is old and status is active"), `superseded_by` chains.

---

## 5. The write path

### 5.1 Capture

The harness instruction (protocol #5 in `MEMORY.md`): when something worth remembering comes up in a
session, append it to the inbox as a `## HH:MM` block and move on. One write operation; no reading,
no classification, no index update. Capture is best-effort: if it fails, the session is not broken.

**The one-way write rule (non-negotiable):** during interaction, only `inbox/` and `archive/` are
written. `domains/`, `people/`, `MEMORY.md` and `state.md` are written **only by consolidation**
(and by the human). This rule is the number one insurance policy against half-finished updates and
against bleed. (A human editing files by hand is not an error; it is a first-class write path — all
rules live in lint, and the gate is the same for everyone.)

### 5.2 Sleep consolidation — one phase plus a mechanical wrapper

A six-phase pipeline was **deliberately rejected** (distributed-systems engineering for one person's
nightly chore). Instead:

```
1. Pre-flight (script): is the working tree clean → pre-sleep checkpoint commit
2. LLM pass (as much sub-context per domain as it needs):
   input  = unprocessed inbox logs + the relevant _index files + the target files
            + the ENTIRE alias table from people/_index.md (it is small — namesake detection needs all of it)
   task   = triage (do not distil what has no lasting value) → sort (pick the target file)
            → merge/update (per the fact grammar; a duplicate becomes a link)
            → COMPRESS (as hard as you can — budgets are targets, not ceilings; because the
              raw data is in the archive, aggressive distillation is lossless, §13.4)
            → resolve conflicts (§5.3) → refresh the Hot/Files blocks of every index
            → refresh state.md
   output = file updates + questions.md items
3. Lint (script): the rules in §10.3; if red, the model gets one repair attempt, then abort (reset)
4. Processed logs move to archive/inbox/ → one atomic commit → human diff review (every run in v1)
```

If a run goes wrong: `git reset --hard pre-sleep` and run again. Making a 40k-token pass resumable
costs more than re-running it. Cost is measured from the harness's real usage log, not estimated,
and written into the commit message.

**Approval gates (default in v1).** These operations are not applied automatically; they land in
`questions.md` as a proposed diff: (a) merging two entities, (b) attaching a new name to an existing
entity (adding an alias), (c) any change that drops content without a source. The reason: a wrong
merge is the most expensive mistake this system can make (two people's histories interleave, and
pulling them apart hurts) and lint cannot catch it — everything looks structurally valid. As trust
is earned through measurement (R1), the gates loosen.

**Mechanical namesake pre-rule:** if a name in a record matches more than one entity in the alias
table, **or** matches none of them exactly, automatic assignment is forbidden → `questions.md`. This
is a mechanical rule, not a polite request that the model be careful.

**New-domain decision (the anti-junkyard brake):** consolidation does not force unfileable records
into a domain, but it does not open domains freely either. The rule: no new domain may be proposed
until **≥5 unfileable records** accumulate on the same theme; the proposal goes through the approval
gate and there is a rate limit (at most one proposal per month). Records below the threshold go into
the nearest existing domain with a `(provisional)` note — if the theme grows in later runs, they
move. Closing a domain goes through the same gate (files move to the archive, the index line drops).

### 5.3 Conflict resolution (first match wins)

0. **State transition, or recording error?** If the provenance points at the same event, assume an
   error → `[void: t]`.
1. **Temporality:** if it is a state transition, apply the update (the old line goes to `## History`).
2. **Layered source trust, then recency:** *user's own statement > user's document > third party or
   model inference*. Low-trust new information may not overwrite high-trust old information →
   `questions.md`. A phrase carrying a temporariness signal ("this term", "for now") does not
   overwrite a durable fact; it is written next to it.
3. **Ask threshold:** a high-impact area (identity, relationships, health, finance) or two user
   statements close together in time → do not resolve automatically, ask. A fact awaiting an answer
   stays in the file marked `(?)` and is presented as "disputed" on retrieval.

`questions.md` caps at 5 items: a question over the cap is not asked, and the fact lives on with
`(?)` — so that the question queue does not become the new manual-filing burden.

### 5.4 Forgetting policy

- **Never deleted:** the raw layer (L2), core identity and relationship facts, decisions and their
  reasoning. Consolidation has no `delete` power; output containing `git rm` is rejected outright.
  Real deletion happens only by human hand.
- **Falls out of the distilled layer:** completed tasks and events (reduced to a single summary
  line), transient states, the operational detail of finished projects.
- **Two-stage retirement:** (1) a line drops to `## History`; (2) a file moves to `archive/` and its
  index line drops (from that moment it is treated as immutable raw material; promotion back is a
  `git mv`). There is no intermediate `attic/` stop.

---

## 6. The read path

### 6.1 Cost model

The real unit of cost is the **tool-call turn**: every Read or Grep re-bills the entire context
accumulated so far (~2–2.5k effective tokens per turn), and whatever is read stays in context for
the rest of the session. Therefore:

- The target for a typical query is **≤2 Reads**. Spending three turns to retrieve 350 tokens costs
  more than one 1,200-token read.
- A file under 600 tokens is **read in full**; section-targeted reading is only for files over the ceiling.
- Index lines carry **full paths** → no Glob turn is spent resolving a link.
- Progressive disclosure is used only where it actually prevents a large read: a domain with one or
  two files can have its index folded into the root.
- Grep calls are bounded with `-m 20`; the output tokens count against the query budget.

### 6.2 Protocol and escalation

Hierarchical navigation and semantic search are **both first-class capabilities**; the escalation
order is a cost ordering, not a capability restriction: **structural → lexical → semantic (from v2)
→ abstain.** No query starts in the expensive mode — but the user can skip the order with an
explicit request ("search the archive" → straight to semantic mode).

| Step | What | Exit condition |
|---|---|---|
| 0 | `MEMORY.md` is already loaded; on a memory task, read `state.md` (≤200) | — |
| 1 | Pick a domain from the root table (no reading); if unsure, take the top two | — |
| 2 | Read `_index.md` (≤500) | if the answer is in Hot or on a line, STOP |
| 3 | 2 files expected, 5 allowed (from the full path); deepen until found | fact found and no detail requested → STOP |
| 4 | Domain-scoped `rg -m 20`, with synonyms and other languages | a hit → go to that file |
| 5 | If there is a detail signal ("what exactly did they say", "what is the source"), follow the provenance link to the archive file | — |
| 6 | All missed → **"that isn't in my memory"** + the nearest partial match | — |

**Target traces:**
(a) "When is my partner's birthday?" → root table → `family/_index.md` (Hot or a line), or one more
entity file: **1–2 turns, ~350–600 tokens**.
(b) "What is the status of project X?" → the `work/_index.md` line, then the file if needed:
**1–2 turns, ~400–700 tokens**.
(c) "What were the details of my conversation with Y last month?" → index → the summary in the topic
plus `←[[transcript]]` → the archive file: **3 turns, ~2,000–2,500 tokens**.

### 6.3 Domain isolation — what is mechanical and what is not

- Mechanical and conventional barriers: single-home (no copies), the domain-scoped grep pattern
  being mandatory in the protocol, the ban on facts in the root file (lint), the domain segment in
  the archive path, and cross-domain facts entering an answer **with a domain label**.
- Deliberate cross-domain triggers: "all" or "everything" quantifiers, an entity that spans domains,
  a person-centred question ("everything about A"), and temporal sweeps. Protocol: N indexes →
  candidate files → at most 5 files; never a wholesale scan.
- **Honest limit:** in a harness with free Read and Grep there is no *complete* mechanical wall on
  the read path — an agent can run a repo-wide grep if it decides to. This is **residual risk** and
  is not counted as closed. The defence has three layers: (1) the protocol instruction, (2)
  structural measures (single-home + a clean root + domain-scoped archive paths → there is no copy
  to leak), and (3) measurement (the bleed metric is computed mechanically from the harness's tool
  log: the intersection of the paths read with the selected domain).

### 6.4 Abstention

For anything not in memory, say it is not in memory. (The lesson from LongMemEval: the weakest
capabilities are knowledge updating and temporal reasoning, so abstention beats invention.)
`[void:]` lines are not used in temporal reasoning. Facts marked `(?)` are presented as disputed.

---

## 7. v2: semantic search over the raw archive

This is **committed scope**, not an optional extra — it is one of the two first-class retrieval
modes (§6.2). The R2 measurement determines only the **timing**: if grep suffices in v1, vectors
arrive in v2; if it does not, they are pulled forward. L1 is never embedded (it must stay small and
greppable, and semantic similarity punches straight through the domain wall). The design is ready
on the shelf:

- **Store:** sqlite-vec (one file, zero processes; a personal archive stays in the 10⁴–10⁵ chunk
  band, where brute force is <100ms and the metadata filter is in the same SQL). LanceDB was
  rejected — ANN and versioning are dead features at this scale.
- **Model:** bge-m3 (multilingual is mandatory for mixed-language memory; cross-lingual matching is
  the real value of semantic mode: a query in one language hitting a chunk in another). Lighter
  alternative: multilingual-e5-base. **Local embedding only; a cloud embedding path never exists in
  the codebase** — the best prevention is the absence of the path.
- **Chunks:** heading-aware, 250–400 tokens (max 512); paragraph windowing with ~12% overlap on
  transcripts; a breadcrumb prepended to the embedded text (`"Meeting 2026-03-05 Atlas > Budget:
  <chunk>"`). Metadata: path, heading path, line range, **domain (from the archive path)**, date,
  content hash.
- **Sync:** incremental, based on mtime plus hash; at the end of every consolidation; a <50ms
  staleness check before a query, with live grep as the fallback when stale. If the index breaks,
  behaviour *degrades* rather than becoming wrong; deleting and rebuilding it is always legitimate.
- **Filter mandatory:** the search tool requires a `--domain` flag; the unfiltered mode needs an
  explicit `--all` and its output is domain-labelled.

---

## 8. Privacy and security

An honest threat model: the harness LLM already sees everything during distillation — that is a
trust decision made when the harness was chosen. The real targets are:

1. **`secret/` (a binary model):** content is either in the system or in `secret/`. `secret/` does
   not enter consolidation, is not embedded (v2), and only a human touches it. A distilled file may
   link to it but may not take content from it — which is structurally guaranteed, because
   consolidation never reads it. (Three-level sensitivity with inheritance linting was deferred to
   v2; the middle `private` tier only earns its keep alongside a vector index.)
2. **Third-party data:** other people's structured records (students' grades, clients' details) stay
   out of the corpus, in whatever institutional system owns them; anything that must come in is
   de-identified. Role-based phrasing usually suffices.
3. **Remote hygiene:** the repository is either local-only (plus an encrypted backup) or on a
   private remote; a pre-push check validates the remote URL against an allowlist. The repository
   lives outside sync folders (iCloud, Dropbox).

---

## 9. Worst-case analysis and design invariants

| Risk | Likelihood/Impact | Main defence | Detection | Recovery |
|---|---|---|---|---|
| Two namesakes merging | H/H | Alias-uniqueness lint error; mechanical namesake pre-rule; merge is an approval gate | Golden-set trap questions | Revert that commit; separate via provenance; worst case, re-distil from the archive |
| The root file bloating into "a summary of everything" | H/H | No facts in root + budget lint; volatile → state.md | Lint | Prune the root |
| Stale status ("active" but finished) | H/M | Consolidation sweep for "updated is old and status is active" | The same sweep | Verify or close |
| Consolidation hallucination | M/H | Mandatory link on archive-sourced facts; human diff review in v1; no-deletion rule | Diff review; monthly loss audit | Revert the commit; re-distil from source |
| Consolidation deleting too much | M/M→L | No-deletion rule; sourceless content loss is an approval gate | Lint (traces of vanished lines) | Revert |
| Index/file bloat (2 years, 10k files) | H/H | Budgets are numbers in lint; closed files collapse to one line; chronological records stay out of indexes | Budget lint + size trend in the commit message | Split / summarise / archive |
| Two machines colliding | M/M | Machine-suffixed disjoint inboxes; consolidation on one machine, pull required | git | Markdown merges are human-resolvable |
| Vector index staleness (v2) | H/M | Hash-based sync; index outside git, derived per machine | `--check` | Delete, rebuild |
| Sensitive data leaving the machine | L/H (irreversible) | Local embedding as the only path; structural `secret/` exclusion; pre-push allowlist | Embed audit (v2) | Can be deleted locally — had it gone to an API, it could not |

**The invariants (the system's constitution — written at the top of `rules/format.md`):**

1. L2 is append-only and immutable; L1 can always be re-derived from it.
2. Every consolidation is one atomic commit; a risky operation gets its own commit.
3. The single source of truth for "processed" is file location; there is no separate state file.
4. Lint is mechanical, is the only gate, and is identical for humans and models.
5. There is no deletion; forgetting = moving to History/archive + dropping from the index.
6. The root file holds no facts; volatile context lives in `state.md`.
7. Single-home: a fact has one home, everything else is a link. Ambiguous bare names are a lint error.
8. Budgets are numbers (in characters) and they live in lint.
9. Data leaving the machine is default-deny: local embeddings, `secret/` exclusion, remote allowlist.
10. Only consolidation (and the human) writes to `domains/`, `people/`, the root and `state.md`.

### 9.1 The v1 mechanical toolkit — two scripts

- **`lint.py`** — three rule classes: (1) frontmatter parse + enums + required fields (configured
  from `format.md`), (2) `[[link]]`/path target existence + alias uniqueness, (3) character budgets.
  A consolidation commits only on green.
- **`eval.py`** — the golden-set runner: question → answer → correctness (scored by hand) plus turn
  count and token cost logging.

(A full seven-script set — index_rebuild, embed_sync, staleness, mv_note, metrics — was deliberately
deferred: staleness is one grep line inside the consolidation task, metrics are `wc` output in the
commit message, renaming is close to forbidden anyway, and embedding is a v2 concern.)

---

## 10. Measurement and success criteria

### 10.1 The golden set (primary, and the only set)

**20+ questions** from your own life, versioned in git, where an old question is never deleted:

| Category | Count | Note |
|---|---|---|
| Single-fact extraction | 6 | "What is X's thesis topic?" |
| Multi-session synthesis | 3 | "What decisions did I make on project Y?" |
| Temporal | 3 | "Did I decide that before Z?" |
| Knowledge update | 3 | Must return the current value, not the old one |
| Abstention | 3 | Not in memory; the correct answer is "I don't know" |
| Confusion trap | 2+ | Namesakes or similar entities in different domains; a leak is an alarm |

Rules: mix languages if your memory is multilingual, with at least three cross-language questions;
**score by hand for the first three months** (it is far too easy to fool yourself with an LLM judge;
promote one only once it agrees with a human ≥90% of the time); cadence is **monthly**, about 30
minutes. Measurement budget: roughly one hour a month. Any measurement more expensive than that is a
YAGNI violation.

### 10.2 Thresholds

| Metric | v0 | v1 | v2 |
|---|---|---|---|
| Overall accuracy | ≥60% | ≥75% | ≥85% |
| Abstention (not inventing) | ≥70% | ≥80% | ≥90% |
| Knowledge update | — | ≥70% | ≥80% |
| Confusion leakage | ≤1 | 0 | 0 |
| Single-fact query median | ≤2 turns | ≤2 turns / ≤1,000 tok | same |
| Deep query p95 | — | ≤4 turns / ≤4,000 tok | same |

Also: measure the baseline once ("dump all of L1 into context") and pin it; the target is ≥5x
savings. If tokens fall but accuracy drops by ≥5 points, the optimisation is reverted. Consolidation
quality: pick 5 changed facts at random per run and compare them against their source (target
inventions: 0); once a month, audit 5 important facts for loss (≤1 of 5).

### 10.3 Risky assumptions and the order in which to test them

| # | Assumption | Cheapest test | Plan B if negative |
|---|---|---|---|
| R1 | LLM consolidation is trustworthy | 2 weeks, 5 hand-triggered runs, eyeball every diff | Approval gates become permanent (proposal mode stays the default) |
| R2 | Grep + progressive disclosure is enough; vectors can wait for v2 | Run the v0 golden set grep-only; watch cross-language and morphology questions | Add an English keyword/alias line convention to L1; if that fails, pull vectors into v1 |
| R3 | Hierarchy + links prevent mixing | The v0 trap questions | Tighten entity naming to be domain-qualified |
| R4 | The maintenance load is sustainable (abandonment is the number one cause of death) | 2 weeks of daily use; threshold ≤15 min/week | Simplify capture further, lower the consolidation frequency, prune the schema |
| R5 | The root can stay small | Log its size on every run; 800-token threshold | Split the root: a core plus an extended index read on demand |
| R6 | The golden set is not fooling us | Write some of the questions 2+ weeks after the event (natural forgetting is a realistic test) | Have a model generate questions from the archive and verify the answers by hand |

**Test R1 and R2 first** — v0 plus two weeks, roughly four hours of effort. A negative on either
changes the architecture; the others only change parameters.

---

## 11. Roadmap

### v0 — the first weekend (the "grep is enough" experiment)

Folder skeleton + `MEMORY.md` + `state.md` + the domain `_index.md` files + `rules/format.md`;
manual distillation (no consolidation); retrieval via Read/Grep/Glob and the protocol only; the
first 10 golden-set questions plus simple cost logging. **The goal is an experiment, not a
product:** testing R2 and R3 against real data.

### v1 — the lifecycle (3–4 weeks)

Append-only inbox + the capture instruction; hand-triggered single-phase consolidation (checkpoint →
LLM → lint → move → commit → diff review); approval gates; the fact grammar with `[void:]` and the
conflict rules; `lint.py` and `eval.py`; the full 20-question golden set.
**Not included:** vectors, scheduling, automated guards.

### v2 — depth (if the need is proven)

A local vector index over the archive (§7); scheduled nightly consolidation plus a mechanical guard
for sourceless loss (which replaces the human diff review as that becomes less frequent); and, if
needed, index_rebuild/embed_sync scripts, three-level sensitivity, and a human-calibrated LLM judge.

### Firmly deferred (the YAGNI list)

Knowledge graphs / graph DBs / PageRank · continuous observer and reflector daemons · automatic NER
· importance scoring and decay functions · embedding-based link suggestion · vectors for L1 · a
multi-model abstraction layer · due-date tracking · record-ID plumbing · concept entities · a
separate decision file type · an `attic/` waypoint · `state.json` · multi-phase consolidation · a
quarantine branch.

---

## 12. Positioning against the literature

| System | Taken | Rejected | Why |
|---|---|---|---|
| Claude Code memory | Root index + single-topic files + frontmatter — **the primary template** | — | The consumer is already this harness; convention compatibility is free |
| MemGPT / Letta | The two-layer split; letting the LLM edit memory | A separate runtime; self-editing on every turn | The harness exists; editing happens at consolidation |
| Zep / Graphiti | Temporal validity + provenance discipline | The graph DB | Markdown plus a grammar carries the same information; graph infrastructure is expensive for one person |
| A-MEM | Atomic notes + cross links | Embedding-based automatic linking | Consolidation writes links explicitly |
| HippoRAG | "Small index in front, heavy content behind" | Graph + PPR retrieval | Progressive disclosure does the same job on a filesystem |
| Mastra | Append-only capture; the aggressive distillation target | Continuous observer/reflector processes | Periodic consolidation does the same job |
| Mem0 | Giving add/update decisions to the LLM | A hosted API; extraction on every message | Data ownership; extraction happens in batch |
| Sleep-consolidation literature | Offline consolidation; selective forgetting | NREM/REM simulation | The metaphor guides; it does not dictate an architecture |
| LongMemEval | Five capability categories as the golden-set template; the abstention metric | — | Adopted directly as the evaluation framework |
| Hand-scored evaluation | Manual scoring, a versioned fixed set | Early trust in an LLM judge | Fooling yourself is the cheapest mistake to make |

---

## 13. UX principles

The core has to be "invisible but dependable": memory work never interrupts the user, never
surprises them, and can always account for itself. Ten rules:

### 13.1 External connections: read freely, never write without approval

- The harness's API connections (mail, calendar, drive) are **read sources**; the system reads them
  as it needs to, without asking the user again and again.
- **Writing to an external system** (sending mail, creating a calendar entry, changing a file,
  sending a message) requires **explicit approval, without exception** — every time, never
  generalised across a session.
- Data read from an external source is never written straight into L1; like everything else it goes
  through the inbox gate. The source appears as a trace on the fact line ("from calendar").

### 13.2 The short-term to long-term flow is visible and automatic

Session context (working memory) → inbox (short-term) → L1 via consolidation (long-term). The user
never makes a "where should this go" decision at capture time; the system decides what to promote
and what to forget during sleep (§2.1, §5.2).

### 13.3 Both query modes are first-class

Structural querying and semantic querying are both directly available; the escalation order is a
cost ordering, not a capability restriction (§6.2). The user can jump straight to semantic mode by
saying "search the archive".

### 13.4 Compression is a task, not a preference

Consolidation compresses as hard as it can on every run; budgets are targets, not ceilings. Because
the raw data sits in the archive, aggressive distillation is lossless — and the denser the distilled
layer, the cheaper every query.

### 13.5 New domains: allowed, but braked

For unfileable records the system **may propose** a new domain; the threshold (≥5 records on the
same theme), the approval gate and the rate limit (≤1 proposal per month) keep it from turning into
a junkyard (§5.2). Records below the threshold enter the nearest domain with a `(provisional)` note.

### 13.6 The rare-access tag

Files that will rarely be needed get `access: rare` in their frontmatter; they drop off the main
index list into a single summary line ("rare: N files — list: ..."). Retrieval reads them only on
an explicit request or during miss escalation, so the hot path stays thin.

### 13.7 Minimising interruption

Memory work never interrupts the user: questions accumulate in `questions.md` (cap 5), at most one
question surfaces per session, and consolidation proposals are presented in one batch. There is no
rain of individual notifications.

### 13.8 Transparency: "how do you know that?"

Because every distilled fact carries a date or a provenance trace, the source can be shown in one
step when asked. "What do you have about me?" is answered with domain summaries — the memory is not
a black box, it is readable markdown.

### 13.9 Correction is one step

When the user says "that's wrong", the correction goes into the inbox **at the highest trust class**
(the user's own statement) and is processed with the `[void:]` grammar at the next consolidation; if
it is urgent, the file is corrected by hand immediately (human writing is a first-class path). You
do not argue with the user; you show the source and fix it.

### 13.10 "Forget that"

An explicit deletion request from the user is the **only legitimate real deletion** in the system:
the fact is removed from the distilled layer and from the archive; if git-history cleaning is also
wanted, it is done separately and with approval (a heavy operation). The system's own forgetting is
always a move, never a deletion (§5.4).

---

## 14. Open questions

1. Which model should run consolidation? (Quality versus cost: distillation errors compound, so a
   strong model is recommended; decide by measurement.)
2. Which query classes should read `state.md`? (In v0, "every memory-related task"; narrow it if
   measurement shows the load is unnecessary.)
3. How automatic should inbox capture be in the harness — a summary at the end of each session, or
   in the moment? To be settled by trying it in v1.

---

## 12. What 25 days of running this taught us [2026-09-15]

The reference deployment ran v1 for 25 days and measured it. The core claim held: L1 grew from
42 files / 23 KB to 70 files / 102 KB, and **the cost per query stayed flat** (~7 KB — one index
plus at most two files). Three things did not work, and each fix follows the same shape.

**1. Budgets silently became ceilings.** `consolidation.md` had said "budgets are targets, not
ceilings; aggressive distillation is lossless" from day one. After 25 days, 20 of 61 topic files
sat in the top 5% band of the ceiling, **none went over**, and two sat exactly at it. Consolidation
was optimising "do not turn the lint red" rather than "distil" — and because lint was green, nobody
saw it. The lesson generalises: **a prose rule does not change behaviour where no mechanism checks
it.** The fix is `sleep-audit.py`'s BLOAT and RATCHET checks plus a per-run compression quota.

**2. Unattended sleep had no quality gate.** Once the nightly scheduled run was enabled, the human
diff review disappeared and nothing replaced it. `sleep-audit.py` became the second gate after
lint. Note how it was validated: the first version compared only *date stamps*, and it **failed its
own negative test** — deleting three dated lines left it green because another line carried the
same date. It now compares content. **Writing a guard is not enough; you have to try to break it.**

**3. The question queue froze.** A five-item cap plus a one-question-per-session drip rule meant the
same five questions sat untouched for eleven days, four of them tied to classes that started in the
meantime. A cap does not shrink a human-facing queue, it freezes it. The cap is gone;
`question-pick.py` picks by effective due date and consolidation closes overdue items with an
explicit status quo.

Two further mechanisms came out of the same review. **Rule routing** moves rules out of the
always-loaded router into `memory/rules/`, which only works because lint now catches an *orphan
rule* (a rule file the router never names) and an *orphan tool* (a script missing from
`tools/_index.md`) — a capability that dies quietly is a bug, not a silent gap. And the
**inflation brake** mechanises the trigger rather than the judgement: `AGENTS.md` carries a lint
budget, so once it is red, a new rule cannot be added until an old one comes out.
