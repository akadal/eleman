#!/usr/bin/env python3
"""literature-fetch.py - bridge to a WoS + Scopus literature search (memory/rules/literature.md).

WHY: a literature search answered from web search or from the model's own memory produces
papers that do not exist and misses the ones that do. The search belongs to the indexes
themselves, through their APIs. The toolkit that does it already exists as a separate
repository (default `akadal/literature-review`: query, deduplicate, cross-check WoS against
Scopus, write a report where every line carries an evidence ID). This script does NOT
re-implement it and no crawler is ever written here. It only removes the friction:

  1. clones the toolkit under `temp/literature-review`, or pulls it if present (AGENTS.md 11);
  2. copies the keys from `memory/secret/literature.json` into the clone's `.env`
     (values are never printed, only "synced" / "already the same");
  3. gives the clone its own `.venv` on first use, so nothing lands in the system Python;
  4. runs the search and prints the FULL paths of the outputs.

Nothing is written to this repository: the corpus stays in the clone's `output/`. Only a
human-readable decision or summary enters memory, through the inbox (invariant 10).

Keys (the owner types them in their own terminal, AGENTS.md section 9):
  python memory/tools/secret-put.py literature wos_api_key scopus_api_key
Optional fields: scopus_insttoken, unpaywall_email.

The toolkit repository is public (MIT), so no access step is needed. Point elsewhere with
ASSISTANT_LITERATURE_REPO.

Usage:
  python memory/tools/literature-fetch.py --doctor
  python memory/tools/literature-fetch.py --topic "blockchain tourism" --years 2020-2026 --max 50
  python memory/tools/literature-fetch.py --wos 'TS=("LLM" AND education)' \\
                                          --scopus 'TITLE-ABS-KEY("LLM" AND education)'
  python memory/tools/literature-fetch.py --topic "x" --dry-run   # show, do not run
"""
import argparse, hashlib, json, os, re, subprocess, sys
from pathlib import Path

# Windows consoles open in a legacy code page; non-ASCII output would raise. Line buffering
# keeps our lines in order with the child's output when stdout is a pipe.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

MEM = Path(__file__).resolve().parent.parent
ROOT = MEM.parent
CLONE = ROOT / "temp" / "literature-review"
REMOTE = os.environ.get("ASSISTANT_LITERATURE_REPO", "https://github.com/akadal/literature-review")
KEYS = MEM / "secret" / "literature.json"
# literature.json field -> .env name
MAPPING = {"wos_api_key": "WOS_API_KEY", "scopus_api_key": "SCOPUS_API_KEY",
           "scopus_insttoken": "SCOPUS_INSTTOKEN", "unpaywall_email": "UNPAYWALL_EMAIL"}
REQUIRED = ("wos_api_key", "scopus_api_key")


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd, cwd=None, capture=False, extra=None):
    """Subprocess with a UTF-8 child environment, so Windows output is not mangled."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", **(extra or {}))
    if capture:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    return subprocess.run(cmd, cwd=cwd, env=env).returncode, ""


def keys():
    if not KEYS.exists():
        die(f"{KEYS} is missing. Ask the owner to run:\n"
            "  python memory/tools/secret-put.py literature wos_api_key scopus_api_key")
    try:
        d = json.loads(KEYS.read_text(encoding="utf-8"))
    except ValueError:
        die(f"{KEYS} is not valid JSON.")
    missing = [f for f in REQUIRED if not str(d.get(f, "")).strip()]
    if missing:
        die(f"empty in literature.json: {', '.join(missing)}")
    return {MAPPING[f]: str(v).strip() for f, v in d.items() if f in MAPPING and str(v).strip()}


def prepare_clone(dry=False):
    if not CLONE.exists():
        if dry:
            print(f"[dry-run] git clone {REMOTE} {CLONE}")
            return
        CLONE.parent.mkdir(parents=True, exist_ok=True)
        print(f"no clone yet, fetching: {REMOTE}")
        if run(["git", "clone", REMOTE, str(CLONE)])[0]:
            die("clone failed: check the network and that git runs (`git --version`). "
                f"The repository is {REMOTE}.")
        return
    if dry:
        print(f"[dry-run] git -C {CLONE} pull --ff-only")
        return
    code, out = run(["git", "-C", str(CLONE), "pull", "--ff-only"], capture=True)
    if code:
        print(f"WARNING: pull failed, continuing with the existing clone:\n{out.strip()[:300]}")
    else:
        print(f"clone up to date: {out.strip().splitlines()[-1] if out.strip() else 'ok'}")


def sync_env(dry=False):
    """Write the keys into the clone's .env. Other lines are kept; no value is printed."""
    env = CLONE / ".env"
    lines = env.read_text(encoding="utf-8", errors="replace").splitlines() if env.exists() else []
    new, changed = [], []
    for name, value in keys().items():
        for i, line in enumerate(lines):
            m = re.match(rf"\s*{name}\s*=\s*(.*)", line)
            if m:
                if m.group(1).strip().strip('"') != value:
                    lines[i] = f"{name}={value}"
                    changed.append(name)
                break
        else:
            new.append(f"{name}={value}")
            changed.append(name)
    if not changed:
        print("keys: .env already matches literature.json")
        return
    if dry:
        print(f"[dry-run] .env would be updated: {', '.join(changed)}")
        return
    env.write_text("\n".join(lines + new).rstrip() + "\n", encoding="utf-8")
    print(f"keys: .env synced ({', '.join(changed)})")


