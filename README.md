<h1 align="center">eleman</h1>

<p align="center"><strong>Not intelligence. Memory.</strong></p>

<p align="center">
  <em>A personal memory core for AI assistants — plain markdown, plain git, no service to run.</em>
</p>

<p align="center"><a href="https://eleman.akadal.tr">eleman.akadal.tr</a> · <a href="https://eleman.akadal.tr/tr/">Türkçe</a></p>

<p align="center">
  <a href="LICENSE"><img alt="MIT licence" src="https://img.shields.io/badge/licence-MIT-blue.svg"></a>
  <img alt="stdlib only" src="https://img.shields.io/badge/dependencies-none-brightgreen.svg">
  <img alt="works with any agent" src="https://img.shields.io/badge/harness-agent--agnostic-8a2be2.svg">
  <a href="https://doi.org/10.5281/zenodo.23975338"><img alt="DOI" src="https://zenodo.org/badge/DOI/10.5281/zenodo.23975338.svg"></a>
</p>

---

Your AI assistant forgets you every morning. The usual fixes are to paste your life into the prompt
(expensive, and everything bleeds into everything else) or to hand it to a hosted memory service
(someone else's database, someone else's terms).

eleman is the third option: **a repository your assistant reads and writes as its long-term memory.**
Markdown files, a directory convention, three small scripts, and git underneath. No daemon, no
database, no API key. Any agent that can read files can use it — Claude Code, Codex, Cursor, or the
next one.

```
you talk ──▶ inbox/  ──[ sleep consolidation ]──▶ domains/  ──▶ answers
             raw, append-only                     distilled, budgeted
             immutable                            re-derivable, linted
```

## Why it is built this way

**Two layers.** Everything you say lands raw in an append-only log. Nothing is filed, tagged or
classified at that moment — friction at capture time is what kills a memory system. Later, one
consolidation pass distils those logs into small, budgeted topic files. The raw layer is immutable,
so the distilled layer can always be rebuilt from it, and aggressive compression is lossless.

**One write gate.** During a conversation, only the inbox is written. Domain files, people files and
the root are touched by consolidation alone. Half-finished updates stop being possible.

**A fact has exactly one home.** Everything else links to it. This is the structural cure for
context bleed: two copies of the same fact cannot exist, so a question about your family cannot drag
in your work.

**Cost is measured in tool calls, not tokens.** Every read re-bills the whole context, so the design
optimises for *few turns*: a root table routes to a domain index, the index line carries the full
path, and a typical question is answered in one or two reads.

**Time is in the grammar.** `- [2026-03-14]` happened, `- [2026-03-14→]` still true,
`- [t1→t2]` was true then, `- [void: t]` was never true. An update is not a correction — a memory
that cannot tell those apart turns its own mistakes into history.

**Lint is the only gate.** Schemas, enums and budgets live in one file, and the linter is configured
from that same file, so the schema and its enforcement cannot drift apart. Nothing gets committed
red — and the rule is identical whether a human or a model wrote the change.

**It says "I don't know".** Abstention is a first-class outcome and a measured metric. Making
something up is the expensive failure.

## Quick start

You need a repository of your own — this one is a template, not a service.

1. **Click "Use this template" → "Create a new repository" → set it to Private.**
   Your memory core will hold your family, your health, your work. It belongs in a private
   repository. (Do not *fork* for personal use: a fork of a public repository is public, and GitHub
   will not let you flip it to private afterwards.)

2. **Clone it and open it in your agent.**

   ```bash
   git clone https://github.com/<you>/<your-repo>.git && cd <your-repo>
   claude          # or codex, or whatever reads AGENTS.md
   ```

3. **Say hello.**

   The agent notices there is no `memory/MEMORY.md`, reads [`INSTALL.md`](INSTALL.md) and runs a
   short setup interview: your language, who you are, which domains you want, a name for this
   machine. Under ten minutes. Then it commits.

That is the whole installation. There is nothing to run, nothing to install, and no configuration
file to hand-edit.

<details>
<summary>Prefer the command line?</summary>

```bash
gh repo create my-memory --template <owner>/eleman --private --clone
cd my-memory && claude
```

</details>

