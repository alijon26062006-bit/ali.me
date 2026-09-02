#!/usr/bin/env bash
#
# Копейка — установка на сервер одной командой.
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/ali.me/claude/charming-davinci-jhnk9o/scripts/deploy.sh | bash
#
# Без аргументов скрипт спрашивает всё сам: токен бота, домен, валюту,
# часовой пояс и ключ для распознавания чеков. Дальше ставит Docker
# (если его нет), забирает код, генерирует секреты, поднимает бота и панель
# и выпускает HTTPS-сертификат.
#
# Для автоматизации те же значения можно передать флагами — тогда вопросов не будет:
#   ... | bash -s -- --token 123:AA... --domain kopeyka.mysite.ru
#
# Повторный запуск = обновление: база и секреты сохраняются.
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
TOKEN_FROM_FLAG=0

say()  { printf '\033[1;32m▸\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Копейка — трекер расходов в Telegram.

  deploy.sh                        мастер: спросит всё по шагам
  deploy.sh --token TOKEN [опции]  без вопросов, всё из флагов

Опции:
  --token TOKEN        токен бота от @BotFather
  --domain DOMAIN      домен панели; включает HTTPS и вебхук
                       (без него — панель на http://IP:PORT, бот на long polling)
  --username NAME      имя бота без @ (обычно определяется само по токену)
  --anthropic-key KEY  включить распознавание чеков по фото
  --currency CODE      базовая валюта (по умолчанию UZS)
  --tz-offset MINUTES  часовой пояс в минутах от UTC (по умолчанию 300 = UTC+5)
  --port PORT          порт приложения без домена (по умолчанию 3000)
  --dir PATH           куда установить (по умолчанию /opt/kopeyka)
  --branch NAME        ветка репозитория
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --token)          BOT_TOKEN="${2:-}"; TOKEN_FROM_FLAG=1; shift 2 ;;
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

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null || die "Запустите от root или установите sudo"
  SUDO="sudo"
fi

run() { if [ "$DRY_RUN" = "1" ]; then echo "  [dry-run] $*"; else $SUDO "$@"; fi; }

# ── вопросы задаём в терминал напрямую, чтобы работало и через curl | bash ──
TTY_OPEN=0
if exec 3</dev/tty; then TTY_OPEN=1; fi 2>/dev/null || TTY_OPEN=0

ask() { # ask ПЕРЕМЕННАЯ "вопрос" [значение по умолчанию]
  local var="$1" prompt="$2" default="${3:-}" answer=""
  [ -n "$default" ] && prompt="$prompt [$default]"
  if [ "$TTY_OPEN" = "1" ]; then
    printf '\033[1;36m?\033[0m %s: ' "$prompt" >&2
    IFS= read -r answer <&3 || answer=""
  fi
  printf -v "$var" '%s' "${answer:-$default}"
}

confirm() { # confirm "вопрос" — да по умолчанию
  local answer=""
  [ "$TTY_OPEN" = "1" ] || return 0
  printf '\033[1;36m?\033[0m %s [Y/n]: ' "$1" >&2
  IFS= read -r answer <&3 || answer=""
  case "$answer" in [nNнН]*) return 1 ;; *) return 0 ;; esac
}

looks_like_placeholder() {
  case "$1" in *'<'*|*'>'*|*ТОКЕН*|*TOKEN*|*ВАШ*|*ваш*|*your*|*YOUR*|*example.com|*example.org|*домен*) return 0 ;; esac
  return 1
}

valid_token() { printf '%s' "$1" | grep -qE '^[0-9]{5,15}:[A-Za-z0-9_-]{20,}$'; }
valid_domain() { printf '%s' "$1" | grep -qE '^[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,}$'; }

# Проверяем токен через Telegram и заодно узнаём имя бота.
check_token() {
  local response username
  response="$(curl -fsS --max-time 10 "https://api.telegram.org/bot$1/getMe" 2>/dev/null || true)"
  case "$response" in
    *'"ok":true'*)
      username="$(printf '%s' "$response" | sed -n 's/.*"username":"\([^"]*\)".*/\1/p')"
      [ -n "$username" ] && BOT_USERNAME="$username"
      say "Токен принят: бот @${BOT_USERNAME:-?}"
      return 0 ;;
    *'"ok":false'*)
      warn "Telegram не принял этот токен (проверьте, что скопировали целиком)"
      return 1 ;;
    *)
      warn "Не удалось связаться с Telegram — токен не проверен, продолжаю"
      return 0 ;;
  esac
}

