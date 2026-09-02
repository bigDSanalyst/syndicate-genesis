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

echo "== 4. BYOK reminders =="
echo "  - Obsidian-Git plugin: author email must match git email"
echo "  - .env is gitignored. Keys never enter the repo."
