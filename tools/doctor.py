#!/usr/bin/env python3
"""Where is this syndicate, and what is the next command?

The first thing an adopter should run, and safe to run at any time: it reads
the repository and writes nothing. Every other tool in this repo answers one
question and refuses when its precondition is missing. Useful, and between
them they leave an adopter to assemble the map themselves - which is the
support conversation this file exists to make unnecessary.

WHAT IT MAY AND MAY NOT DO
  It computes. It does not advise. Every line it prints is derived from the
  manifest and the repository state, so it inherits operator rule #8 - a green
  check must never lie - and the corollary this tool adds: it must never assert
  repository state it did not compute. That is also why `--json` exists. An
  agent reading this repo should run doctor and report what it returns, rather
  than reading the manifest and narrating its own impression of it.

  The rules themselves live in tools/manifest.py, imported here. A rule stated
  twice is a rule that will disagree with itself (finding #38's lesson, again),
  and doctor is exactly the place that temptation is strongest: it touches
  every rule in the repo and none of them are its own.

STATUSES
  ok      nothing owed
  DECIDE  a decision this syndicate has not made yet. Not a fault: a fresh
          syndicate legitimately owes several. Each one names the tool that
          will refuse until it is made, so the consequence is never a surprise.
  WARN    works, but something is off or unfinished
  BLOCK   wrong now - a tool will refuse, or a record is being written wrong

EXIT
  0  no BLOCK (decisions may still be owed - they are listed, and named)
  1  at least one BLOCK

This tool is deliberately offline. It never calls the network, so it cannot
hang or rate-limit on the one command an adopter runs before anything works.
Drift against the template needs the network, so doctor reports whether a
lineage exists and hands you `drift_check.py check` rather than running it.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest as M                                          # noqa: E402

try:
    import yaml
except ImportError:                                           # pragma: no cover
    print("doctor needs PyYAML: pip install -r tools/requirements.txt", file=sys.stderr)
    sys.exit(1)

OK, DECIDE, WARN, BLOCK = "ok", "DECIDE", "WARN", "BLOCK"
NARRATIVE = ("FINDINGS.md", "ROADMAP.md", "docs")


class Check:
    """One computed finding. `fix` is a command or an act, never an opinion."""

    def __init__(self, key, status, headline, detail="", fix=""):
        self.key, self.status = key, status
        self.headline, self.detail, self.fix = headline, detail, fix

    def as_dict(self):
        return {"check": self.key, "status": self.status, "headline": self.headline,
                "detail": self.detail, "fix": self.fix}


def git(repo, *args):
    """Stdout, or None. Never raises: doctor runs in repos that are mid-mess."""
    try:
        r = subprocess.run(("git",) + args, cwd=str(repo), text=True,
                           capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


# ─────────────────────────────── the checks ───────────────────────────────

def check_gates(cfg):
    """Operator rule #2. A gate above members-1 deadlocks; the cap is not advice."""
    members = cfg.get("members") or []
    gates = (cfg.get("governance") or {}).get("review_gates") or {}
    cap = max(len(members) - 1, 1)
    over = {p: n for p, n in gates.items() if isinstance(n, int) and n > cap}
    if not over:
        return Check("gates", OK, "review gates are within max(members-1, 1) = %d" % cap)
    return Check(
        "gates", BLOCK,
        "%d review gate(s) above the cap of %d" % (len(over), cap),
        "GitHub will not let an author approve their own pull request, so a gate "
        "of %d needs %d other members and this roster has %d. Every PR touching "
        "%s deadlocks - and it deadlocks at merge time, after the work is done. "
        "A gate of 0 is not the fix: Agreement 10.1 needs at least one approving "
        "review to exist."
        % (max(over.values()), max(over.values()), len(members),
           ", ".join(sorted(over))),
        "edit governance.review_gates in syndicate.yaml: " +
        ", ".join("%s -> %d" % (p, cap) for p in sorted(over)))


