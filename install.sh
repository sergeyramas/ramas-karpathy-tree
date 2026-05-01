#!/usr/bin/env bash
# Ramas-Karpathy-Tree — быстрая установка для Mac
# Полное руководство по настройке — в README.md.
set -euo pipefail

INSTALL_DIR="$HOME/.claude-memory-compiler"
SETTINGS="$HOME/.claude/settings.json"

echo "==> Устанавливаем Ramas-Karpathy-Tree в $INSTALL_DIR"

# 1. Копируем файлы
cp -r "$(dirname "$0")" "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 2. Копируем шаблон projects.json если ещё не существует
if [ ! -f "projects.json" ]; then
  cp projects.json.example projects.json
  echo "  Создан projects.json из шаблона — отредактируйте его, добавив маппинг cwd → slug."
fi

# 3. Создаём нужные директории
mkdir -p daily logs knowledge/concepts knowledge/connections knowledge/qa reports

# 4. Синхронизируем зависимости через uv
if command -v uv &>/dev/null; then
  uv sync
else
  echo "  uv не найден. Установите командой: curl -fsSL https://astral.sh/uv/install.sh | sh"
  exit 1
fi

# 5. Напоминаем о регистрации hooks
echo ""
echo "==> Следующие шаги:"
echo "  1. Отредактируйте $INSTALL_DIR/projects.json — добавьте ваши проекты и cwd пути."
echo "  2. Укажите VAULT_DIR в окружении (или отредактируйте hooks/session-start.py):"
echo "       export VAULT_DIR=\"\$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/YourVault\""
echo "  3. Зарегистрируйте hooks в $SETTINGS — см. README.md 'Шаг 4: Регистрируем hooks'."
echo "  4. Запустите тесты: cd $INSTALL_DIR && uv run pytest tests/ -v"
echo ""
echo "Готово."