# Переводим «+5», «-3:30», «utc+5», «300» в минуты от UTC.
tz_to_minutes() {
  local value="${1//[[:space:]]/}" hours minutes sign=1
  value="${value#[uU][tT][cC]}"
  [ -n "$value" ] || { printf '300'; return; }
  case "$value" in -*) sign=-1; value="${value#-}" ;; +*) value="${value#+}" ;; esac
  case "$value" in
    *:*) hours="${value%%:*}"; minutes="${value##*:}" ;;
    *)   hours="$value"; minutes=0 ;;
  esac
  case "$hours$minutes" in *[!0-9]*) printf '300'; return ;; esac
  # Значения больше 14 считаем уже минутами: «300» — это UTC+5.
  if [ "$hours" -gt 14 ] 2>/dev/null && [ "$minutes" = "0" ]; then
    printf '%s' "$((sign * hours))"
  else
    printf '%s' "$((sign * (hours * 60 + minutes)))"
  fi
}

# ── уже установлено? тогда просто обновляем ──────────────────────────────────
PREV_ENV="$($SUDO cat "$DIR/.env" 2>/dev/null || true)"
prev() { printf '%s\n' "$PREV_ENV" | sed -n "s/^$1=//p" | head -1; }

if [ "$TOKEN_FROM_FLAG" = "0" ] && [ -n "$(prev BOT_TOKEN)" ]; then
  BOT_TOKEN="$(prev BOT_TOKEN)"
  BOT_USERNAME="$(prev BOT_USERNAME)"
  [ -n "$DOMAIN" ] || DOMAIN="$(prev DOMAIN)"
  CURRENCY="$(prev DEFAULT_CURRENCY)"; CURRENCY="${CURRENCY:-UZS}"
  TZ_OFFSET="$(prev DEFAULT_TZ_OFFSET)"; TZ_OFFSET="${TZ_OFFSET:-300}"
  ANTHROPIC_API_KEY="$(prev ANTHROPIC_API_KEY)"
  APP_PORT="$(prev APP_PORT)"; APP_PORT="${APP_PORT:-3000}"
  say "Нашёл установку в $DIR${BOT_USERNAME:+ (бот @$BOT_USERNAME)} — обновляю с текущими настройками"
  if [ "$TTY_OPEN" = "1" ] && ! confirm "Обновить с этими настройками?"; then
    BOT_TOKEN=""   # ответили «нет» — спросим всё заново
    say "Хорошо, настроим заново"
  fi
fi

# ── мастер ───────────────────────────────────────────────────────────────────
if [ "$TOKEN_FROM_FLAG" = "0" ] && [ -z "$BOT_TOKEN" ]; then
  [ "$TTY_OPEN" = "1" ] || die "Нет терминала для вопросов. Передайте значения флагами: deploy.sh --token 123:AA... --domain kopeyka.mysite.ru"

  cat >&2 <<'HELLO'

  🪙  Копейка — трекер расходов в Telegram
  Сейчас задам несколько вопросов и всё подниму сам.
  Пустой ответ = значение в скобках.

HELLO

  attempt=0
  while :; do
    attempt=$((attempt + 1))
    ask BOT_TOKEN "Токен бота от @BotFather (вида 123456789:AAH...)" "$BOT_TOKEN"
    if [ -z "$BOT_TOKEN" ] || looks_like_placeholder "$BOT_TOKEN"; then
      warn "Нужен настоящий токен. Откройте @BotFather → /newbot (или /mybots → API Token)."
      BOT_TOKEN=""
    elif ! valid_token "$BOT_TOKEN"; then
      warn "Не похоже на токен: ожидается вид 123456789:AAH... Скопируйте его целиком."
      BOT_TOKEN=""
    elif check_token "$BOT_TOKEN"; then
      break
    else
      BOT_TOKEN=""
    fi
    [ "$attempt" -lt 5 ] || die "Токен так и не подошёл. Возьмите свежий у @BotFather и запустите команду снова."
  done

  while :; do
    ask DOMAIN "Домен для панели, например kopeyka.mysite.ru (Enter — работать по IP, без HTTPS)" ""
    DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"
    [ -z "$DOMAIN" ] && break
    if looks_like_placeholder "$DOMAIN" || ! valid_domain "$DOMAIN"; then
      warn "Домен «$DOMAIN» выглядит неправильно. Пример: kopeyka.mysite.ru"
      continue
    fi
    break
  done

  ask CURRENCY "Основная валюта (UZS, USD, RUB, KZT, EUR…)" "$CURRENCY"
  CURRENCY="$(printf '%s' "$CURRENCY" | tr '[:lower:]' '[:upper:]')"

  ask TZ_ANSWER "Часовой пояс, например +5 (Ташкент) или +3 (Москва)" "+$((TZ_OFFSET / 60))"
  TZ_OFFSET="$(tz_to_minutes "$TZ_ANSWER")"

  ask ANTHROPIC_API_KEY "Ключ Anthropic API для распознавания чеков по фото (Enter — пропустить)" ""

  if [ -n "$DOMAIN" ]; then PANEL_LINE="https://$DOMAIN"; else PANEL_LINE="по IP сервера, порт $APP_PORT"; fi

  cat >&2 <<SUMMARY

  ── Проверьте ────────────────────────────────────
   Бот:           @${BOT_USERNAME:-неизвестно}
   Панель:        $PANEL_LINE
   Валюта:        $CURRENCY
   Часовой пояс:  UTC$([ "$TZ_OFFSET" -ge 0 ] && echo -n '+')$((TZ_OFFSET / 60))
   Чеки по фото:  $([ -n "$ANTHROPIC_API_KEY" ] && echo 'включены' || echo 'выключены')
   Каталог:       $DIR
  ─────────────────────────────────────────────────

