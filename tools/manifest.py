#!/usr/bin/env python3
"""The manifest rules that must mean the same thing everywhere they are checked.

One definition, imported by join.py (which must not hand an adopter a manifest
their own suite rejects) and by the generation smoke suite (which is what an
adopter's CI runs). A rule stated twice is a rule that will disagree with itself.
"""

SOLO, MULTI = "solo", "multi"
PLACEHOLDER_HANDLE = "github-handle"
PLACEHOLDER_EPOCH = "YYYY-MM-DD"


def is_unprovisioned_template(cfg) -> bool:
    """True only while the manifest still carries the template's placeholder row."""
    members = cfg.get("members") or []
    return any(m.get("github") == PLACEHOLDER_HANDLE
               for m in members if isinstance(m, dict))


def formation_ok(cfg):
    """(True, "") when the roster and the declared formation agree.

    Solo is supported - the unaffiliated independent usually starts alone, and
    one human with stakes is a signer seat. What is NOT supported is arriving
    there by accident: a one-member manifest with no declaration is the shape
    that deadlocks on its first gated PR, and it is indistinguishable from a
    two-person syndicate whose second member never arrived. The declaration is
    what separates a decision from a misconfiguration, and it is what the
    operator bypass (ledger row 48) is justified by: a solo syndicate merges on
    the founder's own authority, with the anchor chain as the compensating
    control, and says so in its manifest where anyone auditing can read it.

    Sticky: a second member ends solo formation in the PR that adds them.
    """
    members = cfg.get("members") or []
    declared = (cfg.get("governance") or {}).get("formation")

    # A mold is not a syndicate (operator rule #10). It ships one placeholder row
    # and declares nothing, which is correct rather than undeclared-solo: the
    # question binds at genesis, when a real member replaces the placeholder.
    if is_unprovisioned_template(cfg):
        return True, ""

    if declared not in (SOLO, MULTI, None):
        return False, ("governance.formation is %r; it is 'solo' or 'multi'" % declared)
    if len(members) == 1 and declared != SOLO:
        return False, (
            "one member, and this syndicate has not declared itself solo. A review "
            "gate needs someone other than the author, so this manifest deadlocks "
            "on its first gated PR. If you are starting alone, set "
            "governance.formation: solo - supported, and the declaration is what "
            "makes merging on your own authority legible to anyone reading the "
            "record. If a second member is coming, add them before the first "
            "gated PR.")
    if len(members) > 1 and declared == SOLO:
        return False, (
            "governance.formation is solo but the roster has %d members. The "
            "marker is sticky: the second member ends solo formation, in the PR "
            "that adds them. Set it to multi." % len(members))
    return True, ""


def member_addresses(cfg):
    """{address: primary email} over every member's email and emails: aliases."""
    out = {}
    for m in cfg.get("members") or []:
        if not isinstance(m, dict) or not m.get("email"):
            continue
        for addr in [m["email"]] + list(m.get("emails") or []):
            out[addr] = m["email"]
    return out


def member_keys(cfg):
    """{primary email: [public key lines]} for members who listed any."""
    out = {}
    for m in cfg.get("members") or []:
        if isinstance(m, dict) and m.get("email"):
            out[m["email"]] = [k for k in (m.get("keys") or []) if str(k).strip()]
    return out


def signing_epoch(cfg):
    """(epoch, None) or (None, reason). Commits before the epoch are not checked.

    An epoch is required rather than defaulted because every repository that
    adopts signing has unsigned history behind it - including a freshly
    generated syndicate, whose first commit GitHub makes and signs with its own
    key. Defaulting to "all of history" would fail every repo on day one and
    teach its members to ignore the check; defaulting to "nothing" would ship a
    rule that never fires. So it is a decision, refused until made - the same
    shape as governance.formation.
    """
    epoch = (cfg.get("governance") or {}).get("signing_since")
    if not epoch or epoch == PLACEHOLDER_EPOCH:
        return None, ("governance.signing_since is not set. Put the date this "
                      "syndicate started signing commits (YYYY-MM-DD) - members "
                      "configure a key, then that date goes here. Commits before "
                      "it are not checked; commits after it must be signed by a "
                      "key this manifest lists for their author.")
    return str(epoch), None