## What using it looks like

```
you   Talked to Alex today — the Atlas migration slipped to October.
      Also, I finally booked the dentist for the 20th.

      → appended to memory/inbox/2026-03-14--laptop.md. Nothing else happens.
        No filing question, no "which project is this?", no interruption.

...a few days later...

you   Where did Atlas land?

      → root table says "work" → reads memory/domains/work/_index.md
      → the answer is on the index line. One read.

you   Run a consolidation.

      → triage, sort, merge, compress, resolve conflicts, refresh indexes
      → lint → green → one atomic commit → processed logs move to the archive
```

Ask "how do you know that?" and it shows you the line and its source. Ask "what do you have about
me?" and it walks the domain summaries. It is all markdown; you can read the whole thing yourself in
an editor, and `git log` is the audit trail.

## What is in the box

| Path | What it is |
|---|---|
| [`AGENTS.md`](AGENTS.md) | The operating rules your agent loads every session — the constitution |
| [`INSTALL.md`](INSTALL.md) | The first-run setup interview (executed by the agent, not by you) |
| [`memory/rules/format.md`](memory/rules/format.md) | The single schema authority: schemas, enums, budgets, fact grammar |
| [`memory/rules/consolidation.md`](memory/rules/consolidation.md) | The consolidation task definition |
| [`memory/tools/lint.py`](memory/tools/lint.py) | Mechanical checks — frontmatter, links, alias uniqueness, budgets |
| [`memory/tools/eval.py`](memory/tools/eval.py) | Golden-set runner: is the memory actually getting better? |
| [`docs/DESIGN.md`](docs/DESIGN.md) | The full design contract — every decision and why it was made |
| [`docs/UPGRADING.md`](docs/UPGRADING.md) | Pulling mechanism improvements without touching your memory |

Python 3 with the standard library. No packages, no lockfile, no build step.

## Privacy

The honest threat model is on the table in [`docs/DESIGN.md`](docs/DESIGN.md) §8: whichever model
runs your consolidation sees your memory during distillation. That is a trust decision you make when
you pick a harness, and no amount of file-shuffling changes it. What the design *can* control, it
does:

- **Keep the repository private.** Setup checks, and refuses to continue on a public one.
- **`secret/` is structurally excluded** — never read by consolidation, never embedded, gitignored
  by default. Distilled files may link to it; they cannot take content from it.
- **Data leaving the machine is default-deny.** Semantic search (v2) uses local embeddings only, and
  a cloud embedding path does not exist in the codebase — the best prevention is the absence of the path.
- **External systems are read-only by default.** Reading your calendar is automatic; writing to it
  is never automatic. The optional Google tap ships with no send capability *by construction*, not
  by policy.
- **Nothing is hidden from you.** No binary blobs, no opaque index, no vendor account. Delete a file
  and it is gone.

## Compatibility

Anything that reads `AGENTS.md` (or `CLAUDE.md`, which points at it) and can read and write files.
It has no dependency on any one vendor's memory feature, MCP server or plugin system — that is
deliberate, so that the same repository works from a different machine with a different assistant
tomorrow.

## Website and enterprise

The project site is [eleman.akadal.tr](https://eleman.akadal.tr). Companies that want eleman set up
on their own servers, under their own rules, can reach the maintainer through the form there.

## Contributing

Improvements to the *mechanism* are very welcome; your memory content is yours and never leaves your
repository. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

The bar for a new feature is the YAGNI list in [`docs/DESIGN.md`](docs/DESIGN.md) §11. This project
has said no to knowledge graphs, observer daemons, importance-decay functions and due-date tracking
on purpose. If a proposal is on that list, it needs to explain what changed.

## Citing eleman

If eleman helped your work, please cite it. The DOI below covers every version, so all citations
stay on one record; name the version you used in your text.

> Akadal, E. (2026). *eleman: A personal memory core for AI assistants* [Computer software].
> Zenodo. https://doi.org/10.5281/zenodo.23975338

BibTeX and other formats come from the "Cite this repository" button on the GitHub page, which
reads [`CITATION.cff`](CITATION.cff).

## Licence

MIT — see [`LICENSE`](LICENSE).
