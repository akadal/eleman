# INSTALL.md — the first-run setup interview

**This file is executed by an AI agent, not by a human.** When `memory/MEMORY.md` does not exist,
`AGENTS.md` §0 sends the agent here. If you are a human reading this, you do not have to do
anything: open the repository in your agent (Claude Code, Codex, Cursor, or anything else that
reads `AGENTS.md`) and say hello. Setup will start on its own.

---

## Instructions for the agent

You are setting up a personal memory core for the person you are talking to. At the end of this
interview the repository stops being a template and becomes *their* brain. Take it seriously and
keep it short — six steps, most of them one message each.

**Rules for how you run this:**

- Ask the questions in **batches**, not one at a time. A setup that takes twenty round trips is a
  setup people abandon.
- Every question has a sensible default. Anyone can answer "skip" or "you decide" and you keep going.
- Do not invent facts about the user. Everything you write in step 5 has to come from something
  they actually told you.
- Do not read or fetch anything they did not offer.
- The whole thing should take under ten minutes.

---

### Step 0 — Safety check (do this before asking anything)

Personal memory belongs in a **private** repository. Run:

```bash
git remote -v
```

Then verify three things, and stop to resolve anything that fails:

1. **`origin` is the user's own repository**, not the upstream template. If `origin` still points
   at the project this was copied from, tell them: they need their own repository, because
   everything they say from here on gets committed and pushed to it. Do not continue until it is
   fixed. (`gh repo create <name> --private --source=. --remote=origin` is one way.) Then keep
   the template as `upstream`, so every sleep can take mechanism updates
   (`docs/UPGRADING.md`): `git remote add upstream <template URL>`. For a "Use this template"
   copy, `gh repo view --json templateRepository` names it.
2. **The repository is private.** If you can check (`gh repo view --json isPrivate -q .isPrivate`),
   check. If it is public, say so plainly and stop: a public memory core exposes everything they
   are about to tell you. Do not continue until it is private or they explicitly, knowingly accept
   the risk in their own words.
3. **Python 3 is available** — and actually *runs*. Do not settle for `command -v python3`: on
   Windows that name is usually a Microsoft Store "app execution alias" stub, so the lookup
   succeeds while running it prints `Python was not found…` and exits **49**. Test by executing it:
   `python3 -c "import sys"`, falling back to `python` and then `py`. Whichever one exits 0 is the
   interpreter to use in the commands you give them. If none works, note that `lint.py` and
   `eval.py` will not run; everything else still works. Do not block on it.

### Step 1 — Language

Ask which language they want. This sets two things: the language you reply in, and the language the
memory content is written in. Default is English.

Tell them the one thing that is *not* configurable, in a single sentence: directory names, file
names, frontmatter keys, enum values (`active`, `paused`, `closed`) and section headings (`## Hot`,
`## Files`, `## History`) stay in English because they are schema, and the linter checks them.
Everything they will ever read — facts, summaries, your replies — is in their language.

If their language packs noticeably fewer characters per token than English (agglutinative or
non-Latin scripts, for instance), lower `char_per_token` in the `lint-config` block of
`memory/rules/format.md` and scale `budgets_chars` down by the same ratio. Budgets exist to bound
tokens; characters are only the mechanical proxy.

### Step 2 — Who they are

Ask, in one message:

- What should you call them?
- What do they do — the two-line version, work and anything else that takes up their time?
- Is there anything you should always keep in mind when working with them? (How they like to be
  talked to, what they never want you to do.)

Then offer, explicitly as optional:

> If you want me to start with a bit of context instead of a blank page, you can paste links
> (a personal site, a GitHub profile, a public CV) or any text you have written about yourself.
> I will only read what you give me, and I will only keep what looks durable.

If they give you links or text: read it, and distil it into a handful of durable facts. Durable
means "still true in a year" — a role, a field, a long-running project, a language they work in.
Not news, not a current to-do, not anything you inferred rather than read. If they give you
nothing, that is a completely normal way to start; the memory fills up through use.

### Step 3 — Domains

Domains are the top-level folders that keep subjects from bleeding into each other. Propose a set
based on what they told you in step 2, and say they can change it.

A reasonable default:

