---
aliases: ["Graph Machine: Towards Better Pretraining via Edges"]
tags: [literature/arxiv, status/triage]
arxiv_id: "2609.02881"
url: "http://arxiv.org/abs/2609.02881v1"
published: "2026-09-02T17:56:41Z"
ingested: "2026-09-03T11:04:57Z"
authors:
  - "Lintai Hou"
---

# Graph Machine: Towards Better Pretraining via Edges

## Abstract

> We introduce the Graph Machine (GM), an architecture that maintains an $O(n)$-sized state and
> accesses it through sparse, dynamic routing. Unlike methods with fixed-size states or sparse but
> static routing, GM preserves $O(n)$ complexity in its sparse layers without restricting the
> potentially accessible state size to $O(1)$. Instead, GM uses edges - pointer-like objects
> updated differentiably by a referral mechanism resembling pointer chasing. We replace 75% of the
> dense Transformer layers in Qwen3-0.6B with GM sparse layers and pretrain from scratch on 15.7B
> tokens. With only 2 of 4,096 tokens retrieved per KV head in each sparse layer, loss degrades
> only slightly; with 4, the best model marginally improves loss.

---
## Reading Notes
*Annotations below. Update the status tag as you triage; the arxiv_id frontmatter must survive edits - it is the dedup key.*

