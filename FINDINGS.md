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
| 9 | review gates above members-1 deadlock the syndicate | auto-cap gates at genesis | manifest note |
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

<!-- Rows 23-26 are referenced in planning but were never committed to this
     ledger. See row 41: the gap is left open deliberately rather than
     silently renumbered. Reconstruct and insert them here. -->

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
| 41 | **rows 23-26 are referenced in planning and absent from this ledger** — §1.2 firing on the findings ledger itself | reconstruct and commit, or void explicitly; never leave ledger rows in conversation | open — decision needed |
| 42 | no tests or CI for ~700 lines of tooling the Agreement executes through; rows 30-34 and 38-40 were all unit-testable and all reached production | `tests/test_generation_smoke.py` + `smoke.yml`: generate a syndicate, run every tool against what generation produced | tests/ — e38c5e8 (#1) |

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
