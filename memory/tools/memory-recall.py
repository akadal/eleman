#!/usr/bin/env python3
"""memory-recall.py: recall without navigation. The harness retrieves, the model answers once.

Why: on a 50-question benchmark over a real memory repository, a weak local model (gemma3:4b)
that navigated the index itself scored 16%. With every navigation aid (root map, a retriever
handing it addresses or passages, guards against made-up paths and early abstention) it reached
36%. The same model, given five passages retrieved by local embeddings and asked to answer in one
shot with no navigation at all, scored 50%; a lexical retriever in the same one-shot setup scored
34%. Every extra turn handed to a weak model is one more chance to wander off. The idea of
recalling at the harness, before the model starts, comes from oh-my-pi's memory layer.

What it does: chunks memory (minus `secret/` and the golden set) the way the benchmark did,
embeds the chunks with local bge-m3 through Ollama, prints the k chunks closest to the question.
`--answer` has a local model answer in one shot from those chunks: that is the local-model mode
itself (AGENTS.md §4).

Privacy (invariant #9, docs/DESIGN.md §7): embedding is local only, there is no cloud path in
this code, the Ollama address must be this machine and system proxies are bypassed. The index is
derived (`memory/.index/`, gitignored), refreshed incrementally by per-file content hash, and
deleting it is always legitimate. Without Ollama it falls back to lexical retrieval and says so;
that path scored lower in the benchmark.

Usage:
  python3 memory/tools/memory-recall.py "What is Alex's thesis about?"
  python3 memory/tools/memory-recall.py --answer "..." [--model gemma3:4b]
  python3 memory/tools/memory-recall.py --build      # refresh the index only
Dependencies: stdlib. Environment: OLLAMA_URL (default localhost), ASSISTANT_LOCAL_MODEL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import operator
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from array import array
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # memory/
INDEX = ROOT / ".index"
META = INDEX / "recall-meta.json"
VECTORS = INDEX / "recall-vec.bin"
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
EMBED_MODEL = "bge-m3"          # docs/DESIGN.md §7; changing it rebuilds the index
LOCAL_MODEL = os.environ.get("ASSISTANT_LOCAL_MODEL", "gemma3:4b")
K = 5                           # the benchmark's vector arm used k=5
MAX_CHUNK = 3000                # characters; a long chunk is truncated silently by the embedder
EXCLUDE = ("secret/", "tools/golden-set.md", ".index/")   # the answer key must never be retrievable
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

SYSTEM = """You are a personal assistant and you keep your owner's memory. {owner}
Answer ONLY from the memory records below. If something is not in them, say "that isn't in my
memory"; never guess, never invent. The current value is always the most recently written one;
lines under "## History" are old. Keep the answer short: two sentences at most."""


class NotLocal(Exception):
    pass


def warn(m: str) -> None:
    print(m, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- chunking
def _split(text: str) -> list[str]:
    """Splits an over-long chunk on line boundaries: a truncated chunk loses information silently."""
    if len(text) <= MAX_CHUNK:
        return [text]
    out, buf, size = [], [], 0
    for line in text.splitlines(keepends=True):
        if size + len(line) > MAX_CHUNK and buf:
            out.append("".join(buf))
            buf, size = [], 0
        buf.append(line)
        size += len(line)
    if buf:
        out.append("".join(buf))
    return out


def chunk(text: str) -> list[str]:
    """The benchmark's chunking: a file with '## ' headings splits into blocks, a file without
    them is one chunk; frontmatter is dropped, a date prefix is kept."""
    m = re.search(r"^date:\s*(\S+)", text, re.M)
    prefix = f"[{m.group(1)}] " if m else ""
    blocks = re.split(r"\n(?=## )", text)
    if len(blocks) == 1:
        return _split(text.strip())
    out = []
    for b in blocks:
        body = re.sub(r"^---.*?---\s*", "", b, flags=re.S).strip()
        if len(body) >= 15:
            out += [prefix + c for c in _split(body)]
    return out


def files() -> dict[str, Path]:
    out = {}
    for p in sorted(ROOT.rglob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        if not rel.startswith(EXCLUDE):
            out[rel] = p
    return out


# --------------------------------------------------------------------------- Ollama
def _post(endpoint: str, body: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(f"{OLLAMA}{endpoint}", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with _OPENER.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ollama_ready() -> bool:
    if urllib.parse.urlparse(OLLAMA).hostname not in LOCAL_HOSTS:
        raise NotLocal(OLLAMA)
    try:
        with _OPENER.open(f"{OLLAMA}/api/tags", timeout=3) as r:
            names = {m.get("name", "").split(":")[0] for m in json.loads(r.read()).get("models", [])}
        return EMBED_MODEL in names
    except (OSError, ValueError, urllib.error.URLError):
        return False


def embed(texts: list[str]) -> list[list[float]]:
    out = []
    for i in range(0, len(texts), 32):
        out += _post("/api/embed", {"model": EMBED_MODEL, "input": texts[i:i + 32]})["embeddings"]
    return out


def unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


# --------------------------------------------------------------------------- index
def load_index() -> tuple[dict, array]:
    empty = ({"model": EMBED_MODEL, "dim": 0, "files": {}}, array("f"))
    try:
        meta = json.loads(META.read_text(encoding="utf-8"))
        vec = array("f")
        with VECTORS.open("rb") as f:
            vec.frombytes(f.read())
    except (OSError, ValueError):
        return empty
    if meta.get("model") != EMBED_MODEL:
        return empty
    # The two files are written separately, so an interrupted run can leave old metadata next to
    # new vectors; unchanged files would then copy the wrong slices and, since their hashes still
    # match, carry the damage forward forever. Any mismatch means rebuild.
    dim = meta.get("dim", 0)
    total = sum(len(d["chunks"]) for d in meta["files"].values())
    if not dim or len(vec) != dim * total or any(
            d["chunks"] and (d["first"] < 0 or (d["first"] + len(d["chunks"])) * dim > len(vec))
            for d in meta["files"].values()):
        warn("index inconsistent; rebuilding.")
        return empty
    return meta, vec


def refresh_index(quiet: bool = False) -> tuple[dict, array]:
    """Re-embeds changed files and drops deleted ones. The first build takes minutes (about 7 for
    4,200 chunks on a consumer GPU); afterwards only changed files are embedded."""
    meta, vec = load_index()
    old, dim = meta["files"], meta.get("dim", 0)
    new_meta: dict = {}
    new_vec = array("f")
    todo: list[tuple[str, list[str]]] = []
    for rel, p in files().items():
        text = p.read_text(encoding="utf-8", errors="ignore")
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()
        e = old.get(rel)
        if e and e["hash"] == h and dim:
            start = len(new_vec) // dim
            new_vec.extend(vec[e["first"] * dim:(e["first"] + len(e["chunks"])) * dim])
            new_meta[rel] = {"hash": h, "first": start, "chunks": e["chunks"]}
        else:
            todo.append((rel, chunk(text)))
            new_meta[rel] = {"hash": h, "first": 0, "chunks": []}
    total = sum(len(c) for _, c in todo)
    if total and not quiet:
        warn(f"index: embedding {total} chunks from {len(todo)} files...")
    t0 = time.time()
    for rel, cs in todo:
        if not cs:
            continue
        vv = [unit(v) for v in embed(cs)]
        dim = dim or len(vv[0])
        new_meta[rel] = {"hash": new_meta[rel]["hash"], "first": len(new_vec) // dim, "chunks": cs}
        for v in vv:
            new_vec.extend(v)
    if todo or set(old) != set(new_meta):
        INDEX.mkdir(parents=True, exist_ok=True)
        meta = {"model": EMBED_MODEL, "dim": dim, "files": new_meta}
        v_tmp, m_tmp = VECTORS.with_suffix(".tmp"), META.with_suffix(".tmp")
        with v_tmp.open("wb") as f:
            new_vec.tofile(f)
        m_tmp.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        os.replace(v_tmp, VECTORS)       # if interrupted between the two, load_index catches it
        os.replace(m_tmp, META)
        if total and not quiet:
            warn(f"index: done ({time.time() - t0:.0f} s)")
        return meta, new_vec
    return meta, vec


def vector_retrieve(question: str, k: int) -> list[dict]:
    meta, vec = refresh_index()
    dim = meta["dim"]
    q = unit(embed([question])[0])
    scored = []
    for rel, d in meta["files"].items():
        for j, text in enumerate(d["chunks"]):
            i = (d["first"] + j) * dim
            scored.append((sum(map(operator.mul, q, vec[i:i + dim])), rel, text))
    scored.sort(key=lambda x: -x[0])
    return [{"path": p, "text": t, "score": round(s, 3)} for s, p, t in scored[:k]]


# --------------------------------------------------------------------------- lexical fallback
def _stems(text: str) -> list[str]:
    a = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return [t[:5] for t in re.findall(r"[a-z0-9]+", a) if len(t) >= 3]


def lexical_retrieve(question: str, k: int) -> list[dict]:
    """Fallback without Ollama: rare words weigh more, a word in the path earns a bonus (the first
    stage of oh-my-pi's find tool). Weaker than vectors in the benchmark; it exists so the tool
    still works."""
    chunks = [(r, c) for r, p in files().items()
              for c in chunk(p.read_text(encoding="utf-8", errors="ignore"))]
    counts = [Counter(_stems(c)) for _, c in chunks]
    df = Counter(t for c in counts for t in c)
    n = len(chunks)
    query = list(dict.fromkeys(_stems(question)))
    scored = []
    for (rel, text), c in zip(chunks, counts):
        in_path = set(_stems(rel.replace("/", " ").replace("-", " ")))
        s = sum(min(6.0, max(0.5, math.log((n + 1) / (df[t] + 1)))) * (2 * (t in in_path) + math.log1p(c[t]))
                for t in query if t in df)
        if s > 0:
            scored.append((s * (0.85 if rel.startswith("archive/") else 1.0), rel, text))
    scored.sort(key=lambda x: -x[0])
    return [{"path": p, "text": t, "score": round(s, 2)} for s, p, t in scored[:k]]


# --------------------------------------------------------------------------- answer
def owner() -> str:
    """The owner line comes from MEMORY.md; without it the introduction drops, the rules stay."""
    try:
        m = re.search(r"^Owner:\s*(.+)$", (ROOT / "MEMORY.md").read_text(encoding="utf-8"), re.M)
    except OSError:
        m = None
    return f"Owner: {m.group(1).strip()}" if m else ""


def answer(question: str, chunks: list[dict], model: str) -> str:
    context = "\n\n".join(f"=== {c['path']} ===\n{c['text']}" for c in chunks)
    messages = [{"role": "system", "content": SYSTEM.format(owner=owner())},
                {"role": "user", "content": f"Memory records:\n\n{context}\n\n---\nQuestion: {question}"}]
    chars = sum(len(m["content"]) for m in messages)
    ctx = next((c for c in (8192, 16384, 32768, 65536, 131072) if chars / 2.8 + 1212 <= c), 131072)
    r = _post("/api/chat", {"model": model, "messages": messages, "stream": False, "think": False,
                            "options": {"temperature": 0, "seed": 7, "num_ctx": ctx, "num_predict": 700}})
    return (r.get("message") or {}).get("content", "").strip()


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Recall without navigation (local-model mode).")
    ap.add_argument("question", nargs="*")
    ap.add_argument("--answer", action="store_true", help="have a local model answer in one shot")
    ap.add_argument("--model", default=LOCAL_MODEL, help="Ollama model for --answer")
    ap.add_argument("-k", type=int, default=K, help="chunks to retrieve (benchmark: 5)")
    ap.add_argument("--build", action="store_true", help="refresh the index only")
    a = ap.parse_args()
    question = " ".join(a.question).strip()
    if not question and not a.build:
        ap.error("a question or --build is required")

    vectors = ollama_ready()
    if a.build:
        if not vectors:
            warn(f"ERROR: Ollama or {EMBED_MODEL} not available ({OLLAMA}); index not built.")
            return 1
        refresh_index()
        return 0
    if vectors:
        chunks = vector_retrieve(question, a.k)
    else:
        warn(f"WARNING: Ollama or {EMBED_MODEL} not available; lexical retrieval (weaker in the benchmark).")
        chunks = lexical_retrieve(question, a.k)
    if a.answer:
        if not vectors:
            warn("ERROR: --answer needs a local model; Ollama is not available.")
            return 1
        print(answer(question, chunks, a.model))
        print("\nSources: " + ", ".join(dict.fromkeys(c["path"] for c in chunks)))
        return 0
    for c in chunks:
        print(f"=== {c['path']}  [{c['score']}] ===\n{c['text'].strip()}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except NotLocal as e:
        warn(f"ERROR: the Ollama address is not this machine ({e}); memory is never sent out (invariant #9).")
        sys.exit(1)
    except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
        warn(f"ERROR: Ollama request failed ({type(e).__name__}: {e}); is the model installed?")
        sys.exit(1)
