# Notion notebook: optional

A session's report dies with the session. This integration gives it a home that outlives it: when
the owner says "take a note" or "write it in the notebook", the result of the work becomes a
dated page in their own Notion notebook, and "look at that note" lets a fresh session read it and
carry on. A note is a checkpoint. The rule that governs it is `memory/rules/notebook.md`.

Standard library only, talking to the Notion REST API directly (no MCP server, for the same reason
as the Google integration: the repository has to work with any assistant on any machine).

## What it does

| Command | Direction | Notes |
|---|---|---|
| `write --title ... --file note.md` | write | New sub-page under the group page. Title starts with `YYYYMMDD`; an existing title is refused. |
| `append "<search \| url>" --file more.md` | write | Dated addendum at the end of an existing note. |
| `read "<search \| url>"` | read | The note as Markdown. Falls back to Notion's title search outside the group. |
| `list` | read | Notes in the group, newest first. |

Markdown goes in and comes back out: headings, paragraphs, bullets, numbered items, to-dos,
quotes, code, tables, dividers, inline formatting and links. Long text is split to Notion's limits
(2,000 characters per text run, 100 blocks per request). Each write ends with a footer (time,
machine, session, repository commit) and leaves a one-line `(notebook)` trace in the inbox, so the
memory knows the note exists without copying its body.

The script writes only under the group page. It never shares a page, never deletes one and never
edits the rest of the notebook.

## Setup

1. **notion.so/profile/integrations** → *New integration* → internal, with *Read content*,
   *Update content* and *Insert content*. Copy the secret.
2. In Notion, open the page you use as a notebook → *⋯* → *Connections* → add the integration.
   Notion shows an integration only the pages shared with it.
3. Store the key and the notebook page (its URL or id):

   ```bash
   python memory/tools/secret-put.py notion api_key notebook_page_id
   ```

   Optional: add `"group_title"` to `memory/secret/notion.json` to name the group page (default
   `eleman`). The group page is created on the first write.
4. Try it without touching Notion, then for real:

   ```bash
   python memory/tools/integrations/notion/notebook.py write --title "test note for the notebook" --file note.md --dry-run
   python memory/tools/integrations/notion/notebook.py list
   ```
