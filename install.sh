#!/usr/bin/env bash
# Ramas-Karpathy-Tree — quick install for Mac
# See README.md for full setup guide.
set -euo pipefail

INSTALL_DIR="$HOME/.claude-memory-compiler"
SETTINGS="$HOME/.claude/settings.json"

echo "==> Installing Ramas-Karpathy-Tree to $INSTALL_DIR"

# 1. Copy files
cp -r "$(dirname "$0")" "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 2. Copy projects.json template if not already present
if [ ! -f "projects.json" ]; then
  cp projects.json.example projects.json
  echo "  Created projects.json from example — edit it to map your cwd paths to slugs."
fi

# 3. Create required directories
mkdir -p daily logs knowledge/concepts knowledge/connections knowledge/qa reports

# 4. Sync dependencies with uv
if command -v uv &>/dev/null; then
  uv sync
else
  echo "  uv not found. Install with: curl -fsSL https://astral.sh/uv/install.sh | sh"
  exit 1
fi

# 5. Remind about hooks registration
echo ""
echo "==> Next steps:"
echo "  1. Edit $INSTALL_DIR/projects.json — add your projects and cwd paths."
echo "  2. Set VAULT_DIR in your environment (or edit hooks/session-start.py):"
echo "       export VAULT_DIR=\"\$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/YourVault\""
echo "  3. Register hooks in $SETTINGS — see README.md 'Step 4: Register hooks'."
echo "  4. Run tests: cd $INSTALL_DIR && uv run pytest tests/ -v"
echo ""
echo "Done."
