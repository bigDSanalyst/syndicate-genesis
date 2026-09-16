# AUDIT-001 — external cold audit, tool-executing

**Auditor:** Claude Opus 5 (Claude Code session), no prior context.
**Date:** 2026-09-16.
**Subjects:** `syndicate-shakedown` (pass 1), `syndicate-genesis` @ `c599ca5` (pass 2).
**Outcome:** 16 findings, rows 27-42. Nine fixed and merged in `e38c5e8` (PR #1).

---

## Method, and why it is the finding that matters most

The audit executed the tooling instead of reading it. It ran `attribution.py`
and `anchor.py verify` against live repositories, queried the GitHub REST API
directly to check field shapes, parsed real `.ots` files with the `ots` CLI,
compiled the manifest's regexes against the names of bots that have actually
run, cross-checked every cited arXiv ID against the vault, and ran `join.py`
against an unmodified clone of the template.

Every finding below came from running something. None came from reading source
and forming an opinion. That distinction is not stylistic: **the most severe
finding in this audit (row 38) sits in code that reads fine.** `join.py` is
99 lines of clear, well-commented Python with a sensible failure message. A
reviewer reading it carefully would approve it. It could not parse the manifest
shipped in the same commit, and no amount of reading would have revealed that,
because the bug lives in the relationship between two files rather than inside
either one.

> **Prior audits of this project read *about* the system. This one ran it.**
> The gap between those two activities is the entire yield of AUDIT-001.

---

## Scope, and the error that proved productive

**Pass 1** audited `syndicate-shakedown` alone. The auditor did not know
`syndicate-genesis`, `FINDINGS.md`, `ROADMAP.md`, or the oracle layer existed.

That was a real error, and it produced real mistakes in both directions: template
bugs were reported as instance problems, and instance drift was reported as
current system state.

**Pass 2** added the template after the maintainer identified the blind spot.
It confirmed that six of pass 1's findings were byte-identical in the mold —
and found row 38, which does not exist in the shakedown at all, because
`join.py` postdates it.

The error is recorded here rather than quietly corrected, because the correction
*is* row 37:

> A single-repo audit of a multi-repo protocol verifies a projection, not the
> system. The propagation gap — fixes land in the mold and never reach
> already-generated repos — was invisible until an auditor mistook a stale
> instance for the current system. The recheckability principle this project
> applies to research applies to auditing itself.

---

## Findings by class

### Shipped in the template, inherited by every generated repo

Rows **27, 30, 31, 32, 33, 34** — verified byte-identical in both repos.
All except 27 are fixed in `e38c5e8`.

The pattern connecting 30, 31 and 34 is worth naming: **each is a place where
the tooling accepted a wrong answer instead of no answer.** The height regex
didn't crash, it recorded `null`. The `merged_by` lookup didn't fail, it
returned zero. The API error didn't stop the run, it degraded the window and
exited green. In a ledger that divides money, silence about a missing input is
more dangerous than a crash, and all three failed silently for the entire
operating life of the system.

### The v1.2 release regression

Rows **38, 39, 40**. The `# #` artifact appears in exactly five places, all in
v1.2-era files, and zero in any repo generated before v1.2. It is row 21's fix —
doubling comment markers — leaking into string literals, where a comment-marker
fix becomes a logic bug.

Row 21 was recorded as closed. It was not. It changed shape and moved somewhere
it had teeth. **The template's entry path was a brick from the moment the
template gained an entry path**, and Track 1's design-partner hand-hold would
have failed on its first use.

Rows 39 and 40 are in the same file and reachable by the same adopter following
the documented command: the PAT persisted in `.git/config` after exit, and every
git call ran through `shell=True` with adopter-supplied input interpolated.
SECURITY.md ranks secrets exposure as threat #2; the join path created it.

### Instance-level, `syndicate-shakedown`

Rows **28, 29, 35, 36**. Of these, row 29 deserves emphasis: it is row 17,
predicted in the ledger, occurring in production, unnoticed for twelve days, and
quantified only because someone ran the tool. The affected member's shares read
`0.7619 / 0.2381` with `churn=0.0, files=0` — every commit they authored scored
nothing.

**A correction to pass 1 belongs here.** Pass 1 reported the shakedown's
comment-poisoned queries as an oversight. They were not: `invariant-question.md`
labels its own corpus "a byproduct of finding #13". The operator diagnosed the
bug and left the instance deployed. That is a different failure from not
noticing, and row 28 states it accurately.

### Architectural

Rows **37, 41, 42**.

Row 41 was the uncomfortable one. At the time of the audit, `FINDINGS.md`
contained rows 1-22, while rows 23-26 were cited in planning as established
ledger rows and did not exist in the record. Agreement §1.2: *"Work done outside
it and not committed does not count for any purpose under this Agreement."* The
findings ledger is the single artifact that cannot afford uncommitted rows, and
it had four.

**Closed in `7182fd8`.** The maintainer reconstructed rows 23-26 from the session
record and committed them, with the violation itself noted in the commit message.
This document's rows resume at 27, so the references that were already in
circulation stay valid and the ledger now reads 1-42 unbroken. The row remains
in the ledger because a findings ledger records what happened, not only what is
still broken.

---

## What was fixed, and how it was verified

Nine findings fixed in `e38c5e8`, merged as `61455cf`. Verification used real
data at every step — never a fixture, because a fixture drifts from the template
in exactly the way that produced row 38:

```
row 30   0001-2026-09-04: confirmed=True  height=965528   min(965532, 965554, 965528)
         0007-2026-09-15: confirmed=False height=None     pending, correctly unconfirmed
row 33   syndicate-anchor[bot] / dependabot[bot] / github-actions[bot] → excluded
         1+founder@users.noreply.github.com                            → not excluded
rows 31/32/34   window 2026-09-08 → 2026-09-15, merges=1   (merges was permanently 0)
row 38   join.py inserts a parseable member row into an unmodified template
row 39   no ghp_ token remains in .git/config after exit
```

`tests/test_generation_smoke.py` generates a syndicate into a tmpdir with a real
local remote and runs every tool against what generation produced. Each guard
was mutation-tested — reverting any single fix fails that guard and only that
guard:

```
── revert join anchor  ──  1 failed, 7 passed, 1 skipped
── revert height regex ──  1 failed, 7 passed, 1 skipped
── revert bot pattern  ──  1 failed, 7 passed, 1 skipped
── revert PAT handling ──  1 failed, 7 passed, 1 skipped
── all restored        ──  8 passed, 1 skipped
```

A green suite that would not have gone red proves nothing. This one goes red.

---

## Deliberately not fixed

**Review-gate deadlock (row 9, still open).** The template ships one placeholder
member against `ledger/**: 2` and `agreements/**: 2` — gates no two-member
syndicate can satisfy. The manifest comment states the rule (`gates auto-cap at
members-1`) and nothing enforces it, so the shakedown inherited the deadlock and
is living in it. The smoke test *skips* rather than passes on an unedited
manifest and binds at genesis.

Lowering the defaults or implementing the auto-cap changes governance
thresholds. That is the maintainer's decision, not an auditor's, and PR #1
changed nothing.

---

## What pass 1 got wrong

Recorded because an audit that will not audit itself is the thing it warns about.

1. **Scope.** Reported instance state as system state, in both directions.
2. **Row 28.** Reported the poisoned queries as unnoticed. The vault note shows
   they were diagnosed and left. The real finding was row 37.
3. **Everything in the v1.2 regression class was outside pass 1's scope.** The
   most severe finding in this audit was invisible to the audit as first scoped
   — which is the strongest available argument for row 37, and for AUDIT-002.

## Recommended next audit

**AUDIT-002 — full corpus, cold, tool-executing.** Template, shakedown and
kernel together; same method; complete scope. The contrast is diagnostic:
whatever still fails in 002 is system-level truth, whatever disappears was
instance drift.

One refinement on method, from row 38: full context would not have caught
`join.py`. A cold auditor holding every document would still have read it and
found it plausible. What caught it was **generating a syndicate from scratch and
running every tool in the documented order.** AUDIT-002 should be built around
that act, not around reading a larger corpus.

The generation smoke test that now enforces it was the maintainer's proposal,
not the auditor's.
