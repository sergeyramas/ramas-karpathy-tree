import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Load hooks/session-start.py via importlib (file has hyphen — not a valid module name)
SS_PATH = Path(__file__).resolve().parent.parent / "hooks" / "session-start.py"
_spec = importlib.util.spec_from_file_location("session_start_mod", SS_PATH)
ss = importlib.util.module_from_spec(_spec)
sys.modules["session_start_mod"] = ss
_spec.loader.exec_module(ss)


@pytest.fixture
def fake_vault(tmp_path, monkeypatch):
    """Build a minimal vault tree under tmp_path and point session-start at it."""
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    projects_betaline = wiki / "projects" / "betaline"
    projects_betaline.mkdir(parents=True)

    (wiki / "index.md").write_text("# Wiki Index\n\n## Projects\n- betaline\n")
    (projects_betaline / "index.md").write_text("# BetaLine\n\nTelegram bot project.\n")
    (projects_betaline / "MEMORY.md").write_text("- Use Postgres, not SQLite\n")
    (projects_betaline / "open-questions.md").write_text("- How to scale webhooks?\n")

    journal = projects_betaline / "journal"
    journal.mkdir()
    (journal / "2026-04-30.md").write_text("# 2026-04-30\nDecided to migrate to Next.js\n")

    daily = tmp_path / "daily" / "betaline"
    daily.mkdir(parents=True)
    (daily / "2026-05-01.md").write_text("# Daily Log [betaline]: 2026-05-01\n\nSession outcome.\n")

    routes_path = tmp_path / "projects.json"
    routes_path.write_text(json.dumps({
        "routes": [{"slug": "betaline", "cwd_prefixes": ["/work/betaline"]}],
        "fallback_slug": "_global",
    }))

    monkeypatch.setattr(ss, "VAULT_WIKI", wiki)
    monkeypatch.setattr(ss, "VAULT_PROJECTS", wiki / "projects")
    monkeypatch.setattr(ss, "DAILY_DIR", tmp_path / "daily")
    monkeypatch.setattr(ss, "PROJECTS_JSON", routes_path)
    monkeypatch.setattr(ss, "ROOT_CLAUDE_MD", tmp_path / "CLAUDE.md.absent")
    monkeypatch.setattr(ss, "GLOBAL_MEMORY_INDEX", tmp_path / "MEMORY.md.absent")
    return tmp_path


def test_loads_project_leaf_when_cwd_in_project(fake_vault):
    ctx = ss.build_context(cwd="/work/betaline/src/api.py")
    assert "BetaLine" in ctx
    assert "Use Postgres, not SQLite" in ctx
    assert "How to scale webhooks?" in ctx
    assert "Decided to migrate to Next.js" in ctx
    assert "Session outcome." in ctx


def test_does_not_leak_other_projects(fake_vault, tmp_path):
    other = tmp_path / "vault" / "wiki" / "projects" / "ebay"
    other.mkdir(parents=True)
    (other / "index.md").write_text("# eBay\nSecret stuff\n")

    ctx = ss.build_context(cwd="/work/betaline/src/api.py")
    assert "Secret stuff" not in ctx
    assert "eBay" not in ctx


def test_global_fallback_for_unknown_cwd(fake_vault):
    ctx = ss.build_context(cwd="/var/log/system.log")
    assert "Wiki Index" in ctx


def test_emits_valid_hook_json(fake_vault, capsys):
    ss.emit_hook_output(cwd="/work/betaline/x.py")
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "BetaLine" in payload["hookSpecificOutput"]["additionalContext"]
