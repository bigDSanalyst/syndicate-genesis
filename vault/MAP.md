# Vault Map — rules for AI agents reading this workspace

This file is the map for any agent (Claude, MCP filesystem clients, etc.)
operating on this vault. Read it before touching anything. It encodes the
vault's conventions, schemas, and the rules that are load-bearing for the
syndicate's machinery — breaking them corrupts attribution, dedup, or
governance.

## Folder semantics (workflow order, not just categories)

- `00-inbox/` — untriaged landing zone. Scrapers target it; humans move items
  out. Nothing here is authoritative.
- `10-literature/` — ingested source material, one file per paper, machine-
  written by `tools/ingest_arxiv.py`. Humans annotate in place or move to
  `20-notes/`.
- `20-notes/` — human research notes. The thinking layer.
- `30-experiments/` — protocols, methods, parameters, code plans.
- `40-drafts/` — publication drafts. REQUIRES CODEOWNERS review to merge.
- `50-decisions/` — ADRs: why the team chose X. Load-bearing history.
- `_templates/` — note templates with frontmatter schemas.
- `maps/` — relationship diagrams (.canvas).

## Frontmatter schemas

Every note carries YAML frontmatter. Required keys by folder:

- literature notes: `arxiv_id`, `url`, `published`, `ingested`, `authors`,
  `tags` (list, must include a `status/…` tag)
- research notes: `title`, `tags`, `status`
- drafts: `title`, `authors`, `status`, `milestone`

## THE LAWS (breaking these breaks the machinery)

1. **NEVER delete or alter the `arxiv_id` line.** It is the dedup key. Re-
   ingestion checks it; delete it and the paper duplicates on next run.
2. **Status tags move forward only: triage → reading → read → archived.**
   They drive the team's triage Dataview queries.
3. **Never edit another member's EXECUTION-LOG row or another member's note
   frontmatter `authors`.** Identity binding is the attribution foundation.
4. **`50-decisions/` and `ledger/` are append-mostly.** Corrections are new
   entries, not rewrites — the anchored record depends on append semantics.
5. **Files in `40-drafts/` are confidential pre-publication** (Agreement §7).
   Do not quote their contents outside this workspace.

## What an agent should do here

- When asked to summarize the research: read `20-notes/` and `50-decisions/`
  first; `10-literature/` is raw material, not conclusions.
- When asked to find a paper: search `arxiv_id` values in frontmatter.
- When asked to triage: move inbox items, set status tags, NEVER touch law 1.
- When you do not find information: say so. Do not invent citations.
  (The vault rewards honest failure; the record punishes confident invention.)

## Naming

lowercase-hyphens for notes you create; ingested files keep their
`arXiv_<id> - <title>.md` shape (law 1 extends to the filename prefix).
