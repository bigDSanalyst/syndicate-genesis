---
aliases: ["GRADSOLVE: fast exact gradients for ODE ensembles on GPUs"]
tags: [literature/arxiv, status/triage]
arxiv_id: "2609.02876"
url: "http://arxiv.org/abs/2609.02876v1"
published: "2026-09-02T17:56:10Z"
ingested: "2026-09-03T11:04:57Z"
authors:
  - "Alessio Spurio Mancini"
---

# GRADSOLVE: fast exact gradients for ODE ensembles on GPUs

## Abstract

> Ordinary differential equations (ODEs) underlie models in science and engineering, and many
> applications need derivatives of their solutions with respect to parameters. Ensembles of
> independent trajectories suit graphics processing units (GPUs), but current GPU software forces
> a trade-off: the fastest ensemble solvers cannot be differentiated in reverse mode at the speed
> they solve, and the solvers built for differentiation solve more slowly. No single tool has yet
> offered a reverse-mode gradient at the speed of a fused-kernel solve. We present GRADSOLVE, an
> open-source JAX library for solving and reverse-mode differentiating low-dimensional ODE
> ensembles on NVIDIA GPUs. It records the steps an adaptive solver accepts and differentiates a
> fixed-step replay of them; the returned gradient is the exact discrete adjoint of those steps,
> the same derivative Diffrax returns by default, obtained more cheaply from a fixed-length chain
> than from an adaptive loop. It targets ensembles differentiated many times against one recorded
> mesh, keeps Diffrax as a fallback, and supports explicit and Rosenbrock integrators. Used as a
> solver, GRADSOLVE's forward-only kernel ran 2.8x faster than DiffEqGPU.jl; used for gradients,
> once a record exists, it computed them 5.6-14.1x faster than Diffrax's checkpointed adjoint at
> matched forward-state accuracy across three GPU generations, the advantage narrowing on large
> ensembles and, on stiff systems, down to parity at tight accuracy. GRADSOLVE is released at
> https://github.com/ECLIPSE-AI4Science/gradsolve.

---
## Reading Notes
*Annotations below. Update the status tag as you triage; the arxiv_id frontmatter must survive edits - it is the dedup key.*

