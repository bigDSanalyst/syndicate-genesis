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

## Operator bypass, and what actually constrains the operator

The `main` ruleset requires a pull request. The operator's account sits in its
bypass list in `always` mode, so a direct push from that account lands anyway -
the gate on `ledger/**` is advisory against the operator's own token, not
binding. This is a standing decision, not an oversight, and the reason is
mechanical:

GitHub's bypass list takes two modes, `always` and `pull_request`. The narrower
mode exempts pull-request merges only; direct pushes are evaluated. But the
anchor and ingest workflows push directly to `main` carrying the operator's PAT,
so they are indistinguishable from the operator at the gate. One bypass entry
serves both a person and two bots, and narrowing it stops the bots.

What the ruleset does buy is real but narrower than it looks: deletion,
force-push and the pull-request requirement bind every actor *not* in that one
bypass row - a future collaborator, a CI token, a compromised credential. Before
it existed they bound nobody.

**The compensating control is the record itself.** Every bypassed push is still
a commit: authored, attributed, and swept into the next anchor's manifest and
from there into Bitcoin. A gate can be walked around. The chain cannot be walked
back - a rewritten history breaks `anchor.py verify` at the first mismatched
`prev`, and the mismatch is public. In a no-custody protocol, transparency is
the deeper control; the gate is the convenient one.

**The path out is a separate identity for the machines** (ledger row 16): a
GitHub App with its own bypass grant, after which the operator's entry can move
to `pull_request` and the gate binds the human without stopping the bots. Until
that exists, this posture stands and is stated here rather than left implied.

## Cryptographic inventory

| Use | Primitive | PQC horizon |
|---|---|---|
| Anchors, manifests, ledger digests | SHA-256 | safe (Grover only halves strength) |
| **Member commit signatures (shipped)** | **SSH Ed25519** | **quantum-vulnerable, forward-only — see below** |
| Bitcoin attestations (OTS) | SHA-256 + Bitcoin ECDSA | ecosystem-level migration, not ours |
| `genesis.sig` (future, oracle era) | Ed25519 (planned) | **quantum-vulnerable — upgrade path required; re-sign on epoch** |
| ML-DSA / ML-KEM (future, oracle era) | FIPS 204/203 | the PQC layer; verify implementations with [pq-verify](https://github.com/bigDSanalyst/pq-verify) |

Designated verifier for the PQC layer: **pq-verify** (independent ML-KEM/
ML-DSA implementation verification against NIST ACVP vectors). Its workflow
pins Python 3.12 deliberately — see the comment in `pq-verify.yml.disabled`,
and the guard that keeps the pin honest.

### Why the signature row says "forward-only"

Commit signatures are the one shipped primitive a quantum adversary threatens,
and the exposure is narrower than the word "vulnerable" suggests.

A forged Ed25519 signature made in some future cannot insert a commit into a
tree that Bitcoin already covers. The anchor protects everything signed before
the break; the key protects only what is signed after it. So the migration is
**rotation, not re-signing**: `keys:` is a list, rotation is a manifest PR, and
a commit signed by a key the manifest listed as of a confirmed anchor stays
verifiable afterwards. The old signatures do not have to be redone, because the
timestamp already fixed the window they were valid in.

One honest limit: **post-quantum commit signing waits on OpenSSH.** Git signs
with what ssh supports — ed25519, ecdsa, rsa, the sk- variants — and there is no
ML-DSA option to select today. The upgrade path is real and it is upstream, not
ours to schedule. When it arrives, it arrives as another key in the same list.

## Reporting

Report vulnerabilities via GitHub security advisories on this repo, or
contact the maintainers directly. Do not open public issues for
vulnerabilities.

## Compliance note

This is a coordination protocol, not a hosted system: no NIST/FedRAMP
obligations attach to the template itself. A syndicate handling CUI or
selling to federal contractors takes on its own SP 800-171 obligations
(Agreement §8: the platform is not a party).
