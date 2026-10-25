# Capability index — `memory/tools/`

The single answer to "what do I have?". `AGENTS.md` points here; **tool detail is not repeated
there** (invariant #7, one home per fact). Each tool's rationale and usage live in its own
docstring — this file carries only *what it does* and its **trigger** (when to run it).

Lint checks both directions: every `.py`/`.sh` under `memory/tools/` must appear here, and every
path here must exist. A tool without a trigger dies silently — that is why this file exists.

## Memory core

- `memory/tools/lint.py` — schema, link targets, alias uniqueness, character budgets; also checks
  the rule files themselves (router/rule) and catches orphan rules and orphan tools.
  **Trigger:** before every consolidation commit; whenever a memory file is edited by hand.
- `memory/tools/sleep-audit.py` — mechanical quality audit of the consolidation diff: fabrication,
  loss, bloat, ratchet, L2 integrity, delegated sleep tasks. **Trigger:** during consolidation,
  after lint and before the commit (the second gate); `--last` to audit a past sleep commit.
- `memory/tools/sleep-check.sh` — sleep trigger; exit 0 means a run is due. Says "NO SLEEP" while
  a fresh lock exists. `--nightly`: skips the once-a-day test, so the scheduled run is
  unconditional (AGENTS.md §6c). **Trigger:** at the start of every session; `--nightly` from
  `sleep-run.sh`.
- `memory/tools/sleep-run.sh` — scheduled, unattended sleep runner: pull → due? → lock → harness →
  release. It does no distilling itself. **Trigger:** a scheduler on **one** machine only.
- `memory/tools/upstream-sync.py` — takes mechanism updates from the template: files never
  edited here are updated in their own commit, customised ones are listed in the inbox, lint
  red rolls it back. No-op without an `upstream` remote. **Trigger:** every sleep (step 0b of
  `rules/consolidation.md`, and `sleep-run.sh`); `--check` to just look.
- `memory/tools/question-pick.py` — picks the question of the day by effective due date;
  `--asked` bumps the counter. **Trigger:** session start; immediately after asking (`--asked`).
- `memory/tools/eval.py` — golden-set runner; logs accuracy, turns and tokens to `eval-log.csv`.
  `kayit`/`record` subcommand logs non-interactively. **Trigger:** whenever the north-star metric
  is measured — after a schema change or a change in distillation behaviour, **and whenever the
  newest row in `eval-log.csv` is more than 30 days old**. The prose trigger alone does not
  fire: in the original deployment measurement died silently twice (25 and 35 days), because
  "did distillation behaviour change?" is a question nobody notices asking. Put the calendar
  check wherever your health check lives.
- `memory/tools/session-wrapup.py` — closes a session on purpose: writes the agent's own
  wrap-up to the inbox with a `(wrapup)` trace, runs lint as the gate, commits and pushes. Runs
  no consolidation; stamps the block when other sessions were open at the same time.
  **Trigger:** the owner says the session is over ("wrap up", "that's a wrap", "stop"). Bind a
  slash command to it if your harness has them.
- `memory/tools/golden-set.md` — the versioned question set; an old question is never removed.

- `memory/tools/delegate.py` — hands bulk, low-judgement work to an external agent CLI. Roles
  are configuration (`chain`, `backup`; `ASSISTANT_DELEGATE_*` then `memory/delegate.ini`), so no
  vendor is hardcoded. Never opens the repository root or `secret/`; exit 3 means the chain is
  exhausted, give the work to the backup. **Trigger:** work that is high in volume and low in
  judgement (AGENTS.md section 12).

## Integrations

- `memory/tools/secret-put.py` — the owner types a key into their own terminal; it lands in
  `secret/<name>.json`. **Trigger:** every time a token or key is needed from the owner.

- `memory/tools/integrations/google/` — optional, read-first Google connectors (calendar, tasks,
  mail, drive). **Trigger:** only when the owner has configured credentials; see the directory's
  own README. Writing outward is never automatic.

- `memory/tools/integrations/notion/` — optional Notion notebook: `notebook.py` `write`, `append`,
  `read`, `list`; Markdown in, Markdown out, a `(notebook)` trace in the inbox. **Trigger:** the
  owner says "take a note", "write it in the notebook", "look at that note"
  (`memory/rules/notebook.md`).
