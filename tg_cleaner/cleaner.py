#!/usr/bin/env python3
"""
Telegram account cleaner (userbot).

Для СВОЕГО взломанного аккаунта:
  1. Выкидывает все остальные сессии (взломщика).
  2. Покидает все каналы и группы (свои каналы — по желанию удаляет).
  3. Удаляет все личные чаты и чаты с ботами (боты — по желанию блокирует).
  4. Удаляет все контакты.
  5. (По желанию) удаляет сам аккаунт.

Вход: по номеру телефона (код + пароль 2FA) или по QR-коду.
Работает "как человек": случайные паузы между действиями, обработка FloodWait.
"""
import argparse
import asyncio
import getpass
import os
import random
import sys

from telethon import TelegramClient, errors, events, functions, password as pwd_mod
from telethon.tl.types import Channel, Chat, User

TELEGRAM_SERVICE_ID = 777000  # приходят коды входа — никогда не трогаем

# Публичные ключи из открытого кода Telegram Desktop (github.com/telegramdesktop/tdesktop)
PUBLIC_API_ID = 2040
PUBLIC_API_HASH = "b18441a1ff607e10a989891a5462e627"


def log(msg: str) -> None:
    print(msg, flush=True)


async def human_pause(args) -> None:
    await asyncio.sleep(random.uniform(args.min_delay, args.max_delay))


async def safe(call, what: str, args):
    """Выполнить действие с повтором при FloodWait."""
    for attempt in range(5):
        try:
            return await call()
        except errors.FloodWaitError as e:
            wait = e.seconds + random.randint(2, 6)
            log(f"   ⏳ Telegram просит подождать {wait} c ({what})")
            await asyncio.sleep(wait)
        except errors.RPCError as e:
            log(f"   ⚠️  {what}: {e.__class__.__name__}: {e}")
            return None
    log(f"   ⚠️  {what}: не удалось после нескольких попыток")
    return None


# ---------------------------------------------------------------- login

async def login_phone(client: TelegramClient, phone: str | None) -> None:
    phone = phone or input("Номер телефона (+998...): ").strip()
    await client.send_code_request(phone)
    try:
        await client.sign_in(phone, input("Код из Telegram/SMS: ").strip())
    except errors.SessionPasswordNeededError:
        await enter_2fa(client)


async def enter_2fa(client: TelegramClient) -> None:
    """Ввод облачного пароля с повторами, подсказкой и восстановлением."""
    info = await client(functions.account.GetPasswordRequest())
    log("\nНужен облачный пароль (2FA).")
    if info.hint:
        log(f"   Подсказка к паролю: {info.hint}")
    if info.has_recovery:
        log(f"   Почта для восстановления: {info.email_unconfirmed_pattern or 'есть'}")
    while True:
        log("\n  1 — ввести пароль (ввод скрыт, символы не видны — это нормально)"
            "\n  2 — восстановить через почту (код придёт на почту восстановления)"
            "\n  3 — сбросить пароль (Telegram сбросит через 7 дней)"
            "\n  0 — выход")
        choice = input("Выбор: ").strip()
        if choice == "1":
            try:
                await client.sign_in(password=getpass.getpass("Пароль 2FA: "))
                return
            except errors.PasswordHashInvalidError:
                log("   ❌ Неверный пароль. Проверьте раскладку (RU/EN) и CapsLock.")
            except errors.FloodWaitError as e:
                log(f"   ⏳ Слишком много попыток, подождите {e.seconds} c.")
        elif choice == "2":
            try:
                r = await client(functions.auth.RequestPasswordRecoveryRequest())
                log(f"   Код отправлен на {r.email_pattern}")
                code = input("   Код из письма: ").strip()
                await client(functions.auth.RecoverPasswordRequest(code=code))
                log("   ✅ Вход выполнен, облачный пароль снят. Потом поставьте новый!")
                return
            except errors.RPCError as e:
                log(f"   ❌ {e.__class__.__name__}: {e}")
        elif choice == "3":
            try:
                r = await client(functions.account.ResetPasswordRequest())
                log(f"   Ответ Telegram: {r}")
                log("   Если назначен сброс — запустите скрипт снова после указанной даты.")
            except errors.RPCError as e:
                log(f"   ❌ {e.__class__.__name__}: {e}")
        elif choice == "0":
            sys.exit("Выход.")


