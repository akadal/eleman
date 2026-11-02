# literature.md: academic literature search

Read when the owner asks for academic work that rests on the literature: a literature review,
"what has been done on X", a gap analysis, related work for a paper or thesis, a reply to a
reviewer that needs sources.

## The source is the indexes, not the web

The evidence comes from the **Web of Science and Scopus APIs**: not web search, not Scholar
scraping, not the model's own memory. A model asked for references from memory produces papers
that do not exist; a web search misses most of what the indexes hold. One command:

```bash
python memory/tools/literature-fetch.py --topic "<topic>" --years 2020-2026 --max 50
```

The script is a **bridge, not a crawler**. It clones the public toolkit repository
`akadal/literature-review` (MIT) under `temp/literature-review` (AGENTS.md section 11), copies the
keys from `memory/secret/literature.json` into its `.env`, runs it in its own venv and prints the
full paths of the outputs. No search tool is ever written in this repository; a missing feature
becomes a flag on the bridge or a fix in the toolkit repository.

Do not wait to be asked twice: when the trigger above appears, the search is the first move, not
an offer. In Claude Code the skill in `.claude/skills/literature/` fires on its own; elsewhere the
routing table in AGENTS.md section 7 brings you here.

First use, once per machine: `--doctor` checks the clone, the keys and one live call per API.
If the keys file is missing, hand the owner the command and nothing else (AGENTS.md section 9):
`python memory/tools/secret-put.py literature wos_api_key scopus_api_key`. Scopus may refuse a
bare key off campus (401 with a correct key): the owner asks the library for an institution
token and stores it as the `scopus_insttoken` field with the same command.

## Which index for what

| Question | Source |
|---|---|
| Gap search (does this gap really exist?) | WoS only |
| Literature review (what has the field done?) | WoS + Scopus |
| arXiv, conference anthologies | discovery only, **never evidence** |

A gap claim never rests on a preprint. A preprint can refute a gap idea (look again) but cannot
support one: in front of a reviewer, the support is WoS.

## Reading the output

- Every article-level claim is tied to an evidence ID (`WOS:...`, `SCOPUS:...`) from
  `articles.csv` or `evidence_groups.json`. A record seen by both indexes is the strongest
  evidence; a single-source record is never presented as confirmed.
- Nothing is inferred beyond what the exported fields show (title, abstract, journal, year,
  citations, keywords). Missing data is reported, not smoothed over.
- A multi-word topic is AND-joined, not searched as a phrase: phrase-wrapping silently collapses
  recall ("blockchain tourism" as a phrase: 2 Scopus and 1 WoS records; AND-joined: 774 and 95).
  Quote inside the topic only for a deliberate phrase.
- The corpus (`review.md`, `articles.csv`, `evidence_groups.json`) **stays in the clone**; it is
  never copied here. What was searched, what came back and what was decided enters memory as one
  inbox block (AGENTS.md section 5).
- Screening a long result list is high-volume, low-judgement work: `memory/rules/delegation.md`.
