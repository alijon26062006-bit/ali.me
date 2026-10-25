import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiohttp import web

from .catalog import catalog_sync_loop, load_cached_supplier_catalog
from .config import config
from .db import db
from .handlers import admin, panel, shop, user
from .keyboards import reply_menu
from .subscription import SubscriptionMiddleware
from .services import (apply_menu_button, balance_watcher, delivery_worker, receipt_reminder, requeue_unsent_orders,
                       supplier_poller)
from .web import create_app


async def send_panel_buttons(bot: Bot):
    """Gives every admin the bottom «🛠 Панел» button once, without waiting for them to press /start."""
    sent = [x for x in config.overrides.get("panel_kb_sent", "").split(",") if x]
    for admin_id in list(config.admin_ids):
        if str(admin_id) in sent:
            continue
        user = await db.get_user(admin_id)
        lang = user["lang"] if user else "tj"
        try:
            await bot.send_message(admin_id, "🛠 <b>Шумо админи бот ҳастед.</b>\nПанел — тугмаи «🛠 Панел» дар поён ё /panel",
                                   reply_markup=reply_menu(lang, admin_id))
            sent.append(str(admin_id))
        except Exception as e:  # never pressed Start yet: Telegram doesn't let bots write first
            logging.info("panel button for %s not sent: %s", admin_id, e)
    await db.set_setting("panel_kb_sent", ",".join(sent))


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.bot_token:
        raise SystemExit("BOT_TOKEN is not set (see .env.example)")

    await db.connect()
    await load_cached_supplier_catalog()
    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_routers(admin.router, panel.router, shop.router, user.router)  # admin first: its FSM states must win
    dp.message.outer_middleware(SubscriptionMiddleware())
    dp.callback_query.outer_middleware(SubscriptionMiddleware())

    await bot.set_my_commands([BotCommand(command="start", description="Менюи асосӣ")])
    await apply_menu_button(bot)
    await send_panel_buttons(bot)
    if not config.webapp_url.startswith("https://"):
        logging.warning("WEBAPP_URL is not an https:// URL — Mini App buttons are disabled")

    runner = web.AppRunner(create_app(bot))
    await runner.setup()
    await web.TCPSite(runner, config.web_host, config.web_port).start()
    logging.info("Mini App server on http://%s:%s", config.web_host, config.web_port)

    tasks = [asyncio.create_task(supplier_poller(bot)), asyncio.create_task(receipt_reminder(bot)),
             asyncio.create_task(balance_watcher(bot))]
    tasks += [asyncio.create_task(delivery_worker(bot)) for _ in range(3)]
    await requeue_unsent_orders()
    tasks.append(asyncio.create_task(catalog_sync_loop()))
    if not config.admin_ids:
        logging.warning("ADMIN_IDS is empty — receipts will not reach anyone. Send /id to the bot and set ADMIN_IDS.")
    if not config.payment_methods:
        logging.warning("No card numbers configured — set them in /panel → Реквизитҳо")
    try:
        await dp.start_polling(bot)
    finally:
        for task in tasks:
            task.cancel()
        await runner.cleanup()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
