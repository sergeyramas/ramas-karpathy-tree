# Ramas-Karpathy-Tree

**A cwd-aware, per-project memory layer for Claude Code, built on top of Karpathy's LLM Wiki pattern.**

Version `v2-foundation-2026-05-01` — 18/18 tests passing.

---

## The Problem

Claude Code has no persistent memory across sessions. The common workaround — a `CLAUDE.md` + daily session flush into a flat knowledge base — works fine for one project. It breaks when you have several:

- Every session loads context from all projects, burning tokens on things that don't matter right now.
- A refactoring decision from `work-api` contaminates the context when you're debugging `sideproject`.
- Flush quality degrades because the LLM must pattern-match which facts belong to which codebase.
- Cost scales with the total number of projects, not the current one.

---

## The Solution: A Tree, Not a Flat File

```
ROOTS (archive)     wiki/_archive/   — old knowledge, out of active context
TRUNK (always on)   ~/CLAUDE.md + Karpathy_Guidelines + global MEMORY.md + wiki/index.md
BRANCHES (on demand) entities/ ideas/ references/ — loaded when referenced
LEAVES (cwd-routed) wiki/projects/<slug>/{index,MEMORY,decisions,journal/}
HOT-STATE (in repo) <project>/AGENT_ACTIVITY.md
```

Each session loads only the leaf for the project whose directory it starts in. Other projects are silent.

---

## Karpathy Original vs Ramas-Karpathy-Tree

| Dimension | Karpathy LLM Wiki | Ramas-Karpathy-Tree |
|-----------|------------------|---------------------|
| Daily logs | `daily/<date>.md` — one file, all projects | `daily/<slug>/<date>.md` — isolated per project |
| Session start | Loads full `knowledge/index.md` | Loads only the active slug's leaf + trunk |
| Project isolation | None — all knowledge in one pool | Strict: slug routing prevents cross-project leaks |
| Pre-filter | None — every session costs money | Deterministic Python skip: empty / too-short / bash-only sessions → $0 |
| Flush model | Configurable | Haiku 4.5 (~$0.005/flush) — cheap enough to run every session |
| Memory structure | One flat `MEMORY.md` | Two-tier: global (≤20 lines) + per-project (≤30 lines), cwd-routed |
| Compile step | `compile.py` runs nightly (Sonnet) | Foundation ships without compile; Plan B adds it in a future iteration |
| Test coverage | Not specified | 18 unit tests, TDD from day 1 |

---

## Architecture

```
~/.claude-memory-compiler/
  projects.json            # cwd → slug routing table (YOU edit this)
  scripts/
    slug_router.py         # pure Python, longest-prefix match, no deps
    pre_filter.py          # deterministic skip-trivial logic
    flush.py               # per-slug daily log writer + Haiku 4.5
    config.py              # paths, models, env var overrides
    utils.py               # shared helpers
  hooks/
    session-start.py       # cwd-aware: builds context from trunk + active leaf only
    session-end.py         # passes cwd to flush.py (background process)
    pre-compact.py         # fires before auto-compaction — saves what would be lost
  daily/
    <slug>/
      <date>.md            # per-project session stenography
  knowledge/
    index.md               # master catalog (Plan B: auto-updated by compile.py)
  tests/
    test_slug_router.py
    test_pre_filter.py
    test_session_start.py
    test_flush_paths.py
    fixtures/
```

### Data Flow

```
Session starts
  └─> session-start.py reads cwd
      └─> slug_router.py: cwd → "myapp"
          └─> loads trunk + wiki/projects/myapp/* only
              └─> injects ~3-5k tokens of relevant context

Session ends
  └─> session-end.py extracts transcript → context file
      └─> pre_filter.py: skip if empty / <1k chars / bash-only
          └─> spawns flush.py (background, non-blocking)
              └─> Haiku 4.5: extract structured summary
                  └─> appends to daily/myapp/<date>.md
```

---

## Cost

For an active developer working 4 projects, ~3-5 sessions/day:

