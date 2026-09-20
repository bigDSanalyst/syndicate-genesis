#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "== 1. Identity gate =="
EMAIL=$(git config --get user.email || true)
if ! grep -q "$EMAIL" syndicate.yaml; then
  echo "WARNING: $EMAIL not in syndicate.yaml - commits would be unattributed."
  read -rp "Set git email to your registered address? [y/N] " r
  [[ "$r" == "y" ]] && read -rp "Email: " e && git config user.email "$e" || true
fi

echo "== 2. Install identity pre-commit hook =="
cat > .git/hooks/pre-commit <<'EOF'
#!/bin/sh
EMAIL=$(git config user.email)
grep -q "$EMAIL" syndicate.yaml || {
  echo "BLOCKED: $EMAIL is not registered in syndicate.yaml"; exit 1; }
EOF
chmod +x .git/hooks/pre-commit

echo "== 3. Wire local MCP config =="
sed "s|__VAULT_PATH__|$(pwd)/vault|" agents/mcp.json.template > agents/mcp.json
echo "  -> agents/mcp.json bound to local vault"

echo "== 4. Template lineage and narrative strip =="
# Instances inherit machinery and rules, never narrative: FINDINGS.md is the
# mold's scar tissue and ROADMAP.md is the protocol's priorities, not this
# syndicate's. Both live on in the template repo, which the lineage points at.
# Guarded on the placeholder member row, the same marker anchor.py keys on: a
# mold running its own bootstrap must not strip the originals.
if grep -q '"github-handle"' syndicate.yaml; then
  echo "  -> mold detected (placeholder member row); skipping strip and lineage"
else
  STRIP=""
  for f in FINDINGS.md ROADMAP.md docs; do
    [ -e "$f" ] && STRIP="$STRIP $f"
  done
  if [ -n "$STRIP" ]; then
    echo "  Upstream narrative still present:$STRIP"
    # The strip list strips inheritance, not identity. docs/ is inherited, so
    # anything this syndicate wrote about itself must move to audits/ first -
    # that drawer is a record organ and is never stripped.
    if [ -n "$(find docs -type f -name 'AUDIT-*' 2>/dev/null)" ]; then
      echo "  ⚠ docs/ contains AUDIT-* files. Those are THIS repo's history:"
      echo "    move them to audits/ before answering yes."
    fi
    read -rp "  Remove it? Template keeps the originals. [y/N] " r
    if [ "$r" = "y" ]; then
      rm -rf $STRIP
      echo "  -> stripped:$STRIP"
    else
      echo "  -> kept; drift_check.py ignores these paths either way"
    fi
  fi
  python3 tools/drift_check.py record || \
    echo "  -> lineage not recorded (see above); re-run: python3 tools/drift_check.py record"
fi

echo "== 5. BYOK reminders =="
echo "  - Obsidian-Git plugin: author email must match git email"
echo "  - .env is gitignored. Keys never enter the repo."

echo
echo "== 6. Where this syndicate stands =="
# bootstrap runs once; doctor answers the question bootstrap leaves behind -
# what is still owed, and what the next command is. Re-runnable, read-only, and
# the thing to run first whenever anything is unclear. Its exit code is not
# this script's: a fresh syndicate legitimately owes decisions, and bootstrap
# succeeding at what bootstrap does is a separate fact from the repo being
# fully configured.
python3 tools/doctor.py || true
echo
echo "Re-run it any time:  python3 tools/doctor.py"
