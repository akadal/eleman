---
name: literature
description: Use for any academic work that rests on the literature - a literature review, "what has been done on X", a gap analysis, related work for a paper or thesis, sources for a reviewer reply. The source is the Web of Science and Scopus APIs through memory/tools/literature-fetch.py, never web search or the model's own memory. The rule body is memory/rules/literature.md.
---

# literature - binding file

This file holds **no rules** (AGENTS.md section 7: rules are harness-independent). It only binds
Claude Code's skill mechanism to the canonical rule, so the search starts on its own when the
topic comes up. Other harnesses reach the same rule through the routing table in AGENTS.md.

1. Read `memory/rules/literature.md`: source, evidence and query rules live there.
2. Run the search through the bridge; never write a crawler:

   ```bash
   python memory/tools/literature-fetch.py --topic "<topic>" --years 2020-2026 --max 50
   ```

   First time on a machine: `--doctor`. Missing keys: hand the owner the `secret-put.py`
   command from the rule, nothing else.
3. Read the outputs in the clone (`review.md`, `articles.csv`, `evidence_groups.json`); tie every
   claim to an evidence ID, mark cross-source records apart. Do not copy the corpus here.
4. Log what was searched and what came back in the inbox (AGENTS.md section 5).
