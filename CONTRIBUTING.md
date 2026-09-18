# Contributing

Outside pull requests are welcome, including on the governance text. This file
says what will and won't get merged, so you find out before you write the patch
rather than after.

## What this repository is

A template. Every file here is copied into somebody's research syndicate the
moment they press **Use this template**, so a change here is a change to repos
you will never see. That asymmetry drives most of the rules below.

## Before you open a PR

```bash
pip install -r tests/requirements.txt
python -m pytest tests/ -q
```

The suite generates a syndicate into a temporary directory — with a real local
git remote — and runs the tools against what generation actually produced. It
does not use fixtures, because a fixture drifts from the template in exactly the
way that shipped `join.py` unable to parse the manifest in the same commit
(finding #38). It needs no network: GitHub and arXiv calls are stubbed.

## The rules a patch is judged by

**1. Fix the template first.** If a defect exists in both this repo and a
generated instance, the fix lands here first and propagates outward. A fix
applied only to an instance is a defect every future syndicate still inherits.
This is the most repeated lesson in `FINDINGS.md` — it has its own row number
(37) and it fired three times in the session that closed it.

**2. A guard must be mutation-tested.** If you add a check, break the thing it
checks and watch the check fail, then restore it. A test that passes whether or
not the defect is present is worse than no test, because it makes the next
person confident. Three guards in this suite passed for the wrong reason and
were only caught this way: two asserted an exit code that a *different* guard
also produced, and one answered "no" to a prompt where declining saved
everything regardless.

**3. A green check must never lie.** Operator rule #8. A tool that cannot reach
its API exits differently from one that looked and found nothing. `0` means
"I looked", never "I could not look" — see the exit-code split in
`tools/ingest_arxiv.py`, `tools/ingest_repos.py` and `tools/drift_check.py`.

**4. Never commit an anchor chain, or an audit, to the mold.** A template is
not a syndicate (operator rule #10). Anything in `ledger/` or `audits/` here is
inherited by every repo generated from this one, as if it were their own
history. Guarded, but do not make the guard do the work.

**5. Machinery and rules are inherited; narrative is not.** `FINDINGS.md`,
`ROADMAP.md` and `docs/` are this repository's own scar tissue and priorities.
They are stripped at activation, and `tools/drift_check.py` ignores changes to
them. One constant, `STRIP_AT_ACTIVATION`, decides both.

**6. A rule lives in one place.** If a check must mean the same thing in a tool
and in the suite, it goes in `tools/manifest.py` and both import it. A rule
stated twice is a rule that will disagree with itself.

## Commits and identity

Your commit email is your identity here: `tools/attribution.py` computes member
shares from committer identity, so a commit from an unregistered address is
invisible to it. You do not need to be in `syndicate.yaml` to contribute to the
template — that manifest is this repo's own membership, not a contributor list.

Write commit messages that say what changed and *why it was not the obvious
thing* — the ledger's value is in the reasoning, not the diff.

## What gets rejected

- A guard with no mutation test behind it
- A fix applied to an instance but not to this template
- A test that skips on the condition it exists to check (a skip let a review
  gate of `0` reach `main` once — see row 9)
- A change to the consortium agreement's substance without a matching note in
  `FINDINGS.md` saying what problem it solves. The agreement is executed by real
  signatures against a hash; changing it is a governance act, not a typo fix.

## Reporting a vulnerability

Do not open a public issue. See `SECURITY.md` — GitHub security advisories on
this repository, or contact the maintainers directly.
