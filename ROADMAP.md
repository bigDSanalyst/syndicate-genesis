# Roadmap

## Near term (v1.2 — code push)

- tools/join.py: one-command member onboarding (identity lookup, branch,
  manifest row, PR) — born from shakedown findings #4 and the sha256 wall
- agents/queries.yaml fix: comments outside quotes; designed novelty channel
- README: member-path section, noreply how-to, sha256 how-to
- MAP.md: status/superseded convention; people-triage section

## Mid term

- ingest_people.py: candidate discovery via public APIs (GitHub, ORCID,
  arXiv authors) -> 00-inbox/people/ cards; agent-generated outreach
  briefs; the initiator sends. Discovery agentic, transmission human.
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
