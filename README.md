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

## Как было vs Как стало

Это самая важная часть документа. Без понимания проблемы не ясно, зачем вообще нужен апдейт.

---

### 1. Что такое Karpathy original (для тех, кто не знает)

Андрей Карпати [описал паттерн «LLM Wiki»](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — три слоя: raw sources → wiki → schema. В Claude Code это выглядит как:

- `SessionEnd` хук пишет flush в `daily/<date>.md` — **плоско**, все проекты в одном файле
- ночной cron (`compile.py`) читает daily, обновляет `knowledge/index.md`
- `SessionStart` хук грузит `knowledge/index.md` + последний daily в **каждую** новую сессию

Идея блестящая. Но в наивной реализации:

- **20+ тыс. токенов на старт каждой сессии** — index растёт линейно, грузится весь
- **Контекст всех проектов вперемешку** — открыл чат для betaline, видишь обсуждения ebay, fundament21, архивные мысли
- **Нет лимита на стоимость** — flush гонит Sonnet каждый раз, даже если ты сделал `ls && pwd`
- **Если flush падает — тишина** — `daily/` пустой, ты не знаешь что сломано

---

### 2. Реальная картина «до» в моём случае

Я (Сергей) поставил Karpathy compiler 21 апреля 2026. До 1 мая он **молча не работал ни одного дня**.

`uv` не был установлен на системе. Хук пытался спавнить `flush.py` через `uv run`, получал `FileNotFoundError`, тихо логировал ошибку и выходил. `daily/` оставался пустым. Я думал «работает в фоне».

Параллельно я вёл Jarvis-vault руками в Obsidian (отдельная система с проектами, конспектами, Karpathy_Guidelines). Между Karpathy compiler и Jarvis vault не было никакой связи. **Двойная база**, оба источника рассинхронизированы.

**Симптомы которые я ощущал:**

- Возвращаешься к работе через 3 часа — пересказываешь Claude задачу с нуля
- Открываешь чат в `betaline/` — модель «помнит» обрывки про `ebay` (контекст из других проектов просочился через CLAUDE.md или ручные вставки)
- Не понимаешь сколько денег уходит на flush — он ведь должен крутиться в фоне после каждой сессии
- Дайджеста за день нет — что было вчера? нужно смотреть git-историю или искать в Obsidian руками

> **Warning:** Если твой `daily/` пустой после нескольких дней работы — проверь `logs/flush.log`. Вероятно, `uv` недоступен по PATH в хуке. Хуки работают со stripped PATH; наивная установка именно на этом и ломается.

---

### 3. Что починил апдейт «Дерево Рамас-Карпати»

**Метафора дерева** — главная идея. Память не куча, а структура с уровнями релевантности:

```
КОРНИ — глубокий архив
  wiki/_archive/                    cold storage, не в контексте никогда
  Pinecone (когда страниц > 500)    отложено на Plan B+
  доступ:                           только через явный /wiki-query

СТВОЛ — всегда в контексте, ~1500 токенов
  ~/CLAUDE.md                              ~500 токенов
  Karpathy_Guidelines.md (компактная)      ~300 токенов
  global MEMORY.md (≤ 20 строк)            ~150 токенов
  wiki/index.md (только заголовки)         ~400 токенов

ВЕТКИ — по запросу, не на старте
  wiki/entities/                     каталог инструментов/людей/сервисов
  wiki/ideas/, wiki/references/      хабы
  wiki/synthesis/                    cross-project синтез

ЛИСТИКИ — грузится ОДИН по cwd
  wiki/projects/<slug>/
    ├── index.md             карточка проекта    (~600 токенов)
    ├── MEMORY.md            preferences         (~500)
    ├── decisions.md         лог решений с why
    ├── lessons.md           грабли и обходы
    ├── open-questions.md    что висит
    └── journal/<вчера>.md   детальный лог дня   (~800)

HOT-STATE — в самом репо проекта
  <project>/AGENT_ACTIVITY.md       семафор multi-agent
```

Когда ты открываешь Claude Code в `~/Documents/betaline/`, **только** ствол + листик `betaline/` грузятся в контекст. `ebay/`, `fundament21/`, `karpathy-vault/` — невидимы.

---

### 4. Как именно это работает технически

**На закрытии сессии (SessionEnd hook):**

1. Хук получает `cwd` из stdin (Claude Code сам передаёт через JSON)
2. Извлекает последние ~30 turns транскрипта в markdown-формат
3. Спавнит детач-процесс `flush.py` через **абсолютный путь** `~/.local/bin/uv` — потому что хуки работают со stripped PATH. Это была основная поломка в наивной установке.
4. `flush.py` определяет slug по cwd через `projects.json` (longest-prefix match)
5. **Pre-filter без LLM** — если контекст < 1000 символов или только bash-команды → пропуск, $0
6. Иначе — Haiku 4.5 (60-секундный timeout) сжимает в структурированную выжимку 200-400 слов: контекст / решения / препятствия / open-вопросы / action items
7. Append к `daily/<slug>/<date>.md`

```
daily/
  betaline/
    2026-05-01.md    <- только betaline, только этот день
  ebay/
    2026-05-01.md    <- изолировано
  _global/
    2026-05-01.md    <- если открыт чат вне проектной директории
```

**На старте сессии (SessionStart hook):**

1. Хук читает `cwd` из stdin
2. Резолвит slug через `projects.json`
3. Собирает контекст: ствол (CLAUDE.md + global MEMORY + wiki index headers) + **только** листик активного проекта (index, MEMORY, open-questions, последние 3 journal-файла) + сегодняшний/вчерашний daily log этого slug + AGENT_ACTIVITY.md из репо если есть
4. Жёсткий cap **18 000 символов (~5000 токенов)** — trunk сначала, потом truncate листика
5. Возвращает JSON хуку, Claude Code инжектит как `additionalContext`

---

### 5. Конкретные метрики до/после

| Параметр | Karpathy original (наивный) | Дерево Рамас-Карпати |
|---|---|---|
| Токенов в SessionStart контексте | 15–25k (всё подряд) | 3–5k (только активный листик) |
| Утечка проектов | Все видны всегда | Изолированы по cwd |
| Цена за flush средней сессии | $0.05–0.15 (Sonnet, без фильтра) | $0.005–0.01 (Haiku, после pre-filter) |
| Цена за тривиальную сессию (`ls` + `pwd`) | $0.05+ (всё равно гонит LLM) | $0 (детерминистский pre-filter режет) |
| Стоимость в месяц при 4 проектах × 10 сессий/день | $60–150 | $15–30 (с Plan B) |
| Загрузка нового чата | Все индексы + всё daily | Только trunk + 1 leaf |
| Видимость поломок | Тишина, daily пустой | Структурный лог в `logs/flush.log`, статусы `FLUSH_OK` / `FLUSH_ERROR` |
| Память про вчерашний день | Нужно угадывать или искать руками | Daily log активного проекта автоматически в SessionStart |
| Fault tolerance flush'а | Один failure mode (silent exit) | Timeout + sanitize + cleanup + structured logs |

---

### 6. Сценарии повседневного использования

**Сценарий А: «вернулся через 3 часа в проект»**

- *Раньше:* открываешь чат в betaline, спрашиваешь «на чём остановились?» — модель не знает, либо рассказывает что-то про ebay из общего контекста. Пересказываешь сам.
- *Сейчас:* открываешь чат, модель читает `daily/betaline/<сегодня>.md` + `journal/<вчера>.md` + `open-questions.md` betaline'а — отвечает «вчера остановились на webhook scaling, висят вопросы X, Y; в open-questions ещё Z». Без пересказа.

**Сценарий B: «запустил два разных проекта параллельно»**

- *Раньше:* в каждом чате весь контекст обоих проектов смешан, модель путается, иногда даёт совет из чужой архитектуры.
- *Сейчас:* физически невозможно — `_project_leaf("ebay")` не читает `wiki/projects/betaline/`. Тестом покрыто: `test_does_not_leak_other_projects`.

**Сценарий C: «открыл Claude в случайной папке `~/Downloads`»**

- *Раньше:* грузится весь knowledge index, ~20k токенов, контекст забит ничего не значащей информацией.
- *Сейчас:* slug = `_global`, грузится только trunk (CLAUDE.md, Karpathy_Guidelines, wiki/index.md headers) — ~1500 токенов. Чисто.

**Сценарий D: «сделал в чате `ls && cat README.md`»**

- *Раньше:* SessionEnd триггерит flush, Sonnet тратит ~$0.05 чтобы «выжать» «пользователь посмотрел README».
- *Сейчас:* pre-filter определяет `TRIVIAL_OPS` → `return False`, $0 потрачено, daily log не загрязняется бесполезным.

---

### 7. Что ещё впереди (Plan B)

Сейчас зафиксирован **foundation**: стенография в `daily/<slug>/`. Plan B — ночной compile (Sonnet 4.6) который читает daily и обновляет project leaves (`journal/`, `decisions.md`, `lessons.md`, `MEMORY.md`), плюс утренний digest.

**Foundation работает, но Plan B compile.py ещё не сделан — daily logs пока накапливаются как сырьё.** Запустится после 1-2 недель работы foundation в проде — нужно сначала убедиться что pipeline не падает и логи имеют нужную структуру.

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
