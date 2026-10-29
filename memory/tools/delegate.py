#!/usr/bin/env python3
"""delegate.py - hand bulk work to an external agent CLI (AGENTS.md section 12).

WHY: high-volume, low-judgement work (screening a result list, reading mail, scanning a
codebase, batch summarising) burns the main session's context for very little thinking. An
external agent CLI reads those fifty files in ITS OWN context and hands back ten lines. The
main context stays clean and the work is billed to whatever subscription you already pay for.

WHY A CLI AND NOT MCP: MCP binds the repository to one harness. This repository is explicitly
multi-harness and multi-AI (AGENTS.md section 7), so the bridge is a plain CLI call: sh plus the
standard library, identical on every machine.

WHAT IT DOES NOT BUY YOU: anything needing the repository's own rules, the owner's voice, or a
memory write. Treat whatever comes back as a HYPOTHESIS and verify it before acting.

ROLES ARE CONFIGURATION, NOT CODE. Which model leads and which one backs it up is yours to set
and will change over time: today the main session may be Claude with Gemini doing the grunt
work, tomorrow the reverse. Nothing here hardcodes a vendor.

  chain   comma-separated engine names, tried in order
  backup  who picks the work up when the chain is exhausted. This is a HARNESS-side actor
          (a sub-agent), so this script never calls it; it exits 3 and names it for the caller.

Resolution order for both roles and engine definitions:
  1. environment: ASSISTANT_DELEGATE_CHAIN / ASSISTANT_DELEGATE_BACKUP
  2. memory/delegate.ini  (gitignored; copy memory/delegate.ini.example to start)
  3. the built-in defaults below

SAFETY (invariant 9, default-deny on data egress): whatever the external CLI can see goes to its
vendor. So the repository root can NEVER be the working directory. Two legitimate modes:

  --path DIR    a clone or a directory outside the repository (code work, no personal memory)
  --give PATH   named paths are staged into a scratch directory and the agent sees ONLY those

memory/secret/ is hard-blocked in both modes. Paths that look like third-party data produce a
warning: whether that leaves your machine is your call, not the tool's.

Usage:
  python memory/tools/delegate.py --path ../some-clone "scan this and report X"
  python memory/tools/delegate.py --give memory/domains/work "which items are still open?"
  echo "prompt" | python memory/tools/delegate.py --tier advice --path ../some-clone
"""
from __future__ import annotations

import argparse
import configparser
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FORBIDDEN = (ROOT / "memory" / "secret").resolve()
CONFIG = ROOT / "memory" / "delegate.ini"
# Directory names that often hold third-party data. Warned about, never silently blocked:
# only the owner knows what is actually sensitive in their own repository.
SENSITIVE = ("people", "secret", "health", "clients")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Built-in engine definitions. These are EXAMPLES of the shape, not an endorsement: the CLIs
# below change their flags often, and yours may not be here at all. Override or add your own in
# memory/delegate.ini; see memory/delegate.ini.example.
#
# Two tiers, deliberately only two: `grunt` (scan, list, summarise) and `advice` (reasoning).
# Picking the cheapest model for the grunt tier is a false economy when you already pay a flat
# subscription: a half-good answer costs the main session a verification pass, which is the very
# thing delegation was meant to save.
DEFAULT_ENGINES = {
    "gemini": {
        "command": "agy",
        "args": "--model {model} --sandbox --dangerously-skip-permissions -p {prompt}",
        "model_grunt": "gemini-4-argon-medium",
        "model_advice": "gemini-4-argon-high",
    },
    "grok": {
        "command": "grok",
        "args": "--reasoning-effort {model} --permission-mode bypassPermissions -p {prompt}",
        "model_grunt": "low",
        "model_advice": "high",
    },
}
DEFAULT_ROLES = {"chain": "gemini", "backup": "a sub-agent on the backup model"}

# An engine failed BY ITSELF (quota, sign-in, not installed) -> fall through to the next one.
# A call that failed because of the WORK does not fall through: the same work would fail on
# every engine in the chain and burn all of them.
INFRA = ("quota", "rate limit", "rate-limit", "429", "401", "403", "unauthorized",
         "authorization", "authentication", "invalid_grant", "authorization grant",
         "login", "sign in", "oauth", "expired", "credential", "not authenticated",
         "not configured", "is not available", "no provider",
         "no such file", "command not found", "insufficient", "exceeded", "billing")


def _ini():
    cp = configparser.ConfigParser()
    try:
        cp.read(CONFIG, encoding="utf-8")
    except (OSError, configparser.Error) as e:
        print(f"delegate: {CONFIG.name} could not be read ({e}); using defaults", file=sys.stderr)
    return cp


