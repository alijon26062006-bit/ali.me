#!/usr/bin/env bash
# One-command installer for the donat bot (Ubuntu / Debian).
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/ali.me/claude/quirky-cannon-jv0k4o/donat-bot/install.sh | sudo bash -s -- <BOT_TOKEN> [DONATIX_KEY] [ADMIN_ID] [owner=NEW_OWNER_ID] [DOMAIN]
# Installs everything, starts the bot as a service and prints a one-time link: press START in it to become admin.
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
# Arguments in any order, recognised by their shape:
#   123456:ABC…   bot token        dx_live_…  Donatix API key
#   7418217143    admin ID         shop.tj    domain
#   owner=7418217143  new owner: full access, gets the Panel button
BOT_TOKEN=${BOT_TOKEN:-}; ADMIN_IDS=${ADMIN_IDS:-}; DOMAIN=${DOMAIN:-}; SUPPLIER_KEY=${SUPPLIER_KEY:-}; NEW_OWNER=""
for arg in "$@"; do
  arg=${arg//[[:space:]]/}
  if [[ "$arg" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]]; then BOT_TOKEN=$arg
  elif [[ "$arg" =~ ^dx_[A-Za-z0-9_]+$ ]]; then SUPPLIER_KEY=$arg
  elif [[ "$arg" =~ ^owner[=:]([0-9]{5,15})$ ]]; then NEW_OWNER=${BASH_REMATCH[1]}; ADMIN_IDS=${ADMIN_IDS:+$ADMIN_IDS,}$NEW_OWNER
  elif [[ "$arg" =~ ^[0-9]{5,15}$ ]]; then ADMIN_IDS=${ADMIN_IDS:+$ADMIN_IDS,}$arg
  elif [[ "$arg" =~ ^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then DOMAIN=$arg
  elif [ -n "$arg" ]; then echo "⚠️ Номаълум / Неизвестный аргумент: ${arg:0:12}…"
  fi
done
getenv() { [ -f "$APP/.env" ] && grep -E "^$1=" "$APP/.env" | cut -d= -f2- || true; }
# update: keep what is already saved on the server
BOT_TOKEN=${BOT_TOKEN:-$(getenv BOT_TOKEN)}
SUPPLIER_KEY=${SUPPLIER_KEY:-$(getenv SUPPLIER_API_KEY)}
DOMAIN=${DOMAIN:-$(getenv WEBAPP_URL | sed -n 's#^https://##p' | grep -v trycloudflare || true)}
if [ -z "$BOT_TOKEN" ]; then  # interactive fallback
  while [ -z "$BOT_TOKEN" ]; do
    BOT_TOKEN=$(ask_secret "Токени бот (аз @BotFather): ")
    [[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]] || { echo "Токен нодуруст / Неверный токен"; BOT_TOKEN=""; }
  done
fi
[[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]] || { echo "❌ Токен нодуруст / Неверный токен"; exit 1; }
echo "✅ Токен қабул шуд / Токен принят"
[ -n "$SUPPLIER_KEY" ] && echo "✅ Donatix API: ${SUPPLIER_KEY:0:8}…" || echo "ℹ️ Donatix API нест — иҷрои дастӣ / без API — ручная выдача"

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
[ "$(getenv SHOP_NAME)" = "ALI DONAT TJ" ] && set_env SHOP_NAME "NEMAT DONAT"  # old placeholder name
if [ -n "$ADMIN_IDS" ]; then  # add to the admins already saved, never replace them
  OLD_ADMINS=$(getenv ADMIN_IDS)
  MERGED=$(printf '%s,%s' "$OLD_ADMINS" "$ADMIN_IDS" | tr ',' '\n' | grep -E '^[0-9]+$' | awk '!seen[$0]++' | paste -sd, -)
  set_env ADMIN_IDS "$MERGED"
  echo "👥 Админҳо / Админы: $MERGED"
fi
if [ -n "$SUPPLIER_KEY" ]; then
  set_env SUPPLIER_API_KEY "$SUPPLIER_KEY"
  set_env SUPPLIER_API_URL "https://donatix.tj/api/v1"
fi
OWNER_CODE=$(getenv OWNER_CODE)
if [ -z "$OWNER_CODE" ]; then
  OWNER_CODE=$(python3 -c "import secrets; print(secrets.token_hex(8))")
  set_env OWNER_CODE "$OWNER_CODE"
fi
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
# Starts a quick Cloudflare tunnel, waits for its https URL, runs the bot with WEBAPP_URL set, and watches both:
# if the tunnel dies or its URL stops answering, everything exits and systemd restarts it with a fresh URL.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$DIR/tunnel.log"
: > "$LOG"
PORT=$(grep -E '^WEB_PORT=' "$DIR/.env" | cut -d= -f2-)
cloudflared tunnel --no-autoupdate --protocol http2 --url "http://127.0.0.1:${PORT:-8080}" >"$LOG" 2>&1 &
TUNNEL=$!
BOT=""
cleanup() { kill $TUNNEL $BOT 2>/dev/null; }  # systemd stops anything left in the service group
trap cleanup EXIT
URL=""
for _ in $(seq 1 60); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1)
  [ -n "$URL" ] && break
  kill -0 $TUNNEL 2>/dev/null || break
  sleep 1
done
[ -n "$URL" ] || { echo "Tunnel did not start"; cat "$LOG"; exit 1; }
echo "Mini App URL: $URL"
echo "$URL" > "$DIR/webapp_url.txt"
export WEBAPP_URL="$URL"
"$DIR/venv/bin/python" "$DIR/run.py" &
BOT=$!
sleep 30  # give the new hostname time to become reachable
FAILS=0
while kill -0 $TUNNEL 2>/dev/null && kill -0 $BOT 2>/dev/null; do
  if curl -fsS -m 15 -o /dev/null "$URL/"; then FAILS=0; else FAILS=$((FAILS + 1)); fi
  if [ "$FAILS" -ge 3 ]; then echo "Tunnel URL is not answering — restarting"; exit 1; fi
  sleep 60
done
echo "Tunnel or bot stopped — restarting"
exit 1
SH
  chmod +x "$APP/start-tunnel.sh"
  START_CMD="$APP/start-tunnel.sh"
fi

if [ -n "$ADMIN_IDS" ]; then  # also save them in the bot's database (what the Panel → 🛡 Админҳо list uses)
  python3 - "$APP/data.db" "$ADMIN_IDS" "$NEW_OWNER" <<'PY'
import sqlite3, sys
path, ids, owner = sys.argv[1:]
db = sqlite3.connect(path)
db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
def put(key, value):
    db.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, value))
