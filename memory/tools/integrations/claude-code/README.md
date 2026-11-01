# Claude Code guards (optional)

Two hooks that turn written read-protocol rules (AGENTS.md §4) into mechanics, for owners who run
the memory under Claude Code. Other harnesses keep the prose rules; nothing here is required.

- `read-path-guard.py` (PreToolUse on `Read`): a read of a non-existent path inside `memory/` is
  sent back with the file the model most likely meant, or the nearest existing directory.
- `abstention-guard.py` (Stop): a short "that isn't in my memory" answer given without any search
  in the turn is sent back once with a reminder to search first. If your memory abstains in
  another language, set `ASSISTANT_ABSTAIN_PATTERN` to a regex for your phrase.

Both are stdlib Python, exit silently on any error, and never block a session twice in a row.
On a 50-question benchmark they never cost a correct answer; for a weak model they cut early
abstentions by more than half.

## Enable

Add to `.claude/settings.json` in the repository root (use `python` instead of `python3` on
Windows, where `python3` is often a Microsoft Store stub):

```json
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "Read", "hooks": [{"type": "command", "timeout": 10,
        "command": "python3 \"$CLAUDE_PROJECT_DIR/memory/tools/integrations/claude-code/read-path-guard.py\""}]}
    ],
    "Stop": [
      {"hooks": [{"type": "command", "timeout": 10,
        "command": "python3 \"$CLAUDE_PROJECT_DIR/memory/tools/integrations/claude-code/abstention-guard.py\""}]}
    ]
  }
}
```

Each Read then costs one short Python start (about 0.3 s on Windows).