def role(key: str) -> str:
    val = os.environ.get("ASSISTANT_DELEGATE_" + key.upper())
    if val:
        return val.strip()
    cp = _ini()
    if cp.has_option("roles", key):
        return cp.get("roles", key).strip()
    return DEFAULT_ROLES[key]


def engines() -> dict:
    """Built-in engines, overridden and extended by [engine:<name>] sections in the ini."""
    out = {k: dict(v) for k, v in DEFAULT_ENGINES.items()}
    cp = _ini()
    for sec in cp.sections():
        if not sec.startswith("engine:"):
            continue
        name = sec.split(":", 1)[1].strip()
        out.setdefault(name, {}).update({k: cp.get(sec, k) for k in cp.options(sec)})
    return {k: v for k, v in out.items() if v.get("url") or (v.get("command") and v.get("args"))}


def opt_in(spec: dict) -> bool:
    """Pay-per-token engines run only when named with --engine; they never join the chain."""
    return str(spec.get("opt_in", "")).lower() in ("1", "true", "yes")


def chain() -> list:
    """Delegation order. Unknown names are dropped rather than failing the whole chain."""
    known = engines()
    names = [x.strip() for x in role("chain").split(",")
             if x.strip() in known and not opt_in(known[x.strip()])]
    return names or [k for k in sorted(known) if not opt_in(known[k])][:1]


TEXT_CAP, FILE_CAP = 600_000, 60_000


def gather(cwd: Path) -> str:
    """Text files under cwd as one body, for engines that cannot open files themselves."""
    parts, total = [], 0
    for f in sorted(cwd.rglob("*")):
        if not f.is_file() or {".git", "node_modules", "secret"} & set(f.parts):
            continue
        try:
            t = f.read_text(encoding="utf-8")[:FILE_CAP]
        except (UnicodeDecodeError, OSError):
            continue
        if total + len(t) > TEXT_CAP:
            parts.append(f"[delegate: text cap reached, {f.relative_to(cwd)} and later omitted]")
            break
        parts.append(f"=== {f.relative_to(cwd).as_posix()} ===\n{t}")
        total += len(t)
    return "\n\n".join(parts)


def run_http(spec: dict, model: str, prompt: str, cwd: Path, limit: int):
    """One call to an OpenAI-compatible chat endpoint (e.g. OpenRouter). No tools: the files
    under cwd are sent as text. The usage line at the end shows tokens and cost when the
    endpoint reports them, so a paid engine never spends silently."""
    import json
    import urllib.error
    import urllib.request
    key = os.environ.get(spec.get("key_env", ""), "")
    if not key:
        return 1, f"[delegate: {spec.get('key_env')} is not set (not configured)]"
    body = {"model": model, "usage": {"include": True},
            "messages": [{"role": "user", "content": f"{prompt}\n\n--- FILES ---\n{gather(cwd)}"}]}
    if spec.get("provider_json"):
        body["provider"] = json.loads(spec["provider_json"])
    req = urllib.request.Request(spec["url"], data=json.dumps(body).encode("utf-8"),
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=limit) as r:
            out = json.load(r)
    except TimeoutError:
        return 124, f"[delegate: timed out after {limit}s]"
    except urllib.error.HTTPError as e:
        return 1, f"[delegate: HTTP {e.code}] {e.read().decode('utf-8', 'replace')[:300]}"
    except urllib.error.URLError as e:
        return 1, f"[delegate: network error, not available] {e.reason}"
    text = (out.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    u = out.get("usage") or {}
    return 0, (f"{text}\n[delegate: {u.get('prompt_tokens')}+{u.get('completion_tokens')} tokens, "
               f"cost {u.get('cost')}]")


def safe_path(p: Path) -> Path:
    """The working directory must be a clone or live outside the repo; use --give for memory."""
    p = p.resolve()
    if not p.is_dir():
        sys.exit(f"delegate: no such directory: {p}")
    if p == FORBIDDEN or FORBIDDEN in p.parents or str(FORBIDDEN).startswith(str(p) + os.sep):
        sys.exit(f"delegate: {p} can see memory/secret; refusing (invariant 9).")
    if p == ROOT or ROOT in p.parents:
        sys.exit(f"delegate: a directory inside this repository cannot be --path. "
                 f"Use --path for a separate clone, --give for memory files.")
    return p


def stage(paths: list) -> Path:
    """Copy the named paths into a scratch directory; the agent sees only those."""
    dest = Path(tempfile.mkdtemp(prefix="delegate-"))
    for raw in paths:
        src = (ROOT / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        if src == FORBIDDEN or FORBIDDEN in src.parents:
            shutil.rmtree(dest, ignore_errors=True)
            sys.exit(f"delegate: memory/secret never leaves this machine ({raw}).")
        if not src.exists():
            shutil.rmtree(dest, ignore_errors=True)
            sys.exit(f"delegate: no such path: {raw}")
        inner = dest / src.name
        if src.is_dir():
            shutil.copytree(src, inner, ignore=shutil.ignore_patterns("secret", ".git"))
        else:
            shutil.copy2(src, inner)
        if any(h in str(src).lower() for h in SENSITIVE):
            print(f"delegate: WARNING may contain third-party data, going to the vendor: {raw}",
                  file=sys.stderr)
    return dest


def infra_failure(code: int, text: str) -> bool:
    """Did the engine itself fail (quota/sign-in/install), or did the work fail?"""
    if code == 0:
        return not text.strip()          # a silent success is also a malfunction
    low = text.lower()
    return any(sig in low for sig in INFRA)


def run(name: str, spec: dict, model: str, prompt: str, cwd: Path, limit: int):
    """Run one engine; returns (code, raw output). Timeout is 124."""
    if spec.get("url"):
        return run_http(spec, model, prompt, cwd, limit)
    if not shutil.which(spec["command"]):
        return 127, f"[delegate: {spec['command']} is not installed (command not found)]"
    argv = [spec["command"]]
    for tok in shlex.split(spec["args"]):
        argv.append(prompt if tok == "{prompt}" else tok.replace("{model}", model))
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=limit, env=env)
    except subprocess.TimeoutExpired:
        return 124, f"[delegate: timed out after {limit}s]"
    raw = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.returncode else "")
    return r.returncode, raw


