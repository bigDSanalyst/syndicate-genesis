# Working in a syndicate repository

You are an agent working inside a repository generated from
[syndicate-genesis](https://github.com/bigDSanalyst/syndicate-genesis). This
repository is a governance record as well as a codebase: some of its files are
evidence, and editing them the way you would edit source code destroys what
they are for. Read this before you change anything.

## The first rule: compute, do not narrate

**Run `python3 tools/doctor.py --json` before you answer any question about
this repository's state.** Report what it returns.

Do not read `syndicate.yaml` and form your own impression of whether this
syndicate is configured correctly. Doctor already encodes every rule, imports
them from the one module that owns them, and cannot be wrong about them in a
way the repository's own test suite does not catch. You can. A confident
sentence from you about signing, formation, gates or lineage that doctor did
not produce is the exact failure operator rule #8 exists to prevent: **a green
check must never lie**, and to a human reading your output, you are a check.

If doctor says a thing is blocked, it is blocked. If doctor is silent about
something, you have not verified it — say so rather than filling the gap.

## Record organs — append, never rewrite

Three directories are the record of what this syndicate proved, who it bound,
and what was found wrong in it:

| Path | What it is |
|---|---|
| `ledger/` | what this syndicate proved, and the anchor chain over it |
| `agreements/EXECUTION-LOG.md` | who bound themselves to the Agreement, and when |
| `audits/` | what was found wrong in this syndicate |

**`vault/MAP.md` law 4 — `50-decisions/` and `ledger/` are append-mostly, and
a correction is a new entry, never a rewrite.** A ratified window stands as
ratified even after you find the arithmetic that produced it was wrong; you add
the correction, you do not edit the row. This is not fussiness about git
history: an anchor chain hashes these files, so rewriting one silently
invalidates every proof downstream of it. Treat the other two organs the same
way — law 3 already forbids editing another member's execution-log row, and an
audit you rewrite is an audit nobody can cite.

`ledger/anchors/log.jsonl` is an append-only hash chain. Never reformat it,
never reorder it, never "clean up" an entry. If it looks wrong, say so.

**`vault/MAP.md` law 1 — `arxiv_id` is the dedup key.** The frontmatter line is
load-bearing. Ingestion is idempotent because of it. Do not restructure vault
note frontmatter.

## Things that are somebody's, not yours

- **A member's manifest row belongs to that member.** Identity, email aliases
  and signing keys change by a PR that member authors or approves — the change
  should arrive *through* the gate, not around it. If you are asked to add a
  key to someone else's row, say who should author it instead. `vault/MAP.md`
  law 3 says the same thing about execution-log rows and members' own notes.
- **Approval is a human act.** You do not approve pull requests, and you do not
  merge past a review gate. Agreement §10.1 needs a real approving review from
  someone other than the author to exist.
- **Agreement text is lawyer-territory.** `agreements/consortium-agreement.md`
  is hashed into the execution log. Changing a character invalidates every
  signature row's hash. Propose amendments; do not edit it.

## Never soften a guard to make it pass

If a test in `tests/` fails, the test is the finding until proven otherwise.
Do not skip it, do not loosen its assertion, do not special-case the input that
breaks it. The suite exists because tools shipped broken against their own
template (finding #38) and because four separate guards were once observed
passing for the wrong reason. A guard that passes for the wrong reason is worse
than no guard, because it is *trusted*.

The standard for trusting a guard here is mutation testing: break the thing the
guard checks, watch it fail, restore it. If you add a guard, do that, and say
you did.

## Fixes go to the mold first

This repository was generated from a template. A bug in inherited machinery is
a bug in the template, and fixing it only here means every other syndicate
keeps it — and your fix gets reported as drift the next time anyone checks.

    python3 tools/drift_check.py check     # what the template changed since this fork

When you find an inherited bug: fix it upstream, then pull it down. When that
is not possible in the moment, say explicitly that the fix is local and owes an
upstream port.

## The tools, and what each one refuses

Every tool refuses rather than guessing, and each refusal names its reason.
Read the refusal; it is usually the whole answer.

| Tool | Answers | Exit codes |
|---|---|---|
| `tools/doctor.py` | where is this syndicate, what is the next command | 0 ok · 1 blocked |
| `tools/drift_check.py` | what did the template change since we forked | 0 · 1 human · 2 transient · 3 drift |
| `tools/verify_signatures.py` | is every member commit signed by *that member's* key | 0 · 1 human |
| `tools/anchor.py` | stamp repository state, upgrade stamps to Bitcoin proofs | 0 · 1 human · 2 transient |
| `tools/attribution.py` | each member's share of a window | 0 · 1 human |
| `tools/join.py` | add a member, correctly | 0 · 1 human |
| `tools/ingest_arxiv.py` | pull literature into the vault, idempotently | 0 · 1 human · 2 transient |

Where a tool has an exit 2, it means *try again later* — a rate limit, a
timeout, an outage. It is not a failure to route to a human, and it is not a
reason to retry in a loop. `drift_check.py`, `ingest_arxiv.py` and `anchor.py`
have one; the rest split 0 / 1, and `drift_check.py` alone uses 3 for "drift
found", which is actionable rather than an error.

`anchor.py`'s exit 2 is worth knowing by name. It means the OpenTimestamps
calendars could not be reached, so some anchors' state is **unknown** — which
is not the same as unconfirmed. Unconfirmed is a claim about Bitcoin;
unreachable is a claim about the network. Reporting the second as the first is
how a chain silently stops advancing while everything looks normal (row 62).

This table is checked by `tests/test_generation_smoke.py`. If you change a
tool's exit codes, the guard will tell you that you changed them here too.

## Money paths use exact arithmetic

`tools/attribution.py` decides revenue splits and uses `Decimal` throughout.
Never introduce a float into it, including a float literal that looks
harmless — `Decimal(0.35)` is not `Decimal("0.35")`. Ratified windows stand as
ratified (law 4); an arithmetic change applies going forward and is recorded as
a change.

## When you are unsure

Say what you verified, what you did not, and what you would need to verify it.
This repository's entire value proposition is that its claims are checkable.
An unsourced claim from you costs more here than a missing answer.
