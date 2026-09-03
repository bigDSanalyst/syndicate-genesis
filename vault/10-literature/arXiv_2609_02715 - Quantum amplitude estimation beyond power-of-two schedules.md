---
aliases: ["Quantum amplitude estimation beyond power-of-two schedules"]
tags: [literature/arxiv, status/triage]
arxiv_id: "2609.02715"
url: "http://arxiv.org/abs/2609.02715v1"
published: "2026-09-02T15:20:50Z"
ingested: "2026-09-03T11:04:53Z"
authors:
  - "Farrokh Labib"
---

# Quantum amplitude estimation beyond power-of-two schedules

## Abstract

> Non-adaptive quantum amplitude estimation (QAE) fixes its Grover depths in advance, so every
> circuit can run in parallel, but it has so far needed more queries than the best adaptive
> methods. We show that most of this gap comes from two conventional choices: subspace-based post-
> processing and power-of-two depth ladders. We replace the first by the exact maximum-likelihood
> estimate, one matrix multiplication per batch of estimates, and the second by a geometric ladder
> with ratio $r \approx 1.45$. The result is a fully parallel, deterministic-schedule estimator
> with total query complexity $2.8$-$3.1/\varepsilon$ at 95% confidence for target errors from
> $3.5\times 10^{-3}$ to $10^{-6}$. This matches the average-case complexity of chebAE, the best
> benchmarked adaptive method, within statistical uncertainty (with the lower point estimate at
> every scale tested), beats its maximum-observed complexity by $1.6\times$, and needs a maximum
> sequential depth of only $0.21/\varepsilon$ against chebAE's $2.9/\varepsilon$. Relative to
> csAE, the best non-adaptive benchmark, the constants improve by 30-35% at 95% and
> $1.5$-$1.7\times$ at 99% confidence. The optimal ratio has a simple origin. Doubling is the
> fastest depth growth at which the data can still tell neighboring candidate values apart, so
> power-of-two ladders sit at the edge of confusion and must buy reliability with extra shots; a
> slightly denser ladder checks every scale redundantly. An error-probability analysis reproduces
> the measured failure rates and locates the optimum. The likelihood formulation extends directly
> to noise-aware estimation, and uniformly scaling the capped ladder covers the depth-limited
> regime, realizing the optimal trade-off $M N_{\mathrm{tot}} \approx (0.4$-$0.6)/\varepsilon^2$
> within $\sim 1.1\times$ of the schedule's Cramér-Rao limit.

---
## Reading Notes
*Annotations below. Update the status tag as you triage; the arxiv_id frontmatter must survive edits - it is the dedup key.*

