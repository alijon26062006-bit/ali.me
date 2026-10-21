import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo
from aiohttp import web

from .config import config
from .db import db
from .handlers import admin, panel, shop, user
from .services import receipt_reminder, supplier_poller
from .web import create_app


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.bot_token:
        raise SystemExit("BOT_TOKEN is not set (see .env.example)")

    await db.connect()
    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_routers(admin.router, panel.router, shop.router, user.router)  # admin first: its FSM states must win

    await bot.set_my_commands([BotCommand(command="start", description="Менюи асосӣ")])
    if config.webapp_url.startswith("https://"):
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Мағоза",
                                                                    web_app=WebAppInfo(url=config.webapp_url + "/")))
    else:
        logging.warning("WEBAPP_URL is not an https:// URL — Mini App buttons are disabled")

    runner = web.AppRunner(create_app(bot))
    await runner.setup()
    await web.TCPSite(runner, config.web_host, config.web_port).start()
    logging.info("Mini App server on http://%s:%s", config.web_host, config.web_port)

    tasks = [asyncio.create_task(supplier_poller(bot)), asyncio.create_task(receipt_reminder(bot))]
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
