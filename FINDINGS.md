# Findings Ledger — lessons this template already paid for

Every row was caught live, in a real repo, by the protocol failing loudly
(or nearly silently — which is itself the lesson).

| # | Finding | Fix | Where fixed |
|---|---|---|---|
| 1 | manifest email mis-paste (no space, no quotes) breaks strict parsers | canonical manifest rewrite + parse validation | sim manifest cell |
| 2 | silent `except ImportError` degrades OTS to 'not installed' with no reason | errors must name themselves | anchor.py v2 |
| 3 | python-opentimestamps 0.4.5 API churn breaks all library-era code | ots CLI over library; measured version pins | anchor.py v2, requirements |
| 4 | placeholder noreply email instructions point to a README section that does not exist | join.py + README identity how-to | v1.2 |
| 5 | mobile review UI hides the Approve control | desktop-mode instructions; approval-comment fallback clause | runbook |
| 6 | branch protection off: gate was convention, not enforcement | ruleset with approvals=1, admins included | shakedown |
| 7 | bot/human push race rejects bot pushes | fetch+rebase before push | workflows |
| 8 | 'Re-run failed jobs' executes the old workflow file; fixes never run | fresh dispatch rule | operator checklist |
| 9 | review gates above members-1 deadlock the syndicate | gates set to members-1 (decision A); auto-cap validator queued for template (C) | manifest PR + this row |
| 10 | attribution default label path NameError | date.fromisoformat import | 3917224 |
| 11 | template generate API is async; clone races the copy | verify file count, not API response | checklist |
| 12 | template ran the syndicate pipeline on itself (cron in the mold) | dispatch-only workflows in template; Activation docs | 68a4b8b |
| 13 | YAML comments inside quoted arXiv queries poison the search | comments outside quotes; novelty channel | v1.2 |
| 14 | day-zero assumes founder manifest row exists; founder skipped it | Activation: founder fills row first | v1.2 |
| 15 | classic branch rules have no Actions bypass; GH006 forever | rulesets + actor bypass | shakedown |
| 16 | GITHUB_TOKEN actor cannot be bypass-granted; PAT-in-secret is the bootstrap, GitHub App the production answer | checkout token secret | workflows |
| 17 | web-UI commits default to private email; attribution loses the member | join.py checks email binding; README | v1.2 |
| 18 | GitHub's workflow validator catches indent that yaml.safe_load passes | dispatch-test workflow edits before 'done' | checklist |
| 19 | close/reopen adjacent to merge controls; accidental PR closure on mobile | documented hazard | checklist |
| 20 | spec-claim gravity: overclaiming constructs reinsert themselves after removal | don't make the claim; park it with requirements documented | ORACLE-SPEC/SUBSTRATE |
| 21 | paste-proof converter swallowed code after comment markers | compile gate caught it pre-commit; repair cell | 47b |
| 22 | template workflows re-fired on push after partial dispatch-only conversion | full trigger reset verified by check cell | Cell 48 |
| 23 | cold readers flag documented studs — the pitch doesn't route to the ledger | failure-ledger-first framing: FINDINGS.md leads the README and the launch thread | deepseek review (rebuttal) |
| 24 | adopter-facing register missing; all copy pitched builder-ward | two-register copy: builder line for threads, adopter line ('your collaborators, your rules, receipts that outlast the collaboration') for DMs | deepseek review (rebuttal) |
| 25 | dispute-stories are lagging and unschedulable; the countable unit is the near-miss | syndicate #1 instruments near-misses: consulted-and-boring, or reached-for-under-friction — countable, falsifiable in six weeks | deepseek review (rebuttal) |
| 26 | model-on-model convergence is mirrors, not witnesses | no claim of external validation until one human practitioner, cold, wants it | deepseek review (rebuttal) |