def check_identity(repo, cfg):
    """Operator rule #9. The silent one: unregistered commits score zero."""
    email = git(repo, "config", "--get", "user.email")
    addrs = M.member_addresses(cfg)
    if not email:
        return Check(
            "identity", BLOCK, "this clone has no git author address configured",
            "attribution.py reads the commit author address and matches it "
            "against the manifest. With none set, git will guess one from your "
            "hostname and every commit you make scores zero.",
            "git config user.email <the address in your manifest row>")
    if email in addrs:
        return Check("identity", OK, "you commit as %s, which your manifest row claims" % email)
    return Check(
        "identity", BLOCK,
        "you commit as %s, which no manifest row claims" % email,
        "Operator rule #9: email is identity. Commits from an unregistered "
        "address do not fail - they are invisible to attribution.py, and score "
        "zero in every window until someone notices. Registered addresses: " +
        (", ".join(sorted(addrs)) or "(none)"),
        "git config user.email <your registered address>, or add this address "
        "to your manifest row's `emails:` aliases by PR")


def check_signing(repo, cfg):
    """The epoch is a decision, not a default - manifest.signing_epoch says why."""
    epoch, why = M.signing_epoch(cfg)
    if why:
        return [Check(
            "signing.epoch", DECIDE,
            "this syndicate has not set the date it started signing commits",
            why + " Until it is set, tools/verify_signatures.py exits 1 and the "
            "verify-signatures workflow cannot pass.",
            "each member adds their SSH signing public key to their manifest row "
            "(`keys:`), then set governance.signing_since to that date - one PR, "
            "through the gate, because that review IS the trust decision")]

    out, keys = [], M.member_keys(cfg)
    keyless = sorted(m for m, k in keys.items() if not k)
    if keyless:
        out.append(Check(
            "signing.keys", BLOCK,
            "signing is in force since %s, and %d member(s) list no key" % (epoch, len(keyless)),
            "Every commit these members author after %s fails verification, "
            "because there is no key on file to verify it against: %s"
            % (epoch, ", ".join(keyless)),
            "each listed member adds their SSH signing public key line to their "
            "own manifest row by PR - it is their row, so the change should "
            "arrive through the gate rather than around it"))
    else:
        out.append(Check("signing.keys", OK,
                         "signing in force since %s; every member lists a key" % epoch))

    email = git(repo, "config", "--get", "user.email")
    primary = M.member_addresses(cfg).get(email or "")
    if primary and keys.get(primary):
        fmt = git(repo, "config", "--get", "gpg.format")
        signing = git(repo, "config", "--get", "user.signingkey")
        if not signing:
            out.append(Check(
                "signing.local", BLOCK,
                "your manifest row lists a key, but this clone is not configured to sign",
                "Your row promises signatures this clone cannot produce, so your "
                "own next commit is the one that fails the check.",
                "git config gpg.format ssh && git config user.signingkey "
                "<path to your public key> && git config commit.gpgsign true"))
        elif fmt != "ssh":
            out.append(Check(
                "signing.local", WARN,
                "this clone signs with gpg.format=%s; the manifest carries SSH keys"
                % (fmt or "openpgp"),
                "verify_signatures.py matches the signing key fingerprint against "
                "the SSH key lines in your row. A signature in another format "
                "will not match one.",
                "git config gpg.format ssh"))
        else:
            out.append(Check("signing.local", OK, "this clone is configured to sign with SSH"))
    return out


def check_lineage(repo, cfg):
    """No lineage means this fork can never learn that the template moved."""
    t = cfg.get("template") or {}
    commit = t.get("commit")
    if commit and commit != "RECORD-AT-ACTIVATION":
        return Check(
            "lineage", OK,
            "lineage recorded at %s (%s@%s)" % (commit[:12], t.get("repo"), t.get("ref") or "main"),
            "Run `python3 tools/drift_check.py check` to see what the template "
            "has changed since then. That needs the network, so doctor does not "
            "run it for you.")
    return Check(
        "lineage", BLOCK, "no template lineage recorded",
        "Without a lineage commit there is nothing to diff against, so this "
        "repository can never be told that the template fixed something. Every "
        "fix the mold has made since you generated stays invisible.",
        "python3 tools/drift_check.py record")


