"""Required channel subscription: customers must join the channel set in /panel before they can buy."""
import logging
import time

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from .config import config
from .texts import t

log = logging.getLogger(__name__)
_ok_until: dict[int, float] = {}   # user id -> time until which the last positive check is trusted
_warned_admins = 0.0


def channel_url(channel: str) -> str:
    return f"https://t.me/{channel.lstrip('@')}" if channel.startswith("@") else config.reviews_url


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """True if no channel is required, the user is an admin or a member. If the bot can't check
    (not an admin of the channel), customers are not blocked and admins get a warning."""
    global _warned_admins
    channel = config.sub_channel
    if not channel or user_id in config.admin_ids:
        return True
    if _ok_until.get(user_id, 0) > time.time():
        return True
    try:
        member = await bot.get_chat_member(channel, user_id)
    except Exception as e:
        log.warning("subscription check failed: %s", e)
        if time.time() - _warned_admins > 3600:
            _warned_admins = time.time()
            for admin in config.admin_targets:
                try:
                    await bot.send_message(admin, f"⚠️ Обунаро санҷида натавонистам ({channel}). Ботро ба канал ҳамчун "
                                                  f"<b>админ</b> илова кунед.\n<code>{str(e)[:150]}</code>")
                except Exception:
                    pass
        return True
    ok = member.status not in ("left", "kicked")
    if ok:
        _ok_until[user_id] = time.time() + 600
    return ok


def subscribe_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "sub_join"), url=channel_url(config.sub_channel))],
        [InlineKeyboardButton(text=t(lang, "sub_check"), callback_data="sub:check", style="success")],
    ])


class SubscriptionMiddleware(BaseMiddleware):
    """Stops buying actions (donate menu, products, payment) for users who haven't joined the channel."""

    GUARDED_PREFIXES = ("m:donate", "sg:", "sc:", "sp:", "sm:")

    async def __call__(self, handler, event: TelegramObject, data: dict):
        if not config.sub_channel:
            return await handler(event, data)
        user = data.get("event_from_user")
        guarded = (isinstance(event, CallbackQuery) and (event.data or "").startswith(self.GUARDED_PREFIXES)) or \
                  (isinstance(event, Message) and (event.text or "").startswith("/start"))
        if not user or not guarded or await is_subscribed(data["bot"], user.id):
            return await handler(event, data)
        from .db import db
        u = await db.get_user(user.id)
        lang = u["lang"] if u else "tj"
        if isinstance(event, CallbackQuery):
            await event.answer(t(lang, "sub_need_short"), show_alert=True)
            await event.message.answer(t(lang, "sub_need", channel=config.sub_channel), reply_markup=subscribe_kb(lang))
            return None
        await handler(event, data)  # /start still registers the user and shows the menu…
        if user.id in config.admin_ids:  # e.g. the owner link just made them admin
            return None
        await event.answer(t(lang, "sub_need", channel=config.sub_channel), reply_markup=subscribe_kb(lang))
        return None