| Component | Cost |
|-----------|------|
| Session flush (Haiku 4.5) | ~$0.005/flush × 100/month = ~$0.50 |
| Session start context (Sonnet 4.6) | ~$0.01/session × 150/month = ~$1.50 |
| Pre-filter savings | ~40-60% of flushes skipped = ~$0.25 saved |
| Plan B: nightly compile (Sonnet 4.6) | ~$0.10/compile × 30 = ~$3 |
| **Total** | **~$5-15/month** |

Without the pre-filter and per-slug isolation, a naive full-context load + flush per session runs $30-80/month for the same workload.

---

## Quick Start (Mac)

**Requirements:** Python 3.12+, [uv](https://astral.sh/uv), Claude Code 1.x, an Obsidian vault (or any directory you want to use as your wiki).

### Step 1: Clone

```bash
git clone https://github.com/sergeyramas/ramas-karpathy-tree ~/.claude-memory-compiler
cd ~/.claude-memory-compiler
```

### Step 2: Install dependencies

```bash
uv sync
```

### Step 3: Configure

Copy the projects template and edit it:

```bash
cp projects.json.example projects.json
```

Edit `projects.json` to map your working directories to slugs:

```json
{
  "routes": [
    {
      "slug": "myapp",
      "cwd_prefixes": ["/Users/you/code/myapp"]
    }
  ],
  "fallback_slug": "_global"
}
```

Set your vault path (add to `~/.zshrc` or `~/.bashrc`):

```bash
export VAULT_DIR="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/YourVault"
export UV_BIN="$HOME/.local/bin/uv"   # or: which uv
```

### Step 4: Register hooks

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/you/.local/bin/uv run --directory /Users/you/.claude-memory-compiler python /Users/you/.claude-memory-compiler/hooks/session-start.py"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/you/.local/bin/uv run --directory /Users/you/.claude-memory-compiler python /Users/you/.claude-memory-compiler/hooks/session-end.py"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/you/.local/bin/uv run --directory /Users/you/.claude-memory-compiler python /Users/you/.claude-memory-compiler/hooks/pre-compact.py"
          }
        ]
      }
    ]
  }
}
```

Replace `/Users/you` with your actual home directory path.

### Step 5: Run tests

```bash
uv run pytest tests/ -v
```

All 18 tests should pass. Then start a Claude Code session in one of your configured project directories and check `daily/<slug>/` for your first log entry.

---

## Configuration

All paths are configurable via environment variables. No hardcoded user paths in the core code.

| Variable | Default | Description |
|----------|---------|-------------|
| `VAULT_DIR` | `~/obsidian-vault` | Root of your Obsidian/wiki vault |
| `UV_BIN` | `~/.local/bin/uv` | Absolute path to uv binary |
| `CLAUDE_MD` | `~/CLAUDE.md` | Path to your trunk CLAUDE.md file |
| `MEMORY_MD` | `~/.claude/projects/memory/MEMORY.md` | Path to global MEMORY.md |

Edit `scripts/config.py` for deeper customization (flush model, char threshold, timezone).

---

## Roadmap

- [x] **Foundation** (this release): cwd routing + pre-filter + per-slug flush + cwd-aware session-start + two-tier MEMORY scaffold
- [ ] **Plan B**: `compile.py` — nightly Sonnet digest of daily logs into `knowledge/` articles
- [ ] **Plan B**: `digest.py` — weekly cross-project synthesis
- [ ] **Plan B**: `cleanup.py` — archive old daily logs, prune stale knowledge
- [ ] **Plan B**: `launchd` cron setup for Mac (no-crontab, survives sleep)
- [ ] Windows support (hooks tested on Mac only)
- [ ] Linux support

Plan B will be developed once the foundation has run in production for ~1 week.

---

## Notes on Privacy

`projects.json` is in `.gitignore` — it contains your real directory paths and project names, which you probably don't want public. The `.json.example` template is committed instead.

The `daily/`, `knowledge/`, and `logs/` directories are also gitignored — these contain your session transcripts and compiled knowledge, which is personal.

---

## License

MIT

---

## Credits

Inspired by [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

Built on [Anthropic's Claude Agent SDK](https://docs.anthropic.com/en/api/overview) and [Claude Code hooks](https://docs.anthropic.com/en/docs/claude-code/hooks).

Stack: Python 3.12, uv, pytest, Haiku 4.5 (flush), Sonnet 4.6 (compile — Plan B).
