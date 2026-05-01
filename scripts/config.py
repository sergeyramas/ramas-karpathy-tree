"""Path constants and configuration for the personal knowledge base.

HOW TO CONFIGURE:
  Set these environment variables (or edit the defaults below for your machine):

  VAULT_DIR   — absolute path to your Obsidian/wiki vault root
                e.g. ~/Library/Mobile Documents/iCloud~md~obsidian/Documents/MyVault
  UV_BIN      — absolute path to the uv binary (needed because hooks run with
                a stripped PATH)
                e.g. ~/.local/bin/uv  (Mac default via `curl -fsSL https://astral.sh/uv/install.sh | sh`)
  CLAUDE_MD   — absolute path to your ~/CLAUDE.md trunk file
  MEMORY_MD   — absolute path to your global MEMORY.md (Claude Code per-project memory dir)

  See README.md "Configuration" section for full setup guide.
"""

import os
from pathlib import Path
from datetime import datetime, timezone

# ── Paths ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT_DIR / "daily"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
CONCEPTS_DIR = KNOWLEDGE_DIR / "concepts"
CONNECTIONS_DIR = KNOWLEDGE_DIR / "connections"
QA_DIR = KNOWLEDGE_DIR / "qa"
REPORTS_DIR = ROOT_DIR / "reports"
SCRIPTS_DIR = ROOT_DIR / "scripts"
HOOKS_DIR = ROOT_DIR / "hooks"
AGENTS_FILE = ROOT_DIR / "AGENTS.md"

INDEX_FILE = KNOWLEDGE_DIR / "index.md"
LOG_FILE = KNOWLEDGE_DIR / "log.md"
STATE_FILE = SCRIPTS_DIR / "state.json"

# ── Timezone ───────────────────────────────────────────────────────────
TIMEZONE = "UTC"  # Change to your timezone, e.g. "Europe/Moscow", "America/New_York"


def now_iso() -> str:
    """Current time in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    """Current date in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


# ── v2 paths (Memory Architecture v2 Foundation) ────────────────────────
PROJECTS_JSON = ROOT_DIR / "projects.json"
LOGS_DIR = ROOT_DIR / "logs"

# Vault root — configure via env var or edit the fallback for your machine.
# Mac iCloud Obsidian default: ~/Library/Mobile Documents/iCloud~md~obsidian/Documents/<VaultName>
_vault_env = os.environ.get("VAULT_DIR", "")
VAULT_DIR = Path(_vault_env).expanduser() if _vault_env else Path.home() / "obsidian-vault"
VAULT_WIKI = VAULT_DIR / "wiki"
VAULT_PROJECTS = VAULT_WIKI / "projects"


def daily_log_path(slug: str, date_iso: str) -> Path:
    """Return path to daily log file for given slug + date (v2: per-slug)."""
    return DAILY_DIR / slug / f"{date_iso}.md"


# ── Models ──────────────────────────────────────────────────────────────
FLUSH_MODEL = "claude-haiku-4-5-20251001"
FLUSH_CHAR_THRESHOLD = 1000

# ── Subprocess invocation (hooks run with stripped PATH) ────────────────
# uv is not on the stripped PATH that Claude Code hooks receive.
# Set UV_BIN env var or edit this fallback to your actual uv location.
# Find it with: which uv  (after `curl -fsSL https://astral.sh/uv/install.sh | sh`)
UV_BIN = os.environ.get("UV_BIN", str(Path.home() / ".local" / "bin" / "uv"))
