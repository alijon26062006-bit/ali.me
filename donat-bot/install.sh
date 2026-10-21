#!/usr/bin/env bash
# One-command installer for the donat bot (Ubuntu / Debian).
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/ali.me/claude/quirky-cannon-jv0k4o/donat-bot/install.sh | sudo bash -s -- <BOT_TOKEN> [ADMIN_ID] [DOMAIN]
# Without arguments it asks for the bot token and admin ID, installs everything and starts the bot as a service.
# With a domain it serves the Mini App over HTTPS via Caddy; without one it uses a free
# temporary Cloudflare tunnel (the https address changes after every restart — fine for testing).
set -euo pipefail

REPO="https://github.com/alijon26062006-bit/ali.me.git"
BRANCH="claude/quirky-cannon-jv0k4o"
SRC="/opt/donat-src"
APP="/opt/donat-src/donat-bot"
SERVICE="donat-bot"

say() { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }
ask() { local v; read -r -p "$1" v </dev/tty; v=${v//$'\r'/}; v=${v//[[:space:]]/}; printf '%s' "$v"; }
ask_secret() { local v; read -r -s -p "$1" v </dev/tty; echo >/dev/tty; v=${v//$'\r'/}; v=${v//[[:space:]]/}; printf '%s' "$v"; }

[ "$(id -u)" -eq 0 ] || { echo "Run as root: ... | sudo bash"; exit 1; }

say "Танзимот / Настройки"
# Non-interactive: ... | sudo bash -s -- <BOT_TOKEN> [ADMIN_ID] [DOMAIN]
BOT_TOKEN=${1:-${BOT_TOKEN:-}}
ADMIN_IDS=${2:-${ADMIN_IDS:-}}
DOMAIN=${3:-${DOMAIN:-}}
BOT_TOKEN=${BOT_TOKEN//[[:space:]]/}
EXISTING_TOKEN=""
[ -f "$APP/.env" ] && EXISTING_TOKEN=$(grep -E '^BOT_TOKEN=' "$APP/.env" | cut -d= -f2- || true)
if [ -z "$BOT_TOKEN" ] && [ -n "$EXISTING_TOKEN" ]; then  # update: keep saved token and settings
  BOT_TOKEN=$EXISTING_TOKEN
  ADMIN_IDS=${ADMIN_IDS:-$(grep -E '^ADMIN_IDS=' "$APP/.env" | cut -d= -f2- || true)}
  DOMAIN=${DOMAIN:-$(grep -E '^WEBAPP_URL=https://' "$APP/.env" | sed 's#^WEBAPP_URL=https://##' || true)}
fi
if [ -z "$BOT_TOKEN" ]; then  # interactive fallback
  while [ -z "$BOT_TOKEN" ]; do
    BOT_TOKEN=$(ask_secret "Токени бот (аз @BotFather)${EXISTING_TOKEN:+ [Enter = кӯҳна]}: ")
    [ -z "$BOT_TOKEN" ] && BOT_TOKEN=$EXISTING_TOKEN
    [[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]] || { echo "Токен нодуруст / Неверный токен"; BOT_TOKEN=""; }
  done
  ADMIN_IDS=$(ask "Telegram ID-и админ (ё Enter): ")
  DOMAIN=$(ask "Домен ё Enter барои тест: ")
fi
[[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]] || { echo "❌ Токен нодуруст / Неверный токен"; exit 1; }
echo "✅ Токен қабул шуд / Токен принят"

say "Насби барномаҳо / Установка пакетов"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git curl ca-certificates iproute2

say "Боргирии код / Загрузка кода"
if [ -d "$SRC/.git" ]; then
  git -C "$SRC" fetch --depth 1 origin "$BRANCH"
  git -C "$SRC" reset --hard FETCH_HEAD
else
  git clone --depth 1 --branch "$BRANCH" "$REPO" "$SRC"
fi

python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install --upgrade pip -q
"$APP/venv/bin/pip" install -r "$APP/requirements.txt" -q

say "Файли .env"
[ -f "$APP/.env" ] || cp "$APP/.env.example" "$APP/.env"
set_env() {  # set_env KEY VALUE
  if grep -qE "^$1=" "$APP/.env"; then
    python3 - "$APP/.env" "$1" "$2" <<'PY'
import sys
path, key, value = sys.argv[1:]
lines = open(path).read().splitlines()
lines = [f"{key}={value}" if l.startswith(key + "=") else l for l in lines]
open(path, "w").write("\n".join(lines) + "\n")
PY
  else
    echo "$1=$2" >> "$APP/.env"
  fi
}
set_env BOT_TOKEN "$BOT_TOKEN"
[ -n "$ADMIN_IDS" ] && set_env ADMIN_IDS "$ADMIN_IDS"
set_env WEB_HOST "127.0.0.1"
PORT=$(grep -E '^WEB_PORT=' "$APP/.env" | cut -d= -f2- || true)
systemctl stop "$SERVICE" 2>/dev/null || true
port_busy() { ss -ltnH "sport = :$1" 2>/dev/null | grep -q .; }
if [ -z "$PORT" ] || port_busy "$PORT"; then
  for p in $(seq 8080 8099); do port_busy "$p" || { PORT=$p; break; }; done
fi
set_env WEB_PORT "$PORT"
echo "Порт: $PORT"
chmod 600 "$APP/.env"

if [ -n "$DOMAIN" ]; then
  say "HTTPS бо Caddy барои $DOMAIN"
  set_env WEBAPP_URL "https://$DOMAIN"
  if ! command -v caddy >/dev/null; then
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https gnupg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -y && apt-get install -y caddy
  fi
  printf '%s {\n    reverse_proxy 127.0.0.1:%s\n}\n' "$DOMAIN" "$PORT" > /etc/caddy/Caddyfile
  systemctl restart caddy
  START_CMD="$APP/venv/bin/python $APP/run.py"
else
  say "Туннели муваққатии Cloudflare (бе домен)"
  set_env WEBAPP_URL ""
  if ! command -v cloudflared >/dev/null; then
    arch=$(dpkg --print-architecture)
    curl -fsSL -o /usr/local/bin/cloudflared "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$arch"
    chmod +x /usr/local/bin/cloudflared
  fi
  cat > "$APP/start-tunnel.sh" <<'SH'
#!/usr/bin/env bash
# Starts a quick Cloudflare tunnel, waits for its https URL, then runs the bot with WEBAPP_URL set.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$DIR/tunnel.log"
: > "$LOG"
PORT=$(grep -E '^WEB_PORT=' "$DIR/.env" | cut -d= -f2-)
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:${PORT:-8080}" >"$LOG" 2>&1 &
TUNNEL=$!
trap 'kill $TUNNEL 2>/dev/null' EXIT
URL=""
for _ in $(seq 1 60); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1)
  [ -n "$URL" ] && break
  sleep 1
done
[ -n "$URL" ] || { echo "Tunnel did not start"; cat "$LOG"; exit 1; }
echo "Mini App URL: $URL"
echo "$URL" > "$DIR/webapp_url.txt"
export WEBAPP_URL="$URL"
"$DIR/venv/bin/python" "$DIR/run.py"
SH
  chmod +x "$APP/start-tunnel.sh"
  START_CMD="$APP/start-tunnel.sh"
fi

say "Хизмати systemd / Сервис"
cat > /etc/systemd/system/$SERVICE.service <<UNIT
[Unit]
Description=Donat Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$APP
ExecStart=$START_CMD
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null
systemctl restart "$SERVICE"

sleep 8
if systemctl is-active --quiet "$SERVICE"; then
  say "ТАЙЁР! Бот кор мекунад / ГОТОВО! Бот работает"
  [ -f "$APP/webapp_url.txt" ] && [ -z "$DOMAIN" ] && echo "Mini App: $(cat "$APP/webapp_url.txt")"
  echo "Логҳо / Логи:        journalctl -u $SERVICE -f"
  echo "Аз нав / Перезапуск: systemctl restart $SERVICE"
  [ -z "$ADMIN_IDS" ] && echo "Админ: ба бот /id нависед ва ҳамин фармонро бо ID такрор кунед / напишите боту /id и повторите команду с ID"
  echo "Танзимот / Настройки: nano $APP/.env  (рақами кортҳо, дастгирӣ ва ғ.)"
  echo "Навсозӣ / Обновить:  такрор кардани ҳамин фармон / повторить эту же команду"
else
  say "Хато / Ошибка — логҳо:"
  journalctl -u "$SERVICE" -n 40 --no-pager
  exit 1
fi
