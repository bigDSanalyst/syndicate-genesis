#!/usr/bin/env python3
"""Report what the template changed since this syndicate was generated from it.

The guard symmetry this completes: the smoke suite proves the mold works, and
nothing until now proved an instance still matches the mold it came from. Row 37
fired three times in the session that closed it, and remediating design-partner
repos by hand is the chore that kills adoption.

Git-native, no version numbers: syndicate.yaml records the upstream commit this
repo's lineage starts at, and the diff between that commit and upstream HEAD IS
the remediation checklist.

WHAT COUNTS AS DRIFT
--------------------
Instances inherit machinery and rules, never narrative. FINDINGS.md, ROADMAP.md
and docs/ are the template's own scar tissue and priorities; they are stripped at
activation and changes to them are not this repo's business. Everything else the
template ships is machinery, so the filter is a denylist rather than an allowlist
on purpose: a new upstream directory should show up as drift the first time it
appears, and being told about a file that turns out not to matter is a smaller
failure than never being told about one that does.

The rule that decides the hard cases: THE STRIP LIST STRIPS INHERITANCE, NOT
IDENTITY. A repo's record organs - ledger/ (what is proven), agreements/ (who is
bound), audits/ (what was found wrong) - are the syndicate's own receipts, and
the protocol exists to preserve them. An audit written about THIS repo is this
repo's history even though it reads like narrative; the mold's findings are
someone else's. Hence audits/ is a root directory beside the other record
organs rather than a docs/ subfolder: docs/ is inherited and stripped, so
instance-authored history kept there would be one prompt away from deletion.

Commands
--------
    drift_check.py check     what changed upstream since this repo's lineage commit
    drift_check.py record    write the current upstream head into syndicate.yaml

Exit codes (a green run must never mean "I could not look"):
    0  in sync
    1  needs a human: a mold, no lineage recorded, or a commit upstream disowns
    2  transient: the network or the rate limiter, try later
    3  drift found - actionable, not an error
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

API_ROOT = "https://api.github.com"
USER_AGENT = "syndicate-genesis/1.0 (drift check)"
PLACEHOLDER_HANDLE = "github-handle"
PLACEHOLDER_COMMIT = "RECORD-AT-ACTIVATION"

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 4
MAX_RETRY_AFTER_S = 120

OK, DRIFT, NEEDS_HUMAN, TRANSIENT = 0, 3, 1, 2

# Narrative and instance-owned paths. Changes here upstream are not drift.
# STRIP_AT_ACTIVATION is the subset bootstrap.sh removes from a generated repo -
# kept in the same file as the filter so the two can never disagree.
STRIP_AT_ACTIVATION = ("FINDINGS.md", "ROADMAP.md", "docs/")

# Record organs: what this syndicate proved, who it bound, and what was found
# wrong in it. Instance-owned, never stripped, never drift.
RECORD_ORGANS = ("ledger/", "agreements/EXECUTION-LOG.md", "audits/")

NOT_INHERITED = STRIP_AT_ACTIVATION + RECORD_ORGANS + (
    "vault/00-inbox/", "vault/10-literature/", "vault/20-notes/",
    "vault/30-experiments/", "vault/40-drafts/", "vault/50-decisions/",
    "vault/maps/",
    # tests/ and the workflow that runs it: measured at 37 of 75 failing inside
    # a provisioned instance (row 60). Eight assert mold behaviour and can never
    # pass there; the rest fail because every fixture in the suite starts by
    # pretending the tree under test still carries the placeholder member row,
    # so provision() is a no-op and the rosters it builds are not the ones the
    # assertions name. Listing it as inherited told every adopter to import a
    # suite that is permanently half red, which teaches people to ignore CI -
    # operator rule #8 inverted. Not the final answer: the suite conflates tests
    # OF GENERATION, which are template-only by definition, with tests of the
    # machinery's invariants, which are worth more in an instance than here.
    # Splitting those is the fix; excluding it is what stops the checklist
    # giving bad advice today. See ROADMAP.
    "tests/", ".github/workflows/smoke.yml",
)

# The drawer's label is machinery; what goes in the drawer is identity. The
# convention doc for audits/ ships from the template and should keep tracking it.
INHERITED_ANYWAY = ("audits/README.md",)


def inherited(path: str) -> bool:
    if path in INHERITED_ANYWAY:
        return True
    return not any(path == p or path.startswith(p) for p in NOT_INHERITED)


# ───────────────────────────── manifest ─────────────────────────────
def load_manifest(repo: Path):
    text = (repo / "syndicate.yaml").read_text(encoding="utf-8")
    return text, yaml.safe_load(text) or {}


def is_unprovisioned_template(cfg) -> bool:
    """True only when the manifest still carries the template's placeholder row.

    Same marker anchor.py keys on, and for the same reason: `oracle_ref` says
    "template" in every generated repo too, so gating on it would refuse real
    syndicates. Fails open - only a positive placeholder sighting refuses.
    """
    members = cfg.get("members") or []
    return any(m.get("github") == PLACEHOLDER_HANDLE
               for m in members if isinstance(m, dict))


def lineage(cfg):
    """(repo, ref, commit) or (None, reason) when it cannot be used."""
    t = cfg.get("template") or {}
    repo, ref, commit = t.get("repo"), t.get("ref") or "main", t.get("commit")
    if not repo:
        return None, "syndicate.yaml has no `template.repo` - nothing to compare against"
    if not commit or commit == PLACEHOLDER_COMMIT:
        return None, ("no lineage commit recorded yet - run `drift_check.py record`, "
                      "which bootstrap.sh does at activation")
    return (repo, ref, commit), None


# ─────────────────────────────── HTTP ───────────────────────────────
def request_headers():
    h = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        h["Authorization"] = "Bearer " + token
    return h


def is_rate_limited(err) -> bool:
    """GitHub answers 403 both when it is throttling and when it is refusing.

    The two need opposite handling, and reading one as the other either hammers a
    closed door or gives up on an open one (ingest_repos.py, same seam).
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


