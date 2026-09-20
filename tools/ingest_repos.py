#!/usr/bin/env python3
"""Ingest GitHub repositories into the syndicate vault as inbox cards.

Repos as literature: the same standing-query surveillance ingest_arxiv.py runs
over papers, pointed at GitHub Search. Same skeleton, same laws.

Idempotency: a repo is skipped if any .md under the repo carries its full_name
in `repo_id` frontmatter, or matches its filename prefix. The frontmatter is the
dedup key and is load-bearing (vault/MAP.md law 1) - it survives renames and
moves, the filename does not.

Discovery finds; humans approach. This writes cards to an inbox. It does not
contact anyone, and per docs/DISCOVERY.md it must never model who could endorse
a submission.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

API_URL = "https://api.github.com/search/repositories"
USER_AGENT = "syndicate-genesis/1.0 (repo ingestion)"
REQUEST_GAP_S = 3

# GitHub's search endpoint is 30 requests/minute authenticated and 10
# unauthenticated - stricter than arXiv, and it answers 403 rather than 429 when
# it throttles. A 403 is therefore ambiguous: it means "rate limited" or "not
# allowed", and the two need opposite handling. Guessing wrong is how row 51
# happened, one API over.
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 4
MAX_RETRY_AFTER_S = 120

REJECTED, BLOCKED, TRANSIENT = "rejected", "blocked", "transient"


def sanitize(text: str) -> str:
    clean = re.sub(r"[^\w\s-]", "", text or "")
    return re.sub(r"\s+", " ", clean).strip()[:60]


def safe_id(full_name: str) -> str:
    return re.sub(r"[^\w-]", "_", full_name)


def find_scan_root(out_dir: Path) -> Path:
    """Dedup scope = whole repo: triage moves cards anywhere in the vault."""
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           cwd=out_dir, text=True, capture_output=True)
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip()).resolve()
    except Exception:
        pass
    return out_dir


def scan_existing(scan_root: Path):
    ids, prefixes = set(), set()
    for f in scan_root.rglob("*.md"):
        if f.name.startswith("gh_"):
            prefixes.add(f.name.split(" - ")[0])
        try:
            with f.open(encoding="utf-8", errors="ignore") as fh:
                head = fh.read(4096)
        except OSError:
            continue
        m = re.search(r"^repo_id:\s*[\"']?([^\s\"'#]+)", head, re.MULTILINE)
        if m:
            ids.add(m.group(1))
    return ids, prefixes


def yq(s: str) -> str:
    """Escape for a double-quoted YAML scalar."""
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')


def is_rate_limited(err) -> bool:
    """Distinguish GitHub's throttling 403 from its forbidding 403.

    Both arrive as 403. Rate limiting is transient and must be retried; a real
    authorization failure is permanent and must not be. Reading the wrong one
    into the other either hammers a closed door or gives up on an open one.
    """
    if err.code not in (403, 429):
        return False
    headers = getattr(err, "headers", None)
    if headers:
        if headers.get("Retry-After"):
            return True
        if headers.get("X-RateLimit-Remaining") == "0":
            return True
    try:
        body = err.read().decode("utf-8", "replace").lower()
    except Exception:
        body = ""
    return "rate limit" in body or "abuse" in body


def retry_delay(err, attempt: int) -> float:
    headers = getattr(err, "headers", None)
    after = headers.get("Retry-After") if headers else None
    if after:
        try:
            return min(float(after), MAX_RETRY_AFTER_S)
        except ValueError:
            pass
    return BACKOFF_BASE_S * (2 ** attempt)


def request_headers():
    h = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        h["Authorization"] = "Bearer " + token
    return h


class MalformedResponse(Exception):
    """The endpoint answered, and the answer was not this API. Its own class
    so it can never be collapsed into "transient" or into an empty result."""


def fetch_once(query: str, per_page: int):
    params = urllib.parse.urlencode({
        "q": query, "per_page": per_page, "sort": "updated", "order": "desc"})
    req = urllib.request.Request(f"{API_URL}?{params}", headers=request_headers())
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    # Valid JSON is not a search result. GitHub's search API always returns
    # both `total_count` and `items`; a body carrying neither is an error
    # envelope, an auth problem, or a different endpoint - and
    # payload.get("items", []) rendered every one of them as "your search
    # matched nothing", exit 0. The absent key IS the signal, so it is read
    # as one rather than defaulted away.
    if not isinstance(payload, dict) or "items" not in payload:
        keys = (", ".join(sorted(payload)[:6]) if isinstance(payload, dict)
                else type(payload).__name__)
        raise MalformedResponse(
            "expected a search result carrying `items`, got {%s}" % keys)
    return payload


def fetch_repos(query: str, per_page: int):
    """(repos, None) on success, or (None, REJECTED | BLOCKED | TRANSIENT)."""
    payload = None
    malformed = False
    for attempt in range(MAX_ATTEMPTS):
        err = None
        try:
            payload = fetch_once(query, per_page)
            break
        except urllib.error.HTTPError as e:
            if e.code == 422:
                print(f"  ❌ GitHub rejected this query as malformed (422): {query}")
                return None, REJECTED
            if not (e.code in RETRY_STATUSES or is_rate_limited(e)):
                print(f"  ⛔ GitHub refused the request itself: HTTP {e.code}. "
                      f"Not the query - check GITHUB_TOKEN and its scopes "
                      f"(search is 10 req/min unauthenticated and often refused).")
                return None, BLOCKED
            err, reason = e, f"HTTP {e.code}"
        except MalformedResponse as e:
            err, reason = e, ("malformed response: %s" % e)
            malformed = True
        except Exception as e:
            err, reason = e, (str(e) or type(e).__name__)
        if attempt == MAX_ATTEMPTS - 1:
            if malformed:
                print(f"  ⛔ the endpoint answered {MAX_ATTEMPTS} times and "
                      f"never with a search result ({reason}). Not an empty "
                      f"search - check GITHUB_TOKEN and that {API_URL} is "
                      f"still the endpoint.")
                return None, BLOCKED
            print(f"  ⏳ transient failure after {MAX_ATTEMPTS} attempts: {reason}")
            return None, TRANSIENT
        delay = retry_delay(err, attempt)
        print(f"  ⏳ {reason}; retrying in {delay:.0f}s "
              f"({attempt + 1}/{MAX_ATTEMPTS - 1})")
        time.sleep(delay)

    repos = []
    for item in payload.get("items", []):
        if not item.get("full_name"):
            continue
        repos.append({
            "full_name": item["full_name"],
            "url": item.get("html_url", ""),
            "description": " ".join((item.get("description") or "").split()),
            "stars": item.get("stargazers_count", 0),
            "language": item.get("language") or "",
            "topics": item.get("topics") or [],
            "pushed_at": item.get("pushed_at", ""),
            "license": ((item.get("license") or {}).get("spdx_id") or ""),
        })
    return repos, None


def write_card(repo: dict, out_dir: Path) -> Path:
    filename = f"gh_{safe_id(repo['full_name'])} - {sanitize(repo['description'])}.md"
    path = out_dir / filename
    ingested = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    topics = "\n".join(f'  - "{yq(t)}"' for t in repo["topics"]) or "  []"
    described = textwrap.wrap(repo["description"], 96) or ["(no description)"]
    description = "\n".join("> " + ln for ln in described)
    body = (
        "---\n"
        f'aliases: ["{yq(repo["full_name"])}"]\n'
        "tags: [literature/repo, status/triage]\n"
        f'repo_id: "{repo["full_name"]}"\n'
        f'url: "{repo["url"]}"\n'
        f'stars: {repo["stars"]}\n'
        f'language: "{yq(repo["language"])}"\n'
        f'license: "{yq(repo["license"])}"\n'
        f'pushed_at: "{repo["pushed_at"]}"\n'
        f'ingested: "{ingested}"\n'
        f"topics:\n{topics}\n"
        "---\n\n"
        f"# {repo['full_name']}\n\n"
        "## Description\n\n"
        f"{description}\n\n"
        "---\n"
        "## Triage Notes\n"
        "*A repo card is executable, unlike a paper: clone it and run its own\n"
        "checks before trusting it. Update the status tag as you triage; the\n"
        "repo_id frontmatter must survive edits - it is the dedup key.*\n\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--per-page", type=int, default=10)
    args = ap.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    queries = config.get("github_subscriptions") or []
    if not queries:
        print("no github_subscriptions in config - nothing to do")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    scan_root = find_scan_root(args.out)
    ids, prefixes = scan_existing(scan_root)
    print(f"vault: {len(ids)} known repo ids under {scan_root}")
    if not (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")):
        print("warning: no GITHUB_TOKEN - search is 10 req/min unauthenticated "
              "and is frequently refused outright")

    new, rejected, blocked, transient = 0, 0, 0, 0
    for i, query in enumerate(queries):
        if i:
            time.sleep(REQUEST_GAP_S)
        print(f"\n🔍 {query}")
        repos, err = fetch_repos(query, args.per_page)
        if err == REJECTED:
            rejected += 1
            continue
        if err == BLOCKED:
            blocked += 1
            continue
        if err == TRANSIENT:
            transient += 1
            continue
        for repo in repos:
            key = f"gh_{safe_id(repo['full_name'])}"
            if repo["full_name"] in ids or key in prefixes:
                print(f"  ⏭️  {repo['full_name']} already in vault")
                continue
            path = write_card(repo, args.out)
            ids.add(repo["full_name"]); prefixes.add(key); new += 1
            print(f"  ✅ {path.name}")

    print(f"\n{new} new card(s), {rejected} rejected, {blocked} blocked, "
          f"{transient} transient")
    if blocked:
        print("FAILED: GitHub refused the request at the HTTP level. The queries "
              "are not the problem - check GITHUB_TOKEN and its scopes.")
        return 1
    if rejected:
        print(f"FAILED: {rejected} quer(ies) rejected as malformed - fix "
              f"agents/queries.yaml")
        return 1
    if transient:
        print(f"DEFERRED: {transient} quer(ies) hit transient errors after "
              f"{MAX_ATTEMPTS} attempts each; the vault is unchanged and the "
              f"next run retries. Not a configuration problem.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
