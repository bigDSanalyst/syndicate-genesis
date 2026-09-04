# Security Policy

## Threat model (ranked)

1. **Member GitHub account compromise.** The entire trust chain binds to
   account control. Mitigation: hardware-key or TOTP 2FA for all members,
   mandatory — a compromised account defeats every cryptographic guarantee
   here. This is the single highest-leverage control.
2. **Secrets exposure.** BYOK keys must never enter the repo. Fine-grained,
   repo-scoped, short-lived PATs only; regenerate on any suspected exposure
   (a token echoed in logs is exposure).
3. **Supply chain.** All dependencies pinned to measured versions.
   Upgrade = deliberate, tested act (see operator checklist #4).
4. **Workflow egress.** Actions with write access can exfiltrate repo
   secrets via crafted workflows. Keep scrape keys out of Actions; use
   GitHub environments with required reviewers for anything sensitive.
5. **Identity binding drift.** Commits from emails not in `syndicate.yaml`
   are unattributed (the pre-commit hook blocks them locally; CI audits).

## Cryptographic inventory

| Use | Primitive | PQC horizon |
|---|---|---|
| Anchors, manifests, ledger digests | SHA-256 | safe (Grover only halves strength) |
| Bitcoin attestations (OTS) | SHA-256 + Bitcoin ECDSA | ecosystem-level migration, not ours |
| `genesis.sig` (future, oracle era) | Ed25519 (planned) | **quantum-vulnerable — upgrade path required; re-sign on epoch** |
| ML-DSA / ML-KEM (future, oracle era) | FIPS 204/203 | the PQC layer; verify implementations with [pq-verify](https://github.com/bigDSanalyst/pq-verify) |

Designated verifier for the PQC layer: **pq-verify** (independent ML-KEM/
ML-DSA implementation verification against NIST ACVP vectors).

## Reporting

Report vulnerabilities via GitHub security advisories on this repo, or
contact the maintainers directly. Do not open public issues for
vulnerabilities.

## Compliance note

This is a coordination protocol, not a hosted system: no NIST/FedRAMP
obligations attach to the template itself. A syndicate handling CUI or
selling to federal contractors takes on its own SP 800-171 obligations
(Agreement §8: the platform is not a party).
