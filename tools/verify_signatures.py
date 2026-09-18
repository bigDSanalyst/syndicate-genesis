#!/usr/bin/env python3
"""Every member commit after the signing epoch is signed by a key this manifest
lists for that member.

WHY GIT'S OWN CHECK IS NOT ENOUGH
---------------------------------
`git verify-commit` answers "is this signature good, by a key in the allowed
signers file". It does NOT check that the key belongs to the commit's author.
Measured, not assumed: a commit authored by t@example.com and signed with a key
listed under someone-else@example.com reports `%G?` = G and exits 0.

So a tool that trusted git's boolean would let any member sign as any other
member - the exact impersonation this feature exists to prevent, passing green.
This tool therefore checks two things per commit: git says the signature is good
(the cryptography), AND the signing key's fingerprint is one the manifest lists
for that commit's author (the binding). Neither alone is the guarantee.

WHAT IS NOT CHECKED, AND WHY
----------------------------
* Commits before `governance.signing_since`. Every repo adopting signing has
  unsigned history behind it; the epoch is where the rule starts.
* Merge commits. GitHub's merge button signs with GitHub's key, not the
  merger's, and the gate - not a signature - is what authorises a merge. The
  content a merge carries was signed on the branch it came from. Residual risk:
  an "evil merge" that introduces changes present in neither parent would pass
  here; the review gate is what catches that.
* Commits by non-members, including the anchor and ingest bots. They are not in
  the manifest, so there is no key to check against and no member to impersonate.

Exit codes: 0 every checked commit is properly signed; 1 a violation, or the
epoch is unset (needs a human either way).
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manifest import (is_unprovisioned_template, member_addresses,  # noqa: E402
                      member_keys, signing_epoch)

GOOD = "G"          # git's status for a good signature by an allowed key


def sh(*args, cwd=None, check=True):
    r = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and r.returncode != 0:
        sys.exit("ERROR: " + " ".join(args) + " -> " + r.stderr.strip())
    return r.stdout


def fingerprint(pubkey: str):
    """SHA256:... for a public key line, via ssh-keygen. None if unreadable."""
    with tempfile.NamedTemporaryFile("w", suffix=".pub", delete=False) as fh:
        fh.write(pubkey.strip() + "\n")
        path = fh.name
    try:
        out = sh("ssh-keygen", "-lf", path, check=False)
        parts = out.split()
        return parts[1] if len(parts) > 1 and parts[1].startswith("SHA256:") else None
    finally:
        Path(path).unlink(missing_ok=True)


def allowed_signers(keys_by_email) -> str:
    """git's allowed-signers format. Every listed key, under its owner."""
    lines = []
    for email, keys in sorted(keys_by_email.items()):
        for k in keys:
            lines.append('%s namespaces="git" %s' % (email, k.strip()))
    return "\n".join(lines) + ("\n" if lines else "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--since", help="override governance.signing_since")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    cfg = yaml.safe_load((repo / "syndicate.yaml").read_text(encoding="utf-8")) or {}

    if is_unprovisioned_template(cfg):
        print("not a syndicate yet: a mold has no members to hold keys "
              "(operator rule #10). Nothing to verify.")
        return 0

    epoch = args.since
    if not epoch:
        epoch, why = signing_epoch(cfg)
        if not epoch:
            print("❌ " + why)
            return 1

    aliases = member_addresses(cfg)
    keys = member_keys(cfg)
    missing = [e for e, k in keys.items() if not k]
    if missing:
        print("❌ these members list no signing key, so their commits cannot be "
              "verified:\n  " + "\n  ".join(missing) +
              "\n  Add `keys:` to their manifest row - see README, "
              "\"Signing your commits\".")
        return 1

    prints = {email: {fingerprint(k) for k in ks} - {None}
              for email, ks in keys.items()}

    signers = repo / ".git" / "syndicate-allowed-signers"
    signers.parent.mkdir(parents=True, exist_ok=True)
    signers.write_text(allowed_signers(keys), encoding="utf-8")

    fmt = "%H%x1f%G?%x1f%GK%x1f%ae%x1f%cI%x1f%P"
    # The epoch is applied here, not by `git log --since`. Git's date parser
    # silently ignores what it cannot read - `--since=2999-01-01` returned the
    # whole history rather than nothing - so a filter that matters is not left to
    # approxidate. ISO dates compare correctly as strings; a commit ON the epoch
    # date is checked.
    log = sh("git", "-c", "gpg.ssh.allowedSignersFile=" + str(signers),
             "log", "--format=" + fmt, cwd=repo)

    checked = skipped = 0
    bad = []
    for line in log.splitlines():
        if not line.strip():
            continue
        sha, status, key, author, when, parents = line.split("\x1f")
        if when[:10] < epoch:                 # before this syndicate signed
            skipped += 1
            continue
        if len(parents.split()) > 1:          # merge: see the docstring
            skipped += 1
            continue
        if author not in aliases:             # not a member: bots, outsiders
            skipped += 1
            continue
        member = aliases[author]
        checked += 1
        if status != GOOD:
            bad.append((sha, member, when, "not signed by an allowed key "
                                           "(git status %r)" % status))
        elif key not in prints.get(member, set()):
            # Git said the signature is good; it did not say whose key it is.
            bad.append((sha, member, when,
                        "signed with %s, which this manifest does not list for "
                        "%s - a good signature by the wrong member is still "
                        "impersonation" % (key or "an unknown key", member)))

    print("signing epoch: %s | checked %d member commit(s), skipped %d "
          "(merges, bots, non-members)" % (epoch, checked, skipped))
    if not bad:
        print("✅ every checked commit is signed by a key its author's row lists")
        return 0
    print("\n%d commit(s) fail the signing rule:\n" % len(bad))
    for sha, member, when, why in bad:
        print("  %s  %s  %s\n      %s" % (sha[:12], when[:10], member, why))
    print("\nThis is not repaired by a rewrite: history that is already pushed "
          "stays as it is.\nFix the cause (configure your key, see README), and "
          "if these commits predate\nthis syndicate's signing practice, move "
          "governance.signing_since forward -\nthrough a PR, like any other "
          "governance change.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
