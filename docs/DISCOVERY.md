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
