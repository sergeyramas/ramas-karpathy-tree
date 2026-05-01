# Ramas-Karpathy-Tree

**cwd-aware слой памяти для Claude Code, основанный на паттерне Karpathy LLM Wiki.**

Версия `v2-foundation-2026-05-01` — 18/18 тестов проходят.

---

## Проблема

У Claude Code нет постоянной памяти между сессиями. Стандартный обходной путь — `CLAUDE.md` + ежедневный flush в плоскую базу знаний — работает нормально для одного проекта. Но ломается, когда проектов несколько:

- Каждая сессия загружает контекст из всех проектов, тратя токены на то, что сейчас неважно.
- Решения по рефакторингу из `work-api` загрязняют контекст, когда вы отлаживаете `sideproject`.
- Качество flush деградирует: LLM должен угадывать, какие факты к какой кодовой базе относятся.
- Стоимость растёт пропорционально общему числу проектов, а не текущему.

---

## Решение: Дерево, а не плоский файл

```
КОРНИ (архив)      wiki/_archive/   — старые знания, вне активного контекста
СТВОЛ (всегда)     ~/CLAUDE.md + Karpathy_Guidelines + global MEMORY.md + wiki/index.md
ВЕТКИ (по запросу) entities/ ideas/ references/ — загружаются при обращении
ЛИСТИКИ (cwd)      wiki/projects/<slug>/{index,MEMORY,decisions,journal/}
HOT-STATE (в репо) <project>/AGENT_ACTIVITY.md
```

Каждая сессия загружает только листик для проекта, в директории которого она стартует. Остальные проекты молчат.

---

## Оригинальный паттерн Карпати vs Ramas-Karpathy-Tree

| Параметр | Karpathy LLM Wiki | Ramas-Karpathy-Tree |
|----------|------------------|---------------------|
| Дневные логи | `daily/<date>.md` — один файл, все проекты | `daily/<slug>/<date>.md` — изолированы по проекту |
| Старт сессии | Загружает весь `knowledge/index.md` | Загружает только листик активного slug + ствол |
| Изоляция проектов | Нет — все знания в одном пуле | Строгая: slug routing исключает межпроектные утечки |
| Pre-filter | Нет — каждая сессия стоит денег | Детерминированный Python-пропуск: пустые / короткие / только bash → $0 |
| Модель flush | Настраивается | Haiku 4.5 (~$0.005/flush) — достаточно дёшево для каждой сессии |
| Структура памяти | Один плоский `MEMORY.md` | Двухуровневая: глобальная (≤20 строк) + per-project (≤30 строк), cwd-маршрутизация |
| Компиляция | `compile.py` запускается ночью (Sonnet) | Foundation выходит без compile; Plan B добавит его в следующей итерации |
| Покрытие тестами | Не указано | 18 юнит-тестов, TDD с первого дня |

---

## Архитектура

```
~/.claude-memory-compiler/
  projects.json            # таблица маршрутизации cwd → slug (редактируете вы)
  scripts/
    slug_router.py         # чистый Python, longest-prefix match, без зависимостей
    pre_filter.py          # детерминированная логика пропуска тривиальных сессий
    flush.py               # запись дневного лога по slug + Haiku 4.5
    config.py              # пути, модели, переопределения через env vars
    utils.py               # общие вспомогательные функции
  hooks/
    session-start.py       # cwd-aware: собирает контекст из ствола + активного листика
    session-end.py         # передаёт cwd в flush.py (фоновый процесс)
    pre-compact.py         # срабатывает перед авто-компакцией — сохраняет то, что иначе потеряется
  daily/
    <slug>/
      <date>.md            # стенография сессий по проекту
  knowledge/
    index.md               # мастер-каталог (Plan B: обновляется автоматически через compile.py)
  tests/
    test_slug_router.py
    test_pre_filter.py
    test_session_start.py
    test_flush_paths.py
    fixtures/
```

### Поток данных

```
Сессия стартует
  └─> session-start.py читает cwd
      └─> slug_router.py: cwd → "myapp"
          └─> загружает ствол + wiki/projects/myapp/* только
              └─> инжектирует ~3-5k токенов релевантного контекста

Сессия завершается
  └─> session-end.py извлекает транскрипт → context file
      └─> pre_filter.py: пропустить если пусто / <1k символов / только bash
          └─> запускает flush.py (фон, неблокирующий)
              └─> Haiku 4.5: извлекает структурированную выжимку
                  └─> дописывает в daily/myapp/<date>.md
```

