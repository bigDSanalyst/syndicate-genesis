# Publication path — spec for `deposit_zenodo.py`

**Status:** spec. Not built. One design decision is deliberately open (§4).

---

> **Scope note.** This document treats the arXiv endorsement gate at length
> because it is unrecoverable when it bites, not because it is common. Most
> syndicates will have a member who can submit. The Zenodo-first ordering in
> §3 stands on its own merits for everyone: it is where data and code get a
> DOI, ungated, regardless of who is on the roster.

## 1. Why this tool comes before the ingest tools

`ingest_repos.py` and `ingest_people.py` add intake. Reading was never the
bottleneck — the vault holds 100 notes nobody has published from.

`deposit_zenodo.py` closes the first loop the protocol has: gate-approved draft
→ deposit → DOI → back into the record → anchored. It is the only unbuilt tool
that removes a blocker instead of adding material, and the blocker it removes is
the one the whole Phase 3 story rests on.

## 2. The constraint that sets the order

arXiv requires an **endorsement** for a member's first submission in a category.
It is granted by an established author in that category and registered in
arXiv's system — external, institutional, and not something a syndicate can
create, simulate, or approve its way around.

Most researchers never notice it because **institutional affiliation
auto-endorses**, and most adopters of this protocol are expected to be students
and researchers already publishing - people who hold an endorsement or get one
from a supervisor without friction. **For them arXiv is available and this
section is background.**

It matters for the minority it applies to, and there it is absolute. A syndicate
of unaffiliated independents may hold zero endorsements between them, and no
amount of internal governance produces one. The failure is quiet and late: it
surfaces at submission, after the work is done, which is why Activation states
it at genesis instead.

The protocol therefore has **two single-point external dependencies**, and they
have the same shape:

| | one member must hold | the group cannot create it because |
|---|---|---|
| **Settlement Agent** (§6.2) | a counterparty a buyer will sign with | trust is external |
| **Endorsed submitter** | a credential arXiv will accept | standing is external |

§6.2 is written carefully — appointment, duties, breach. The endorsement
equivalent was not written at all before this document.

## 3. The sequence

```
draft in 40-drafts/  →  publication PR  →  gate approval  →  merge
                                                              │
                                              deposit_zenodo.py
                                                              │
                         DOI + ORCID  ←──────────────────────┘
                              │
                              ├──→ written back into the repo, swept into the
                              │    next anchor manifest → Bitcoin
                              │
                              └──→ the package a member carries to an endorser,
                                   a journal, or arXiv once endorsed
```

**Zenodo is the native exit.** No endorsement, no affiliation, a real DOI, ORCID
attached. arXiv, where available, is a second deposit of the same work — not the
first stop, and not the default. `archive_targets` is ordered `[zenodo, arxiv]`
to say so.

### What this does and does not buy

It does **not** open the arXiv gate. Endorsement stays a human judgment and
nothing here manufactures one.

What it changes is the *shape of the ask*. Without it, an unaffiliated
researcher requesting an endorsement is saying "trust me." With it they are
saying: here is a DOI'd deposit, an ORCID, a Bitcoin-anchored record of when
this existed, and a peer-approved contribution history. That is not a
substitute for standing. It is the strongest evidence an outsider can assemble
without any, and assembling it is something the protocol is uniquely good at.

Claim it exactly that precisely. "We get you published" is false. "You hold
citable, anchored evidence from day one, and you ask for endorsement carrying
receipts nobody else has" is true.

## 4. OPEN DESIGN DECISION — what provenance travels with the deposit

This is the part that is genuinely undecided, and it should be argued rather
than defaulted. "Everything" is a reflex, not an answer.

**Option A — minimal deposit.** The gate-approved draft plus standard metadata.
Clean, conventional, what Zenodo expects. The repo remains the provenance layer.

**Option B — full record.** Draft, contribution record, anchor chain, the
executed agreement. Maximally evidentiary: an auditor following the DOI gets
everything in one place.

**The tension.** Option B is also maximally *exposing*. Contribution shares,
member identities, and dispute history become public, permanently, under a DOI
that cannot be withdrawn. A syndicate that later disagrees about attribution has
published its disagreement. Evidence and exposure are the same act.

**Current lean, not a verdict — Option C, the split:** the deposit carries the
artifact plus a **provenance manifest** — anchor ID, Bitcoin block height,
milestone tag, repo pointer, ORCID. The DOI points at citable work; the manifest
points at the proof; the syndicate keeps the internals under its own access
rules. Anyone who wants the full record follows the pointer and asks.

This mirrors the vault's own design: publish the artifact, keep the workings,
make the workings *reachable* rather than *broadcast*. Splitting evidence from
exposure is the same principle one layer out.

**Whoever builds this must settle §4 first and record the decision in
`50-decisions/`.** The implementation is straightforward; this is not.

## 5. Implementation notes

- Zenodo's deposition API supports reserving a DOI before publishing, so the DOI
  can be written into the record and anchored *before* the deposit goes live.
  That ordering is worth keeping: the anchor should cover the DOI, not chase it.
- `sandbox.zenodo.org` is a full test environment. The tool must be exercised
  there end to end before it ever touches production — this codebase's own
  ledger is largely a record of tools that had never been run (rows 38, 43).
- The token is a secret and must never reach `.git/config` or a log. See row 39
  for how that goes wrong.
- ORCID is load-bearing here and is a placeholder in the shipped manifest.
  Required for the publication path; not required for membership — raising the
  joining bar is against everything `join.py` exists to lower.

## 6. What stays human, permanently

Submission to arXiv. Requesting an endorsement. Choosing whom to ask.

The protocol prepares the package and records the decision. It does not send
mail, and `ingest_people.py` **must not** be able to answer "who could endorse
me" — see the MUST in `docs/DISCOVERY.md`. A discovery tool that can rank by
endorsement eligibility is an endorsement-farming tool with a disclaimer, and
the reputational damage from one campaign is not recoverable.