| Domain | Scope |
|---|---|
| `personal` | preferences, identity, routines |
| `people` | *(not a domain — the entity layer, always present)* |
| `work` | job, projects, decisions |
| `projects` | side projects, things they build |
| `health` | health records |
| `ideas` | raw ideas, nothing committed yet |

Add `family` if they mentioned a household. Add a domain matching their field if the whole point of
their memory is that field (`research`, `writing`, `clients`, `studies`).

Guidance to give them in one line: four to eight domains is the sweet spot. Too few and everything
lands in one bucket; too many and you spend your life deciding where things go. Opening a domain
later is cheap — a folder and an index line.

Domain folder names are ASCII kebab-case, like every other name in the repository.

### Step 4 — Machine alias

Inbox files are named `<YYYY-MM-DD>--<machine>.md`. The machine suffix is what makes two computers
writing on the same day a non-event instead of a merge conflict.

Propose a short alias for the machine you are running on (`laptop`, `desktop`, `work-mac`) — derive
a sensible guess from the hostname and let them correct it. Write it to `memory/.machine`, which is
gitignored, because it is per-machine and must not sync.

### Step 5 — Write the memory core

Now create the files. Templates are in `setup/templates/`; `memory/rules/format.md` is the schema
authority and wins any disagreement.

| Create | From | Notes |
|---|---|---|
| `memory/MEMORY.md` | `setup/templates/MEMORY.md` | Identity lines, the domain table, the protocol. **No facts, no names of other people, no dated status.** |
| `memory/state.md` | `setup/templates/state.md` | Starts nearly empty; consolidation fills it. |
| `memory/questions.md` | `setup/templates/questions.md` | Empty. |
| `memory/todo.md` | `setup/templates/todo.md` | Empty. |
| `memory/domains/<d>/_index.md` | `setup/templates/domain-index.md` | One per domain from step 3. |
| `memory/people/_index.md` | `setup/templates/people-index.md` | The alias table, empty for now. |
| `memory/inbox/<today>--<machine>.md` | `setup/templates/inbox-log.md` | The first log: what they told you in step 2, as a single `## HH:MM` block. |
| `memory/.machine` | — | Just the alias, one line. Gitignored. |

Two things worth being careful about:

- **The durable facts from step 2 go into the inbox, not into domain files.** The write gate applies
  from the very first minute (invariant #10) — you capture, consolidation distils. The only
  exception is `MEMORY.md` itself, whose identity lines are a static contract rather than a fact.
- **`MEMORY.md` must stay under its budget** (3,200 characters). It is the tax paid on every single
  session. If it does not fit, the identity lines are too long, not the table.

Then run the linter and commit:

```bash
python3 memory/tools/lint.py
git add -A && git commit -m "setup: initial memory core" && git push origin main
```

If lint is red, fix it before committing. Green is the only state from which this repository moves.

### Step 6 — Tell them what happens now

Close with a short message, not a manual. It needs to carry four things:

1. **Capture is automatic.** They talk normally; anything worth keeping lands in the inbox. They
   never decide where something goes.
2. **Consolidation is the distillation step.** Say "run a consolidation" (or `/sleep`, if their
   harness has slash commands) and everything in the inbox gets sorted, merged, compressed and
   committed. It also happens on its own if the inbox has been sitting for more than a day.
3. **Everything is theirs, in plain markdown, in git.** Nothing is hidden. "What do you know about
   me?" is answerable at any time, and so is "where did you get that?".
4. **Optional extras exist, and they can wait**: external read taps
   (`memory/tools/integrations/`), the WoS + Scopus literature search for academic work
   (`memory/rules/literature.md`), the golden-set evaluation (`memory/tools/golden-set.md`), and
   mechanism updates from upstream (`docs/UPGRADING.md`).

Do not offer to configure the optional pieces now. Day one is for capture.

---

## Re-running setup

Setup is defined as done when `memory/MEMORY.md` exists. To start over, delete the generated files
(`memory/MEMORY.md`, `memory/state.md`, `memory/questions.md`, `memory/todo.md`, the contents of
`memory/domains/` and `memory/people/`) and say "run setup". Nothing in `memory/inbox/` or
`memory/archive/` is touched by setup — captured material survives a re-run.
