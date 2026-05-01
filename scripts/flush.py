"""
Memory flush agent v2 — per-project stenography.

Spawned by session-end.py as a background process. Reads pre-extracted
conversation context, runs deterministic pre-filter, then (if it passes) calls
Haiku 4.5 to extract a structured summary, and appends it to
daily/<slug>/<date>.md.

Usage:
    uv run python flush.py <context_file.md> <session_id> <cwd>
"""

from __future__ import annotations

import os
os.environ["CLAUDE_INVOKED_BY"] = "memory_flush"

import asyncio
import json
import logging
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT / "daily"
SCRIPTS_DIR = ROOT / "scripts"
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
STATE_FILE = SCRIPTS_DIR / "last-flush.json"
LOG_FILE = LOGS_DIR / "flush.log"
PROJECTS_JSON = ROOT / "projects.json"

# Ensure ROOT is on sys.path so `from scripts.X import ...` works when this
# file is invoked as `python scripts/flush.py` (which puts scripts/ on path,
# not ROOT). Without this, imports below fail with ModuleNotFoundError.
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Local imports (after logging configured so import errors surface to log)
from scripts.slug_router import resolve_slug
from scripts.pre_filter import should_flush, FilterReason

FLUSH_MODEL = "claude-haiku-4-5-20251001"
CHAR_THRESHOLD = 1000
FLUSH_TIMEOUT_SEC = 60  # hard wall-clock cap on the Haiku SDK call


def load_flush_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_flush_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def append_to_daily_log_for_slug(
    slug: str,
    content: str,
    section: str = "Session",
    date_iso: str | None = None,
) -> Path:
    """Append content to daily/<slug>/<date>.md, creating skeleton if missing."""
    if date_iso is None:
        date_iso = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")

    log_dir = DAILY_DIR / slug
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{date_iso}.md"

    if not log_path.exists():
        log_path.write_text(
            f"# Daily Log [{slug}]: {date_iso}\n\n## Sessions\n\n",
            encoding="utf-8",
        )

    time_str = datetime.now(timezone.utc).astimezone().strftime("%H:%M")
    entry = f"### {section} ({time_str})\n\n{content}\n\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)

    return log_path


async def run_flush_haiku(context: str) -> str:
    """Use Haiku 4.5 via Agent SDK to extract structured summary."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    prompt = f"""Сожми разговор ниже в структурированную выжимку 200-400 слов.

Формат (только секции с реальным содержанием):

**Контекст:** [одна строка о чём сессия]

**Решения:** [принятые решения с why]

**Препятствия:** [возникшие проблемы и обходы]

**Open вопросы:** [нерешённое, на чём остановились]

**Action items:** [что сделать дальше]

Пропусти: рутинные tool calls, тривиальные обмены, обсуждения форматирования.

Если в сессии нет ничего ценного — ответь ровно: FLUSH_OK

## Разговор

{context}"""

    response = ""

    async def _consume() -> None:
        nonlocal response
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                cwd=str(ROOT),
                model=FLUSH_MODEL,
                allowed_tools=[],
                max_turns=2,
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response += block.text
            elif isinstance(message, ResultMessage):
                pass

    try:
        await asyncio.wait_for(_consume(), timeout=FLUSH_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        logging.error("Agent SDK timeout after %ds", FLUSH_TIMEOUT_SEC)
        response = f"FLUSH_ERROR: TimeoutError: SDK exceeded {FLUSH_TIMEOUT_SEC}s"
    except Exception as e:
        logging.error("Agent SDK error: %s\n%s", e, traceback.format_exc())
        response = f"FLUSH_ERROR: {type(e).__name__}: {e}"

    return response


def main() -> None:
    if len(sys.argv) < 4:
        logging.error("Usage: %s <context_file.md> <session_id> <cwd>", sys.argv[0])
        sys.exit(1)

    context_file = Path(sys.argv[1])
    session_id = sys.argv[2]
    cwd = sys.argv[3]

    slug = resolve_slug(cwd, PROJECTS_JSON)
    logging.info("flush.py started: session=%s cwd=%s slug=%s", session_id, cwd, slug)

    if not context_file.exists():
        logging.error("Context file not found: %s", context_file)
        return

    # Dedupe: same session within 60s
    state = load_flush_state()
    if (
        state.get("session_id") == session_id
        and time.time() - state.get("timestamp", 0) < 60
    ):
        logging.info("Skipping duplicate flush for session %s", session_id)
        context_file.unlink(missing_ok=True)
        return

    context = context_file.read_text(encoding="utf-8").strip()

    # Pre-filter (no LLM cost)
    decision = should_flush(context, char_threshold=CHAR_THRESHOLD)
    if not decision.proceed:
        logging.info("Pre-filter SKIP: reason=%s slug=%s chars=%d", decision.reason.value, slug, len(context))
        context_file.unlink(missing_ok=True)
        save_flush_state({"session_id": session_id, "timestamp": time.time()})
        return

    logging.info("Flushing: slug=%s session=%s chars=%d model=%s", slug, session_id, len(context), FLUSH_MODEL)

    response = asyncio.run(run_flush_haiku(context))

    if "FLUSH_OK" in response:
        logging.info("Result FLUSH_OK: slug=%s — nothing worth saving", slug)
    elif "FLUSH_ERROR" in response:
        logging.error("Result %s: slug=%s", response, slug)
        append_to_daily_log_for_slug(slug, response, section="Memory Flush Error")
    else:
        log_path = append_to_daily_log_for_slug(slug, response, section="Session")
        logging.info("Result saved: slug=%s path=%s len=%d", slug, log_path, len(response))

    save_flush_state({"session_id": session_id, "timestamp": time.time()})
    context_file.unlink(missing_ok=True)
    logging.info("Flush complete: slug=%s session=%s", slug, session_id)


if __name__ == "__main__":
    main()
