# Roadmap

## Near term (v1.2 — code push)

- tools/join.py: one-command member onboarding (identity lookup, branch,
  manifest row, PR) — born from shakedown findings #4 and the sha256 wall
- agents/queries.yaml fix: comments outside quotes; designed novelty channel
- README: member-path section, noreply how-to, sha256 how-to
- MAP.md: status/superseded convention; people-triage section

## Mid term

- template drift check: syndicate.yaml records the template commit hash it
  was generated from; a workflow compares that against the template's current
  main and reports the diff. Git-native, no version-number bureaucracy, and
  the diff IS the remediation checklist. Completes the guard symmetry - the
  smoke suite proves the mold works, nothing yet proves an instance matches
  the mold it came from. Row 37 fired three times in the session that closed
  it, and three design-partner tables remediated by hand is the chore that
  kills adoption.
- deposit_zenodo.py: gate-approved draft -> Zenodo deposition -> DOI + ORCID
  -> written back and anchored. FIRST in this section deliberately: the only
  unbuilt tool that removes a blocker rather than adding intake, and the one
  publication route with no institutional gate. Spec and the open provenance
  decision: docs/PUBLICATION.md
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
