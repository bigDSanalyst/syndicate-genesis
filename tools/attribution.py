#!/usr/bin/env python3
"""Attribution ledger: per-member shares from the Repository Record (Agreement section 4).

Sources: git numstat -> churn/breadth (survivorship-weighted); GitHub API ->
review + merge acts; prompts out of scope (weights renormalized). Identity by
manifest email/handle; display names are cosmetic. Merge acts credit the merger
(GitHub authors merge commits as the PR author - author-only parsing would
mis-attribute governance acts). Bots excluded via exclude_authors_matching.
"""
import argparse
import json
import math
import re
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

import yaml

SURVIVOR_WEIGHT = 0.3
API = "https://api.github.com"


def sh(*args, cwd):
    r = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if r.returncode != 0:
        sys.exit("ERROR: git command failed: " + r.stderr.strip())
    return r.stdout.strip()


def api_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "syndicate-attribution/1.0", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except Exception as e:
        print("WARNING: API failed (review credit degraded):", url, "->", e)
        return None


def main():
    ap = argparse.ArgumentParser(description="Compute attribution shares for a ledger window.")
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--label", default=None)
    args = ap.parse_args()
    repo = args.repo.resolve()
    cfg = yaml.safe_load((repo / "syndicate.yaml").read_text())
    members = cfg["members"]
    weights = cfg["attribution"]["weights"]
    window_days = cfg["governance"]["objection_window_days"]
    patterns = [re.compile(p) for p in cfg["attribution"]["exclude_authors_matching"]]
    def excluded(name, email):
        return any(p.search(name or "") or p.search(email or "") for p in patterns)
    mem_by_email = {m["email"]: m for m in members}
    mem_by_login = {m["github"]: m for m in members}
    head_tree = set(sh("git", "ls-tree", "-r", "--name-only", "HEAD", cwd=repo).splitlines())
    dates = sh("git", "log", "--pretty=format:%cd", "--date=short", "HEAD", cwd=repo).splitlines()
    start, end = min(dates), max(dates)
    label = args.label or "{}-W{:02d}".format(*date.fromisoformat(end).isocalendar()[:2])
    churn = {m["email"]: 0.0 for m in members}
    files = {m["email"]: set() for m in members}
    log = sh("git", "log", "--pretty=format:%H|%an|%ae|%cd", "--date=short", "--numstat", "HEAD", cwd=repo)
    cur = None
    for ln in log.splitlines():
        if not ln.strip():
            continue
        fields = ln.split("|")
        if len(fields) == 4 and len(fields[0]) == 40:
            an, ae, cd = fields[1].strip(), fields[2].strip(), fields[3].strip()
            cur = (ae, cd) if (ae in mem_by_email and start <= cd <= end and not excluded(an, ae)) else None
        elif cur is not None and ln.count("\t") == 2:
            a, d, f = ln.split("\t")
            try:
                adds = int(a) if a != "-" else 0
                dels = int(d) if d != "-" else 0
            except ValueError:
                continue
            w = 1.0 if f in head_tree else SURVIVOR_WEIGHT
            churn[cur[0]] += (adds + dels) * w
            files[cur[0]].add(f)
    merges = {m["github"]: 0 for m in members}
    reviews = {m["github"]: 0 for m in members}
    remote = sh("git", "remote", "get-url", "origin", cwd=repo)
    owner_repo = re.search(r"github\.com[:/](.+?)(\.git)?$", remote).group(1)
    prs = api_get(API + "/repos/" + owner_repo + "/pulls?state=all&per_page=100") or []
    for pr in prs:
        mb = (pr.get("merged_by") or {}).get("login")
        merged_at = (pr.get("merged_at") or "")[:10]
        if mb in mem_by_login and start <= merged_at <= end:
            merges[mb] += 1
        rv = api_get(API + "/repos/" + owner_repo + "/pulls/" + str(pr["number"]) + "/reviews") or []
        for r_ in rv:
            who = (r_.get("user") or {}).get("login")
            when = (r_.get("submitted_at") or "")[:10]
            if who in mem_by_login and r_.get("state") in ("APPROVED", "COMMENTED", "CHANGES_REQUESTED") and start <= when <= end:
                reviews[who] += 1
    A = {m["email"]: math.log(1 + churn[m["email"]]) for m in members}
    B = {m["email"]: math.log(1 + len(files[m["email"]])) for m in members}
    R = {m["github"]: float(reviews[m["github"]] + merges[m["github"]]) for m in members}
    def norm(d):
        mx = max(d.values()) if d else 0
        return {k: (v / mx if mx > 0 else 0.0) for k, v in d.items()}
    An, Bn, Rn = norm(A), norm(B), norm(R)
    tw = weights["churn"] + weights["breadth"] + weights["review"]
    x = {m["github"]: (weights["churn"] * An[m["email"]] + weights["breadth"] * Bn[m["email"]] + weights["review"] * Rn[m["github"]]) / tw for m in members}
    tot = sum(x.values()) or 1.0
    shares = {k: v / tot for k, v in x.items()}
    now_s = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    deadline = (datetime.now(timezone.utc) + timedelta(days=window_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_dir = repo / "ledger" / "windows" / label
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = ["github,email,churn_w,files,reviews,merges,A_log,B_log,R_acts,x_raw,share"]
    for m in members:
        g = m["github"]
        rows.append(",".join(str(v) for v in [g, m["email"], round(churn[m["email"]], 1), len(files[m["email"]]), reviews[g], merges[g], round(A[m["email"]], 4), round(B[m["email"]], 4), int(R[g]), round(x[g], 5), round(shares[g], 4)]))
    (out_dir / "attribution.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    evidence = {"window": {"label": label, "start": start, "end": end}, "members": members, "weights_used": {"churn": weights["churn"] / tw, "breadth": weights["breadth"] / tw, "review": weights["review"] / tw}, "raw": {m["github"]: {"churn_w": churn[m["email"]], "files": sorted(files[m["email"]]), "reviews": reviews[m["github"]], "merges": merges[m["github"]]} for m in members}, "survivor_weight": SURVIVOR_WEIGHT, "clock": "committer dates; push-time gating is the admissible clock per 4.2 (v1 limitation)", "generated_at": now_s, "objection_deadline": deadline, "window_head": sh("git", "rev-parse", "HEAD", cwd=repo)}
    (out_dir / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("window", label, start, "->", end)
    for ln in rows: print(ln)
    print("objection deadline (silence = ratification):", deadline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
