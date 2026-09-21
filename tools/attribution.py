#!/usr/bin/env python3
"""Attribution ledger: per-member shares from the Repository Record (Agreement section 4).

ARITHMETIC CHANGE, 2026-09-18: shares are computed in Decimal, not float. Windows
computed before this date used binary floats, so recomputing one of them now can
differ in the last digits. That is a change of instrument, not of the record:
ratified windows stand as ratified (MAP.md law 4 - corrections are new entries,
never rewrites), and a diff between an old window and its recomputation is this
note, not tampering. Any window ratified from here is exact and reproducible.

Sources: git numstat -> churn/breadth (survivorship-weighted); GitHub API ->
review + merge acts; prompts out of scope (weights renormalized). Identity by
manifest email/handle; display names are cosmetic. Merge acts credit the merger
(GitHub authors merge commits as the PR author - author-only parsing would
mis-attribute governance acts). Bots excluded via exclude_authors_matching.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_EVEN, getcontext
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manifest import is_unprovisioned_template            # noqa: E402

# These numbers decide revenue splits (Agreement section 5), so the arithmetic is
# exact and reproducible rather than platform-dependent. Binary floats make
# 0.1 + 0.2 != 0.3 and make the result depend on summation order; a member
# recomputing a window on another machine must get the same digits, or the
# evidence is not evidence. Logs still need real transcendentals - Decimal.ln()
# provides them at this precision, deterministically.
getcontext().prec = 28
ZERO, ONE = Decimal(0), Decimal(1)
SURVIVOR_WEIGHT = Decimal("0.3")
API = "https://api.github.com"


def dec(x) -> Decimal:
    """Decimal from anything, via str: Decimal(0.35) inherits the float's error."""
    return x if isinstance(x, Decimal) else Decimal(str(x))


def q(d: Decimal, places: int) -> Decimal:
    """Round half-to-even, the banker's rule - unbiased across many windows."""
    return dec(d).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)


def sh(*args, cwd):
    r = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if r.returncode != 0:
        sys.exit("ERROR: git command failed: " + r.stderr.strip())
    return r.stdout.strip()


def api_get(url):
    """Fetch one API page. Raises on failure: a degraded window must never
    print a green result (operator rule #8 - a green check must never lie)."""
    headers = {"User-Agent": "syndicate-attribution/1.0", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp), resp.headers.get("Link", "")
    except Exception as e:
        sys.exit("ERROR: GitHub API failed (review/merge credit would be wrong): "
                 + url + " -> " + str(e) + "\n"
                 "  set GITHUB_TOKEN to raise the 60/hr anonymous rate limit.")


def api_paged(url):
    """Follow rel=next so windows past 100 PRs are not silently truncated."""
    out = []
    while url:
        page, link = api_get(url)
        out.extend(page)
        url = None
        for part in link.split(","):
            if 'rel="next"' in part and "<" in part:
                url = part[part.index("<") + 1:part.index(">")]
    return out


SHARE_PLACES = 4
# (mutation marker)        # digits published in attribution.csv


def apportion(shares, places):
    """Round shares to `places` digits so they still sum to exactly one.

    The internal arithmetic is exact Decimal; the PUBLISHED split was not.
    Rounding each share independently is the classic apportionment error:
    three members at exactly one third publish 0.3333 each and allocate
    0.9999 of the revenue, and six publish 0.1667 each and allocate 1.0002 -
    a ledger promising 100.02% of the money. Measured, not reasoned: at 2
    members it happens to work, at 3, 6, 7, 9 and 11 it does not.

    Largest-remainder (Hamilton): floor every share to the grid, then hand
    the leftover units one each to the largest fractional remainders. The
    result sums to exactly one by construction, no member is off by more
    than one unit in the last place, and it is deterministic - ties break on
    the member key, which is stated rather than left to dict ordering so two
    people recomputing the same window get the same file.

    An empty window sums to zero, and zero is the honest answer there; it
    must not be apportioned up to one.
    """
    if not shares:
        return {}
    total = sum(shares.values(), ZERO)
    grid = Decimal(1).scaleb(-places)                 # e.g. 0.0001
    if total == ZERO:
        return {k: ZERO.quantize(grid) for k in shares}

    units = {k: (v / grid).to_integral_value(rounding=ROUND_FLOOR)
             for k, v in shares.items()}
    target = (total / grid).to_integral_value(rounding=ROUND_HALF_EVEN)
    short = int(target - sum(units.values(), ZERO))
    # largest remainder first; the member key breaks ties deterministically
    order = sorted(shares, key=lambda k: (-(shares[k] / grid - units[k]), k))
    for k in order[:max(short, 0)]:
        units[k] += 1
    return {k: (v * grid).quantize(grid) for k, v in units.items()}


