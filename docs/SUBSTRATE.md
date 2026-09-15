# The Evidence Substrate

## What syndicate-genesis is, positioned

A git-native substrate producing the records an agent-native internet
would need to answer trust queries: records that are anchored, attributed,
appealable, and machine-legible. Research syndicates are the first use
case; the records are the point.

## The four primitives (implemented today)

1. **Anchored time** — `tools/anchor.py`: OTS-stamped state chain;
   Bitcoin attestations; bare-export verification. A record's existence
   at time T is provable without any server.
2. **Computed attribution** — `tools/attribution.py`: contribution shares
   derived from the repository record, windowed, objection-gated,
   survivorship-weighted. Who did what is computed, not asserted.
3. **Appealed commitments** — `agreements/consortium-agreement.md`:
   signatures executed by PR review; objection windows where silence
   ratifies; a dispute ladder in §9. Commitments are structured and
   dispute-resolvable by construction.
4. **Machine-legibility** — `vault/MAP.md` + frontmatter schemas: agents
   read the same laws humans follow; the record is navigable by both.

## Network-era mechanisms (designed, deliberately not shipped)

- **Cluster-signed oracle verdicts (watermarks):** require (a) an
  aggregate signature scheme with node key management, (b) a registry of
  issued responses, and (c) an anchoring cadence binding response hashes
  into the OTS chain — without (c), watermark chains are rebuildable by
  any node operator and provide no security property. Parked until
  multi-node deployments exist.
- **Slashing / staked reputation:** an economic layer, entangled with the
  securities questions the protocol quarantines. Parked.
- **Threshold genesis.sig:** t-of-n founding members co-sign formation
  attestations (FROST/Ed25519; ML-DSA via pq-verify verification later).
  Designed; see ROADMAP.md.

## What a network adds later

Multiple independent responders, consensus over conflicting verdicts, and
reputation derived from anchored history. None of these are required for
recheckable answers, which is why v0 ships without them.