async def login_qr(client: TelegramClient, qr_png: str) -> None:
    import qrcode

    while True:
        qr = await client.qr_login()
        img = qrcode.QRCode(border=1)
        img.add_data(qr.url)
        img.make()
        log("\nОтсканируйте QR: Telegram на телефоне → Настройки → Устройства → "
            "Подключить устройство\n")
        img.print_ascii(invert=True)
        try:
            img.make_image().save(qr_png)
            log(f"\n(QR также сохранён в файл {qr_png})")
        except Exception:
            pass  # Pillow не установлен — хватит QR в терминале
        log("QR действует ~30 секунд. Жду сканирования…")
        try:
            await qr.wait(timeout=60)
            break
        except asyncio.TimeoutError:
            log("QR устарел — генерирую новый…")
        except errors.SessionPasswordNeededError:
            await enter_2fa(client)
            break
    if os.path.exists(qr_png):
        os.remove(qr_png)


# ---------------------------------------------------------------- steps

async def kill_other_sessions(client, args) -> None:
    log("\n[1] Завершаю все чужие сессии…")
    auths = await client(functions.account.GetAuthorizationsRequest())
    others = [a for a in auths.authorizations if not a.current]
    for a in others:
        log(f"   • {a.device_model} | {a.app_name} | {a.ip} | {a.country}")
    if not others:
        log("   Других сессий нет.")
        return
    if args.dry_run:
        return
    try:
        await client(functions.auth.ResetAuthorizationsRequest())
        log("   ✅ Все остальные сессии завершены.")
    except errors.RPCError as e:
        if "FRESH_RESET_AUTHORISATION_FORBIDDEN" in str(e):
            log("   ❌ Telegram запрещает завершать сессии с только что "
                "созданной сессии (нужно ~24 часа). Запустите скрипт ещё раз "
                "через сутки с той же сессией (файл .session сохраняется).")
        else:
            log(f"   ❌ {e}")


async def clean_dialogs(client, args, me) -> None:
    log("\n[2] Чистка каналов, групп, ботов и чатов…")
    stats = {"left": 0, "deleted_channels": 0, "chats": 0, "bots": 0}
    dialogs = [d async for d in client.iter_dialogs()]  # включая архив
    log(f"   Найдено диалогов: {len(dialogs)}")

    for d in dialogs:
        ent = d.entity
        name = (d.name or "без названия")[:50]

        if isinstance(ent, User):
            if ent.id in (me.id, TELEGRAM_SERVICE_ID):
                continue
            kind = "бот" if ent.bot else "чат"
            log(f"   🗑  {kind}: {name}")
            if args.dry_run:
                continue
            await safe(lambda: client.delete_dialog(ent, revoke=args.revoke),
                       f"удаление {kind}а {name}", args)
            if ent.bot:
                stats["bots"] += 1
                if args.block_bots:
                    await safe(lambda: client(functions.contacts.BlockRequest(ent)),
                               f"блокировка бота {name}", args)
            else:
                stats["chats"] += 1

        elif isinstance(ent, (Channel, Chat)):
            kind = "канал" if getattr(ent, "broadcast", False) else "группа"
            owner = getattr(ent, "creator", False)
            if owner and args.delete_owned:
                log(f"   💥 удаляю СВОЙ {kind}: {name}")
                if args.dry_run:
                    continue
                if isinstance(ent, Channel):
                    req = functions.channels.DeleteChannelRequest(ent)
                else:
                    req = functions.messages.DeleteChatRequest(ent.id)
                await safe(lambda: client(req), f"удаление {name}", args)
                stats["deleted_channels"] += 1
            else:
                log(f"   🚪 покидаю {kind}: {name}")
                if args.dry_run:
                    continue
                await safe(lambda: client.delete_dialog(ent),
                           f"выход из {name}", args)
                stats["left"] += 1
        else:
            continue

        await human_pause(args)

    log(f"   Итог: покинуто {stats['left']}, удалено своих каналов/групп "
        f"{stats['deleted_channels']}, чатов {stats['chats']}, ботов {stats['bots']}")


