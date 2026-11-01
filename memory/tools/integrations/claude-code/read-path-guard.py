#!/usr/bin/env python3
"""read-path-guard.py: Claude Code PreToolUse(Read) hook. When a read asks for a memory path
that does not exist, it names the right file.

Why: on a 50-question benchmark a weak model made up a path on its very first read in 20 of 50
questions (`domains/people/_index.md` for `people/_index.md`, say); a strong model did it in 6
of 61 reads. A bare "file not found" made the model give up more often than look again.
oh-my-pi resolves the same situation by the file that uniquely matches the path's tail; in the
benchmark this guard never cost a correct answer.

What it does: looks only at reads of non-existent paths inside `memory/`. If the tail of the path
matches exactly one file, it names that file; if a longer tail matches several, it lists five; if
only the bare file name matches (`_index.md`), it lists the nearest existing directory instead.
The read is denied with that reason, which the model sees. Existing files and paths outside
`memory/` are never touched; `secret/` is never suggested. Any error exits silently: the hook
never breaks a read.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MEMORY = Path(__file__).resolve().parents[3]
SKIP = ("secret/", ".index/", "tools/.state/")


def suggestion(target: Path) -> str | None:
    try:
        rel = target.resolve().relative_to(MEMORY.resolve()).as_posix()
    except ValueError:
        return None
    every = [p.relative_to(MEMORY).as_posix() for p in MEMORY.rglob("*") if p.is_file()]
    every = [e for e in every if not e.startswith(SKIP)]
    parts = [p for p in rel.split("/") if p]
    for i in range(len(parts)):
        tail = "/".join(parts[i:])
        hits = [e for e in every if e == tail or e.endswith("/" + tail)]
        if len(hits) == 1:
            return f"memory/{rel} does not exist. You most likely mean memory/{hits[0]}; read that."
        if len(hits) > 1 and i < len(parts) - 1:
            return (f"memory/{rel} does not exist. The tail of the path matches several files: "
                    + ", ".join(f"memory/{h}" for h in hits[:5]) + ".")
        if len(hits) > 1:
            break          # only the bare file name matches (_index.md): the directory helps more
    up = MEMORY / Path(*parts[:-1]) if len(parts) > 1 else MEMORY
    while up != MEMORY and not up.is_dir():
        up = up.parent
    listing = sorted(p.name + ("/" if p.is_dir() else "") for p in up.iterdir()
                     if not (p.relative_to(MEMORY).as_posix() + "/").startswith(SKIP))[:40]
    name = "memory/" + (up.relative_to(MEMORY).as_posix() + "/" if up != MEMORY else "")
    return (f"memory/{rel} does not exist. The nearest existing directory is {name}, containing: "
            f"{', '.join(listing)}. Do not guess paths; take the full path from the index or search.")


def main() -> int:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    path = (data.get("tool_input") or {}).get("file_path")
    if not path:
        return 0
    target = Path(path)
    if not target.is_absolute():
        target = Path(data.get("cwd") or MEMORY.parent) / target
    if target.exists():
        return 0
    reason = suggestion(target)
    if reason:
        sys.stdout.buffer.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}).encode("utf-8"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:          # hook boundary: never break a read
        sys.exit(0)
