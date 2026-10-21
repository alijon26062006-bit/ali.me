"""Buying inside the chat (without the Mini App): category -> product -> game ID -> payment method."""
import re

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..catalog import GROUPS, get_catalog, get_product
from ..config import config
from ..db import db
from ..keyboards import GROUP_BUTTONS
from ..services import ShopError, create_order, money
from ..texts import t

router = Router(name="shop")
B = InlineKeyboardButton


class Buy(StatesGroup):
    uid = State()


async def _user(tg_user) -> dict:
    user, _ = await db.upsert_user(tg_user.id, tg_user.username, tg_user.first_name)
    return user


def _group_title(group: str, lang: str) -> str:
    for g, icon, tj, ru in GROUP_BUTTONS:
        if g == group:
            return f"{icon} {ru if lang == 'ru' else tj}"
    return GROUPS.get(group, group)


def _valid_uid(cat: dict, uid: str) -> bool:
    if cat["uid_label"] == "ID-и бозӣ":
        return bool(re.fullmatch(r"\d{5,15}", uid))
    return 3 <= len(uid) <= 64


@router.callback_query(F.data.startswith("sg:"))
async def cb_group(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await _user(call.from_user)
    group = call.data[3:]
    cats = [c for c in await get_catalog() if c["group"] == group]
    buttons = [B(text=c["title"], callback_data=f"sc:{c['id']}") for c in cats]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([B(text=f"⬅️ {t(user['lang'], 'btn_back')}", callback_data="m:donate")])
    await call.message.edit_text(t(user["lang"], "shop_group", title=_group_title(group, user["lang"])),
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("sc:"))
async def cb_category(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await _user(call.from_user)
    parts = call.data.split(":")
    cat = next((c for c in await get_catalog() if c["id"] == parts[1]), None)
    if not cat:
        return await call.answer("—", show_alert=True)
    tab = parts[2] if len(parts) > 2 else cat["tabs"][0]["id"]
    rows = []
    if len(cat["tabs"]) > 1:
        rows.append([B(text=("✅ " if tb["id"] == tab else "") + tb["title"], callback_data=f"sc:{cat['id']}:{tb['id']}")
                     for tb in cat["tabs"]])
    items = [B(text=f"{p['title']} — {money(p['price'])}", callback_data=f"sp:{cat['id']}:{i}")
             for i, p in enumerate(cat["products"]) if p["tab"] == tab]
    rows += [items[i:i + 2] for i in range(0, len(items), 2)] if len(items) > 6 else [[b] for b in items]
    back = f"sg:{cat['group']}" if cat["group"] not in ("featured", "telegram") else "m:donate"
    rows.append([B(text=f"⬅️ {t(user['lang'], 'btn_back')}", callback_data=back)])
    await call.message.edit_text(t(user["lang"], "shop_choose_game", title=cat["title"]),
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("sp:"))
async def cb_product(call: CallbackQuery, state: FSMContext):
    user = await _user(call.from_user)
    _, cat_id, idx = call.data.split(":")
    cat = next((c for c in await get_catalog() if c["id"] == cat_id), None)
    if not cat or not idx.isdigit() or int(idx) >= len(cat["products"]):
        return await call.answer(t(user["lang"], "shop_expired"), show_alert=True)
    product = cat["products"][int(idx)]
    await state.set_state(Buy.uid)
    await state.update_data(product_id=product["id"], cat_id=cat_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[B(text=t(user["lang"], "shop_cancel"), callback_data="sx")]])
    await call.message.edit_text(t(user["lang"], "shop_ask_uid", product=product["title"], price=money(product["price"]),
                                   uid_label=cat["uid_label"], placeholder=cat["uid_placeholder"]), reply_markup=kb)
    await call.answer()


@router.message(Buy.uid, F.text & ~F.text.startswith("/") & ~F.text.endswith("Меню"))
async def got_uid(message: Message, state: FSMContext):
    user = await _user(message.from_user)
    data = await state.get_data()
    product = await get_product(data.get("product_id", ""))
    cat = next((c for c in await get_catalog() if c["id"] == data.get("cat_id")), None)
    if not product or not cat:
        await state.clear()
        return await message.answer(t(user["lang"], "shop_expired"))
    uid = message.text.strip().replace(" ", "")
    if not _valid_uid(cat, uid):
        return await message.answer(t(user["lang"], "shop_bad_uid", uid_label=cat["uid_label"]))
    await state.update_data(uid=uid)
    lang = user["lang"]
    rows = []
    if user["balance"] >= product["price"]:
        rows.append([B(text=t(lang, "shop_from_balance", balance=money(user["balance"])), callback_data="sm:balance",
                       style="success")])
    rows += [[B(text=f"🏦 {m.title}", callback_data=f"sm:{m.id}")] for m in config.payment_methods]
    if not rows:
        await state.clear()
        return await message.answer(t(lang, "no_methods"))
    rows.append([B(text=t(lang, "shop_change_uid"), callback_data=f"sp:{cat['id']}:{_index(cat, product['id'])}"),
                 B(text=t(lang, "shop_cancel"), callback_data="sx")])
    await message.answer(t(lang, "shop_confirm", cat=cat["title"], product=product["title"], uid_label=cat["uid_label"],
                           uid=uid, price=money(product["price"]), balance=money(user["balance"])),
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


def _index(cat: dict, product_id: str) -> int:
    return next((i for i, p in enumerate(cat["products"]) if p["id"] == product_id), 0)


@router.callback_query(F.data.startswith("sm:"))
async def cb_pay(call: CallbackQuery, state: FSMContext, bot: Bot):
    user = await _user(call.from_user)
    data = await state.get_data()
    if not data.get("uid") or not data.get("product_id"):
        return await call.answer(t(user["lang"], "shop_expired"), show_alert=True)
    method = call.data[3:]
    try:
        result = await create_order(bot, user, [{"product_id": data["product_id"]}], data["uid"], method)
    except ShopError as e:
        return await call.answer(str(e), show_alert=True)
    await state.clear()
    key = "shop_created_balance" if result["status"] == "processing" else "shop_created_bank"
    await call.message.edit_text(call.message.html_text + "\n\n" + t(user["lang"], key, order=result["order"]))
    await call.answer()


@router.callback_query(F.data == "sx")
async def cb_cancel(call: CallbackQuery, state: FSMContext):
    user = await _user(call.from_user)
    await state.clear()
    await call.message.edit_text(t(user["lang"], "shop_cancelled"))
    await call.answer()
