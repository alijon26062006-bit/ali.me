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

from telethon import TelegramClient, errors, functions, password as pwd_mod
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
    await client.start(
        phone=phone,
        code_callback=lambda: input("Код из Telegram/SMS: ").strip(),
        password=lambda: getpass.getpass("Пароль 2FA (облачный пароль): "),
    )


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
            await client.sign_in(password=getpass.getpass("Пароль 2FA: "))
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

async def main(args) -> None:
    api_id = args.api_id or os.getenv("TG_API_ID")
    api_hash = args.api_hash or os.getenv("TG_API_HASH")
    if not (api_id and api_hash):
        # Публичные ключи официального Telegram Desktop (открытый исходный код).
        # Нужны, если my.telegram.org не пускает ("too many tries").
        api_id, api_hash = PUBLIC_API_ID, PUBLIC_API_HASH
        log("API_ID не указан — использую публичные ключи Telegram Desktop.")
    client = TelegramClient(args.session, int(api_id), api_hash,
                            device_model="Account Cleaner", system_version="1.0")
    await client.connect()

    if not await client.is_user_authorized():
        method = args.login or input("Вход: 1 — по номеру, 2 — по QR: ").strip()
        if method in ("2", "qr"):
            await login_qr(client, args.qr_file)
        else:
            await login_phone(client, args.phone)

    me = await client.get_me()
    log(f"\nВошли как: {me.first_name or ''} (@{me.username}) id={me.id}")
    if args.dry_run:
        log("РЕЖИМ ПРОСМОТРА (--dry-run): ничего не удаляется.")
    else:
        if input('Будут удалены чаты, группы, каналы, боты и контакты.\n'
                 'Напишите "ДА" чтобы продолжить: ').strip().upper() not in ("ДА", "YES"):
            log("Отменено.")
            await client.disconnect()
            return

    if not args.skip_sessions:
        await kill_other_sessions(client, args)
    await clean_dialogs(client, args, me)
    if not args.keep_contacts:
        await delete_contacts(client, args)
    if args.delete_account and not args.dry_run:
        await delete_account(client, args)

    log("\nГотово. Обязательно: Настройки → Конфиденциальность → Облачный пароль "
        "(включите/смените 2FA) и проверьте Устройства.")
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
    p.add_argument("--min-delay", type=float, default=1.5)
    p.add_argument("--max-delay", type=float, default=4.0)
    return p.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(main(parse_args()))
    except KeyboardInterrupt:
        sys.exit("\nПрервано.")
