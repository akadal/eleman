#!/usr/bin/env python3
"""abstention-guard.py: Claude Code Stop hook. Sends a "that isn't in my memory" answer given
without any search back once.

Why: the abstention threshold in AGENTS.md §4 (abstaining is only earned after a search turn)
was prose only. On a 50-question benchmark a weak model gave 22 of its 31 abstentions without a
single search; this guard cut that number from 26 to 12 and from 35 to 10 in two separate setups
and never cost a correct answer. The shape follows DeepSeek Harness's repeat-tool reminder: an
advisory message, not a block on the work, and only once.

What it does: if the turn's final message is short and carries the abstention phrase outside
quotes, it checks the transcript for a search in this turn (Grep, Glob, a sub-agent, or a shell
command with rg/grep/memory-recall). Without one, it sends the turn back once. It does nothing
when it has already sent the turn back (`stop_hook_active`) or the transcript cannot be read.
Long messages (reports, discussion) are out of scope: there the phrase is a topic, not an answer.
Set ASSISTANT_ABSTAIN_PATTERN (a regex) if your memory abstains in another language.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ABSTAIN = re.compile(os.environ.get(
    "ASSISTANT_ABSTAIN_PATTERN",
    r"isn['’]?t\s+in\s+my\s+memory|not\s+in\s+(?:my\s+)?memory|haf[ıi]zamda\s+yok"), re.I)
QUOTES = "\"'“”‘’«`"   # no asterisk: **Not in my memory.** is an answer
MAX_ANSWER = 1200            # characters; a longer message is a report, not an answer
TAIL = 2_000_000             # only the end of the transcript is read
SHELL_SEARCH = re.compile(r"\b(rg|grep|git\s+grep|Select-String|findstr|memory-recall)\b")
SEARCH_TOOLS = {"Grep", "Glob", "Agent", "Task"}

REASON = ("You said the answer isn't in memory without searching in this turn. AGENTS.md §4: "
          "abstaining is only earned after a search turn. Search first (domain-scoped rg, with "
          "synonyms and other languages; memory-recall.py if needed), then decide. Asked once.")


def abstains(text: str) -> bool:
    if not text or len(text) > MAX_ANSWER:
        return False
    for m in ABSTAIN.finditer(text):
        if not any(c in QUOTES for c in text[max(0, m.start() - 2):m.start()]):
            return True
    return False


def genuine_prompt(r: dict) -> bool:
    """Did the user's own message start the turn? The transcript format is undocumented and
    changes between versions: an `origin.kind` field wins when present; otherwise compaction
    summaries, harness injections and tool results are excluded, and list content with text
    (an attached image) still counts as a prompt."""
    msg = r.get("message") or {}
    if r.get("type") != "user" or msg.get("role") != "user" or r.get("isMeta"):
        return False
    if r.get("isCompactSummary") or r.get("isVisibleInTranscriptOnly"):
        return False
    origin = r.get("origin")
    if isinstance(origin, dict) and origin.get("kind"):
        return origin["kind"] == "human"
    content = msg.get("content")
    if isinstance(content, str):
        return bool(content.strip()) and not content.lstrip().startswith("<")
    if isinstance(content, list):
        kinds = {b.get("type") for b in content if isinstance(b, dict)}
        return "text" in kinds and "tool_result" not in kinds
    return False


def turn_records(transcript: Path) -> list[dict] | None:
    try:
        with transcript.open("rb") as f:
            f.seek(0, os.SEEK_END)
            start = max(0, f.tell() - TAIL)
            f.seek(start)
            lines = f.read().decode("utf-8", errors="ignore").splitlines()
            if start:
                lines = lines[1:]          # starting mid-file, the first line is partial
    except OSError:
        return None
    records = []
    for line in lines:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and not r.get("isSidechain"):
            records.append(r)
    for i in range(len(records) - 1, -1, -1):
        if genuine_prompt(records[i]):
            return records[i + 1:]
    return None


def searched(records: list[dict]) -> bool:
    for r in records:
        if r.get("type") != "assistant":
            continue
        for b in (r.get("message") or {}).get("content") or []:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            name, args = b.get("name", ""), b.get("input") or {}
            if name in SEARCH_TOOLS:
                return True
            if name in ("Bash", "PowerShell") and SHELL_SEARCH.search(str(args.get("command", ""))):
                return True
    return False


def main() -> int:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    if data.get("stop_hook_active"):
        return 0
    if not abstains(str(data.get("last_assistant_message") or "")):
        return 0
    records = turn_records(Path(str(data.get("transcript_path") or "")))
    if records is None or searched(records):
        return 0
    sys.stdout.buffer.write(json.dumps({"decision": "block", "reason": REASON}).encode("utf-8"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:          # hook boundary: never break a session
        sys.exit(0)
