#!/usr/bin/env bash
# Установка бота как службы systemd: работает 24/7, стартует после перезагрузки.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

# 1) виртуальное окружение и зависимости
if [ ! -x "$DIR/venv/bin/python" ]; then
  python3 -m venv "$DIR/venv"
fi
"$DIR/venv/bin/pip" install -q -r "$DIR/requirements.txt"

# 2) проверка входа: сессия должна уже существовать
if [ ! -f "$DIR/cleaner.session" ]; then
  echo "Сначала войдите один раз вручную:"
  echo "  $DIR/venv/bin/python $DIR/cleaner.py --login qr"
  echo "После успешного входа запустите install_service.sh снова."
  exit 1
fi

# 3) ставим unit systemd
sed "s#__DIR__#$DIR#g" "$DIR/tg-cleaner.service" | sudo tee /etc/systemd/system/tg-cleaner.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now tg-cleaner.service
echo
echo "Готово. Бот работает 24/7."
echo "  статус:   sudo systemctl status tg-cleaner"
echo "  логи:     journalctl -u tg-cleaner -f"
echo "  стоп:     sudo systemctl stop tg-cleaner"
echo "  убрать:   sudo systemctl disable --now tg-cleaner"