def main():
    ap = argparse.ArgumentParser(description="Compute attribution shares for a ledger window.")
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--label", default=None)
    ap.add_argument("--since", default=None, help="window start YYYY-MM-DD (default: first commit)")
    ap.add_argument("--until", default=None, help="window end YYYY-MM-DD (default: last commit)")
    args = ap.parse_args()
    repo = args.repo.resolve()
    cfg = yaml.safe_load((repo / "syndicate.yaml").read_text())

    # Operator rule #10: a mold is not a syndicate. anchor.py, drift_check.py,
    # verify_signatures.py and doctor.py all refuse one; this tool did not,
    # and it is the tool that decides money. Run in the template it produced a
    # complete window for `github-handle`, carrying an objection deadline and
    # the line "silence = ratification" - a ratifiable revenue split naming a
    # member who does not exist. Nothing downstream distinguishes that file
    # from a real one, and every repository generated from the template would
    # inherit it if it were ever committed here.
    if is_unprovisioned_template(cfg):
        sys.exit(
            "refusing to compute shares: syndicate.yaml still carries the\n"
            "template's placeholder member row, so this repository is a mold,\n"
            "not a syndicate (operator rule #10). A window computed here would\n"
            "name a member who does not exist and carry a real objection\n"
            "deadline. Replace the placeholder row with real members first.")

    members = cfg["members"]
    weights = cfg["attribution"]["weights"]
    window_days = cfg["governance"]["objection_window_days"]
    patterns = [re.compile(p) for p in cfg["attribution"]["exclude_authors_matching"]]
    def excluded(name, email):
        return any(p.search(name or "") or p.search(email or "") for p in patterns)
    # A member commits under more than one address in practice: a web-UI commit
    # uses the account's private noreply, a laptop uses whatever git config says.
    # Keying attribution on one address means the others score zero silently -
    # a member had every line of code they wrote counted as nothing for two
    # weeks because of exactly this (row 29). `emails:` lists the rest; the
    # primary `email` stays canonical so nothing downstream changes.
    aliases = {}
    for m in members:
        for addr in [m["email"]] + list(m.get("emails") or []):
            aliases[addr] = m["email"]
    mem_by_email = {m["email"]: m for m in members}
    mem_by_login = {m["github"]: m for m in members}
    head_tree = set(sh("git", "ls-tree", "-r", "--name-only", "HEAD", cwd=repo).splitlines())
    dates = sh("git", "log", "--pretty=format:%cd", "--date=short", "HEAD", cwd=repo).splitlines()
    start = args.since or min(dates)
    end = args.until or max(dates)
    if start > end:
        sys.exit("ERROR: --since " + start + " is after --until " + end)
    label = args.label or "{}-W{:02d}".format(*date.fromisoformat(end).isocalendar()[:2])
    churn = {m["email"]: ZERO for m in members}
    files = {m["email"]: set() for m in members}
    log = sh("git", "log", "--pretty=format:%H|%an|%ae|%cd", "--date=short", "--numstat", "HEAD", cwd=repo)
    cur = None
    for ln in log.splitlines():
        if not ln.strip():
            continue
        fields = ln.split("|")
        if len(fields) == 4 and len(fields[0]) == 40:
            an, ae, cd = fields[1].strip(), fields[2].strip(), fields[3].strip()
            cur = ((aliases[ae], cd) if (ae in aliases and start <= cd <= end
                                         and not excluded(an, ae)) else None)
        elif cur is not None and ln.count("\t") == 2:
            a, d, f = ln.split("\t")
            try:
                adds = int(a) if a != "-" else 0
                dels = int(d) if d != "-" else 0
            except ValueError:
                continue
            w = ONE if f in head_tree else SURVIVOR_WEIGHT
            churn[cur[0]] += Decimal(adds + dels) * w
            files[cur[0]].add(f)
    merges = {m["github"]: 0 for m in members}
    reviews = {m["github"]: 0 for m in members}
    remote = sh("git", "remote", "get-url", "origin", cwd=repo)
    m = re.search(r"github\.com[:/](.+?)(\.git)?$", remote)
    if m is None:
        # Review and merge credit is 0.25 of the weight and comes from the
        # GitHub API. Without a GitHub origin there is no way to fetch it,
        # and computing the window anyway would zero that quarter silently -
        # row 34, exactly. Every other tool here refuses with a reason; this
        # line used to raise AttributeError on .group(1) and hand the
        # operator a traceback instead.
        sys.exit(
            "refusing to compute shares: `origin` is not a GitHub remote, so "
            "review and merge credit cannot be fetched.\n  origin = " +
            (remote or "(none)") + "\nThat is " +
            str(int(Decimal(str(weights["review"])) * 100)) + "% of the weight; "
            "computing without it would silently score it zero for everyone.")
    owner_repo = m.group(1)
    prs = api_paged(API + "/repos/" + owner_repo + "/pulls?state=all&per_page=100")
    for pr in prs:
        merged_at = (pr.get("merged_at") or "")[:10]
        # merged_by is NOT in the list endpoint's summary representation - it
        # exists only on GET /pulls/{n}. Reading it off the list silently
        # scored every merge act as zero.
        if merged_at and start <= merged_at <= end:
            full, _ = api_get(API + "/repos/" + owner_repo + "/pulls/" + str(pr["number"]))
            mb = (full.get("merged_by") or {}).get("login")
            if mb in mem_by_login:
                merges[mb] += 1
        rv = api_paged(API + "/repos/" + owner_repo + "/pulls/" + str(pr["number"]) + "/reviews")
        for r_ in rv:
            who = (r_.get("user") or {}).get("login")
            when = (r_.get("submitted_at") or "")[:10]
            if who in mem_by_login and r_.get("state") in ("APPROVED", "COMMENTED", "CHANGES_REQUESTED") and start <= when <= end:
                reviews[who] += 1
    A = {m["email"]: (ONE + churn[m["email"]]).ln() for m in members}
    B = {m["email"]: (ONE + Decimal(len(files[m["email"]]))).ln() for m in members}
    R = {m["github"]: Decimal(reviews[m["github"]] + merges[m["github"]]) for m in members}
    def norm(d):
        mx = max(d.values()) if d else ZERO
        return {k: (v / mx if mx > 0 else ZERO) for k, v in d.items()}
    An, Bn, Rn = norm(A), norm(B), norm(R)
    wc, wb, wr = dec(weights["churn"]), dec(weights["breadth"]), dec(weights["review"])
    tw = wc + wb + wr
    x = {m["github"]: (wc * An[m["email"]] + wb * Bn[m["email"]] + wr * Rn[m["github"]]) / tw for m in members}
    # A window in which nobody did anything divides every share by this 1 and
    # yields zeros, which is the honest answer - not an equal split of nothing.
    tot = sum(x.values(), ZERO) or ONE
    shares = {k: v / tot for k, v in x.items()}
    published = apportion(shares, SHARE_PLACES)
    now_s = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    deadline = (datetime.now(timezone.utc) + timedelta(days=window_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_dir = repo / "ledger" / "windows" / label
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = ["github,email,churn_w,files,reviews,merges,A_log,B_log,R_acts,x_raw,share"]
    for m in members:
        g = m["github"]
        rows.append(",".join(str(v) for v in [g, m["email"], q(churn[m["email"]], 1), len(files[m["email"]]), reviews[g], merges[g], q(A[m["email"]], 4), q(B[m["email"]], 4), int(R[g]), q(x[g], 5), published[g]]))
    (out_dir / "attribution.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    evidence = {"window": {"label": label, "start": start, "end": end}, "members": members, "weights_used": {"churn": str(wc / tw), "breadth": str(wb / tw), "review": str(wr / tw)}, "raw": {m["github"]: {"churn_w": str(churn[m["email"]]), "files": sorted(files[m["email"]]), "reviews": reviews[m["github"]], "merges": merges[m["github"]]} for m in members}, "survivor_weight": str(SURVIVOR_WEIGHT), "clock": "committer dates; push-time gating is the admissible clock per 4.2 (v1 limitation)", "generated_at": now_s, "objection_deadline": deadline, "window_head": sh("git", "rev-parse", "HEAD", cwd=repo)}
    (out_dir / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("window", label, start, "->", end)
    for ln in rows: print(ln)
    print("objection deadline (silence = ratification):", deadline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
