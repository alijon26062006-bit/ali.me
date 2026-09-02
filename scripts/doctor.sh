#!/usr/bin/env bash
#
# Копейка — диагностика: почему не отвечает бот или панель.
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/ali.me/claude/charming-davinci-jhnk9o/scripts/doctor.sh | bash
#
# Ничего не меняет, только проверяет и подсказывает. Токен не печатается.
set -uo pipefail

DIR="${KOPEYKA_DIR:-/opt/kopeyka}"
PROBLEMS=0

ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
bad()  { printf '\033[1;31m✗\033[0m %s\n' "$*"; PROBLEMS=$((PROBLEMS + 1)); }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
info() { printf '  %s\n' "$*"; }
head2(){ printf '\n\033[1m── %s\033[0m\n' "$*"; }
fix()  { printf '  \033[1;36m→ %s\033[0m\n' "$*"; }

SUDO=""
[ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null && SUDO="sudo"

# ── 1. Установка на месте? ───────────────────────────────────────────────────
head2 "Установка"
if [ -d "$DIR" ]; then
  ok "каталог $DIR найден"
else
  bad "каталога $DIR нет — установка не выполнялась или ставили в другое место"
  fix "запустите установку: curl -fsSL .../scripts/deploy.sh | bash"
  fix "или укажите свой каталог: KOPEYKA_DIR=/путь bash doctor.sh"
  exit 1
fi

ENV_FILE="$DIR/.env"
if [ -r "$ENV_FILE" ] || [ -n "$SUDO" ]; then
  ENV_TEXT="$($SUDO cat "$ENV_FILE" 2>/dev/null)"
else
  ENV_TEXT=""
fi
[ -n "$ENV_TEXT" ] || { bad "не читается $ENV_FILE (запустите от root)"; exit 1; }

get() { printf '%s\n' "$ENV_TEXT" | sed -n "s/^$1=//p" | head -1; }
BOT_TOKEN="$(get BOT_TOKEN)"
BOT_USERNAME="$(get BOT_USERNAME)"
PUBLIC_URL="$(get PUBLIC_URL)"
DOMAIN="$(get DOMAIN)"
USE_WEBHOOK="$(get USE_WEBHOOK)"
APP_PORT="$(get APP_PORT)"; APP_PORT="${APP_PORT:-3000}"

[ -n "$BOT_TOKEN" ] && ok "токен в .env есть (…${BOT_TOKEN: -6})" || bad "BOT_TOKEN в .env пуст"
info "панель: ${PUBLIC_URL:-не задана}   режим: $([ "$USE_WEBHOOK" = "1" ] && echo вебхук || echo polling)"

# ── 2. Контейнеры ────────────────────────────────────────────────────────────
head2 "Контейнеры"
if ! command -v docker >/dev/null; then
  bad "docker не установлен"
  fix "перезапустите установку — она ставит Docker сама"
else
  PS="$(cd "$DIR" && $SUDO docker compose ps 2>&1)"
  printf '%s\n' "$PS" | sed 's/^/  /'
  if printf '%s' "$PS" | grep -qiE '\bapp\b.*(running|up)'; then
    ok "контейнер приложения запущен"
  else
    bad "контейнер приложения не запущен"
    BUSY="$(($SUDO ss -ltnp 2>/dev/null || $SUDO netstat -ltnp 2>/dev/null) | grep -E ":$APP_PORT " || true)"
    if [ -n "$BUSY" ]; then
      info "порт $APP_PORT уже занят:"; printf '%s\n' "$BUSY" | sed 's/^/    /'
      fix "погасите старые контейнеры и поднимите заново: cd $DIR && $SUDO docker compose down --remove-orphans && $SUDO docker compose up -d --build"
    else
      fix "cd $DIR && $SUDO docker compose up -d --build"
    fi
  fi
  if [ -n "$DOMAIN" ] && ! printf '%s' "$PS" | grep -qiE 'caddy.*(running|up)'; then
    bad "Caddy не запущен, а домен задан — HTTPS не работает"
    fix "cd $DIR && $SUDO docker compose --profile tls up -d"
  fi
fi

# ── 3. Приложение отвечает? ──────────────────────────────────────────────────
head2 "Приложение"
if curl -fsS --max-time 5 "http://127.0.0.1:$APP_PORT/healthz" >/dev/null 2>&1; then
  ok "локально отвечает на порту $APP_PORT"
else
  bad "не отвечает на http://127.0.0.1:$APP_PORT/healthz"
  fix "смотрите логи: cd $DIR && $SUDO docker compose logs --tail=50 app"
fi

# Связь наружу именно из контейнера: сервер может ходить в интернет, а контейнер — нет.
if command -v docker >/dev/null; then
  NET="$(cd "$DIR" && $SUDO docker compose exec -T app node -e \
    "fetch('https://api.telegram.org/').then(r=>console.log('OK '+r.status)).catch(e=>console.log('FAIL '+((e.cause&&e.cause.code)||e.message)))" 2>&1)"
  case "$NET" in
    *OK*)
      ok "из контейнера Telegram доступен" ;;
    *EAI_AGAIN*|*ENOTFOUND*|*getaddrinfo*)
      bad "из контейнера не резолвится api.telegram.org — у него нет рабочего DNS"
      fix "обновитесь: cd $DIR && $SUDO git fetch origin ${KOPEYKA_BRANCH:-claude/charming-davinci-jhnk9o} && $SUDO git checkout -B deploy origin/${KOPEYKA_BRANCH:-claude/charming-davinci-jhnk9o} && $SUDO docker compose up -d --build"
      fix "в новой версии compose задаёт контейнерам DNS 1.1.1.1 и 8.8.8.8" ;;
    *ETIMEDOUT*|*ECONNREFUSED*|*ECONNRESET*|*EHOSTUNREACH*)
      bad "из контейнера не проходит соединение с Telegram: $NET"
      fix "проверьте исходящий трафик и файрвол сервера" ;;
    *FAIL*)
      bad "из контейнера нет связи с Telegram: $NET" ;;
    *)
      : ;;  # контейнер не запущен — об этом уже сказано выше
  esac