def check_narrative(repo):
    """The landmine: docs/ is inherited, but a syndicate's own audit may be in it."""
    present = [n for n in NARRATIVE if (repo / n).exists()]
    if not present:
        return Check("narrative", OK, "the template's narrative is not present")
    audits = sorted(p.name for p in (repo / "docs").glob("AUDIT-*")) if (repo / "docs").is_dir() else []
    if audits:
        return Check(
            "narrative", BLOCK,
            "docs/ holds %d file(s) that are this repository's own record" % len(audits),
            "docs/ is on the strip list, so the next `bash bootstrap.sh` offers to "
            "delete it - and these go with it: %s. The strip list strips "
            "inheritance, not identity. An audit of this syndicate is identity."
            % ", ".join(audits),
            "git mv " + " ".join("docs/" + a for a in audits) + " audits/   "
            "(git mv, so the history follows the file)")
    return Check(
        "narrative", WARN,
        "the template's narrative is still present: " + ", ".join(present),
        "FINDINGS.md is the mold's scar tissue and ROADMAP.md is the protocol's "
        "priorities, not this syndicate's. They live on in the template repo, "
        "which your lineage points at. Harmless, but they will read as yours.",
        "bash bootstrap.sh   (it offers the strip, and warns before it takes anything)")


def check_agreement(repo, cfg):
    """Unexecuted agreement: the governance is described but not yet binding."""
    log = repo / "agreements" / "EXECUTION-LOG.md"
    if not log.exists():
        return Check("agreement", WARN, "agreements/EXECUTION-LOG.md is missing",
                     "This is the record of who bound themselves to the Agreement.",
                     "restore it from the template")
    rows = 0
    for line in log.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|") and not re.match(r"^\|[\s:|-]+\|$", s):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 5 and cells[0] and cells[0] != "Member":
                rows += 1
    total = len(cfg.get("members") or [])
    if rows >= total and total:
        return Check("agreement", OK, "all %d member(s) have executed the Agreement" % total)
    return Check(
        "agreement", DECIDE,
        "%d of %d member(s) have executed the Agreement" % (rows, total),
        "Until a member's row is in the execution log, this repository describes "
        "governance that does not yet bind them. Agreement 10.1: the act is a "
        "merged PR adding the row, carrying an approving review from someone "
        "other than the signer - submit the approval BEFORE merging.",
        "sha256sum agreements/consortium-agreement.md, add your row to "
        "agreements/EXECUTION-LOG.md, open a PR, get the approval, merge")


def check_anchors(repo):
    """Pending stamps are not proof yet - they are a promise of proof."""
    log = repo / "ledger" / "anchors" / "log.jsonl"
    if not log.exists():
        return Check(
            "anchors", DECIDE, "this syndicate has never anchored its state",
            "The anchor chain is the compensating control the whole record leans "
            "on - and for a solo syndicate it is the only external witness that "
            "the record existed when it says it did.",
            "python3 tools/anchor.py run, then dispatch the anchor workflow")
    pending = 0
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            if json.loads(line).get("status") == "pending":
                pending += 1
        except ValueError:
            continue
    if not pending:
        return Check("anchors", OK, "no anchors are waiting on a Bitcoin block")
    return Check(
        "anchors", WARN, "%d anchor(s) are stamped but not yet Bitcoin-confirmed" % pending,
        "A pending stamp proves nothing on its own. Confirmation usually lands "
        "within a day; an upgrade is what writes the block height into the record.",
        "python3 tools/anchor.py upgrade")


# ───────────────────────────────── driver ─────────────────────────────────