row = db.execute("SELECT value FROM settings WHERE key='admin_ids'").fetchone()
saved = [x for x in (row[0] if row else "").split(",") if x.strip().isdigit()]
for x in ids.split(","):
    if x.isdigit() and x not in saved:
        saved.append(x)
put("admin_ids", ",".join(saved))
row = db.execute("SELECT value FROM settings WHERE key='removed_admins'").fetchone()
removed = [x for x in (row[0] if row else "").split(",") if x and x not in ids.split(",")]
put("removed_admins", ",".join(removed))
if owner:
    put("owner_claimed", owner)
    put("panel_kb_sent", "")  # resend the Panel button to every admin on start
db.commit()
print("👑 Соҳиб / Владелец:", owner) if owner else None
PY
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
if ! systemctl is-active --quiet "$SERVICE"; then
  say "Хато / Ошибка — логҳо:"
  journalctl -u "$SERVICE" -n 40 --no-pager
  exit 1
fi
say "ТАЙЁР! Бот кор мекунад / ГОТОВО! Бот работает"
[ -f "$APP/webapp_url.txt" ] && [ -z "$DOMAIN" ] && echo "Mini App: $(cat "$APP/webapp_url.txt")"

owner_claimed() {
  python3 - "$APP/data.db" <<'PY' 2>/dev/null
import sqlite3, sys
try:
    row = sqlite3.connect(sys.argv[1]).execute("SELECT value FROM settings WHERE key='owner_claimed'").fetchone()
    print(row[0] if row else "")
except Exception:
    print("")
PY
}
if [ -z "$ADMIN_IDS" ] && [ -z "$(owner_claimed)" ]; then
  BOT_USERNAME=$(curl -fsS "https://api.telegram.org/bot$BOT_TOKEN/getMe" | python3 -c "import sys, json; print(json.load(sys.stdin)['result']['username'])" 2>/dev/null || true)
  LINK="https://t.me/${BOT_USERNAME:-YOUR_BOT}?start=owner_$OWNER_CODE"
  printf '\n\033[1;36m👉 Ин истинодро кушоед ва START-ро пахш кунед — шумо админ мешавед:\n👉 Откройте ссылку и нажмите START — вы станете админом:\n\n   %s\n\033[0m\n' "$LINK"
  echo "⏳ Интизорӣ… / Ждём нажатия Start… (Ctrl+C — гузаштан / пропустить)"
  for _ in $(seq 1 300); do
    OWNER=$(owner_claimed)
    if [ -n "$OWNER" ]; then
      say "✅ Админ сабт шуд / Админ сохранён: $OWNER"
      echo "Ба бот /panel нависед → 💳 Реквизитҳо — рақами кортҳоро гузоред."
      break
    fi
    sleep 2
  done
  [ -z "$(owner_claimed)" ] && echo "Вақт гузашт. Истинод боз ҳам кор мекунад / Время вышло, ссылка всё ещё работает: $LINK"
fi
echo
if [ -n "$ADMIN_IDS" ]; then
  echo "👥 Админҳо дар бот / Админы в боте: $(python3 -c "import sqlite3,sys; r=sqlite3.connect(sys.argv[1]).execute(\"SELECT value FROM settings WHERE key='admin_ids'\").fetchone(); print(r[0] if r else '')" "$APP/data.db" 2>/dev/null)"
  echo "ℹ️ Админи нав бояд ботро кушода /start пахш кунад → тугмаи «🛠 Панел» пайдо мешавад (ё /panel нависед)."
  echo "ℹ️ Новый админ должен открыть бота и нажать /start → появится кнопка «🛠 Панел» (или написать /panel)."
fi
echo "Логҳо / Логи:        journalctl -u $SERVICE -f"
echo "Аз нав / Перезапуск: systemctl restart $SERVICE"
echo "Навсозӣ / Обновить:  такрор кардани ҳамин фармон / повторить эту же команду"