SUMMARY
  confirm "Ставим?" || die "Отменено. Запустите команду ещё раз, когда будете готовы."
fi

# ── проверки для не-интерактивного запуска ───────────────────────────────────
[ -n "$BOT_TOKEN" ] || die "Нужен токен бота: --token 123456789:AA... (получить у @BotFather)"
if looks_like_placeholder "$BOT_TOKEN"; then
  die "Вместо токена подставился плейсхолдер. Уберите угловые скобки и вставьте настоящий токен от @BotFather."
fi
valid_token "$BOT_TOKEN" || die "Токен не похож на настоящий: ожидается вид 123456789:AAH..."

DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"
if [ -n "$DOMAIN" ]; then
  looks_like_placeholder "$DOMAIN" && die "Укажите свой домен вместо примера, либо запустите без --domain."
  valid_domain "$DOMAIN" || die "Домен «$DOMAIN» выглядит неправильно. Пример: kopeyka.mysite.ru"
fi
[ "$TOKEN_FROM_FLAG" = "1" ] && [ -z "$BOT_USERNAME" ] && check_token "$BOT_TOKEN" >/dev/null 2>&1 || true

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
  warn "Без домена: панель будет по $PUBLIC_URL, без HTTPS и без Mini App"
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

# Без домена панель должна быть доступна снаружи — публикуем порт через override.
OVERRIDE="$DIR/docker-compose.override.yml"
if [ "$DRY_RUN" = "1" ]; then
  [ -z "$DOMAIN" ] && echo "  [dry-run] публикация порта $APP_PORT через $OVERRIDE" \
                   || echo "  [dry-run] порт наружу не публикуется, снаружи только Caddy"
elif [ -z "$DOMAIN" ]; then
  printf 'services:\n  app:\n    ports:\n      - "%s:%s:3000"\n' "$BIND" "$APP_PORT" \
    | $SUDO tee "$OVERRIDE" >/dev/null
else
  $SUDO rm -f "$OVERRIDE"
fi

# ── 4. Запуск ────────────────────────────────────────────────────────────────
say "Собираю и запускаю контейнеры (первый раз это пара минут)…"
if [ "$DRY_RUN" = "1" ]; then
  echo "  [dry-run] docker compose down --remove-orphans && docker compose ${PROFILE[*]:-} up -d --build"
else
  # Сначала гасим старые контейнеры: иначе при смене портов новый не стартует
  # с «port is already allocated». Данные лежат в томе и не теряются.
  (cd "$DIR" && $SUDO docker compose down --remove-orphans 2>/dev/null || true)
  if ! (cd "$DIR" && $SUDO docker compose "${PROFILE[@]}" up -d --build); then
    warn "Контейнеры не поднялись. Кто занимает порты:"
    ($SUDO ss -ltnp 2>/dev/null || $SUDO netstat -ltnp 2>/dev/null) | grep -E ":($APP_PORT|80|443) " | sed 's/^/    /' || true
    die "Смотрите вывод выше и логи: cd $DIR && $SUDO docker compose logs --tail=50"
  fi
fi

# ── 5. Проверка ──────────────────────────────────────────────────────────────
if [ "$DRY_RUN" != "1" ]; then
  say "Жду ответа приложения…"
  for _ in $(seq 1 30); do
    if (cd "$DIR" && $SUDO docker compose exec -T app node -e \
        "fetch('http://127.0.0.1:3000/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))") >/dev/null 2>&1; then
      say "Приложение отвечает"
      break
    fi
    sleep 2
  done
fi

if [ -n "$BOT_USERNAME" ]; then BOT_LINE="https://t.me/$BOT_USERNAME"; else BOT_LINE="откройте своего бота в Telegram"; fi

cat <<DONE

✅ Готово.

   Панель:   $PUBLIC_URL
   Бот:      $BOT_LINE
   Проверка: напишите боту «кофе 350», потом /app — придёт ссылка входа
   Логи:     cd $DIR && docker compose logs -f app
   Обновить: запустите эту же команду ещё раз

DONE

if [ -n "$DOMAIN" ]; then
  cat <<TLS
   Убедитесь, что A-запись $DOMAIN указывает на этот сервер, а порты 80 и 443 открыты —
   Caddy выпускает сертификат сам при первом обращении.
   Чтобы панель открывалась внутри Telegram: @BotFather → /setdomain → $DOMAIN

TLS
fi
