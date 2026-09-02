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
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import yaml

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
USER_AGENT = "syndicate-genesis/1.0 (vault ingestion)"
REQUEST_GAP_S = 3


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


def fetch_papers(query: str, max_results: int):
    """List of papers, [] if none, or None if the query/request failed."""
    params = urllib.parse.urlencode({
        "search_query": query, "max_results": max_results,
        "sortBy": "submittedDate", "sortOrder": "descending",
    })
    req = urllib.request.Request(f"{ARXIV_API_URL}?{params}",
        headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            root = ET.fromstring(resp.read())
    except Exception as e:
        print(f"  ❌ request failed: {e}")
        return None
    papers = []
    for entry in root.findall("atom:entry", ATOM_NS):
        id_url = entry.findtext("atom:id", "", ATOM_NS)
        if not id_url or "/api/errors" in id_url:
            print(f"  ❌ arXiv rejected this query: {id_url}")
            return None
        papers.append({
            "id": extract_arxiv_id(id_url),
            "url": id_url,
            "title": " ".join(entry.findtext("atom:title", "", ATOM_NS).split()) or "(untitled)",
            "summary": " ".join(entry.findtext("atom:summary", "", ATOM_NS).split()),
            "authors": [" ".join(a.findtext("atom:name", "", ATOM_NS).split())
                for a in entry.findall("atom:author", ATOM_NS)],
            "published": entry.findtext("atom:published", "", ATOM_NS),
        })
    return papers


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

    new, failed = 0, 0
    for i, query in enumerate(queries):
        if i:
            time.sleep(REQUEST_GAP_S)
        print(f"\n🔍 {query}")
        papers = fetch_papers(query, args.max_results)
        if papers is None:
            failed += 1
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

    print(f"\n{new} new note(s), {failed} failed query(ies)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