def interpreter(dry=False):
    """The clone's own venv; created on first use so the system Python stays clean."""
    for c in (CLONE / ".venv" / "Scripts" / "python.exe", CLONE / ".venv" / "bin" / "python"):
        if c.exists():
            return str(c)
    if dry:
        print(f"[dry-run] {sys.executable} -m venv {CLONE / '.venv'}")
        return sys.executable
    print("no .venv in the clone yet, creating it...")
    if run([sys.executable, "-m", "venv", str(CLONE / ".venv")])[0]:
        die("could not create the venv.")
    return interpreter()


def ensure_installed(py):
    if run([py, "-c", "import literature_reviewer"], cwd=str(CLONE), capture=True)[0] == 0:
        return
    print("literature_reviewer is not installed, running `pip install -e .`...")
    if run([py, "-m", "pip", "install", "-q", "-e", "."], cwd=str(CLONE))[0]:
        die("install failed; see the clone's README.")


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())[:40].strip("-") or "search"
    return f"{s}-{hashlib.sha1(text.encode()).hexdigest()[:6]}"


def main():
    p = argparse.ArgumentParser(description="WoS + Scopus literature search (bridge).")
    p.add_argument("--topic", default="",
                   help="Plain topic; words are AND-joined. Quote inside for a phrase: '\"digital natives\"'")
    p.add_argument("--wos", default="", help="Raw WoS query, e.g. 'TS=(\"x\" AND y)'")
    p.add_argument("--scopus", default="", help="Raw Scopus query, e.g. 'TITLE-ABS-KEY(\"x\")'")
    p.add_argument("--years", default=None, help="Year or range, e.g. 2020-2026")
    p.add_argument("--max", type=int, default=50, help="Max records per source (default 50)")
    p.add_argument("--sources", default="wos,scopus", help="wos, scopus or both")
    p.add_argument("--doc-type", default="Article OR Review")
    p.add_argument("--out", default=None,
                   help="Output dir, relative to the clone; default output/lit/<slug>")
    p.add_argument("--pdfs", action="store_true", help="Also download legal open-access PDFs")
    p.add_argument("--doctor", action="store_true", help="Setup check plus one tiny live API call")
    p.add_argument("--dry-run", action="store_true", help="Run nothing, show what would happen")
    a = p.parse_args()

    if not (a.doctor or a.topic or a.wos or a.scopus):
        p.error("one of --topic, --wos/--scopus or --doctor is required.")

    prepare_clone(a.dry_run)
    if a.dry_run and not CLONE.exists():
        return
    sync_env(a.dry_run)
    py = interpreter(a.dry_run)
    if not a.dry_run:
        ensure_installed(py)

    if a.doctor:
        cmd = [py, "-m", "literature_reviewer", "doctor", "--check-apis"]
    else:
        out = a.out or f"output/lit/{slug(a.topic or a.wos or a.scopus)}"
        cmd = [py, "-m", "literature_reviewer", "search", "--max-results", str(a.max),
               "--sources", a.sources, "--doc-type", a.doc_type, "--output-dir", out]
        for flag, val in (("--topic", a.topic), ("--wos-query", a.wos),
                          ("--scopus-query", a.scopus), ("--year-range", a.years)):
            if val:
                cmd += [flag, val]
        if a.pdfs:
            cmd += ["--download-pdfs"]

    if a.dry_run:
        print("[dry-run] " + " ".join(cmd))
        return
    print("-> " + " ".join(cmd[1:]) + "\n")
    # The keys also go straight into the child's environment: python-dotenv never overrides an
    # existing variable, so a stale WOS_API_KEY in the shell would silently beat the .env.
    code = run(cmd, cwd=str(CLONE), extra=keys())[0]
    if code:
        die(f"{'doctor' if a.doctor else 'search'} failed (exit {code}).", code)
    if not a.doctor:
        d = (CLONE / out).resolve()
        print("\nOutputs (full path):")
        for name in ("review.md", "articles.csv", "evidence_groups.json", "diagnostics.json"):
            path = d / name
            print(f"  {'ok' if path.exists() else '--'} {path}")
        print("\nNext: read review.md and tie every claim to its evidence ID; the decision or "
              "summary goes to the inbox. Do not copy the corpus into this repository.")


if __name__ == "__main__":
    main()