def main() -> int:
    known = engines()
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?", help="the prompt; read from stdin when omitted")
    ap.add_argument("--engine", choices=sorted(known) or None, help="start with this engine")
    ap.add_argument("--tier", choices=("grunt", "advice"), default="grunt")
    ap.add_argument("--model", help="override the engine's model for this call")
    ap.add_argument("--path", help="working directory: a clone, or anywhere outside this repo")
    ap.add_argument("--give", action="append", default=[],
                    help="path to stage (repeatable); not combined with --path")
    ap.add_argument("--timeout", type=int, default=900, help="seconds (default 900)")
    ap.add_argument("--only", action="store_true", help="do not fall through the chain")
    a = ap.parse_args()

    if not known:
        sys.exit("delegate: no engines defined. See memory/delegate.ini.example.")
    text = a.prompt if a.prompt else sys.stdin.read()
    if not text.strip():
        sys.exit("delegate: empty prompt.")
    if a.path and a.give:
        sys.exit("delegate: --path and --give are not combined.")

    staged = None
    if a.give:
        staged = stage(a.give)
        cwd = staged
    elif a.path:
        cwd = safe_path(Path(a.path) if Path(a.path).is_absolute() else Path.cwd() / a.path)
    else:
        sys.exit("delegate: --path or --give is required (the repo root is never opened).")

    first = a.engine or chain()[0]
    order = [first] if a.only else [first] + [e for e in chain() if e != first]

    state = ROOT / "memory" / "tools" / ".state"
    state.mkdir(parents=True, exist_ok=True)

    code, raw, used, model, skipped = 3, "", None, None, []
    try:
        for name in order:
            spec = known[name]
            # --model applies only to the engine actually asked for; a later engine in the
            # chain must not be handed another engine's model name.
            model = (a.model if (a.model and name == first)
                     else spec.get(f"model_{a.tier}", spec.get("model_grunt", "")))
            code, raw = run(name, spec, model, text, cwd, a.timeout)
            if code == 124:              # a timeout is about the work, not the engine:
                used = name              # the next engine would time out too
                break
            if not infra_failure(code, raw):
                used = name
                break
            tail = raw.strip().splitlines()[-1][:90] if raw.strip() else "empty output"
            skipped.append(f"{name}: {tail}")
            used = None
    finally:
        if staged:
            shutil.rmtree(staged, ignore_errors=True)

    for s in skipped:
        print(f"[delegate] skipped · {s}", file=sys.stderr)

    if used is None:                     # every engine failed on infrastructure
        print(f"[delegate] NO EXTERNAL AGENT: every engine in the chain failed on quota, "
              f"sign-in or install. Do not stall: hand the same work to {role('backup')} "
              f"(AGENTS.md section 12).", file=sys.stderr)
        return 3

    out = state / f"delegate-{used}-{datetime.now():%Y%m%d-%H%M%S}.txt"
    out.write_text(raw, encoding="utf-8")
    lines = raw.splitlines()
    print(f"[delegate] {used}/{model} · {cwd.name} · {len(lines)} lines · {out}")
    print("\n".join(lines[-60:]) if len(lines) > 60 else raw)
    if len(lines) > 60:
        print(f"[delegate: the first {len(lines)-60} lines are in the file]")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
