#!/usr/bin/env python3
"""The manifest rules that must mean the same thing everywhere they are checked.

One definition, imported by join.py (which must not hand an adopter a manifest
their own suite rejects) and by the generation smoke suite (which is what an
adopter's CI runs). A rule stated twice is a rule that will disagree with itself.
"""

SOLO, MULTI = "solo", "multi"
PLACEHOLDER_HANDLE = "github-handle"


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