async def delete_contacts(client, args) -> None:
    log("\n[3] Удаление контактов…")
    res = await client(functions.contacts.GetContactsRequest(hash=0))
    users = list(res.users)
    log(f"   Контактов: {len(users)}")
    if args.dry_run or not users:
        return
    for i in range(0, len(users), 100):
        chunk = users[i:i + 100]
        await safe(lambda: client(functions.contacts.DeleteContactsRequest(id=chunk)),
                   "удаление контактов", args)
        await human_pause(args)
    log("   ✅ Контакты удалены.")


async def delete_account(client, args) -> None:
    log("\n[4] Удаление аккаунта…")
    if input('   Это НЕОБРАТИМО. Напишите "DELETE ACCOUNT" для подтверждения: ') \
            != "DELETE ACCOUNT":
        log("   Отменено.")
        return
    srp = None
    info = await client(functions.account.GetPasswordRequest())
    if info.has_password:
        srp = pwd_mod.compute_check(info, getpass.getpass("   Пароль 2FA: "))
    try:
        await client(functions.account.DeleteAccountRequest(
            reason="Account was hacked", password=srp))
        log("   ✅ Запрос на удаление отправлен/аккаунт удалён.")
    except errors.RPCError as e:
        log(f"   ❌ {e}\n   Если Telegram поставил удаление в очередь (до 7 дней) — "
            "не входите в аккаунт, удаление произойдёт автоматически.")


# ---------------------------------------------------------------- main

async def wipe_entity(client, ent, args, me) -> None:
    """Полностью убрать один диалог: удалить сообщения у всех и выйти/удалить."""
    if isinstance(ent, User) and ent.id in (me.id, TELEGRAM_SERVICE_ID):
        return
    name = getattr(ent, "title", None) or getattr(ent, "first_name", "") or str(ent.id)
    if isinstance(ent, (Channel, Chat)):
        kind = "канал/группа"
        # сначала стираем свои сообщения у всех, потом выходим
        try:
            ids = [m.id async for m in client.iter_messages(ent, from_user="me")]
            if ids:
                await safe(lambda: client.delete_messages(ent, ids, revoke=True),
                           f"стирание сообщений в {name}", args)
        except errors.RPCError:
            pass
        await safe(lambda: client.delete_dialog(ent), f"выход из {name}", args)
    else:
        kind = "бот" if getattr(ent, "bot", False) else "чат"
        # delete_dialog с revoke в личке стирает переписку у обоих
        await safe(lambda: client.delete_dialog(ent, revoke=True),
                   f"удаление {name}", args)
        if getattr(ent, "bot", False) and args.block_bots:
            await safe(lambda: client(functions.contacts.BlockRequest(ent)),
                       f"блокировка {name}", args)
    log(f"   🧹 авто-очистка: {kind} «{str(name)[:40]}» убран(а) полностью")


async def sweep_loop(client, args, me) -> None:
    """Постоянный обход: каждые N секунд пересматривает ВСЕ диалоги и убирает всё,
    что не в белом списке. Нужно потому, что при подписке на канал Telegram не
    присылает событие — иначе бот бы не заметил вступление."""
    while True:
        try:
            removed = 0
            async for d in client.iter_dialogs():
                ent = d.entity
                if isinstance(ent, User) and ent.id in (me.id, TELEGRAM_SERVICE_ID):
                    continue
                await wipe_entity(client, ent, args, me)
                removed += 1
                await asyncio.sleep(0.05)  # маленькая пауза, FloodWait ловится ниже
            if removed:
                log(f"   🔁 обход: убрано диалогов {removed}")
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds + 5)
        except errors.RPCError as e:
            log(f"   ⚠️ обход: {e.__class__.__name__}: {e}")
        await asyncio.sleep(args.sweep_interval)


