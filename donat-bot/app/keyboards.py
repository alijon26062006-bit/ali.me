from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup,
                           WebAppInfo)

from .catalog import CATEGORIES
from .config import config
from .texts import t


def webapp_button(text: str, path: str = "", **kw) -> InlineKeyboardButton:
    if not config.webapp_url.startswith("https://"):
        return InlineKeyboardButton(text=text, callback_data="m:nowebapp", **kw)
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=f"{config.webapp_url}/{path}"), **kw)


def reply_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=f"📋 {t(lang, 'btn_menu')}")]],
                               resize_keyboard=True, is_persistent=True,
                               input_field_placeholder=t(lang, "placeholder"))


def main_menu(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [b(text=f"🛒 {t(lang, 'btn_donate')}", callback_data="m:donate", style="primary")],
        [webapp_button(f"🛍 {t(lang, 'btn_shop')}")],
        [webapp_button(f"⚙️ {t(lang, 'btn_sens')}", "#/sens")],
        [b(text=f"👤 {t(lang, 'btn_profile')}", callback_data="m:profile"),
         b(text=f"ℹ️ {t(lang, 'btn_about')}", callback_data="m:about")],
        [b(text=f"📞 {t(lang, 'btn_support')}", url=config.support_url)],
        [b(text=f"⭐ {t(lang, 'btn_reviews')}", url=config.reviews_url)],
        [b(text=f"🌐 {t(lang, 'btn_lang')}", callback_data="m:lang"),
         b(text=f"💱 {t(lang, 'btn_currency')}", callback_data="m:cur")],
    ])


GROUP_BUTTONS = [  # (group, icon, title tj, title ru)
    ("ff_regions", "🔥", "Free Fire — дигар регионҳо", "Free Fire — другие регионы"),
    ("games", "🎮", "Дигар бозиҳо", "Другие игры"),
    ("services", "💠", "Хизматрасониҳо", "Сервисы"),
]


def donate_menu(lang: str) -> InlineKeyboardMarkup:
    rows = []
    for cat in CATEGORIES:
        if cat["group"] == "featured":
            rows.append([InlineKeyboardButton(text=f"💎 {cat['title']}", callback_data=f"sc:{cat['id']}")])
    for group, icon, tj, ru in GROUP_BUTTONS:
        count = sum(1 for c in CATEGORIES if c["group"] == group)
        if count:
            rows.append([InlineKeyboardButton(text=f"{icon} {ru if lang == 'ru' else tj} ({count})",
                                              callback_data=f"sg:{group}")])
    if any(c["id"] == "telegram" for c in CATEGORIES):
        rows.append([InlineKeyboardButton(text="✈️ Telegram", callback_data="sc:telegram")])
    rows.append([InlineKeyboardButton(text=f"🏠 {t(lang, 'btn_home')}", callback_data="m:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"⬅️ {t(lang, 'btn_back')}", callback_data="m:home")]])


def lang_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇹🇯 Тоҷикӣ", callback_data="set:lang:tj"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set:lang:ru"),
    ], [InlineKeyboardButton(text="⬅️", callback_data="m:home")]])


def currency_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇹🇯 Сомонӣ (см)", callback_data="set:cur:TJS"),
        InlineKeyboardButton(text="🇷🇺 Рубл (₽)", callback_data="set:cur:RUB"),
    ], [InlineKeyboardButton(text="⬅️", callback_data="m:home")]])