def api(path: str):
    """(payload, None) or (None, NEEDS_HUMAN | TRANSIENT)."""
    url = API_ROOT + path
    for attempt in range(MAX_ATTEMPTS):
        err = reason = None
        try:
            req = urllib.request.Request(url, headers=request_headers())
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp), None
        except urllib.error.HTTPError as e:
            if e.code in (404, 422):
                print(f"  ❌ upstream does not recognise this: HTTP {e.code} on {path}\n"
                      f"     A 404 means the template repo or ref is wrong (or private "
                      f"to this token); a 422 means the recorded commit is not an "
                      f"ancestor it can compare - a force-push upstream, or a lineage "
                      f"commit from a fork.")
                return None, NEEDS_HUMAN
            if not (e.code in RETRY_STATUSES or is_rate_limited(e)):
                print(f"  ⛔ GitHub refused the request itself: HTTP {e.code}. "
                      f"Check GITHUB_TOKEN and its scopes.")
                return None, NEEDS_HUMAN
            err, reason = e, f"HTTP {e.code}"
        except Exception as e:
            err, reason = e, (str(e) or type(e).__name__)
        if attempt == MAX_ATTEMPTS - 1:
            print(f"  ⏳ transient failure after {MAX_ATTEMPTS} attempts: {reason}")
            return None, TRANSIENT
        delay = retry_delay(err, attempt)
        print(f"  ⏳ {reason}; retrying in {delay:.0f}s ({attempt + 1}/{MAX_ATTEMPTS - 1})")
        time.sleep(delay)
    return None, TRANSIENT


def upstream_head(repo: str, ref: str):
    payload, problem = api(f"/repos/{repo}/commits/{urllib.parse.quote(ref)}")
    if problem:
        return None, problem
    sha = (payload or {}).get("sha")
    if not sha:
        print("  ❌ upstream answered without a commit sha")
        return None, NEEDS_HUMAN
    return sha, None