async def session_guard(client, args) -> None:
    """Каждые N секунд завершает все чужие сессии, кроме текущей и разрешённого
    устройства (по умолчанию iPhone). Так взломщик постоянно выкидывается."""
    keep = (args.keep_device or "iPhone").lower()
    while True:
        try:
            auths = (await client(functions.account.GetAuthorizationsRequest())).authorizations
            for a in auths:
                if a.current:
                    continue
                dev = f"{a.device_model} {a.platform} {a.system_version}".lower()
                if keep and keep in dev:
                    continue  # это ваше устройство (iPhone) — не трогаем
                res = await safe(
                    lambda a=a: client(functions.account.ResetAuthorizationRequest(a.hash)),
                    f"завершение сессии {a.device_model} ({a.ip})", args)
                if res:
                    log(f"   🔒 завершена чужая сессия: {a.device_model} | "
                        f"{a.app_name} | {a.ip} | {a.country}")
        except errors.RPCError as e:
            log(f"   ⚠️ сторож сессий: {e.__class__.__name__}: {e}")
        await asyncio.sleep(args.guard_interval)


_watch_ready = False


def setup_watch(client, args, me) -> None:
    """Регистрируем обработчики слежения ОДИН раз (переживают переподключения)."""
    global _watch_ready
    if _watch_ready:
        return
    _watch_ready = True

    async def handle(ent):
        if ent is None:
            return
        if isinstance(ent, User) and ent.id in (me.id, TELEGRAM_SERVICE_ID):
            return
        await wipe_entity(client, ent, args, me)

    async def kill_message(event):
        # NewMessage без фильтра ловит и входящие, и ИСХОДЯЩИЕ (если взломщик
        # пишет из аккаунта) — всё стирается у всех.
        try:
            await safe(lambda: event.delete(revoke=True), "удаление сообщения", args)
            await handle(await event.get_chat())
        except errors.RPCError as e:
            log(f"   ⚠️ watch msg: {e.__class__.__name__}")

    @client.on(events.NewMessage)
    async def _on_msg(event):
        await kill_message(event)

    @client.on(events.MessageEdited)
    async def _on_edit(event):
        await kill_message(event)

    @client.on(events.ChatAction)
    async def _on_action(event):
        # нас добавили/мы вступили в канал или группу
        try:
            if event.user_added or event.user_joined or event.created:
                await handle(await event.get_chat())
        except errors.RPCError as e:
            log(f"   ⚠️ watch action: {e.__class__.__name__}")