fi

LOGS="$(cd "$DIR" && $SUDO docker compose logs --tail=60 app 2>/dev/null)"
if printf '%s' "$LOGS" | grep -q '🤖 Бот'; then
  ok "$(printf '%s' "$LOGS" | grep -o '🤖 Бот:.*' | tail -1)"
fi
if printf '%s' "$LOGS" | grep -qiE 'Не удалось запустить бота|нет связи с api.telegram.org'; then
  bad "приложение не смогло подключиться к Telegram:"
  printf '%s' "$LOGS" | grep -i -A2 'Не удалось запустить бота' | tail -3 | sed 's/^/    /'
  fix "проверьте BOT_TOKEN в $ENV_FILE и доступ сервера к api.telegram.org"
fi
if printf '%s' "$LOGS" | grep -qi 'конфликт getUpdates'; then
  bad "тот же токен уже используется другим запущенным ботом"
  fix "остановите вторую копию (старый сервер, локальный запуск) — Telegram отдаёт апдейты только одной"
fi

# ── 4. Что говорит Telegram ──────────────────────────────────────────────────
head2 "Telegram"
if [ -z "$BOT_TOKEN" ]; then
  bad "без токена проверить нельзя"
else
  ME="$(curl -fsS --max-time 10 "https://api.telegram.org/bot$BOT_TOKEN/getMe" 2>/dev/null)"
  case "$ME" in
    *'"ok":true'*)
      BOT_USERNAME="$(printf '%s' "$ME" | sed -n 's/.*"username":"\([^"]*\)".*/\1/p')"
      ok "токен рабочий, бот @$BOT_USERNAME (https://t.me/$BOT_USERNAME)" ;;
    *'"ok":false'*)
      bad "Telegram отклонил токен: $(printf '%s' "$ME" | sed -n 's/.*"description":"\([^"]*\)".*/\1/p')"
      fix "возьмите свежий токен: @BotFather → /mybots → API Token, потом перезапустите установку" ;;
    *)
      bad "сервер не достучался до api.telegram.org"
      fix "проверьте интернет и файрвол: curl -v https://api.telegram.org" ;;
  esac

  HOOK="$(curl -fsS --max-time 10 "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo" 2>/dev/null)"
  HOOK_URL="$(printf '%s' "$HOOK" | sed -n 's/.*"url":"\([^"]*\)".*/\1/p')"
  HOOK_ERR="$(printf '%s' "$HOOK" | sed -n 's/.*"last_error_message":"\([^"]*\)".*/\1/p')"
  PENDING="$(printf '%s' "$HOOK" | sed -n 's/.*"pending_update_count":\([0-9]*\).*/\1/p')"

  if [ "$USE_WEBHOOK" = "1" ]; then
    if [ -n "$HOOK_URL" ]; then
      ok "вебхук зарегистрирован: $HOOK_URL"
    else
      bad "вебхук не зарегистрирован — приложение не смогло его поставить"
      fix "перезапустите: cd $DIR && $SUDO docker compose restart app, потом смотрите логи"
    fi
    if [ -n "$HOOK_ERR" ]; then
      bad "Telegram не может доставить апдейты: $HOOK_ERR"
      case "$HOOK_ERR" in
        *SSL*|*certificate*|*TLS*) fix "сертификат ещё не выпущен: проверьте A-запись домена и открытые порты 80/443, логи Caddy: $SUDO docker compose logs --tail=30 caddy" ;;
        *[Tt]imeout*|*unreachable*|*refused*) fix "сервер недоступен снаружи: откройте порты 80 и 443 (ufw allow 80,443/tcp)" ;;
        *404*|*[Nn]ot\ [Ff]ound*) fix "проверьте PUBLIC_URL в .env — он должен совпадать с реальным доменом" ;;
      esac
    fi
  else
    if [ -n "$HOOK_URL" ]; then
      bad "включён polling, но у бота остался вебхук $HOOK_URL — апдейты уходят туда"
      fix "снимите его: curl -s \"https://api.telegram.org/bot\$BOT_TOKEN/deleteWebhook\" (токен возьмите из $ENV_FILE)"
    else
      ok "вебхук не мешает, режим polling"
    fi
  fi
  [ -n "${PENDING:-}" ] && [ "${PENDING:-0}" -gt 0 ] 2>/dev/null && warn "необработанных апдейтов в очереди: $PENDING"
fi

# ── 5. Домен, порты, сертификат ──────────────────────────────────────────────
if [ -n "$DOMAIN" ]; then
  head2 "Домен и HTTPS"
  SERVER_IP="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null)"
  DNS_IP="$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk '{print $1; exit}')"
  info "IP сервера: ${SERVER_IP:-неизвестен}   A-запись $DOMAIN: ${DNS_IP:-не найдена}"
  if [ -z "$DNS_IP" ]; then
    bad "домен не резолвится — сертификат выпустить нельзя"
    fix "добавьте A-запись $DOMAIN → ${SERVER_IP:-IP сервера} у регистратора и подождите обновления DNS"
  elif [ -n "$SERVER_IP" ] && [ "$DNS_IP" != "$SERVER_IP" ]; then
    bad "домен указывает на $DNS_IP, а сервер — $SERVER_IP"
    fix "поправьте A-запись на $SERVER_IP"
  else
    ok "домен указывает на этот сервер"
  fi

  for port in 80 443; do
    if ($SUDO ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -q ":$port "; then
      ok "порт $port слушается"
    else
      bad "порт $port не слушается — Caddy не поднялся"
      fix "cd $DIR && $SUDO docker compose --profile tls up -d && $SUDO docker compose logs --tail=30 caddy"
    fi
  done

  if curl -fsS --max-time 10 "https://$DOMAIN/healthz" >/dev/null 2>&1; then
    ok "панель открывается снаружи: https://$DOMAIN"
  else
    bad "https://$DOMAIN/healthz не отвечает снаружи"
    fix "откройте порты в файрволе провайдера и на сервере: $SUDO ufw allow 80/tcp && $SUDO ufw allow 443/tcp"
    fix "логи Caddy: cd $DIR && $SUDO docker compose logs --tail=30 caddy"
  fi
fi

# ── Итог ─────────────────────────────────────────────────────────────────────
printf '\n'
if [ "$PROBLEMS" -eq 0 ]; then
  ok "Проблем не нашёл. Напишите боту${BOT_USERNAME:+ @$BOT_USERNAME} «кофе 350» — он должен ответить."
  info "Если молчит — пришлите вывод: cd $DIR && $SUDO docker compose logs --tail=50 app"
else
  printf '\033[1;31mНайдено проблем: %s\033[0m — см. подсказки со стрелкой выше.\n' "$PROBLEMS"
fi
