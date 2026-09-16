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
