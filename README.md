# Syndicate Genesis

Turn a GitHub repository into a self-governing research syndicate: git-native
attribution, a PR-executed consortium agreement, and Bitcoin-anchored priority
proofs. No custody, no platform — the repo is the sole source of truth.

## What this template gives you

- **syndicate.yaml** — the manifest: members, identity, gates, weights
- **agreements/** — the consortium agreement (HAVE COUNSEL REDLINE IT FIRST) + execution log
- **tools/** — `ingest_arxiv.py` (idempotent literature ingestion), `anchor.py` (OTS priority anchoring via the `ots` CLI), `attribution.py` (per-member share windows)
- **.github/workflows/** — daily ingestion, weekly + milestone anchoring (self-healing stamps)
- **vault/** — Obsidian workspace scaffold

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

1. **Re-enable schedules** in `.github/workflows/ingest-arxiv.yml` and `anchor.yml`
   (add the `schedule:` block back under `on:`) — or run everything manually via
   the *Run workflow* button until you trust the cadence.
2. **Enable branch protection** on `main` (require PR + 1 approval) — do this BEFORE
   the first signature PR; the template cannot ship this setting.
3. **Invite members** as collaborators; each edits their `syndicate.yaml` row via PR.

Operator rule #10: *if the template's Actions tab shows scheduled runs, something is
wrong — generated repos run schedules, templates never do.*
