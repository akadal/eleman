# MEMORY — entry point

Owner: {{NAME}} — {{ONE LINE: what they do, and anything that shapes how you work with them}}.
Language: {{LANGUAGE}}. Write memory content and replies in {{LANGUAGE}}; structure stays English.
If something is not in memory, say so plainly. Never invent a fact.
Current context: memory/state.md (read it first on any memory-related task).

## Domains

| Domain | Scope | Entry |
|---|---|---|
| {{domain}} | {{short scope}} | memory/domains/{{domain}}/_index.md |

People and organisations: memory/people/_index.md

## Protocol

1. READ: open the `_index.md` of the matching domain, then follow the full path on the line.
   Never read a folder wholesale; read a file under 600 tokens in full.
1b. STATUS QUESTION ("did it arrive / what happened / where does it stand / what's on me"):
   read `memory/inbox/` plus the last two days of `memory/archive/inbox/` first. An
   "Open/TODO" line in a dated document is a snapshot, not live truth; never answer from one
   file alone. **An external task or calendar list is a snapshot too:** never build an
   "outstanding work" list from it without checking it against the inbox first — today's log
   may already say the task is done. The same applies when you **build a plan**: on a project
   that runs across several sessions, never assemble the work list from a single source —
   scan every inbox file of that day for the project's name.
2. If a person or organisation is involved, check the alias table in memory/people/_index.md.
3. On a miss, search domain-scoped: `rg -m 20 "<term>" -g 'memory/domains/<d>/**'`
   (try the other languages this memory uses). Repo-wide search only with cross-domain intent.
4. Still nothing → say it is not in memory; offer the nearest partial match.
5. WRITE: add new information ONLY to `memory/inbox/<today>--<machine>.md` (append-only).
   Never edit domain or people files during a conversation; consolidation does that.
6. Schemas and grammar: memory/rules/format.md
7. TODO: memory/todo.md — a deliberately minimal list; items carry `[[wikilinks]]`.
8. SESSION START: `sh memory/tools/sleep-check.sh` — if it prints SLEEP DUE, run a
   consolidation (memory/rules/consolidation.md) before the real work.

<!-- TEMPLATE NOTES (delete this comment when you write the real file)
     - Replace every {{...}} placeholder. Add one table row per domain.
     - This file carries NO facts, NO other people's names, NO dated status. It is loaded on
       every single session, which makes it the most expensive file in the repository and the
       easiest place for context bleed to start. Volatile context belongs in state.md.
     - Budget: 3,200 characters, hard ceiling, enforced by lint. -->
