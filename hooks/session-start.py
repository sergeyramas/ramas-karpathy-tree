"""
SessionStart hook v2 — cwd-aware project leaf loading.

Reads cwd from hook input, resolves the slug via projects.json, and assembles a
~3-5k token context containing only:
  • global core (CLAUDE.md, Karpathy_Guidelines, global MEMORY.md, wiki/index.md headers)
  • the active project's leaf (index, MEMORY, open-questions, latest journal)
  • the active project's raw daily log for today
  • AGENT_ACTIVITY.md from the project repo (if found)

Other projects are NOT loaded.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.slug_router import resolve_slug

ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT / "daily"
PROJECTS_JSON = ROOT / "projects.json"

# Configure these via environment variables or edit the fallbacks for your machine.
# See README.md "Configuration" section and config.py for full details.
import os as _os
_vault_env = _os.environ.get("VAULT_DIR", "")
VAULT_DIR = Path(_vault_env).expanduser() if _vault_env else Path.home() / "obsidian-vault"
VAULT_WIKI = VAULT_DIR / "wiki"
VAULT_PROJECTS = VAULT_WIKI / "projects"

# ~/CLAUDE.md — trunk file loaded into every session
ROOT_CLAUDE_MD = Path(_os.environ.get("CLAUDE_MD", str(Path.home() / "CLAUDE.md")))
# Global MEMORY.md — Claude Code auto-memory file for the memory project dir
GLOBAL_MEMORY_INDEX = Path(_os.environ.get("MEMORY_MD", str(
    Path.home() / ".claude" / "projects" / "memory" / "MEMORY.md"
)))

MAX_CONTEXT_CHARS = 18_000
MAX_INDEX_LINES = 100
JOURNAL_DAYS_LOOKBACK = 3
DAILY_LOG_LOOKBACK_DAYS = 2


def _read(path: Path, max_lines: int | None = None) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
        if max_lines is not None:
            lines = text.splitlines()
            if len(lines) > max_lines:
                text = "\n".join(lines[:max_lines]) + "\n... (truncated)"
        return text
    except OSError:
        return ""


def _section(title: str, body: str) -> str:
    return f"## {title}\n\n{body}".rstrip() + "\n"


def _project_leaf(slug: str) -> str:
    if slug == "_global":
        return ""
    leaf_dir = VAULT_PROJECTS / slug
    if not leaf_dir.exists():
        return ""

    parts = []
    for filename in ("index.md", "MEMORY.md", "open-questions.md"):
        body = _read(leaf_dir / filename)
        if body:
            parts.append(_section(f"{slug}/{filename}", body))

    journal_dir = leaf_dir / "journal"
    if journal_dir.exists():
        journal_files = sorted(journal_dir.glob("*.md"), reverse=True)[:JOURNAL_DAYS_LOOKBACK]
        for jf in reversed(journal_files):
            body = _read(jf)
            if body:
                parts.append(_section(f"{slug}/journal/{jf.stem}", body))

    return "\n".join(parts)


def _recent_daily_log(slug: str) -> str:
    today = datetime.now(timezone.utc).astimezone()
    for offset in range(DAILY_LOG_LOOKBACK_DAYS):
        date = today - timedelta(days=offset)
        log_path = DAILY_DIR / slug / f"{date.strftime('%Y-%m-%d')}.md"
        if log_path.exists():
            return _read(log_path)
    return ""


def _agent_activity(cwd: str) -> str:
    if not cwd:
        return ""
    p = Path(cwd)
    while p != p.parent:
        candidate = p / "AGENT_ACTIVITY.md"
        if candidate.exists():
            return _read(candidate, max_lines=50)
        if (p / ".git").exists():
            break
        p = p.parent
    return ""


def build_context(cwd: str) -> str:
    slug = resolve_slug(cwd, PROJECTS_JSON)
    today = datetime.now(timezone.utc).astimezone()

    parts = [f"## Today\n{today.strftime('%A, %B %d, %Y')} (slug: {slug})"]

    claude_md = _read(ROOT_CLAUDE_MD)
    if claude_md:
        parts.append(_section("CLAUDE.md (trunk)", claude_md))

    global_memory = _read(GLOBAL_MEMORY_INDEX)
    if global_memory:
        parts.append(_section("Global MEMORY.md", global_memory))

    wiki_index = _read(VAULT_WIKI / "index.md", max_lines=MAX_INDEX_LINES)
    if wiki_index:
        parts.append(_section("Wiki Index", wiki_index))

    leaf = _project_leaf(slug)
    if leaf:
        parts.append(f"## Active Project Leaf — {slug}\n\n{leaf}")

    daily = _recent_daily_log(slug)
    if daily:
        parts.append(_section(f"Recent Daily Log [{slug}]", daily))

    activity = _agent_activity(cwd)
    if activity:
        parts.append(_section("AGENT_ACTIVITY.md (hot-state)", activity))

    context = "\n\n---\n\n".join(parts)

    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n\n... (truncated)"

    return context


def emit_hook_output(cwd: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": build_context(cwd),
        }
    }
    print(json.dumps(output))


def main() -> None:
    cwd = ""
    try:
        raw = sys.stdin.read()
        if raw.strip():
            payload = json.loads(raw)
            cwd = payload.get("cwd", "") or os.getcwd()
        else:
            cwd = os.getcwd()
    except (json.JSONDecodeError, ValueError):
        cwd = os.getcwd()

    emit_hook_output(cwd)


if __name__ == "__main__":
    main()