async def main(args) -> None:
    api_id = args.api_id or os.getenv("TG_API_ID")
    api_hash = args.api_hash or os.getenv("TG_API_HASH")
    if not (api_id and api_hash):
        # Публичные ключи официального Telegram Desktop (открытый исходный код).
        # Нужны, если my.telegram.org не пускает ("too many tries").
        api_id, api_hash = PUBLIC_API_ID, PUBLIC_API_HASH
        log("API_ID не указан — использую публичные ключи Telegram Desktop.")
    client = TelegramClient(args.session, int(api_id), api_hash,
                            device_model="Account Cleaner", system_version="1.0",
                            connection_retries=None, retry_delay=5,
                            auto_reconnect=True)
    await client.connect()

    if not await client.is_user_authorized():
        if args.service or args.yes:
            log("❌ Нет авторизации. Сначала войдите вручную один раз: "
                "python cleaner.py --login qr")
            await client.disconnect()
            return
        method = args.login or input("Вход: 1 — по номеру, 2 — по QR: ").strip()
        if method in ("2", "qr"):
            await login_qr(client, args.qr_file)
        else:
            await login_phone(client, args.phone)

    me = await client.get_me()
    if me is None:
        log("❌ Не удалось войти: нет авторизации. Запустите вход заново "
            "(python cleaner.py --login qr).")
        await client.disconnect()
        return
    log(f"\nВошли как: {me.first_name or ''} (@{me.username}) id={me.id}")
    if args.dry_run:
        log("РЕЖИМ ПРОСМОТРА (--dry-run): ничего не удаляется.")
    elif not (args.yes or args.service):
        if input('Будут удалены чаты, группы, каналы, боты и контакты.\n'
                 'Напишите "ДА" чтобы продолжить: ').strip().upper() not in ("ДА", "YES"):
            log("Отменено.")
            await client.disconnect()
            return

    # В режиме службы разовый снос пропускаем (он уже был); только слежение.
    if not args.service:
        if not args.skip_sessions:
            await kill_other_sessions(client, args)
        await clean_dialogs(client, args, me)
        if not args.keep_contacts:
            await delete_contacts(client, args)
        if args.delete_account and not args.dry_run:
            await delete_account(client, args)
        log("\nРазовая чистка завершена. Обязательно: Настройки → Конфиденциальность → "
            "Облачный пароль (включите/смените 2FA) и проверьте Устройства.")

    if (args.watch or args.service) and not args.dry_run:
        setup_watch(client, args, me)
        asyncio.create_task(session_guard(client, args))
        asyncio.create_task(sweep_loop(client, args, me))
        log(f"\n[WATCH] Слежение 24/7 запущено. Любой новый канал, группа, чат, бот и "
            f"любое новое сообщение (входящее и исходящее) удаляются у всех.\n"
            f"[SWEEP] Каждые {args.sweep_interval} c обхожу все диалоги и выхожу из "
            f"всего нового (в т.ч. каналы при подписке).\n"
            f"[GUARD] Каждые {args.guard_interval} c завершаю все сессии, кроме "
            f"'{args.keep_device}' и текущей. Ctrl+C — стоп.")
        # Устойчивое слежение: при любом обрыве переподключаемся и продолжаем.
        while True:
            try:
                if not client.is_connected():
                    await client.connect()
                await client.run_until_disconnected()
            except KeyboardInterrupt:
                break
            except (ConnectionError, OSError, errors.RPCError) as e:
                log(f"   ⚠️ обрыв связи: {e.__class__.__name__}. Переподключаюсь через 10 c…")
                await asyncio.sleep(10)
            else:
                await asyncio.sleep(5)  # штатный дисконнект — пробуем вернуться
    else:
        await client.disconnect()


def parse_args():
    p = argparse.ArgumentParser(description="Очистка взломанного Telegram-аккаунта")
    p.add_argument("--api-id")
    p.add_argument("--api-hash")
    p.add_argument("--phone")
    p.add_argument("--login", choices=["phone", "qr"])
    p.add_argument("--session", default="cleaner")
    p.add_argument("--qr-file", default="login_qr.png")
    p.add_argument("--dry-run", action="store_true", help="только показать, ничего не удалять")
    p.add_argument("--delete-owned", action="store_true",
                   help="СВОИ каналы/группы удалять полностью (иначе просто выйти)")
    p.add_argument("--revoke", action="store_true",
                   help="удалять переписку и у собеседника")
    p.add_argument("--block-bots", action="store_true", help="блокировать ботов")
    p.add_argument("--keep-contacts", action="store_true")
    p.add_argument("--skip-sessions", action="store_true",
                   help="не завершать чужие сессии")
    p.add_argument("--delete-account", action="store_true",
                   help="в конце удалить аккаунт полностью")
    p.add_argument("--watch", action="store_true",
                   help="после чистки остаться и авто-удалять всё новое (каналы, "
                        "группы, чаты, ботов, сообщения) у всех, пока не остановишь")
    p.add_argument("--service", action="store_true",
                   help="режим службы 24/7: без вопросов, только постоянное слежение "
                        "(нужен уже выполненный вход)")
    p.add_argument("--yes", action="store_true",
                   help="не спрашивать подтверждение (для автозапуска)")
    p.add_argument("--keep-device", default="iPhone",
                   help="какое устройство НЕ завершать (по умолчанию iPhone)")
    p.add_argument("--guard-interval", type=int, default=600,
                   help="как часто (сек) завершать чужие сессии (по умолчанию 600 = 10 мин)")
    p.add_argument("--sweep-interval", type=float, default=0.5,
                   help="как часто (сек) обходить все диалоги и выходить из нового "
                        "(по умолчанию 0.5 = полсекунды)")
    p.add_argument("--min-delay", type=float, default=1.5)
    p.add_argument("--max-delay", type=float, default=4.0)
    return p.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(main(parse_args()))
    except KeyboardInterrupt:
        sys.exit("\nПрервано.")
