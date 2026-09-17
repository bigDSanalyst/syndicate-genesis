# Discovery Layer Design

## Principle

Discovery is agentic; transmission is human. The agent may read anything
public and draft anything; contact requires a named human identity or an
agent-native channel. No scraping, no automated outreach, no data beyond
what public APIs expose.

## Pipeline

1. ingest_people.py: standing queries over public APIs (GitHub Search,
   ORCID, arXiv authors of ingested papers) -> candidate cards in
   vault/00-inbox/people/ (frontmatter: handle, orcid, noreply, signals;
   handle is the dedup key)
2. ingest_repos.py: the same skeleton over GitHub Search — repos as
   literature; a repo is strictly richer than a paper (history,
   contributors, protocol-native structure). The syndicate-detection
   query (filename:syndicate.yaml) makes every deployed syndicate
   discoverable to every other one — the network's growth loop, mechanical
3. Agent briefs: each card carries a read of the candidate's work —
   summary, complementarity case, drafted first message, evidence links
4. Founder triage: status tags like papers (triage -> contacted ->
   declined -> joined); the initiator sends from their own accounts
5. The record compounds: joined members' anchored work becomes context
   for future briefs; founder choices become the oracle's training signal

## Calibration instruments (arxiv-gauge)

`arxiv-gauge` is a standalone tool built outside this protocol and offered to
it: standard-library Python, no LLM, no key, three sources. It is **not** part
of the pipeline above and this section does not adopt it. It records where the
protocol could use it, what each use would owe, and — because that is how
everything else here enters the record — what an audit found before anyone
believed it.

Two commands and a primitive:

- `digest` — what landed in the configured categories since last run, scored on
  keyword weights, deduplicated against a local SQLite of seen ids
- `check` — *"is this idea occupied?"*, run **before** writing code: searches
  arXiv for a phrase, widens the query when it returns little (5 terms → 3 → 2),
  and reports who is publishing near it
- `watch` — the general primitive: hashes the visible text of any URL and emits
  an item when the hash changes. Covers anything without a feed.

### Adoption preconditions for anything that talks to arXiv

These are protocol-level and apply to every component the syndicate adopts, not
only to this one. Row 51 was found in `tools/ingest_arxiv.py`, but the block it
found belongs to the egress, not to that tool — so the constraint has to live
here, where tools are adopted, rather than in the README of the first tool to
trip over it.

1. **Egress.** arXiv refuses GitHub Actions' Azure egress. A component that
   fetches from arXiv cannot be scheduled on a hosted runner: it runs from a
   self-hosted runner, a notebook, or local cron, and pushes its results into
   the repo, which stays the record wherever the fetch happened. A component
   whose documentation recommends hosted Actions has not been adapted yet,
   however well it works elsewhere.
2. **Legibility of refusal.** A component must exit differently on "the server
   refused me" than on "there was nothing there". Anything that reports a
   refusal as an empty result will eventually put that empty result into the
   Repository Record, where §9.2 gives it an authority it has not earned.

### Three bridges

**1. `watch` as a candidate freshness mechanism.** The vault has no way to know
that a source it ingested has since moved. `watch` is the shape of an answer:
per-URL state is one hash, so cost is O(number of URLs) and independent of page
size, and the id it emits embeds the content hash — so each distinct change is a
*new item* rather than an edit to the old one. That is MAP.md **law 4**
(append-mostly; corrections are new entries, not rewrites) reached in a tool
that never had to obey it, and `sources.py`'s own contract restates law 1's
requirement independently: "stable unique id — must not change per item".

What this bridge does **not** have is a specification. `status/superseded` is
listed in ROADMAP near-term and is not built; no field in any frontmatter schema
records staleness; nothing defines what the vault should *do* when a watched
source changes. `watch` is a mechanism looking for a policy, and the policy is
the unwritten part. Recorded here as a candidate, not a design.

**2. `check` output as §9.2 evidence.** Agreement §9.2: *"Evidence. The
Repository Record only. Client-side timestamps are inadmissible on questions of
time."* A `check` run is a dated claim about what the field contained — exactly
the kind of claim §9.2 refuses to take on a member's word. Committed to
`50-decisions/` as the ADR for "we built X knowing Y was already there", it
stops being a member's assertion and becomes Repository Record; anchored, its
date stops being the member's word too.

Note carefully which part is the evidence. The timestamp the tool prints is
client-side and §9.2 excludes it. The **commit** is the evidence, and the
anchor is what makes its date external. A `check` output pasted into a message
proves nothing the protocol recognises; the same bytes committed and anchored
prove when the search was known to have been run.

**3. `digest` as a triage hypothesis — testable, and currently untested.** The
claim is that daily exposure to names and phrases builds recognition, and that
recognition makes triage cheap. That is a hypothesis about humans, not a
mechanism, and this repo is the wrong place to assert it and the right place to
measure it. The baseline is unflattering and therefore usable: in the shakedown
instance, **127 of 127 literature notes sit at `status/triage`, with zero
advanced** since ingestion. If a digest habit is what moves that number, the
number will move; if it does not, the bridge was decoration. Either result is
worth having, and the second one is worth having most.