| 27 | arXiv 429 with no retry/backoff exits 1; daily ingest ran red three consecutive days | `Retry-After` + exponential backoff in `fetch_papers`; separate transient failure from a bad query in the exit code | open — v1.3 |
| 28 | a deployed instance kept the comment-poisoned queries after the template fixed them, knowingly — the corpus is unfiltered intake | remediate the instance; the general gap is row 37 | shakedown |
| 29 | web-UI commits under a personal email zero out a member's entire churn and breadth (row 17, now quantified: 0.7619/0.2381, `churn=0.0 files=0`) | manifest carries an `emails:` list so historical commits stay recoverable | open — v1.3 |
| 30 | block heights matched as `height N`; `ots` emits `BitcoinBlockHeaderAttestation(N)`, so every height in every ledger was null | regex on the attestation form, `min()` across calendars — the earliest attesting block is the strongest priority claim | anchor.py — e38c5e8 (#1) |
| 31 | `merged_by` is absent from the list-PRs summary representation; merge acts scored zero for everyone, permanently | fetch `GET /pulls/{n}` for merged PRs in-window | attribution.py — e38c5e8 (#1) |
| 32 | attribution windows were cumulative (`min`/`max` over all commits) while labelled with an ISO week | `--since` / `--until` with ordering validation | attribution.py — e38c5e8 (#1) |
| 33 | `'\\[bot\\]$'` in YAML single quotes compiles to a regex for a literal backslash; the attribution firewall never matched a bot | `'\[bot\]$'` | syndicate.yaml — e38c5e8 (#1) |
| 34 | API failure warned, zeroed review credit and exited 0 — a green check lying in the money path | non-zero exit; `GITHUB_TOKEN` auth; `rel=next` pagination | attribution.py — e38c5e8 (#1) |
| 35 | the only substantive research note mis-cites 4 of 10 evidence IDs, already Bitcoin-anchored | appended correction entry, never a rewrite (MAP.md law 4) | open — vault |
| 36 | a placeholder attribution window was committed and anchored; no real window ever ran; no workflow invokes attribution.py | weekly attribution workflow; void the placeholder by appended entry | open — v1.3 |
| 37 | **generated repos are frozen at their generation-time template version; no template→instance propagation path exists** | design an absorption mechanism (upstream cherry-pick, with the anchor chain recording the absorption) | open — ROADMAP v1.4 |
| 38 | **join.py could not parse the manifest it shipped with — the adopter entry path had never been executed.** Row 21's fix doubled comment markers and two landed in string literals, in the same release | match the `members:` key by regex, never a drifting comment; generation smoke test so it cannot recur silently | join.py — e38c5e8 (#1) |
| 39 | join.py wrote the adopter's PAT into `.git/config` via `remote set-url` and never reverted it; `sh()` printed raw git stderr | one-shot authenticated push URL; redact `https://…@` from all output | join.py — e38c5e8 (#1) |
| 40 | join.py ran every git call through `shell=True` with untrusted `--handle` and `--token` interpolated | argv lists throughout | join.py — e38c5e8 (#1) |
| 41 | **rows 23-26 were referenced in planning and absent from this ledger** — §1.2 firing on the findings ledger itself; four findings existed only in conversation | reconstructed from the session record and committed by their author; never leave ledger rows in conversation | 7182fd8 |
| 42 | no tests or CI for ~700 lines of tooling the Agreement executes through; rows 30-34 and 38-40 were all unit-testable and all reached production | `tests/test_generation_smoke.py` + `smoke.yml`: generate a syndicate, run every tool against what generation produced | tests/ — e38c5e8 (#1) |
| 43 | **both template workflows had never once executed.** A doubled `workflow_dispatch:` key from row 22's dispatch-only conversion made GitHub reject them; thirteen dispatches ended in startup_failure while the Actions list showed them "active" under their file path — the parse-failure tell nobody read | remove the duplicate; `test_workflows_have_no_duplicate_keys` with a strict loader | e3ccb95 + f915ffa (#3) |
| 44 | **the mold was stamped with syndicate state.** Verifying row 43's fix by dispatching anchor.yml on the template wrote `ledger/anchors/` into it, so every generated syndicate would have inherited the mold's chain — first anchor `seq=2`, chained to an entry describing the template's tree. Operator rule #10, violated by the act of testing the mold. Assistant raised the rule-10 risk in its own check-in note, then dispatched without re-raising it at the moment of action; the smoke guard caught it within seconds | revert the stamp; `test_mold_ships_no_anchor_chain` so the chain stays empty by construction, not by discipline | f915ffa (#3) |
| 45 | **row 37, quantified: eight discarded block heights.** The instance holding the priority proofs had none of the mold's fixes — eight confirmed Bitcoin attestations recorded as null while the real heights (965528…967082, monotonic) sat in the `.ots` files the whole time | backfill from the stamps, flagged `height_recovered`; `height` is outside CORE_FIELDS so the hash chain is untouched | 7b70566 (shakedown) |
| 46 | **a test passed vacuously when the data shifted under it.** `test_anchor_run_then_verify` asserted on `log.jsonl.splitlines()[0]` and kept reporting green once that first line silently became the mold's inherited entry rather than the one the run created. A positional assertion is a wrong answer waiting for the data to move — rows 30/31/34's class, reproduced inside a guard written to catch that class | locate the entry by the repo's own HEAD and assert exactly one; never by position | f915ffa (#3) |
| 47 | **a strict YAML loader called through `yaml.safe_load` silently no-ops.** `safe_load` hardcodes `SafeLoader` and ignores a `StrictLoader` subclass entirely, so a duplicate-key detector built that way reports every file clean — the detector for row 43's blind spot, with row 43's blind spot | `yaml.load(fh, Loader=StrictLoader)`, and belt-and-braces with an occurrence count | f915ffa (#3) |
| 48 | the ledger gate does not hold against the operator's own token - a push touching `ledger/anchors/log.jsonl` reported `Bypassed rule violations` and landed | closed as documented posture: the bypass stays `always` because the anchor and ingest bots push as the operator's PAT and the narrower mode stops them; the anchor chain is the compensating control; row 16's GitHub App is the path out | SECURITY.md |
| 49 | **the template repo had no branch protection at all** - no ruleset, `protected=false`, while the instance it generates was gated. Any write access could force-push or delete the mold's `main` | mirrored the shakedown's live ruleset by API rather than hand-writing one, so mold and instance are provably identical: require PR (1 approval), restrict deletions, block force pushes | ruleset 23568661 - both repos `protected=true` |
| 50 | **a PR body described work its own diff did not contain.** Row 48/49 edits were staged in a working tree, then `git checkout -B` onto a new branch plus `git checkout <branch> -- <files>` restored the originals, because that branch held no commits - only uncommitted changes. The body was written from intent, and CI stayed green because the claim was prose | read the diff, not the intention, before writing the body; `git diff --stat origin/main` is the check | this row |
| 51 | **arXiv refuses GitHub Actions' Azure egress: HTTP 406 on every request.** Settled by discrimination, not inference: 7 header variants across 2 repositories all refused from Azure (52.161.82.98), while the identical code and queries ingested 27 notes cleanly from a Google Cloud address (34.177.84.223), exit 0. The block follows the network - request shape, repo traffic history, per-IP throttling and the client code are all exonerated. **A template defect, not an instance one:** every generated syndicate hits it on day one, and Activation was telling adopters to schedule exactly that | ingestion runs off hosted runners - self-hosted, notebook or local cron; the tool pushes the notes itself, so the repo stays the record wherever the fetch happens. Activation corrected, the workflow warns in place, anchor.yml unaffected | closed - README + ingest-arxiv.yml |
| 52 | **the publication path assumed a credential some members will not hold.** arXiv requires an endorsement for a member's first submission in a category. Most adopters - students, and researchers already publishing - are auto-endorsed by institutional affiliation or already hold one, so this is a minority case rather than a general blocker. But it is unrecoverable when it applies: a syndicate of unaffiliated members may hold zero endorsements and no internal approval substitutes. `archive_targets` listed the gated route first, no field tracked eligibility, and ORCID shipped as a placeholder | Zenodo first (ungated, real DOI, and where data and code get one regardless of affiliation), the constraint stated at Activation rather than discovered at submission, ORCID required for the publication path but never for membership, `deposit_zenodo.py` spec'd | docs/PUBLICATION.md - spec open |
| 53 | **a ruleset mirrored across repos with different membership produced an unsatisfiable rule.** Row 49 closed by cloning the shakedown's live ruleset onto the template so mold and instance would be provably identical - but the shakedown had two collaborators and the template had one. GitHub forbids self-approval, so a required approving review count of 1 exceeded members-1 and every PR on the template deadlocked on first contact. Row 9's arithmetic, in live GitHub config rather than in a manifest field nothing reads | added the second member to the template as a collaborator, which was independently overdue; verified by PR #9 merging on a satisfied gate rather than a bypass. Identical governance is not the goal - governance a repo's actual roster can satisfy is | collaborator added; gate proven on #9 |
| 54 | **row 51 is a property of the substrate, not of the tool it was found in.** A second arXiv client, built independently and never having touched this repo, targets `export.arxiv.org` and documents GitHub Actions as its recommended deployment - the exact pairing row 51 spent a week proving refused. The block belongs to the egress, so every current and future arXiv-touching component inherits it: the constraint has to live where tools are adopted, not in the one tool's README where it was first written down. Found by audit rather than by a failing run, because the second client was never run here | the egress constraint stated as a protocol-level precondition in docs/DISCOVERY.md's intake section, alongside the outcome-split requirement that makes a refusal legible when it does happen | docs/DISCOVERY.md - adoption boundary |
| 55 | **the deadlock guard's floor blessed the one roster that always deadlocks.** Row 9 capped gates at `max(members-1, 1)`; the floor stops a gate being relaxed to 0, but at one member it makes cap 1 and passes a gate of 1 - and nobody approves their own PR. So the guard agreed with a manifest that had already deadlocked this repo's PRs #6-#8, and it was the shape a launch plan was about to recommend to an audience of independent researchers who start alone. Found by auditing a distribution plan against the code, not by a failing run | solo formation is supported and must be declared: `governance.formation: solo`, refused when absent at one member and refused when it outlives the roster. The declaration is what the operator bypass (row 48) rests on, with the anchor chain as the compensating control. One rule in tools/manifest.py, imported by join.py and the suite, so it cannot disagree with itself | manifest.py + join.py + README |
| 56 | **an external review's checklist asserted eleven things the repo already had, and one the ledger had disproved.** The review's prose was accurate and had clearly read the README - it cited the arXiv 406, solo formation's stickiness, the honest-scope section. Its "P0 ASAP" list was generic: add a LICENSE, add tests for the four tools, add retries to the arXiv ingest, make drift_check dry-run by default, add a solo_mode flag. All present, and drift_check has no apply mode to make safe. Its advice to "handle 406" with retries and a User-Agent is row 51 restated as the fix row 51 disproved. The reviewer later confirmed it never saw the tree | reviews are evidence about two things, the artifact and the reviewer's method: prose that reads is useful for positioning, a checklist without tree access is boilerplate until each line is checked against a file. Seven items survived the fact-check and shipped; the rest was recorded rather than built. Roadmaps proposing a network before the first node are gravity, not guidance | this row + the Bin B changes |
| 57 | **`git verify-commit` does not bind a signature to its author, and a tool trusting it would have shipped impersonation as the identity guarantee.** SSH-signed commits verify against an allowed-signers file, and git's question is "is this key in the file" - not "does this key belong to this commit's author". Measured, not reasoned: a commit authored by one address and signed with a key listed under a different one reports `%G?` = G and exits 0. Every member could have signed as every other member, and the check would have been green - on the one feature whose entire purpose is that an email is a claim and a key is possession | verify_signatures.py checks both halves: git's boolean for the cryptography, and `%GK` against the fingerprints listed for THAT author's row for the binding. The guard asserts git's own acceptance first, so it fails if the premise ever changes | tools/verify_signatures.py |
| 58 | **two more guards passed for the wrong reason, and one of them was satisfied by a parenthetical.** Writing the first-run helper meant writing ten new guards, and mutation-testing them caught two that were green against the defect they claimed to catch. One asserted `"git mv" in fix` to prove the repair preserved an audit's history - and the fix string also ended `(git mv, so the history follows the file)`, so replacing the command itself with `cp` still passed. The other set a review gate of 3 against a one-member roster to prove the cap held; 3 is above every plausible cap, so the assertion never bound to the boundary it was testing and an off-by-one in either direction survived it | substring assertions on a message that also explains itself are checked at the position that matters (`startswith`), and a cap is tested at its boundary and one below it, not at a value that is wrong under every version of the rule. The mutation pass is the only reason either was found: both were written deliberately, reviewed, and passed | tests/test_generation_smoke.py |

## The operator checklist (condensed from the ledger)

1. Branch protection ON before any signature PR (ruleset, approvals, admins included)
2. Gates <= members - 1
3. Fresh dispatch, never re-run
4. Pinned, measured dependencies; CLI over churny libraries
5. Approve radio, not Comment — verify 'approved these changes' text
6. Dedup keys are load-bearing; never edit arxiv_id frontmatter
7. Bots need exclusion identities in the manifest
8. A green check must never lie; deferred failures name their reason
9. Email is identity: manifest email = noreply address, or commits vanish
10. Templates are molds: no schedules, no syndicate pipelines inside them
11. Dispatch-test workflow edits before calling them done
12. Bots pushing to protected main need PAT (bootstrap) or App (production)

## Row 21 is not closed

Row 21 ("paste-proof converter swallowed code after comment markers") was
recorded as fixed. The fix doubled comment markers, and five of those doubled
markers shipped in v1.2 — two of them inside *string literals*, where a
comment-marker fix becomes a logic bug. One broke join.py's manifest anchor
(row 38); the other wrote a malformed comment into every new member's row.

A converter artifact that relocates from comments into data is not the same bug
fixed. It is the same bug moved to where it has teeth. Row 38 is row 21's child.

## Where rows 27-42 came from

AUDIT-001 (`docs/AUDIT-001-opus.md`): an external cold audit that executed the
tooling rather than reading it. Its own scope error — auditing a generated
instance and taking it for the system — is what surfaced row 37. Nothing in this
block was found by reading source; every row was produced by running something.

## What rows 43-48 have in common

Every one reported success while broken. Nothing crashed. `join.py` printed a
sensible error, the workflows showed `active`, `verify` printed `OK`, the smoke
suite went green, the push succeeded. Each failure lived in a seam — two files
disagreeing, two parsers disagreeing, mold against instance, a test against the
data beneath it — and seams do not raise exceptions. They agree with everyone.

What caught all six was running the thing and looking at what came out.

Two of them are worse than that. Row 22's fix created the bug that hid row 22.
Row 47 is row 43's detector containing row 43's defect. A fix that never
reproduced the original failure does not close a bug; it relocates it, usually
somewhere with better cover. That is now the ledger's most repeated shape — rows
21→38 and 22→43 — and the only reliable answer found so far is a guard that has
been mutation-tested: made to fail on the exact defect it claims to catch, before
anyone trusts it green.
