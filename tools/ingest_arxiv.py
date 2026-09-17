#!/usr/bin/env python3
"""Ingest arXiv papers into the syndicate vault as Obsidian notes.

Idempotency: a paper is skipped if any .md under the repo carries its
arxiv_id in frontmatter, or matches its arXiv_<id> filename prefix.
Frontmatter is the primary signal - it survives renames and moves.
"""
import argparse
import re
import subprocess
import sys
import time
import textwrap
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import yaml

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
USER_AGENT = "syndicate-genesis/1.0 (vault ingestion)"
REQUEST_GAP_S = 3

# arXiv throttles shared egress hard, and CI runners share a lot of it. A 429 is
# the API asking us to wait, not a reason to fail the day's ingestion: the
# unretried version ran red four mornings in a row on nothing but rate limiting.
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 4
MAX_RETRY_AFTER_S = 120

REJECTED, BLOCKED, TRANSIENT = "rejected", "blocked", "transient"

# arXiv answers 406 Not Acceptable to a request that does not say what it will
# accept. The API speaks Atom; ask for it explicitly rather than relying on a
# server default that changed under us.
REQUEST_HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/atom+xml"}


def sanitize_filename(title: str) -> str:
    clean = re.sub(r"[^\w\s-]", "", title)
    return re.sub(r"\s+", " ", clean).strip()[:60]


def safe_id(arxiv_id: str) -> str:
    return re.sub(r"[^\w-]", "_", arxiv_id)


def extract_arxiv_id(id_url: str) -> str:
    raw = id_url.split("/abs/")[-1]
    return re.sub(r"v\d+$", "", raw)


def find_scan_root(out_dir: Path) -> Path:
    """Dedup scope = whole repo: triage moves notes anywhere in the vault."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=out_dir, text=True, capture_output=True)
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip()).resolve()
    except Exception:
        pass
    return out_dir


def scan_existing(scan_root: Path):
    """Two rename-surviving signals of what is already in the vault."""
    ids, prefixes = set(), set()
    for f in scan_root.rglob("*.md"):
        if f.name.startswith("arXiv_"):
            prefixes.add(f.name.split(" - ")[0])
        try:
            with f.open(encoding="utf-8", errors="ignore") as fh:
                head = fh.read(4096)
        except OSError:
            continue
        m = re.search(r"^arxiv_id:\s*[\"']?([^\s\"'#]+)", head, re.MULTILINE)
        if m:
            ids.add(m.group(1))
    return ids, prefixes


def yq(s: str) -> str:
    """Escape for a double-quoted YAML scalar."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def write_note(paper: dict, out_dir: Path) -> Path:
    filename = f"arXiv_{safe_id(paper['id'])} - {sanitize_filename(paper['title'])}.md"
    filepath = out_dir / filename
    ingested = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    authors = "\n".join(f'  - "{yq(a)}"' for a in paper["authors"]) or "  []"
    abstract = "\n".join("> " + ln for ln in (textwrap.wrap(paper["summary"], 96) or [""]))
    body = (
        "---\n"
        f'aliases: ["{yq(paper["title"])}"]\n'
        "tags: [literature/arxiv, status/triage]\n"
        f'arxiv_id: "{paper["id"]}"\n'
        f'url: "{paper["url"]}"\n'
        f'published: "{paper["published"]}"\n'
        f'ingested: "{ingested}"\n'
        f"authors:\n{authors}\n"
        "---\n\n"
        f"# {paper['title']}\n\n"
        "## Abstract\n\n"
        f"{abstract}\n\n"
        "---\n"
        "## Reading Notes\n"
        "*Annotations below. Update the status tag as you triage; the "
        "arxiv_id frontmatter must survive edits - it is the dedup key.*\n\n"
    )
    filepath.write_text(body, encoding="utf-8")
    return filepath


def retry_delay(err, attempt: int) -> float:
    """Honour Retry-After when arXiv sends one; otherwise back off exponentially."""
    after = getattr(err, "headers", None) and err.headers.get("Retry-After")
    if after:
        try:
            return min(float(after), MAX_RETRY_AFTER_S)
        except ValueError:
            pass
    return BACKOFF_BASE_S * (2 ** attempt)


