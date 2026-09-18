# Syndicate Genesis

Turn a GitHub repository into a self-governing research syndicate: git-native
attribution, a PR-executed consortium agreement, and Bitcoin-anchored priority
proofs. No custody, no platform — the repo is the sole source of truth.

## What this template gives you

- **syndicate.yaml** — the manifest: members, identity, gates, weights
- **agreements/** — the consortium agreement (HAVE COUNSEL REDLINE IT FIRST) + execution log
- **tools/** — `ingest_arxiv.py` (idempotent literature ingestion), `anchor.py` (OTS priority anchoring via the `ots` CLI), `attribution.py` (per-member share windows)
- **.github/workflows/** — daily ingestion, weekly + milestone anchoring (self-healing stamps)
- **audits/** — this syndicate's receipt drawer: what was found wrong in it
- **tools/drift_check.py** — what the template changed since you generated from it; the diff is the remediation checklist
- **vault/** — Obsidian workspace scaffold

Three of those are **record organs** — `ledger/` (what this syndicate proved),
`agreements/` (who it bound), `audits/` (what was found wrong in it). Activation
strips the template's own narrative (FINDINGS.md, ROADMAP.md, docs/) and never
touches these: the strip list strips inheritance, not identity.

## Day-zero sequence

1. Generate this repo from the template; invite members as collaborators
2. Each member edits their manifest row via PR (identity = noreply email)
3. Each member runs `bash bootstrap.sh` locally (identity gate + MCP wiring)
4. Members sign the agreement: PR adds EXECUTION-LOG row, peer APPROVES, then merge
5. Dispatch the anchor workflow once — the constitution's first Bitcoin stamp

## Operator checklist — lessons this template already paid for

1. **Branch protection ON before any signature PR** (require PR + 1 approval; admins too)
2. **Gates must be ≤ members − 1** (auto-cap; higher = deadlock)
3. **Fresh dispatch, never 'Re-run failed jobs'** — re-run executes the old workflow file
4. **Dependencies: pinned and smoke-tested** — the `ots` CLI over the python library; measured versions only
5. **Approval radio, not Comment** — check the review actually says 'approved these changes'
6. **Dedup keys must survive edits** — the `arxiv_id` frontmatter line is load-bearing
7. **Bots need identities** — the exclusion patterns are the attribution firewall
8. **A green check must never lie** — every deferred failure names its reason
9. **Email is identity** — manifest email must equal the member's noreply address, or commits vanish from attribution

## Running solo

A syndicate of one is supported, and it has to say so. In `syndicate.yaml`:

```yaml
governance:
  formation: solo     # multi | solo
```

**Why the declaration exists.** A review gate needs someone other than the
author — GitHub will not let you approve your own pull request, and a gate of 0
is barred because Agreement §10.1 needs at least one approving review to exist.
So a one-member manifest deadlocks on its first gated PR, and it looks exactly
like a two-person syndicate whose second member never arrived. That is not a
hypothetical: it happened on this repository, in PRs #6–#8, before the guard
existed. Declaring solo formation is what separates a decision from a
misconfiguration, and `tools/manifest.py` refuses the undeclared shape so the
first gated PR is not where you find out.

**What solo actually means.** You merge on your own authority. The repository
owner's token bypasses the gate (ledger row 48), and the anchor chain is the
compensating control: what you cannot get from a second reviewer, you get from
a timestamp nobody can move. The declaration puts that in the manifest, where
anyone auditing the record can read it rather than infer it.

**It is sticky.** The second member ends solo formation, in the same PR that
adds them — `tools/join.py` clears the marker for you. Leaving it set would
have a two-person syndicate declaring itself alone, and the declaration is what
the bypass rests on, so it must not outlive the roster it describes.

Start alone, prove the machinery on real work, recruit from a repository that
already has an anchored record. That is how this template's own test instance
ran for its first week.


## Honest scope (v1)

- Attribution windows use committer dates locally; push-time events are the admissible clock (§4.2) — gate on the events API for production
- Prompts weight is inactive without workspace logs; shares renormalize
- Oracle/genesis.sig, marketplace, and entity formation are future work

## Licensing

- Code (`tools/`, `.github/`, `bootstrap.sh`): MIT — see `LICENSE`.
- Templates and documents (`agreements/`, `README.md`, `vault/_templates/`): CC BY 4.0 — see `LICENSE-CONTENT.md`.
- Everything a syndicate commits to `vault/`, `ledger/`, or `agreements/EXECUTION-LOG.md` is governed exclusively by that syndicate's executed Consortium Agreement.

## Activation — turning a generated repo into a live syndicate

The template ships with workflows in **manual-dispatch mode only**: a template is the mold,
not a syndicate, and its schedules must never run. After generating your repo:

1. **Re-enable the schedule in `anchor.yml`** (add the `schedule:` block back
   under `on:`). Anchoring works fine on GitHub's hosted runners.

   **Do NOT re-enable the schedule in `ingest-arxiv.yml`** without reading this
   first: arXiv returns HTTP 406 to GitHub Actions' Azure egress, so a scheduled
   ingest on a hosted runner fails every morning, permanently. Verified both
   ways — seven header variants from two repositories all refused from Azure;
   the identical code and queries ingest cleanly from a Google Cloud address.
   Nothing client-side fixes it (ledger row 51).

   Run ingestion from an egress arXiv accepts: a self-hosted runner, a notebook,
   a cron job on a machine you control — anything that is not a GitHub-hosted
   runner. The tool commits and pushes the notes itself, so the repository stays
   the record wherever the fetch happens.
2. **Enable branch protection** on `main` (require PR + 1 approval) — do this BEFORE
   the first signature PR; the template cannot ship this setting.
3. **Declare your formation.** `governance.formation` ships as `multi`. If you
   are starting alone, set it to `solo` — supported, and the declaration is what
   keeps your first gated PR from deadlocking on a review nobody can give. A
   one-member manifest that has not declared itself is refused, because that
   shape is indistinguishable from a two-person syndicate whose second member
   never arrived. It is sticky: the second member ends solo formation, and
   `join.py` clears it in the PR that adds them. See **Running solo** above.
4. **Invite members** as collaborators; each edits their `syndicate.yaml` row via PR.
5. **Check your publication route before you need it.** arXiv requires an
   endorsement for a member's first submission in a category, and unaffiliated
   researchers are exactly who does not get auto-endorsed by institutional
   email. If no member holds one, your route is Zenodo (no gate, real DOI) or a
   journal - not arXiv. This is arXiv's rule, not the protocol's, and no amount
   of internal approval substitutes for it. See `docs/PUBLICATION.md`.
6. **Fill in real ORCIDs** for any member who intends to publish. The manifest
   ships `0000-0000-0000-0000` placeholders; they are fine for membership and
   useless for deposit, where the ORCID is what ties the work to the person
   across venues.

Operator rule #10: *if the template's Actions tab shows scheduled runs, something is
wrong — generated repos run schedules, templates never do.*

## If you were invited to a syndicate (the member's path)

You received a collaborator invite to a repo generated from this template.
Your membership is a three-ledger act: GitHub grants access (the invite); the
systicate recognizes you (your manifest row, via PR); the constitution binds
you (your EXECUTION-LOG signature). Do them in order:

1. **Accept the invite**, then join with one command:
   `python tools/join.py --handle <your-github-username> --name "Full Name"`
   It looks up your identity email from the public GitHub API, inserts your
   manifest row on a branch, and hands you the PR link. (Manual alternative:
   the address is `<your-account-ID>+<handle>@users.noreply.github.com` — find the
   ID at `https://api.github.com/users/<handle>`, the `"id":` number.)
2. **Set your local git email** to that address — `git config user.email <addr>` —
   or your commits will not attribute. Web-UI commits default to your private
   email; the attribution ledger keys on the noreply address.
3. **Sign the agreement:** add your EXECUTION-LOG row via PR. The hash column is
   `sha256(consortium-agreement.md)`. Any of: `sha256sum agreements/consortium-agreement.md`
   (Linux/macOS), `Get-FileHash agreements/consortium-agreement.md` (PowerShell), or
   `python -c "import hashlib;print(hashlib.sha256(open('agreements/consortium-agreement.md','rb').read()).hexdigest())"`
   (anywhere with Python, including Colab).
4. **Run `bash bootstrap.sh`** on your own machine when you work locally — it
   installs the identity gate (blocks commits from unregistered emails) and
   wires the MCP config to the vault.

Why GitHub doesn't do this automatically: the invite grants *permission*;
the manifest row is your *self-declared identity* (the assertion the whole
attribution chain inherits trust from); the signature is the *legal act*.
Three ledgers, three acts, one member.
