# Syndicate Consortium Agreement

> **TEMPLATE — NOT LEGAL ADVICE.** This draft binds a research collaboration to mechanisms in this repository. It has not been reviewed by a lawyer. Before the first real syndicate runs, counsel must redline it for the Members' jurisdictions — specifically: (1) whether a git commit plus approving review satisfies local requirements for a *signed writing* transferring copyright (ESIGN/UETA/eIDAS and successors); (2) enforceability of binding arbitration and fee-shifting; (3) moral rights and rights that cannot be assigned; (4) jointly holding IP through an unincorporated consortium. The ⚙ notes describe repository mechanics only.

**Template v1.0.** This Syndicate's parameters live in `syndicate.yaml` (the Manifest). Wherever this Agreement refers to a number, a gate, or a list of Members, the current value in the Manifest governs. Changing the Manifest is an Amendment (Section 10).

**Parties.** The Members listed in the Manifest. The matching platform that generated this repository is expressly **not** a party (Section 8).

**Reading rules.** The Repository Record means this repository's commits, pull requests, approving reviews, issues, tags, and timestamp anchors, as timed by GitHub's servers. Each section's ⚙ note names the mechanism that executes it.

## 1. Purpose and status
1.1 We are independent researchers collaborating through this repository. We are not employees, partners, or agents of one another. Research outputs are provided as-is; nobody warrants any result.
1.2 This repository is the sole workspace of record. Work done outside it and not committed does not count for any purpose under this Agreement.

## 2. Members and identity
2.1 A person becomes a Member by being listed in the Manifest and executing this Agreement (Section 10.1).
2.2 Each Member is bound to exactly one GitHub account and one email address, both recorded in the Manifest. An act on GitHub by that account — a commit under that email, an approving review, an issue — is that Member's act. Circumventing the identity binding is a material breach.
2.3 Trust tiers (`verified`, `standard`, `provisional`) are recorded in the Manifest. A `provisional` Member may not be the sole approver of changes to `ledger/**` or `agreements/**`, may not serve as Settlement Agent, and may not hold submission credentials.
2.4 A Member's own details (wallet address, ORCID, display name) change only by that Member's own pull request.

> ⚙ *bootstrap.sh pre-commit hook enforces the email-Manifest match; CODEOWNERS + branch protection enforce tier gates.*

## 3. Intellectual property
3.1 **Present assignment.** From the repository's genesis commit forward, each Member assigns to the Syndicate — all Members jointly — the entire copyright and other IP rights in every work that Member commits. The assignment is present and immediate, not contingent on payment or completion. Where assignment of a right is not permitted by law, the Member instead grants an irrevocable, exclusive, royalty-free license to the Syndicate for all purposes of this Agreement, with the right to sublicense.
3.2 **Economics vs. title.** Legal title is held jointly and undivided. Economic shares are governed exclusively by ratified ledger windows (Section 4). The ledger never divides title; it divides money.
3.3 **Pre-existing IP.** A Member incorporating work they already own must register it in `agreements/pre-existing-ip.md` in or before the same commit. Unregistered incorporation is deemed a contribution under 3.1.
3.4 **Entity trigger.** Within [30] days of the first accepted commercial offer, the Members will form a legal entity [form and jurisdiction — counsel to select] and transfer all Syndicate IP into it, preserving ledger shares. Until then, joint holding under this section.
3.5 **Moral rights.** To the extent permitted by law, each Member waives moral rights in Syndicate works for uses within the Syndicate's purposes. Authorship attribution in publications follows ordinary scientific practice.
3.6 **Publication.** Decisions to publish (arXiv, Zenodo, journal) are decisions under Section 5 at the drafts gate. Automated record-keeping (anchors, archival snapshots) is not a publication decision.

