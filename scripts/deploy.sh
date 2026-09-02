#!/usr/bin/env bash
#
# Копейка — установка на сервер одной командой.
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/ali.me/claude/charming-davinci-jhnk9o/scripts/deploy.sh \
#     | bash -s -- --token <BOT_TOKEN> --domain kopeyka.example.com
#
# Скрипт ставит Docker (если его нет), забирает код, генерирует секреты,
# поднимает бота и панель, выпускает HTTPS-сертификат и включает вебхук.
# Повторный запуск = обновление: данные и секреты сохраняются.
set -euo pipefail

REPO_URL="${KOPEYKA_REPO:-https://github.com/alijon26062006-bit/ali.me.git}"
BRANCH="${KOPEYKA_BRANCH:-claude/charming-davinci-jhnk9o}"
DIR="${KOPEYKA_DIR:-/opt/kopeyka}"
DRY_RUN="${KOPEYKA_DRY_RUN:-0}"

BOT_TOKEN="${BOT_TOKEN:-}"
BOT_USERNAME="${BOT_USERNAME:-}"
DOMAIN="${DOMAIN:-}"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
CURRENCY="${DEFAULT_CURRENCY:-UZS}"
TZ_OFFSET="${DEFAULT_TZ_OFFSET:-300}"
APP_PORT="${APP_PORT:-3000}"

say()  { printf '\033[1;32m▸\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Копейка — трекер расходов в Telegram.

Использование:
  deploy.sh --token <BOT_TOKEN> [--domain example.com] [опции]

Опции:
  --token TOKEN        токен бота от @BotFather (обязательно)
  --domain DOMAIN      домен панели; включает HTTPS и вебхук
                       (без него панель поднимется на http://IP:PORT, бот — на long polling)
  --username NAME      имя бота без @ для кнопки «Открыть бота»
  --anthropic-key KEY  включить распознавание чеков по фото
  --currency CODE      базовая валюта новых пользователей (по умолчанию UZS)
  --tz-offset MINUTES  часовой пояс в минутах от UTC (по умолчанию 300 = UTC+5)
  --port PORT          порт приложения без домена (по умолчанию 3000)
  --dir PATH           куда установить (по умолчанию /opt/kopeyka)
  --branch NAME        ветка репозитория
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --token)          BOT_TOKEN="${2:-}"; shift 2 ;;
    --domain)         DOMAIN="${2:-}"; shift 2 ;;
    --username)       BOT_USERNAME="${2:-}"; shift 2 ;;
    --anthropic-key)  ANTHROPIC_API_KEY="${2:-}"; shift 2 ;;
    --currency)       CURRENCY="${2:-}"; shift 2 ;;
    --tz-offset)      TZ_OFFSET="${2:-}"; shift 2 ;;
    --port)           APP_PORT="${2:-}"; shift 2 ;;
    --dir)            DIR="${2:-}"; shift 2 ;;
    --branch)         BRANCH="${2:-}"; shift 2 ;;
    -h|--help)        usage; exit 0 ;;
    *)                die "Неизвестный параметр: $1 (--help — список опций)" ;;
  esac
done

if [ -z "$BOT_TOKEN" ] && [ -t 0 ]; then
  read -rp "Токен бота от @BotFather: " BOT_TOKEN
fi
[ -n "$BOT_TOKEN" ] || die "Нужен токен бота: --token <BOT_TOKEN> (получить у @BotFather)"
DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null || die "Запустите от root или установите sudo"
  SUDO="sudo"
fi

run() { if [ "$DRY_RUN" = "1" ]; then echo "  [dry-run] $*"; else $SUDO "$@"; fi; }

# ── 1. Docker ────────────────────────────────────────────────────────────────
if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  say "Docker уже установлен"
else
  say "Ставлю Docker…"
  if [ "$DRY_RUN" = "1" ]; then
    echo "  [dry-run] curl -fsSL https://get.docker.com | sh"
  else
    curl -fsSL https://get.docker.com | $SUDO sh
    $SUDO systemctl enable --now docker 2>/dev/null || true
  fi
  docker compose version >/dev/null 2>&1 || warn "Проверьте, что доступен плагин docker compose"
fi

