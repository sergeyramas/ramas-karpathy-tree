"""Maps a filesystem cwd to a project slug via projects.json longest-prefix match."""

from __future__ import annotations

import json
from pathlib import Path


def resolve_slug(cwd: str, config_path: Path) -> str:
    """Return slug for cwd, or fallback ('_global') if no prefix matches."""
    if not config_path.exists():
        return "_global"

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "_global"

    routes = config.get("routes", [])
    fallback = config.get("fallback_slug", "_global")

    if not cwd:
        return fallback

    cwd_path = str(Path(cwd).resolve()) if Path(cwd).exists() else cwd

    best_slug = fallback
    best_len = 0

    for route in routes:
        slug = route.get("slug", "")
        for prefix in route.get("cwd_prefixes", []):
            if cwd_path == prefix or cwd_path.startswith(prefix.rstrip("/") + "/"):
                if len(prefix) > best_len:
                    best_len = len(prefix)
                    best_slug = slug

    return best_slug
