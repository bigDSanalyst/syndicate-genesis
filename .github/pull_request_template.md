## What this changes, and why it wasn't the obvious thing

<!-- The diff says what. This says why. A reason is what makes the next person
     able to change it safely. -->

## Checks

- [ ] `python -m pytest tests/ -q` passes locally
- [ ] If this adds a guard: I broke the thing it checks and watched the guard
      fail, then restored it. A guard that passes either way is worse than none.
- [ ] If this fixes something that also exists in a generated instance: the fix
      lands **here first** (row 37), and the instance follows.
- [ ] No anchor chain, audit, or narrative committed to the template — it is
      inherited by every syndicate generated from this repo (operator rule #10).

## If this touches `agreements/`

> **This repository is not legal advice.** The consortium agreement is a
> template that has not been reviewed by counsel for any jurisdiction. Changing
> its substance is a governance act, not a typo fix: say what problem the change
> solves, and record it in `FINDINGS.md`. Anyone adopting it should have their
> own counsel redline it first.

- [ ] Substantive change to the agreement → a `FINDINGS.md` row explaining it
- [ ] Signatures already executed against the old hash are accounted for