# ─────────────────────────────── commands ───────────────────────────
def cmd_check(args) -> int:
    repo_root = Path(args.repo).resolve()
    text, cfg = load_manifest(repo_root)

    if is_unprovisioned_template(cfg):
        print("refusing to drift-check: this is the mold, not a syndicate "
              "(operator rule #10). A template has no lineage - it is the lineage.")
        return NEEDS_HUMAN

    info, why = lineage(cfg)
    if not info:
        print(f"❌ {why}")
        return NEEDS_HUMAN
    upstream, ref, base = info

    head, problem = upstream_head(upstream, ref)
    if problem:
        return problem
    if head == base:
        print(f"✅ in sync with {upstream}@{ref} ({base[:8]})")
        return OK

    payload, problem = api(f"/repos/{upstream}/compare/{base}...{head}")
    if problem:
        return problem

    files = payload.get("files") or []
    truncated = len(files) >= 300
    changed = sorted({f["filename"] for f in files if f.get("filename")})
    drifted = [f for f in changed if inherited(f)]
    ignored = len(changed) - len(drifted)

    print(f"# template drift\n")
    print(f"lineage : {upstream}@{ref}")
    print(f"from    : {base[:8]}  (recorded {(cfg.get('template') or {}).get('recorded') or 'unknown'})")
    print(f"to      : {head[:8]}  ({payload.get('ahead_by', '?')} commits ahead)\n")

    if not drifted:
        print(f"✅ nothing inherited changed. {ignored} upstream change(s) were to "
              f"narrative or instance-owned paths, which this repo does not track.")
        print(f"\nRecord the new lineage when you are ready: drift_check.py record")
        return OK

    print(f"{len(drifted)} inherited file(s) changed upstream. This list IS the "
          f"remediation checklist:\n")
    for f in drifted:
        print(f"  - {f}")
    if ignored:
        print(f"\n({ignored} further change(s) ignored: narrative or instance-owned.)")
    if truncated:
        print("\n⚠ upstream returned the maximum comparable file count; the list "
              "above may be incomplete. Compare in the browser for the full set.")
    print(f"\n  https://github.com/{upstream}/compare/{base}...{head}")
    print("\nApply what applies, then record the new lineage: drift_check.py record")
    return DRIFT


def cmd_record(args) -> int:
    repo_root = Path(args.repo).resolve()
    text, cfg = load_manifest(repo_root)

    if is_unprovisioned_template(cfg):
        print("refusing to record lineage: this is the mold, not a syndicate. "
              "A template generated from itself is the loop row 12 already closed.")
        return NEEDS_HUMAN

    t = cfg.get("template") or {}
    upstream, ref = t.get("repo"), t.get("ref") or "main"
    if not upstream:
        print("❌ syndicate.yaml has no `template.repo` to record against")
        return NEEDS_HUMAN

    head, problem = upstream_head(upstream, ref)
    if problem:
        return problem

    today = datetime.now(timezone.utc).date().isoformat()
    new, n = re.subn(r'(?m)^(\s*commit:\s*)"[^"]*"', rf'\g<1>"{head}"', text, count=1)
    if n != 1:
        print("❌ could not find a `commit:` line under `template:` to update. "
              "The manifest is edited in place rather than re-serialised, because "
              "re-serialising drops the comments that carry the governance rules.")
        return NEEDS_HUMAN
    new, n = re.subn(r'(?m)^(\s*recorded:\s*)"[^"]*"', rf'\g<1>"{today}"', new, count=1)
    if n != 1:
        print("❌ could not find a `recorded:` line under `template:` to update.")
        return NEEDS_HUMAN

    (repo_root / "syndicate.yaml").write_text(new, encoding="utf-8")
    print(f"✅ lineage recorded: {upstream}@{ref} {head[:8]} ({today})")
    print("   Commit syndicate.yaml - the lineage is only real once it is in the record.")
    return OK


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["check", "record"], nargs="?", default="check")
    ap.add_argument("--repo", default=".", help="repository root (default: .)")
    args = ap.parse_args()
    return cmd_record(args) if args.command == "record" else cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