> ⚙ *vault/40-drafts/** and ledger/** review gates; pre-existing-ip.md.*

## 4. Counting the work
4.1 Accounting happens in windows recorded under `ledger/windows/`. For each window, `tools/attribution.py` writes `attribution.csv` and `evidence.json` from the Repository Record, using the weights in the Manifest.
4.2 Only the Repository Record counts. Server-side timestamps govern. Dates embedded in commits are not evidence of time.
4.3 **Objection.** For the period set in the Manifest after a window's CSV is committed, any Member may object by opening a GitHub issue against that window. Resolution is a pull request at the ledger gate.
4.4 **Deemed acceptance.** If no issue is opened before the deadline, the window is ratified exactly as committed. Silence is acceptance.
4.5 A ratified window reopens only by Amendment (Section 10) or as an arbitration remedy.

> ⚙ *attribution.py; GitHub issues; ledger/** gate; anchor log timestamps.*

## 5. Decisions
5.1 The default decision rule and gate thresholds are in the Manifest (`governance`). A decision is made when a pull request implementing it is merged after satisfying its gate.
5.2 An approving review from a Member's account is that Member's vote.
5.3 A merged, gate-satisfied pull request is a valid decision even if some Members were silent. Members are responsible for watching the repository.

> ⚙ *PRs + CODEOWNERS + branch protection.*

## 6. Money
6.1 **Exit decisions.** Selling, exclusively licensing, or listing Syndicate IP on any marketplace requires the supermajority recorded in the Manifest.
6.2 **Settlement Agent.** For each transaction, the Members appoint one `verified` Member (or an external escrow) as Settlement Agent — buyers require a single signing counterparty. The Agent signs and receives funds, and must distribute within [10] business days per the ratified windows to the wallet addresses in the Manifest. Misdirection of funds is a breach and arbitrable. The Agent is entitled to reasonable documented costs.
6.3 **No custody elsewhere.** No Member — and never the Platform — holds Syndicate funds except a Settlement Agent acting under 6.2.
6.4 **Taxes.** Each Member is responsible for their own taxes. Nothing is withheld.
6.5 **No agency.** No Member may bind another Member or the Syndicate except through Section 5 mechanisms.

> ⚙ *supermajority PR; Manifest wallet fields; EXECUTION-LOG records each appointment.*

## 7. Confidentiality and priority
7.1 Confidential information is anything in the repository not yet publicly released, plus anything marked confidential. Once a milestone is published or archived, that milestone's content stops being confidential.
7.2 Standard carve-outs: already public through no fault of ours; independently developed; disclosure required by law.
7.3 **No solo publication.** Before a Section 5 publication decision, no Member discloses or publishes Syndicate work outside the Syndicate — including under their own name.
7.4 **Priority proof.** The repository is continuously anchored — weekly and at milestones, via OpenTimestamps into Bitcoin. In any dispute about what existed and when, including against a Member who leaves with the work, the anchored Repository Record is the Syndicate's proof of priority.
7.5 **Defection remedy.** A Member who breaches 7.3 forfeits ledger credit for the affected windows (which may be re-ratified excluding them), in addition to liability under Section 9 and injunctive relief where available.

> ⚙ *anchor.py weekly + milestone cadence; ledger gates for re-ratification.*

## 8. The platform is not a party
8.1 The platform that matched the Syndicate and published this template is an infrastructure publisher. It is not a party, agent, partner, employer, or fiduciary of the Syndicate or any Member.
8.2 Its entire role on record: publishing these files, and `genesis.sig` — a signature over the genesis Manifest attesting only that the listed accounts were matched on the recorded date. It does not vouch for any Member's competence, conduct, or output.
8.3 Disputes run between Members under Section 9. Claims against the Platform are limited to what applicable law does not permit us to waive.

> ⚙ *genesis.sig over syndicate.yaml manifest facts only.*

## 9. Disputes
9.1 **Ladder.** (a) Days 1-7 of an objection: peer resolution by pull request. (b) Days 8-21, optional, by joint request: the Oracle mediates and issues a non-binding recommendation derived from the Repository Record. (c) Otherwise: binding arbitration [seat, rules, panel — counsel].
9.2 **Evidence.** The Repository Record only. Client-side timestamps are inadmissible on questions of time.
9.3 **Bad faith.** Objections repeated without reasonable basis in the Record shift the objector's costs of that resolution.
9.4 Nothing here bars urgent injunctive relief for IP or confidentiality breach where courts allow it.

## 10. Signing, leaving, amending
10.1 **Execution.** A Member signs by a pull request adding their row to the signature table in `agreements/EXECUTION-LOG.md` (name, GitHub username, date, hash of this file), merged with at least one approving review from a `verified` Member. The Agreement binds the Syndicate and that Member on merge, and binds Members among themselves as each signs.
10.2 **Withdrawal.** A Member leaves by a pull request setting their `left:` date in the Manifest at the agreements gate. Ratified shares survive; accrual stops; Section 7 survives for [3] years.
10.3 **Amendments.** Changes to this Agreement or to governance-relevant Manifest values (gates, weights, decision rules, member list) require a pull request at the `agreements/**` gate and take effect on merge.
10.4 **Death or incapacity.** Accrued shares pass to the estate; roles and gates end.

> ⚙ *EXECUTION-LOG.md; agreements/** CODEOWNERS gate; Manifest left: field.*

## 11. General
Governing law [— counsel]; arbitration seat [— counsel]; language English; entire agreement = this file + Manifest + EXECUTION-LOG; severability; amendments per Section 10.3; electronic execution is intended to satisfy [ESIGN/UETA/eIDAS — counsel confirm].

*Signature table: maintained in `agreements/EXECUTION-LOG.md`.*
