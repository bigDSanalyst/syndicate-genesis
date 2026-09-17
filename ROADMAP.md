# Roadmap

## Near term (v1.2 — code push)

- tools/join.py: one-command member onboarding (identity lookup, branch,
  manifest row, PR) — born from shakedown findings #4 and the sha256 wall
- agents/queries.yaml fix: comments outside quotes; designed novelty channel
- README: member-path section, noreply how-to, sha256 how-to
- MAP.md: status/superseded convention; people-triage section

## Mid term

- template drift check (shipped): syndicate.yaml records the upstream commit
  this repo's lineage starts at; tools/drift_check.py diffs it against the
  template's current head and the diff IS the remediation checklist. Git-native,
  no version-number bureaucracy. Completes the guard symmetry - the smoke suite
  proves the mold works, nothing until now proved an instance matches the mold it
  came from. Row 37 fired three times in the session that closed it, and
  remediating design-partner repos by hand is the chore that kills adoption.

  Inheritance rule, settled: **instances inherit machinery and rules, never
  narrative.** FINDINGS.md is the mold's scar tissue and ROADMAP.md is the
  protocol's priorities rather than the instance's, so bootstrap.sh strips both
  (and docs/) at activation and drift_check.py ignores changes to them. The
  operator checklist inherits, because it is distillation rather than story. What
  replaces the stripped files is one line of lineage in the manifest, which is
  also the drift check's own input.

  The rule that decides the hard cases: **the strip list strips inheritance, not
  identity.** audits/ joins ledger/ and agreements/ as a record organ - an audit
  written about a repo is that repo's history even when it reads like narrative,
  so it is a root directory rather than a docs/ subfolder, because docs/ is
  inherited and stripped. Remaining: an activated syndicate may enable a weekly
  schedule on drift-check.yml - safe there, unlike ingest-arxiv.yml, because the
  job only reads the API.
- deposit_zenodo.py: gate-approved draft -> Zenodo deposition -> DOI + ORCID
  -> written back and anchored. FIRST in this section deliberately: the only
  unbuilt tool that removes a blocker rather than adding intake, and the one
  publication route with no institutional gate. Spec and the open provenance
  decision: docs/PUBLICATION.md
- arxiv-gauge bridges: an externally-built occupancy/digest tool offered to
  the protocol. Three candidate uses and their preconditions are recorded in
  docs/DISCOVERY.md - `watch` as a freshness mechanism (needs a policy that
  does not exist yet), `check` output as Agreement 9.2 evidence once committed
  and anchored (needs the outcome split first, or a refusal enters the record
  as an open area), `digest` as a triage hypothesis measurable against the
  shakedown's 127-of-127 untriaged baseline. Placed AFTER deposit_zenodo.py
  deliberately: an exit tool outranks intake refinement. Six audited defects
  and the port-me-back worklist are in the same section.
- ingest_people.py: candidate discovery via public APIs (GitHub, ORCID,
  arXiv authors) -> 00-inbox/people/ cards; agent-generated outreach
  briefs; the initiator sends. Discovery agentic, transmission human.
  MUST NOT model arXiv endorsement eligibility in any form - see the MUST
  in docs/DISCOVERY.md.
- ingest_repos.py: same skeleton over GitHub Search — repos as literature;
  the syndicate-detection query (filename:syndicate.yaml) makes every
  deployed syndicate discoverable to every other one
- events-API push clock for attribution (closes the §4.2 committer-date gap)
- prompt capture: making direction legible; activates the reserved 0.20
  weight; schema pattern from Agentic Stack (sanitized extraction,
  provenance, staged-for-review before becoming evidence)
- Zenodo deposit automation from milestone tags (bare-zip proof already passed)
- Chromebook/VS Code/Logseq/goose as documented vault lenses and agent
  (workspace tool-agnosticism; first agentic loop: CI-triage,
  generator/verifier split, cost instrumented from day one)

## Oracle era

- oracle.py v0: deterministic single-node implementation of ORACLE-SPEC.md;
  responses as vault documents, OTS-anchored on issue
- threshold genesis.sig (FROST/Ed25519 over manifest facts; pq-verify as
  the verification gate for the PQC successor)
- bridge to the oracle kernel: claim derivation from attribution windows,
  admission gate as kernel transition (manifest state committed at a
  specific repo commit — frame-translation must itself be replayable),
  state-root into the anchor manifest
- network layer: multi-node consensus, response-anchoring cadence,
  cluster signatures (see SUBSTRATE.md preconditions)
- DID-portable member credentials; ZK trust-tier proofs

## Parked (deliberate)

- marketplace / fractionalized splits: securities-quarantined until legal
  clearance and real demand
- slashing economics: see SUBSTRATE.md
- arXiv submission automation: human-gated by the venue itself
