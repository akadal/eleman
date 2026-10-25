# notebook.md: "take a note", "write it in the notebook", "look at that note"

Tool: `memory/tools/integrations/notion/notebook.py` (setup in its README).

A report produced in a session dies with the session, and the owner cannot follow up on it. So the
result of a piece of research, a report or a decision goes into the owner's Notion notebook as a
new note. Each note has two readers: the owner, who follows up on it, and a fresh session, which
reads it and carries the work on from where it stopped. A note is a checkpoint.

## Consent: only on the owner's word

The agent goes to Notion only when the owner explicitly says so: no write, no addendum, no read.
The trigger phrases below are that word. On its own initiative the agent may only **offer**: when
a result is worth keeping, or an inbox `(notebook)` trace shows a note would help, it asks in one
sentence ("shall I put this in the notebook?", "shall I look at the X note?") and acts on a yes.
An offer is made once; left unanswered, it is not repeated and the work is not done. A yes covers
that note only, not the next one.

## Trigger

| The owner says | What happens |
|---|---|
| "take a note", "write it in the notebook", "put this in the notebook" | `write`: the session's result for that piece of work becomes a new note |
| "add to the note", "update the note" (for work already in the notebook) | `append`: a dated addendum at the end of the same note |
| "look at that note", "continue from the X note" | `read`: the note is read and the work goes on from it |
| "what is in the notebook" | `list` |

"Remember this" is not this rule: that is memory and goes to the inbox (AGENTS.md section 5). When
both are asked for, do both.

## Place and title

Notes live under the group page inside the notebook page named in `memory/secret/notion.json`.
The tool creates the group page on the first write. Nothing else in the notebook is written to.

A title starts with `YYYYMMDD`, followed by a name that says what the note is on its own:
`20261025 financing strategy for the house purchase`. It carries both subject and purpose; never
an empty word like "report", "notes" or "research". The date is the day the work was done. The
tool prefixes today when the date is missing and refuses fewer than three words after it.

One piece of work, one note. If the subject is already in the notebook (check with `list` or
`read`), new findings go into the same note with `append`; the tool refuses a duplicate title
anyway. A new question or a new phase gets a new note that names the old one.

## Template: the checkpoint

A note is complete enough for someone who never saw the session to carry on. Leave out a section
that would be empty.

```markdown
## Summary
The result first, two to four sentences. The note is useful even if only this is read.

## Context
What was asked and why. The owner's own sentence in quotes, if there is one.

## Findings
The body: report, comparison, table, calculation. Name it after the work: "Plan", "Result",
"Options".

## Decisions
Decisions taken, each with a one-sentence reason. A new session does not reopen them.

## Open items
What is not done, who holds it, what it depends on.

## To continue
The files a new session reads first (repository and full path), the command to run, the first step.

## Sources
Links, documents, data sources.
```

The tool adds the footer (time, machine, session, repository commit); do not write it by hand.

Write for the owner, who reads it: plain sentences, terms explained the first time they appear.
Lists and tables only for things that really are lists. "To continue" is written for the next
session and may be technical. A note is not a transcript: leave out the process, write the result
and what it rests on.

## Flow

1. Write the note as Markdown to a scratch file (outside the repository).
2. Run the tool:

   ```bash
   python memory/tools/integrations/notion/notebook.py write --title "20261025 ..." --file <scratch.md>
   ```

   For an addendum: `append "<search | url>" --file <scratch.md>`; headings inside an addendum use
   `###`, the tool adds the `## Addendum, <date>` heading.
3. The tool appends a one-line `(notebook)` trace to the inbox: title, first sentence of the
   summary, link. That is how the memory knows the note exists; the body is not copied into memory,
   its home is Notion (invariant #7). Then commit and push (AGENTS.md section 0).
4. Tell the owner in one sentence, with the link.

On "look at that note", run `read`. Without one clear match the tool prints candidates (exit 3):
pick from context, and if context cannot decide, ask the owner which one in a single sentence. A
note read back is a **snapshot**: the owner may have edited it in Notion, and the version read is
the one that counts, but its open items are checked against the inbox and the live state before
they are presented as current.

## Limits

Nothing from `memory/secret/`, no key, password or token goes into a note. No third party's
personal data (a student's grades, an ID number); anonymise it if it is needed. The notebook is
the owner's private workspace: the owner's word, or a yes to an offer, is all the approval needed; the tool never shares or
publishes a page, never edits the rest of the notebook and never deletes a note. A wrong note is
corrected with `append`; if it has to go, the owner removes it.
