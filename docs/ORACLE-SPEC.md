# Oracle Query/Response Specification

**Version:** 0.1 (draft for implementation)

## Purpose

A query/response language for trust questions about researchers, work, and
commitments. Any system — agent, oracle node, syndicate tool — may implement
this spec. It defines how to *ask* and what a *defensible answer* must
contain.

## Core principle: recheckability

**MUST:** every response is valid only if each cited source is
independently verifiable by the requester, without trusting the responder.
An answer that cannot be rechecked is not an answer; it is an assertion.

## Query schema

```yaml
query:
  id: "uuid"
  type: "contribution | publication | affiliation | integrity | commitment | capability"
  claim: "string, machine-parseable, unambiguous"
  period: {start: "date", end: "date"}
  evidence_required: "weak | strong | consensus"
  requester: "agent or syndicate identifier"
  timestamp: "ISO-8601"
```

## Response schema

```yaml
response:
  query_id: "uuid"
  verdict: "true | false | uncertain"
  confidence: 0.0-1.0
  response_hash: sha256-of-canonical-response-json   # content-addressable, anchorable
  sources:
    - type: "github-repo | git-commit | orcid | arxiv | doi | bitcoin-anchor | syndicate-ledger"
      location: "URL or repo path + ref"
      evidence: "what at this location supports the verdict"
      verified_by: "how the requester can recheck it (command or fetch)"
  causal_chain:
    - "ordered steps linking evidence to verdict"
  appeal_deadline: "ISO-8601 or null"
  generated_at: "ISO-8601"
```

## Notes on what is deliberately absent

- **No watermarks, no cluster signatures, no consensus fields.** Those are
  network-era mechanisms; see docs/SUBSTRATE.md for the design and its
  preconditions (anchoring cadence, aggregate signature scheme, node
  registry). A single honest responder with recheckable sources satisfies
  this spec completely.
- **No reputation fields.** Trust derives from evidence reconstruction,
  not responder standing.

## Worked example

```yaml
query:
  id: "q-001"
  type: "contribution"
  claim: "satsolverv124 reviewed and merged PR #1 in syndicate-shakedown"
  period: {start: "2026-09-01", end: "2026-09-30"}
  evidence_required: "strong"
response:
  verdict: "true"
  confidence: 0.99
  sources:
    - type: "github-repo"
      location: "bigDSanalyst/syndicate-shakedown PR #1"
      evidence: "approving review by satsolverv124, merge commit d87796e"
      verified_by: "GET /repos/bigDSanalyst/syndicate-shakedown/pulls/1/reviews"
  causal_chain:
    - "review exists on public API"
    - "merge commit references PR #1"
    - "repo HEAD history contains d87796e"
```

## Threat model (network era — informational)

Sybil, circular provenance, eclipse, and disagreement attacks apply to
multi-node deployments. Defenses (quorum, external witnesses, escalation)
are future work and out of scope for v0.1. Single-node implementations
rely entirely on recheckability.
