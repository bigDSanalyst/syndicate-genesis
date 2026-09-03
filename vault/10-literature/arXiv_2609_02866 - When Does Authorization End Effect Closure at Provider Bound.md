---
aliases: ["When Does Authorization End? Effect Closure at Provider Boundaries"]
tags: [literature/arxiv, status/triage]
arxiv_id: "2609.02866"
url: "http://arxiv.org/abs/2609.02866v1"
published: "2026-09-02T17:50:39Z"
ingested: "2026-09-03T11:04:57Z"
authors:
  - "Igor Santos-Grueiro"
---

# When Does Authorization End? Effect Closure at Provider Boundaries

## Abstract

> Revocation completion, clean state, or operation success can leave authorized work able to cause
> an effect the application rejects while the provider stays within its contract. We call the
> absence of all such paths policy-relative effect closure, or effect closure for short. Thus, a
> grant is closed when its existing authorizations retain no such path, and it cannot issue any
> new ones. We present EFFECTBOUND, which uses an evidence-supported finite contract to decide
> whether an interface can truthfully report closure while required work completes. It reduces
> this to finite control with hidden state and returns a strategy, an impossibility certificate,
> or no verdict when evidence is insufficient. Machine-checked proofs establish the reduction and
> checker soundness; the checker derives closure results and validates certificates. Across
> GitHub, Kubernetes, NATS, and Kafka, closure fails in three ways: an interface lacks a needed
> control, clean visible state hides active work, or the model stops before the effect frontier---
> the last point where the effect can be prevented. The GitHub tool cannot bind a merge to the
> reviewed commit; a controlled run confirms that it may merge a different commit. NATS can report
> no stored or pending messages while dispatched work can still publish downstream. In Kafka, all
> fixed-set brokers had applied the revocation, yet an earlier authorized request could still
> append. We add a gate that blocks new use of revoked authority and delays return until earlier
> in-flight work completes. In a fixed-set Kafka~4.3.1 test deployment, this closes the studied
> synchronous, nontransactional write path without blocking unrelated requests. For a grant,
> authorization ends only when issuance stops and no earlier authorization can reach an effect the
> application rejects.

---
## Reading Notes
*Annotations below. Update the status tag as you triage; the arxiv_id frontmatter must survive edits - it is the dedup key.*