command -v git >/dev/null || {
  say "Ставлю git…"
  run sh -c 'apt-get update -qq && apt-get install -y -qq git || yum install -y git'
}

# ── 2. Код ───────────────────────────────────────────────────────────────────
if [ -d "$DIR/.git" ]; then
  say "Обновляю код в $DIR"
  run git -C "$DIR" fetch --depth 1 origin "$BRANCH"
  run git -C "$DIR" checkout -B deploy "origin/$BRANCH"
else
  say "Клонирую $REPO_URL ($BRANCH) в $DIR"
  run mkdir -p "$DIR"
  run git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$DIR"
fi

# ── 3. Настройки и секреты ───────────────────────────────────────────────────
ENV_FILE="$DIR/.env"
keep() { # сохраняем уже сгенерированные секреты, чтобы сессии не слетали
  local key="$1"
  [ -f "$ENV_FILE" ] || return 0
  sed -n "s/^${key}=//p" "$ENV_FILE" | head -1
}
random() { head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; }

SESSION_SECRET="$(keep SESSION_SECRET)"; [ -n "$SESSION_SECRET" ] || SESSION_SECRET="$(random)"
WEBHOOK_SECRET="$(keep WEBHOOK_SECRET)"; [ -n "$WEBHOOK_SECRET" ] || WEBHOOK_SECRET="$(random)"

if [ -n "$DOMAIN" ]; then
  PUBLIC_URL="https://$DOMAIN"; USE_WEBHOOK=1; BIND="127.0.0.1"; PROFILE=(--profile tls)
else
  IP="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')"
  PUBLIC_URL="http://${IP:-localhost}:$APP_PORT"; USE_WEBHOOK=0; BIND="0.0.0.0"; PROFILE=()
  warn "Домен не задан: панель будет по $PUBLIC_URL, без HTTPS и без Mini App"
fi

say "Пишу $ENV_FILE"
ENV_CONTENT="$(cat <<ENVEOF
BOT_TOKEN=$BOT_TOKEN
BOT_USERNAME=$BOT_USERNAME
PUBLIC_URL=$PUBLIC_URL
SESSION_SECRET=$SESSION_SECRET
USE_WEBHOOK=$USE_WEBHOOK
WEBHOOK_SECRET=$WEBHOOK_SECRET
DEFAULT_CURRENCY=$CURRENCY
DEFAULT_TZ_OFFSET=$TZ_OFFSET
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
DOMAIN=$DOMAIN
BIND=$BIND
APP_PORT=$APP_PORT
ENVEOF
)"
if [ "$DRY_RUN" = "1" ]; then
  echo "  [dry-run] содержимое .env:"; echo "$ENV_CONTENT" | sed 's/^/    /'
else
  printf '%s\n' "$ENV_CONTENT" | $SUDO tee "$ENV_FILE" >/dev/null
  $SUDO chmod 600 "$ENV_FILE"
fi

# ── 4. Запуск ────────────────────────────────────────────────────────────────
say "Собираю и запускаю контейнеры…"
if [ "$DRY_RUN" = "1" ]; then
  echo "  [dry-run] docker compose ${PROFILE[*]:-} up -d --build"
else
  (cd "$DIR" && $SUDO docker compose "${PROFILE[@]}" up -d --build)
fi

# ── 5. Проверка ──────────────────────────────────────────────────────────────
if [ "$DRY_RUN" != "1" ]; then
  say "Жду ответа приложения…"
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 3 "http://127.0.0.1:$APP_PORT/healthz" >/dev/null 2>&1; then
      say "Приложение отвечает"
      break
    fi
    sleep 2
  done
fi

cat <<DONE

✅ Готово.

   Панель:  $PUBLIC_URL
   Бот:     напишите ему «кофе 350», затем /app — придёт ссылка входа
   Логи:    cd $DIR && docker compose logs -f app
   Обновить: перезапустите эту же команду

DONE

if [ -n "$DOMAIN" ]; then
  cat <<TLS
   Проверьте, что A-запись $DOMAIN указывает на этот сервер, а порты 80 и 443 открыты —
   Caddy выпускает сертификат сам при первом обращении.
   Чтобы панель открывалась внутри Telegram: @BotFather → /setdomain → $DOMAIN

TLS
fi