### Fourth item: port the outcome split back into the gauge

The gauge's arXiv fetch catches bare `Exception`, so a refusal and an empty
result arrive identically. `tools/ingest_arxiv.py` already solved this shape —
REJECTED/BLOCKED exits 1 because it needs a human, TRANSIENT exits 2 because it
does not — and that split is the precondition for bridge 2. An occupancy check
that cannot tell "nobody is working here" from "the server would not answer" is
not evidence of anything, and committing such a null to `50-decisions/` would
put a false open area into the Repository Record under §9.2's authority, where
it is much harder to retract than it was to create.

Until the split is ported, `check` output is a working note, not evidence.

### What the audit found

Run against a stubbed HTTP 406 with the backoff neutered and nothing else
changed, on 2026-09-17:

| # | Finding | Severity |
|---|---|---|
| G1 | **A refusal is indistinguishable from an open area.** Every request 406s; `check` prints *"No hits, even at the loosest query"*, offers two explanations (open area, wrong vocabulary) of which neither is "the server refused you", and exits 0. `digest` prints *"Nothing above threshold. That is a normal result."* on `scanned 0`, and exits 0. The false-open is the precise failure the tool exists to prevent | blocks bridge 2 |
| G2 | **Inherits row 51.** Both entry points target `export.arxiv.org` — the host proven refused from GitHub Actions' Azure egress across 7 header variants and 2 repositories — while the README recommends GitHub Actions as the deployment. The gauge uses `http://` where row 51 was established on `https://`; urllib would follow a redirect to the same host, but that redirect was not observed and the scheme question is open. `watch` and `nvd` use other hosts and survive | deployment |
| G3 | **The widening ladder repeats itself.** `(min(len(terms),5), 3, 2)` yields `(3,3,2)` for a three-term phrase and `(2,3,2)` for a two-term one, where `terms[:3]` of two terms is the same query — three identical requests, one labelled with a term count it does not have. Against a service whose 3-second etiquette the tool's own README enforces | etiquette |
| G4 | **One malformed CVE kills the run.** `.get("description", [{}])[0]` defaults on an *absent* key, not an empty list; an NVD weakness with `"description": []` raises IndexError out of the source loop. Off by default, so latent | robustness |
| G5 | **Two dedup stores, two commit points.** `page_watch` writes `page_state.json` when its generator finishes; the SQLite `mark_seen` commits only after *all* sources finish. The shipped source order is `["arxiv","watch","nvd"]`, so G4 rolls back the seen-marks while the page hash has already advanced — the watched change is never reported, and the next run matches the new hash and never reports it either. Silent permanent loss | data loss |
| G6 | **The calibration control is advice, not code.** The README prescribes the right check — *"try `check` on a term you KNOW is crowded to confirm the tool is finding things at all"* — and leaves it to the operator. That is the mutation-testing rule stated and not automated: prove the instrument detects the thing before trusting it not to | see below |

G6 is the one with a design answer rather than a patch. A `--self-test` that
queries a known-occupied term first and fails loudly on zero would make the
instrument prove its own detection before reporting a null — the same discipline
the smoke suite applies to its own guards, turned on the tool that needs it most.

**Worklist, if and when the gauge is promoted to a repo of its own:** https
endpoint, outcome split (G1), widening-ladder dedup (G3), NVD description guard
(G4), single commit point (G5), self-test control (G6). Those are the gauge's
own work and sit behind `deposit_zenodo.py` and the drift check in ROADMAP —
an exit tool outranks intake refinement, however good the intake.

What lands here tonight is the design and its boundaries. The tool joins the
record the way every other component did: by surviving an audit that executed
it, with the unflattering results written down first.

## Formation modes

- Founder mode (now): the initialized collaborator invites, reviews,
  approves. Authority is legitimate at genesis — someone holds the keys,
  liability concentrates in the inviter, trust bootstraps socially.
- Oracle mode (later): deterministic, auditable matching for people who
  arrive without a founder. Inherits judgment from founder-mode history.

## Consent rules (design constraints, not preferences)

- Public API queries only; platforms' official doors only
- Discovery finds; humans approach
- Automated outreach would convert the protocol's name into spam within
  ~50 messages; quality bar: 'would a thoughtful human have written this
  after reading the work?'
- **`ingest_people.py` MUST NOT compute, store, or expose any field derived
  from arXiv endorsement eligibility.** Not "must not rank by it" - must not
  have the concept. The data model must be unable to express the question
  "who could endorse me in quant-ph".

  This is a schema constraint rather than a usage policy on purpose. A field
  that exists will eventually be sorted on by someone under deadline, and a
  discovery tool that can answer that question is an endorsement-farming tool
  with a disclaimer on it. arXiv discourages soliciting endorsements from
  strangers; a campaign built on this protocol would poison its name with the
  exact community it needs, and the damage is not recoverable by apologising.

  Discovery finds collaborators and relevant authors. Endorsement is asked of
  someone a member already knows, and what the protocol contributes is the
  evidence they bring to that conversation - never the conversation itself.