def fetch_once(query: str, max_results: int):
    params = urllib.parse.urlencode({
        "search_query": query, "max_results": max_results,
        "sortBy": "submittedDate", "sortOrder": "descending",
    })
    req = urllib.request.Request(f"{ARXIV_API_URL}?{params}",
        headers=REQUEST_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return ET.fromstring(resp.read())


def fetch_papers(query: str, max_results: int):
    """(papers, None) on success, or (None, REJECTED | TRANSIENT).

    The two failures are not the same and must never share an exit path: a
    rejected query is a config error a human has to fix, a transient one is
    the network and resolves itself. Collapsing them is how four days of
    rate limiting looked exactly like a broken subscription.
    """
    root = None
    for attempt in range(MAX_ATTEMPTS):
        err = None
        try:
            root = fetch_once(query, max_results)
            break
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_STATUSES:
                # An HTTP-level refusal is a client problem - headers, endpoint,
                # credentials - and has nothing to do with the search string.
                # Telling the operator to fix queries.yaml over a 406 sends them
                # to a correct file; naming the two failures apart is the fix.
                print(f"  ⛔ arXiv refused the request itself: HTTP {e.code}. "
                      f"This is a client/header problem, not the query.")
                return None, BLOCKED
            err, reason = e, f"HTTP {e.code}"
        except Exception as e:                      # timeouts, DNS, reset, bad XML
            err, reason = e, (str(e) or type(e).__name__)
        if attempt == MAX_ATTEMPTS - 1:
            print(f"  ⏳ transient failure after {MAX_ATTEMPTS} attempts: {reason}")
            return None, TRANSIENT
        # Hold the exception in a local: sys.exc_info() is already cleared here,
        # so reading Retry-After off it silently fell back to exponential.
        delay = retry_delay(err, attempt)
        print(f"  ⏳ {reason}; retrying in {delay:.0f}s "
              f"({attempt + 1}/{MAX_ATTEMPTS - 1})")
        time.sleep(delay)

    papers = []
    for entry in root.findall("atom:entry", ATOM_NS):
        id_url = entry.findtext("atom:id", "", ATOM_NS)
        if not id_url or "/api/errors" in id_url:
            print(f"  ❌ arXiv rejected this query: {id_url}")
            return None, REJECTED
        papers.append({
            "id": extract_arxiv_id(id_url),
            "url": id_url,
            "title": " ".join(entry.findtext("atom:title", "", ATOM_NS).split()) or "(untitled)",
            "summary": " ".join(entry.findtext("atom:summary", "", ATOM_NS).split()),
            "authors": [" ".join(a.findtext("atom:name", "", ATOM_NS).split())
                for a in entry.findall("atom:author", ATOM_NS)],
            "published": entry.findtext("atom:published", "", ATOM_NS),
        })
    return papers, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-results", type=int, default=10)
    args = ap.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    queries = config.get("arxiv_subscriptions") or []
    if not queries:
        print("no arxiv_subscriptions in config - nothing to do")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    scan_root = find_scan_root(args.out)
    ids, prefixes = scan_existing(scan_root)
    print(f"vault: {len(ids)} known arXiv ids under {scan_root}")

    new, rejected, blocked, transient = 0, 0, 0, 0
    for i, query in enumerate(queries):
        if i:
            time.sleep(REQUEST_GAP_S)
        print(f"\n🔍 {query}")
        papers, err = fetch_papers(query, args.max_results)
        if err == REJECTED:
            rejected += 1
            continue
        if err == BLOCKED:
            blocked += 1
            continue
        if err == TRANSIENT:
            transient += 1
            continue
        for paper in papers:
            if not paper["id"]:
                continue
            key = f"arXiv_{safe_id(paper['id'])}"
            if paper["id"] in ids or key in prefixes:
                print(f"  ⏭️  {paper['id']} already in vault")
                continue
            path = write_note(paper, args.out)
            ids.add(paper["id"]); prefixes.add(key); new += 1
            print(f"  ✅ {path.name}")

    print(f"\n{new} new note(s), {rejected} rejected, {blocked} blocked, "
          f"{transient} transient")
    if blocked:
        print(f"FAILED: arXiv refused {blocked} request(s) at the HTTP level. "
              f"The queries are not the problem - check the request headers "
              f"and that {ARXIV_API_URL} is still the right endpoint.")
        return 1
    if rejected:
        print(f"FAILED: {rejected} quer(ies) rejected by arXiv - fix agents/queries.yaml")
        return 1
    if transient:
        print(f"DEFERRED: {transient} quer(ies) hit transient errors after "
              f"{MAX_ATTEMPTS} attempts each; the vault is unchanged and the "
              f"next scheduled run retries. Not a configuration problem.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
