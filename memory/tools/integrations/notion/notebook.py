#!/usr/bin/env python3
"""notebook.py: write, append to, read and list notes in the owner's Notion notebook.

Why it exists: a report produced in a session dies with the session, and the owner cannot follow
up on it. When the owner says "take a note" or "write it in the notebook", the result of the work
becomes a new sub-page under a group page inside their Notion notebook. The note outlives the
session: "look at that note" lets a fresh session read it and carry on where the last one
stopped. A note is a checkpoint. Rule: memory/rules/notebook.md.

Usage:
  python memory/tools/integrations/notion/notebook.py write --title "20261025 financing strategy for the house purchase" --file note.md
  python memory/tools/integrations/notion/notebook.py append "<search | url | id>" --file addendum.md
  python memory/tools/integrations/notion/notebook.py read "<search | url | id>"
  python memory/tools/integrations/notion/notebook.py list [--n 20]

Input is Markdown (--file or stdin): headings, paragraphs, bullets, numbered items, to-dos,
quotes, code, tables, dividers, inline bold/italic/code/links. Reading converts Notion back to
Markdown. A title that does not start with YYYYMMDD gets today's date in front; a title that
already exists under the group is refused (no second copy: use `append`). Every write ends with a
footer (time, machine, session, repo commit) and leaves a one-line trace in the inbox.

Configuration: memory/secret/notion.json
  {"api_key": "...", "notebook_page_id": "...", "group_title": "eleman"}
  (python memory/tools/secret-put.py notion api_key notebook_page_id)
Notion only shows an integration the pages shared with it: share the notebook page. Does not
touch git; committing is the caller's job. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "memory" / "secret" / "notion.json"
INBOX = ROOT / "memory" / "inbox"
API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
GROUP_INTRO = ("Notes the assistant wrote into this notebook. Each note is the output of a "
               "session; \"look at that note\" lets a new session continue from here.")

TEXT_LIMIT = 2000    # Notion: characters per rich_text element
CHILD_LIMIT = 100    # Notion: blocks per request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def die(msg: str, code: int = 2):
    print(f"notebook: {msg}", file=sys.stderr)
    raise SystemExit(code)


# ---------------------------------------------------------------- config and API

def config() -> dict:
    if not CONFIG.exists():
        die("memory/secret/notion.json missing; run: python memory/tools/secret-put.py notion api_key notebook_page_id")
    c = json.loads(CONFIG.read_text(encoding="utf-8"))
    if not c.get("api_key") or not c.get("notebook_page_id"):
        die("notion.json needs api_key and notebook_page_id")
    c["notebook_page_id"] = parse_id(c["notebook_page_id"]) or die("notebook_page_id is not a Notion id or URL")
    c.setdefault("group_title", "eleman")
    return c


_CFG: dict | None = None


def cfg() -> dict:
    global _CFG
    if _CFG is None:
        _CFG = config()
    return _CFG


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    for attempt in range(5):
        r = urllib.request.Request(API + path, data=data, method=method, headers={
            "Authorization": "Bearer " + cfg()["api_key"],
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 409, 502, 503) and attempt < 4:
                time.sleep(float(e.headers.get("Retry-After") or 1 + attempt))
                continue
            die(f"Notion {method} {path}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:400]}", 1)
        except urllib.error.URLError as e:
            if attempt < 4:
                time.sleep(1 + attempt)
                continue
            die(f"cannot reach Notion: {e.reason}", 1)
    die("Notion request retries exhausted", 1)


def children(block_id: str) -> list[dict]:
    out, cursor = [], None
    while True:
        q = f"/blocks/{block_id}/children?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        r = call("GET", q)
        out += r["results"]
        if not r.get("has_more"):
            return out
        cursor = r["next_cursor"]


def page_url(pid: str) -> str:
    return "https://www.notion.so/" + pid.replace("-", "")


def parse_id(s: str) -> str | None:
    """Notion id from a URL or an id; None otherwise."""
    m = re.search(r"([0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12})(?:[?#]|$)", s.strip(), re.I)
    if not m:
        return None
    h = m.group(1).replace("-", "").lower()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def group_id(create: bool) -> str | None:
    name = cfg()["group_title"]
    for b in children(cfg()["notebook_page_id"]):
        if b["type"] == "child_page" and b["child_page"]["title"].strip().casefold() == name.casefold():
            return b["id"]
    if not create:
        return None
    r = call("POST", "/pages", {
        "parent": {"page_id": cfg()["notebook_page_id"]},
        "properties": {"title": {"title": [{"text": {"content": name}}]}},
        "children": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": text_parts(GROUP_INTRO)}}],
    })
    return r["id"]


def notes(gid: str) -> list[dict]:
    return [{"id": b["id"], "title": b["child_page"]["title"], "created": b["created_time"]}
            for b in children(gid) if b["type"] == "child_page"]


# ---------------------------------------------------------------- Markdown -> Notion

def text_parts(s: str, ann: dict | None = None, link: str | None = None) -> list[dict]:
    """Split plain text into rich_text elements of at most 2000 characters."""
    out = []
    for i in range(0, len(s), TEXT_LIMIT):
        o = {"type": "text", "text": {"content": s[i:i + TEXT_LIMIT]}}
        if link:
            o["text"]["link"] = {"url": link}
        if ann:
            o["annotations"] = dict(ann)
        out.append(o)
    return out


INLINE = re.compile(
    r"(?P<code>`[^`\n]+`)"
    r"|(?P<bold>\*\*(?P<bold_i>.+?)\*\*)"
    r"|(?P<strike>~~(?P<strike_i>.+?)~~)"
    r"|(?P<link>\[(?P<link_t>[^\]\n]+)\]\((?P<link_u>[^)\s]+)\))"
    r"|(?P<ital>(?<![\w*])\*(?![\s*])(?P<ital_i>.+?)(?<![\s*])\*(?![\w*]))"
    r"|(?P<ital2>(?<!\w)_(?![\s_])(?P<ital2_i>.+?)(?<![\s_])_(?!\w))"
    r"|(?P<url>https?://[^\s<>()\[\]]*[^\s<>()\[\].,;:!?\"'])"
)


def inline(s: str, ann: dict | None = None) -> list[dict]:
    ann = dict(ann or {})
    out, i = [], 0
    for m in INLINE.finditer(s):
        if m.start() > i:
            out += text_parts(s[i:m.start()], ann or None)
        if m.group("code"):
            out += text_parts(m.group("code")[1:-1], {**ann, "code": True})
        elif m.group("bold"):
            out += inline(m.group("bold_i"), {**ann, "bold": True})
        elif m.group("strike"):
            out += inline(m.group("strike_i"), {**ann, "strikethrough": True})
        elif m.group("link"):
            u = m.group("link_u")
            if re.match(r"(https?|mailto):", u):
                for o in inline(m.group("link_t"), ann):
                    o["text"]["link"] = {"url": u}
                    out.append(o)
            else:  # local path: Notion accepts no such link, keep it as text + code
                out += inline(m.group("link_t"), ann)
                out += text_parts(" (", ann or None) + text_parts(u, {**ann, "code": True}) + text_parts(")", ann or None)
        elif m.group("ital"):
            out += inline(m.group("ital_i"), {**ann, "italic": True})
        elif m.group("ital2"):
            out += inline(m.group("ital2_i"), {**ann, "italic": True})
        elif m.lastgroup == "url":
            out += text_parts(m.group("url"), ann or None, link=m.group("url"))
        i = m.end()
    if i < len(s):
        out += text_parts(s[i:], ann or None)
    if len(out) > 100:  # Notion: at most 100 rich_text elements per block; formatting is dropped
        out = text_parts("".join(o["text"]["content"] for o in out))
    return out


LANGS = {"py": "python", "python": "python", "sh": "shell", "bash": "bash", "shell": "shell",
         "zsh": "shell", "ps1": "powershell", "powershell": "powershell", "js": "javascript",
         "javascript": "javascript", "ts": "typescript", "typescript": "typescript", "json": "json",
         "yaml": "yaml", "yml": "yaml", "md": "markdown", "markdown": "markdown", "sql": "sql",
         "html": "html", "css": "css", "go": "go", "java": "java", "c": "c", "cpp": "c++",
         "c++": "c++", "cs": "c#", "csharp": "c#", "rust": "rust", "r": "r", "xml": "xml",
         "diff": "diff", "dockerfile": "docker", "docker": "docker", "mermaid": "mermaid",
         "latex": "latex", "tex": "latex", "toml": "toml", "ini": "plain text", "solidity": "solidity"}


def block(kind: str, text: str | list, **extra) -> dict:
    rt = text if isinstance(text, list) else inline(text)
    return {"object": "block", "type": kind, kind: {"rich_text": rt, **extra}}


def table_cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
LIST_ITEM = re.compile(r"^(?P<indent>[ \t]*)(?:(?P<mark>[-*+])|(?P<num>\d+)[.)])\s+(?P<text>.*)$")


def md_blocks(md: str) -> list[dict]:
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[dict] = []
    para: list[str] = []
    last_item: dict | None = None  # previous top-level list item, for nesting

    def flush():
        if para:
            out.append(block("paragraph", " ".join(x.strip() for x in para)))
            para.clear()

    i = 0
    while i < len(lines):
        s = lines[i]
        st = s.strip()

        if st.startswith("```"):
            flush(); last_item = None
            lang = LANGS.get(st[3:].strip().lower(), "plain text")
            code, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i]); i += 1
            out.append(block("code", text_parts("\n".join(code)) or text_parts(" "), language=lang))
            i += 1
            continue

        if not st:
            flush(); i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", st)
        if m:
            flush(); last_item = None
            out.append(block(f"heading_{min(len(m.group(1)), 3)}", m.group(2).strip().rstrip("#").strip()))
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", st):
            flush(); last_item = None
            out.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue

        if st.startswith("|") and i + 1 < len(lines) and TABLE_RULE.match(lines[i + 1]):
            flush(); last_item = None
            rows = [table_cells(st)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(table_cells(lines[i])); i += 1
            width = max(len(r) for r in rows)
            head, body = rows[0], rows[1:] or [[""] * width]
            # Notion takes 100 rows per table; longer tables split with the header repeated
            for k in range(0, len(body), CHILD_LIMIT - 1):
                part = [head] + body[k:k + CHILD_LIMIT - 1]
                out.append({"object": "block", "type": "table", "table": {
                    "table_width": width, "has_column_header": True, "has_row_header": False,
                    "children": [{"object": "block", "type": "table_row", "table_row": {
                        "cells": [inline(c) if c else [] for c in (r + [""] * (width - len(r)))]}}
                        for r in part]}})
            continue

        if st.startswith(">"):
            flush(); last_item = None
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip()); i += 1
            out.append(block("quote", " ".join(q for q in quote if q)))
            continue

        m = re.match(r"^!\[([^\]]*)\]\((https?://[^)\s]+)\)$", st)
        if m:
            flush(); last_item = None
            out.append({"object": "block", "type": "image", "image": {
                "type": "external", "external": {"url": m.group(2)},
                "caption": inline(m.group(1)) if m.group(1) else []}})
            i += 1
            continue

        m = LIST_ITEM.match(s)
        if m:
            flush()
            text = m.group("text")
            box = re.match(r"^\[( |x|X)\]\s+(.*)$", text) if m.group("mark") else None
            if box:
                b = block("to_do", box.group(2), checked=box.group(1) != " ")
            elif m.group("num"):
                b = block("numbered_list_item", text)
            else:
                b = block("bulleted_list_item", text)
            indent = len(m.group("indent").replace("\t", "    "))
            if indent >= 2 and last_item is not None:
                # Notion accepts two nesting levels per request: anything deeper collapses to one
                last_item[last_item["type"]].setdefault("children", []).append(b)
            else:
                out.append(b)
                last_item = b
            i += 1
            continue

        # an indented continuation line belongs to the list item above
        if last_item is not None and s[:1] in (" ", "\t") and not para:
            last_item[last_item["type"]]["rich_text"] += text_parts(" ") + inline(st)
            i += 1
            continue

        last_item = None
        para.append(s)
        i += 1

    flush()
    return out


def machine() -> str:
    # same contract as session-wrapup.py, so both write the same day's log
    f = ROOT / "memory" / ".machine"
    if f.is_file():
        name = f.read_text(encoding="utf-8").strip()
        if name:
            return name
    return os.environ.get("ASSISTANT_MACHINE") or socket.gethostname().split(".")[0].lower()


def footer_blocks(what: str) -> list[dict]:
    parts = [f"{what}: {datetime.now():%Y-%m-%d %H:%M}", f"machine {machine()}"]
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if session:
        parts.append(f"session {session[:8]}")
    try:
        c = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        if c.returncode == 0 and c.stdout.strip():
            parts.append(f"{ROOT.name}@{c.stdout.strip()}")
    except (OSError, subprocess.SubprocessError):
        pass
    return [{"object": "block", "type": "divider", "divider": {}},
            block("paragraph", text_parts(" · ".join(parts), {"color": "gray", "italic": True}))]


def append_children(pid: str, blocks: list[dict]):
    for k in range(0, len(blocks), CHILD_LIMIT):
        call("PATCH", f"/blocks/{pid}/children", {"children": blocks[k:k + CHILD_LIMIT]})


# ---------------------------------------------------------------- Notion -> Markdown

def rt_md(rt: list[dict]) -> str:
    out = []
    for o in rt:
        t = o.get("plain_text", "")
        a = o.get("annotations", {})
        if not t:
            continue
        if a.get("code"):
            t = f"`{t}`"
        if a.get("bold"):
            t = f"**{t}**"
        if a.get("italic"):
            t = f"*{t}*"
        if a.get("strikethrough"):
            t = f"~~{t}~~"
        if o.get("href"):
            t = f"[{t}]({o['href']})"
        out.append(t)
    return "".join(out)


LIST_KINDS = {"bulleted_list_item", "numbered_list_item", "to_do", "toggle"}


def blocks_md(blocks: list[dict], indent: str = "") -> list[str]:
    lines: list[str] = []
    n = 0
    for idx, b in enumerate(blocks):
        kind = b["type"]
        d = b.get(kind, {})
        text = rt_md(d.get("rich_text", [])) if isinstance(d, dict) else ""
        n = n + 1 if kind == "numbered_list_item" else 0
        sub = children(b["id"]) if b.get("has_children") and kind not in ("child_page", "child_database", "table") else []
        if kind == "paragraph":
            lines += [indent + text, ""] if text else [""]
        elif kind.startswith("heading_"):
            lines += ["#" * int(kind[-1]) + " " + text, ""]
        elif kind in ("bulleted_list_item", "toggle"):
            lines.append(f"{indent}- {text}")
        elif kind == "numbered_list_item":
            lines.append(f"{indent}{n}. {text}")
        elif kind == "to_do":
            lines.append(f"{indent}- [{'x' if d.get('checked') else ' '}] {text}")
        elif kind in ("quote", "callout"):
            lines += ["> " + text, ""]
        elif kind == "code":
            lines += ["```" + (d.get("language") or ""), "".join(o.get("plain_text", "") for o in d.get("rich_text", [])), "```", ""]
        elif kind == "divider":
            lines += ["---", ""]
        elif kind == "table":
            for k, r in enumerate(children(b["id"])):
                cells = [rt_md(c).replace("|", "\\|") for c in r["table_row"]["cells"]]
                lines.append("| " + " | ".join(cells) + " |")
                if k == 0:
                    lines.append("|" + "---|" * len(cells))
            lines.append("")
        elif kind == "child_page":
            lines.append(f"{indent}- [sub-page] {d.get('title', '')} ({b['id']})")
        elif kind == "child_database":
            lines.append(f"{indent}- [database] {d.get('title', '')} ({b['id']})")
        elif kind in ("image", "file", "pdf", "video"):
            u = (d.get("external") or d.get("file") or {}).get("url", "")
            lines += [f"{indent}![{rt_md(d.get('caption', []))}]({u})", ""]
        elif kind in ("bookmark", "embed", "link_preview"):
            lines += [indent + d.get("url", ""), ""]
        elif kind == "equation":
            lines += ["$$ " + d.get("expression", "") + " $$", ""]
        else:
            lines.append(f"{indent}[{kind}]")
        if sub:
            lines += blocks_md(sub, indent + "  ")
        # blank line after a list, or a following table/heading sticks to it
        if kind in LIST_KINDS and not indent and lines and lines[-1]:
            nxt = blocks[idx + 1]["type"] if idx + 1 < len(blocks) else None
            if nxt not in LIST_KINDS:
                lines.append("")
    return lines


# ---------------------------------------------------------------- search

def fold(s: str) -> str:
    s = s.replace("ı", "i").replace("İ", "I")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().casefold()


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(s))


def score(query: list[str], title: str) -> int:
    """How many query words the title holds. A shared 5-letter start is enough, so inflected
    forms match; words under 3 letters must match exactly; a number matches words it starts
    ("202610" finds October, "20261025" that day only)."""
    tw = words(title)
    n = 0
    for q in query:
        if q.isdigit():
            n += any(w.startswith(q) for w in tw)
        elif len(q) < 3:
            n += q in tw
        else:
            stem = q[:5]
            n += any(w.startswith(stem) or q.startswith(w) and len(w) >= 3 for w in tw)
    return n


def page_title(p: dict) -> str:
    return "".join(x["plain_text"] for v in p["properties"].values() if v.get("type") == "title" for x in v["title"])


def find(target: str) -> tuple[str, str]:
    """Resolve the target to (id, title). Without one clear match, print candidates and exit 3."""
    pid = parse_id(target)
    if pid:
        return pid, page_title(call("GET", f"/pages/{pid}"))
    query = words(target)
    if not query:
        die("empty search")
    gid = group_id(create=False)
    cands = []
    if gid:
        cands = sorted(((score(query, x["title"]), x["title"], x["id"]) for x in notes(gid)),
                       key=lambda c: c[1], reverse=True)          # newest first (date-prefixed titles)
        cands = sorted((c for c in cands if c[0] > 0), key=lambda c: -c[0])
    # A clear match: ahead of the runner-up and holding at least 60% of the query.
    # A natural-language query rarely hits every word.
    if cands:
        second = cands[1][0] if len(cands) > 1 else 0
        if cands[0][0] > second and cands[0][0] >= -(-3 * len(query) // 5):
            return cands[0][2], cands[0][1]
    if not cands:
        # not in the group: the rest of the shared workspace (Notion title search)
        r = call("POST", "/search", {"query": target, "filter": {"property": "object", "value": "page"}, "page_size": 10})
        cands = [(0, page_title(p), p["id"]) for p in r["results"]]
        if len(cands) == 1:
            return cands[0][2], cands[0][1]
    if not cands:
        die(f"no note found for '{target}'", 4)
    print("No single clear match; candidates (score, title, id):")
    for c in cands[:10]:
        print(f"  {c[0]}  {c[1]}  {c[2]}")
    raise SystemExit(3)


# ---------------------------------------------------------------- commands

def read_input(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    raw = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode("utf-8")
    return raw.decode("utf-8", "replace")


def fix_title(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    if not re.match(r"^\d{8}\b", t):
        t = f"{datetime.now():%Y%m%d} {t}"
    try:
        datetime.strptime(t[:8], "%Y%m%d")
    except ValueError:
        die(f"invalid date in title: {t[:8]}")
    if len(t[8:].split()) < 3:
        die("the title must be descriptive: at least three words after the date "
            "(e.g. '20261025 financing strategy for the house purchase')")
    return t


def summary_line(md: str) -> str:
    """For the inbox trace: the first paragraph under '## Summary', else the first plain paragraph."""
    m = re.search(r"^#{1,6}\s*Summary\s*\n+(.+?)(?:\n\s*\n|\n#|\Z)", md, re.M | re.S | re.I)
    t = m.group(1) if m else next((p for p in re.split(r"\n\s*\n", md) if p.strip() and not p.lstrip().startswith(("#", "|", "-", "```", ">"))), "")
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", " ".join(t.split()))
    t = re.sub(r"[*`]|~~|(?<!\w)_|_(?!\w)", "", t)
    if len(t) <= 280:
        return t
    cut = t[:280].rfind(". ")
    return t[:cut + 1] if cut > 80 else t[:280] + "..."


def inbox_trace(text: str):
    now = datetime.now()
    INBOX.mkdir(parents=True, exist_ok=True)
    path = INBOX / f"{now:%Y-%m-%d}--{machine()}.md"
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if not old.lstrip().startswith("---"):
        old = (f"---\ntype: log\ndate: {now:%Y-%m-%d}\nmachine: {machine()}\n---\n"
               f"# {now:%Y-%m-%d} ({machine()})\n") + ("\n" + old.lstrip() if old.strip() else "")
    if not old.endswith("\n"):
        old += "\n"
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(f"{old}\n## {now:%H:%M}\n{text}\n", encoding="utf-8")
    os.replace(tmp, path)  # atomic: a crash never truncates the day's log
    print(f"inbox: {path.relative_to(ROOT).as_posix()}")


def cmd_write(a):
    title = fix_title(a.title)
    md = read_input(a.file)
    if not md.strip():
        die("an empty note is not written")
    blocks = md_blocks(md) + footer_blocks("Written")
    if a.dry_run:
        print(f"[dry-run] title: {title}\n[dry-run] {len(blocks)} blocks: " + ", ".join(b["type"] for b in blocks))
        return 0
    gid = group_id(create=True)
    if any(fold(x["title"]) == fold(title) for x in notes(gid)):
        die(f"'{title}' already exists; no second copy, use `append`", 5)
    p = call("POST", "/pages", {
        "parent": {"page_id": gid},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
        "children": blocks[:CHILD_LIMIT],
    })
    append_children(p["id"], blocks[CHILD_LIMIT:])
    url = p.get("url") or page_url(p["id"])
    print(f"written: {title}\n{url}")
    if not a.no_inbox:
        inbox_trace(f"(notebook) Note written to the Notion notebook: \"{title}\". {summary_line(md)} {url}".replace("  ", " "))
    return 0


def cmd_append(a):
    md = read_input(a.file)
    if not md.strip():
        die("an empty addendum is not written")
    blocks = ([{"object": "block", "type": "divider", "divider": {}}, block("heading_2", f"Addendum, {datetime.now():%Y-%m-%d %H:%M}")]
              + md_blocks(md) + footer_blocks("Appended"))
    if a.dry_run:
        print(f"[dry-run] target: {a.target}\n[dry-run] {len(blocks)} blocks")
        return 0
    pid, title = find(a.target)
    append_children(pid, blocks)
    print(f"appended: {title}\n{page_url(pid)}")
    if not a.no_inbox:
        inbox_trace(f"(notebook) Addendum to the Notion note \"{title}\". {summary_line(md)} {page_url(pid)}".replace("  ", " "))
    return 0


def cmd_read(a):
    pid, title = find(a.target)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(blocks_md(children(pid)))).strip()
    print(f"# {title}\n<!-- {page_url(pid)} -->\n\n{body}")
    return 0


def cmd_list(a):
    gid = group_id(create=False)
    if not gid:
        print(f"No '{cfg()['group_title']}' page under the notebook yet.")
        return 0
    xs = sorted(notes(gid), key=lambda x: (x["title"][:8], x["created"]), reverse=True)
    for x in xs[:a.n]:
        print(f"{x['title']}  {page_url(x['id'])}")
    if not xs:
        print("(no notes yet)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("write", help="new note")
    w.add_argument("--title", required=True, help="YYYYMMDD + descriptive name; today is prefixed when the date is missing")
    w.add_argument("--file", help="Markdown file; stdin when omitted")
    w.add_argument("--dry-run", action="store_true", help="do not call Notion, print what would be written")
    w.add_argument("--no-inbox", action="store_true", help="leave no inbox trace (tests only)")
    w.set_defaults(f=cmd_write)

    p = sub.add_parser("append", help="addendum to an existing note")
    p.add_argument("target", help="search text, Notion URL or id")
    p.add_argument("--file", help="Markdown file; stdin when omitted")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-inbox", action="store_true")
    p.set_defaults(f=cmd_append)

    r = sub.add_parser("read", help="print a note as Markdown")
    r.add_argument("target", help="search text, Notion URL or id")
    r.set_defaults(f=cmd_read)

    li = sub.add_parser("list", help="notes in the group, newest first")
    li.add_argument("--n", type=int, default=20)
    li.set_defaults(f=cmd_list)

    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    raise SystemExit(main())