---

## Стоимость

Для активного разработчика с 4 проектами, ~3-5 сессий в день:

| Компонент | Стоимость |
|-----------|-----------|
| Session flush (Haiku 4.5) | ~$0.005/flush × 100/мес = ~$0.50 |
| Старт сессии — контекст (Sonnet 4.6) | ~$0.01/сессия × 150/мес = ~$1.50 |
| Экономия от pre-filter | ~40-60% flush-ов пропускается = ~$0.25 экономии |
| Plan B: ночная компиляция (Sonnet 4.6) | ~$0.10/компиляция × 30 = ~$3 |
| **Итого** | **~$5-15/мес** |

Без pre-filter и per-slug изоляции наивная полная загрузка контекста + flush на каждую сессию обходится в $30-80/мес при той же нагрузке.

---

## Быстрый старт (Mac)

**Требования:** Python 3.12+, [uv](https://astral.sh/uv), Claude Code 1.x, Obsidian vault (или любая директория для wiki).

### Шаг 1: Клонируем

```bash
git clone https://github.com/sergeyramas/ramas-karpathy-tree ~/.claude-memory-compiler
cd ~/.claude-memory-compiler
```

### Шаг 2: Устанавливаем зависимости

```bash
uv sync
```

### Шаг 3: Настраиваем

Копируем шаблон projects и редактируем:

```bash
cp projects.json.example projects.json
```

Редактируем `projects.json` — маппинг рабочих директорий на slug:

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

Указываем путь к vault (добавляем в `~/.zshrc` или `~/.bashrc`):

```bash
export VAULT_DIR="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/YourVault"
export UV_BIN="$HOME/.local/bin/uv"   # или: which uv
```

### Шаг 4: Регистрируем hooks

Добавляем в `~/.claude/settings.json`:

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

Заменяем `/Users/you` на ваш реальный домашний путь.

### Шаг 5: Запускаем тесты

```bash
uv run pytest tests/ -v
```

Все 18 тестов должны пройти. Затем запустите сессию Claude Code в одной из настроенных директорий и проверьте `daily/<slug>/` — там появится первый лог.

---

## Конфигурация

Все пути настраиваются через переменные окружения. Жёстко заданных пользовательских путей в коде нет.

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `VAULT_DIR` | `~/obsidian-vault` | Корень вашего Obsidian/wiki vault |
| `UV_BIN` | `~/.local/bin/uv` | Абсолютный путь к бинарнику uv |
| `CLAUDE_MD` | `~/CLAUDE.md` | Путь к файлу ствола CLAUDE.md |
| `MEMORY_MD` | `~/.claude/projects/memory/MEMORY.md` | Путь к глобальному MEMORY.md |

Для более глубокой настройки (модель flush, порог символов, часовой пояс) — редактируйте `scripts/config.py`.

---

## Роадмап

- [x] **Foundation** (этот релиз): cwd routing + pre-filter + per-slug flush + cwd-aware session-start + двухуровневый scaffold MEMORY
- [ ] **Plan B**: `compile.py` — ночной дайджест дневных логов в статьи `knowledge/` через Sonnet
- [ ] **Plan B**: `digest.py` — еженедельный кросс-проектный синтез
- [ ] **Plan B**: `cleanup.py` — архивирование старых дневных логов, удаление устаревших знаний
- [ ] **Plan B**: `launchd` cron для Mac (без crontab, выживает после sleep)
- [ ] Поддержка Windows (hooks тестировались только на Mac)
- [ ] Поддержка Linux

Plan B будет разрабатываться после ~1 недели работы Foundation в продакшене.

---

## Конфиденциальность

`projects.json` находится в `.gitignore` — в нём ваши реальные пути и названия проектов, которые вы, вероятно, не хотите публиковать. Вместо него в репо закоммичен шаблон `.json.example`.

Директории `daily/`, `knowledge/` и `logs/` тоже в gitignore — они содержат транскрипты ваших сессий и скомпилированные знания, которые являются личными данными.

---

## Лицензия

MIT

---

## Благодарности

Вдохновлён [паттерном LLM Wiki Андрея Карпати](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

Построен на [Anthropic Claude Agent SDK](https://docs.anthropic.com/en/api/overview) и [Claude Code hooks](https://docs.anthropic.com/en/docs/claude-code/hooks).

Стек: Python 3.12, uv, pytest, Haiku 4.5 (flush), Sonnet 4.6 (compile — Plan B).