def run(repo):
    """(checks, is_mold). Ordered: the earlier a check, the more it blocks."""
    mpath = repo / "syndicate.yaml"
    if not mpath.exists():
        return [Check("manifest", BLOCK, "no syndicate.yaml here",
                      "doctor runs from the root of a syndicate repository.",
                      "cd to the repository root")], False
    try:
        cfg = yaml.safe_load(mpath.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        return [Check("manifest", BLOCK, "syndicate.yaml does not parse",
                      str(e).replace("\n", " ")[:300],
                      "fix the YAML; every tool in this repo reads this file first")], False

    checks = [Check("manifest", OK, "syndicate.yaml parses, %d member row(s)"
                    % len(cfg.get("members") or []))]

    ok, why = M.formation_ok(cfg)
    checks.append(Check("formation", OK, "formation: %s, %d member(s)"
                        % ((cfg.get("governance") or {}).get("formation") or "undeclared",
                           len(cfg.get("members") or [])))
                  if ok else
                  Check("formation", BLOCK, "the roster and the declared formation disagree",
                        why, "edit governance.formation in syndicate.yaml"))
    checks.append(check_gates(cfg))

    # A mold is not a syndicate (operator rule #10). Everything below this line
    # asks a question only a real syndicate can answer - whose key, whose
    # identity, whose lineage - and the template answers all of them with
    # placeholders. Asking them here would hand every adopter a wall of red on
    # a repository that is behaving exactly as designed, which is how a check
    # teaches people to ignore it.
    if M.is_unprovisioned_template(cfg):
        return checks, True

    checks.append(check_identity(repo, cfg))
    checks.extend(check_signing(repo, cfg))
    checks.append(check_lineage(repo, cfg))
    checks.append(check_narrative(repo))
    checks.append(check_agreement(repo, cfg))
    checks.append(check_anchors(repo))
    return checks, False


def wrap(text, width, indent):
    out, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(line)
    return ("\n" + indent).join(out)


def render(checks, is_mold, repo, verbose):
    name = "syndicate"
    try:
        cfg = yaml.safe_load((repo / "syndicate.yaml").read_text(encoding="utf-8")) or {}
        name = (cfg.get("syndicate") or {}).get("name") or name
    except Exception:
        pass
    print("syndicate doctor - " + str(name))
    print()

    for c in checks:
        print("  %-7s %s" % (c.status if c.status != OK else "ok", c.headline))
        if c.status != OK or verbose:
            if c.detail:
                print("          " + wrap(c.detail, 68, "          "))
            if c.fix:
                print("          next: " + wrap(c.fix, 62, "                "))
            print()

    if is_mold:
        print("  This is the template itself, not a syndicate - it still carries the")
        print("  placeholder member row, so the checks that ask whose key, whose")
        print("  identity and whose lineage do not apply to it (operator rule #10).")
        print()
        print("  To start a syndicate: generate a repository from this template on")
        print("  GitHub, replace the placeholder member row with a real one, then run")
        print("  `bash bootstrap.sh` in your clone and `python3 tools/doctor.py` again.")
        return 0

    blocks = [c for c in checks if c.status == BLOCK]
    decides = [c for c in checks if c.status == DECIDE]
    if blocks:
        print("  Start here: " + blocks[0].headline)
        if blocks[0].fix:
            print("    " + blocks[0].fix.split("   ")[0])
        print()
    if decides:
        print("  Decisions this syndicate owes (not faults - nothing is broken):")
        for c in decides:
            print("    - " + c.headline)
        print()
    print("  %d blocked, %d decision(s) owed, %d warning(s)."
          % (len(blocks), len(decides), len([c for c in checks if c.status == WARN])))
    return 1 if blocks else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=".", help="repository root (default: here)")
    ap.add_argument("--json", action="store_true",
                    help="machine-readable; what an agent should read instead of "
                         "forming its own impression of the manifest")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="show detail for passing checks too")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()

    checks, is_mold = run(repo)
    if a.json:
        blocked = [c for c in checks if c.status == BLOCK]
        print(json.dumps({
            "is_template": is_mold,
            "blocked": len(blocked),
            "decisions_owed": len([c for c in checks if c.status == DECIDE]),
            "next": blocked[0].as_dict() if blocked else None,
            "checks": [c.as_dict() for c in checks],
        }, indent=2))
        return 1 if blocked else 0
    return render(checks, is_mold, repo, a.verbose)


if __name__ == "__main__":
    sys.exit(main())
