# Audits — what was found wrong in this syndicate

A record organ, beside `ledger/` (what this syndicate proved) and `agreements/`
(who it bound). This drawer holds what was found wrong in it.

## Convention

One file per audit, numbered in the order they were received:

    audits/AUDIT-001-<auditor>.md
    audits/AUDIT-002-<auditor>.md

Append-only in the sense that matters: an audit is a dated statement of what was
true when it was written. Later corrections are new files or new sections with
their own dates, never edits that make a past auditor appear to have said
something else. Findings that turn into fixes get their row in the record the
fix lands in, not a rewrite of the audit that found them.

## Why this is a root directory

`docs/` is inherited from the template and stripped at activation — so history
written about *this* repo and kept there would be one prompt away from deletion.
The strip list strips inheritance, not identity. An audit written about this
syndicate is this syndicate's history, even when it reads like narrative; the
template's own findings ledger is someone else's.

`tools/drift_check.py` treats everything under `audits/` as instance-owned and
never reports it as drift. This README is the exception: it is the drawer's
label, it ships from the template, and improvements to it should still reach you.

## What the drawer starts with: nothing

A generated syndicate's drawer is empty but for this file, the same way its
ledger starts with no anchor chain. An audit **of the template** is the
template's own scar tissue - the same category as its findings ledger - so it
lives in the template's `docs/` and is stripped at activation. If the mold kept
one here instead, every syndicate ever generated would inherit someone else's
audit as its own history, and the never-strip rule would protect it there
forever.

## What belongs here

External audits, cold reviews, security reviews, post-incident write-ups — any
dated assessment of this repo by someone, human or agent, who looked at it.

What does not: routine findings from your own work (those belong in the commit
and the ledger), and anything pre-publication confidential under Agreement §7,
which stays in `vault/40-drafts/`.
