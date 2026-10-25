"""/panel — button-driven admin panel: receipts, orders, search, customer card, payment details, rate."""
import os
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message

from ..catalog import (CATEGORIES, CATEGORY_BY_ID, FEATURED, FEATURED_TITLES, SOURCE, load_cached_supplier_catalog,
                       sync_supplier_catalog, tjs_price)
from ..keyboards import PANEL_BUTTON
from ..config import config
from ..db import db, order_code, topup_code
from ..services import admin_order_kb, apply_menu_button, any_method, money, receipt_caption, receipt_kb, user_link
from ..supplier import supplier
from ..web import MEDIA_DIR
from .admin import Broadcast, stats_text

router = Router(name="panel")
router.message.filter(F.from_user.id.in_(config.admin_ids))
router.callback_query.filter(F.from_user.id.in_(config.admin_ids))
B = InlineKeyboardButton

STATUS = {"unpaid": "⏳ интизори пардохт", "processing": "🔄 дар раванд", "done": "✅ иҷро шуд",
          "cancelled": "❌ бекор", "waiting": "⏳ интизори чек", "review": "🧾 дар санҷиш",
          "approved": "✅ тасдиқ", "rejected": "❌ рад"}


class PanelInput(StatesGroup):
    period = State()
    new_admin = State()
    price = State()
    setting = State()
    banner = State()
    usd = State()
    markup = State()
    search = State()
    card = State()
    pay_url = State()
    rate = State()
    say = State()
    balance = State()


def kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])


BACK = B(text="⬅️ Панел", callback_data="ap:main")
CANCEL_HINT = "\n\n/cancel — бекор"


def _dt(ts: int) -> str:
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime("%d.%m %H:%M")


# ---------------------------------------------------------------- main
async def panel_view() -> tuple[str, InlineKeyboardMarkup]:
    receipts = len(await db.topups_by_status("review", 100))
    orders = len(await db.orders_by_status("processing", 100))
    text = "🛠 <b>Панели админ</b>\n\n" + await stats_text()
    return text, kb(
        [B(text="🔍 Ҷустуҷӯи фармоиш / чек / муштарӣ", callback_data="ap:search", style="primary")],
        [B(text=f"🧾 Чекҳо ({receipts})", callback_data="ap:receipts"),
         B(text=f"📦 Фармоишҳо ({orders})", callback_data="ap:orders")],
        [B(text="🗂 Архиви чекҳо (30 рӯз)", callback_data="ap:arch"), B(text="💳 Реквизитҳо", callback_data="ap:pay")],
        [B(text="📊 Ҳисобот", callback_data="ap:rep:today"), B(text="👥 Мизоҷон", callback_data="ap:cl:0")],
        [B(text="📢 Рассылка", callback_data="ap:bc"), B(text=f"💱 Қурби рубл: {config.rub_rate}", callback_data="ap:rate")],
        [B(text=f"💵 Қурби $: {config.usd_rate:g}", callback_data="ap:usd"),
         B(text=f"📈 Наценка: {config.markup:g}%", callback_data="ap:markup")],
        [B(text=f"🛒 Каталог: {SOURCE['name']}", callback_data="ap:sync"), B(text="🖼 Баннерҳо", callback_data="ap:ban")],
        [B(text="🏷 Нархҳо", callback_data="ap:pr"), B(text="⚙️ Танзимот", callback_data="ap:set")],
        [B(text="🛡 Админҳо", callback_data="ap:adm"), B(text="🔄 Навсозӣ", callback_data="ap:main")],
    )


@router.message(Command("panel", "admin"))
@router.message(F.text == PANEL_BUTTON)
async def cmd_panel(message: Message, state: FSMContext):
    await state.clear()
    text, markup = await panel_view()
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "ap:main")
async def cb_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = await panel_view()
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except Exception:  # unchanged text or a photo message
        await call.message.answer(text, reply_markup=markup)
    await call.answer()


# ---------------------------------------------------------------- receipts & orders
@router.callback_query(F.data == "ap:receipts")
async def cb_receipts(call: CallbackQuery):
    topups = await db.topups_by_status("review", 30)
    rows = [[B(text=f"{topup_code(tp['id'])} · {money(tp['amount'])} · {_dt(tp['updated_at'])}",
               callback_data=f"ap:r:{tp['id']}")] for tp in topups]
    rows.append([BACK])
    await call.message.edit_text("🧾 <b>Чекҳо дар санҷиш</b>" + ("" if topups else "\n\nҲама коркард шудаанд ✅"),
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


async def send_receipt(message: Message, topup_id: int):
    topup = await db.get_topup(topup_id)
    if not topup:
        return await message.answer("Ёфт нашуд")
    caption = await receipt_caption(topup)
    caption += f"\n📌 Ҳолат: {STATUS.get(topup['status'], topup['status'])}"
    if topup.get("reject_reason"):
        caption += f"\n📝 {topup['reject_reason']}"
    markup = receipt_kb(topup_id) if topup["status"] in ("waiting", "review") else None
    if topup["receipt_file_id"]:
        await message.answer_photo(topup["receipt_file_id"], caption=caption, reply_markup=markup)
    else:
        await message.answer(caption, reply_markup=markup)


@router.callback_query(F.data.startswith("ap:r:"))
async def cb_receipt(call: CallbackQuery):
    await send_receipt(call.message, int(call.data.split(":")[2]))
    await call.answer()


@router.callback_query(F.data == "ap:orders")
async def cb_orders(call: CallbackQuery):
    orders = await db.orders_by_status("processing", 30)
    rows = [[B(text=f"{order_code(o['id'])} · {o['title'][:28]} · {money(o['amount'])}", callback_data=f"ap:o:{o['id']}")]
            for o in orders]
    rows.append([BACK])
    await call.message.edit_text("📦 <b>Фармоишҳо дар раванд</b>" + ("" if orders else "\n\nҲама иҷро шудаанд ✅"),
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


async def send_order(message: Message, order_id: int):
    order = await db.get_order(order_id)
    if not order:
        return await message.answer("Ёфт нашуд")
    user = await db.get_user(order["user_id"])
    method = "Баланс" if order["method"] == "balance" else (any_method(order["method"]).title
                                                            if any_method(order["method"]) else order["method"])
    text = (f"📦 <b>{order_code(order_id)}</b>\n\n👤 {user_link(user)}\n🛍 {order['title']}\n"
            f"🎮 ID: <code>{order['game_uid']}</code>\n💰 {money(order['amount'])} · {method}\n"
            f"📌 {STATUS.get(order['status'], order['status'])}\n🕒 {_dt(order['created_at'])}")
    if order["note"]:
        text += f"\n📝 {order['note']}"
    rows = admin_order_kb(order_id).inline_keyboard if order["status"] == "processing" else []
    rows = [*rows, [B(text="👤 Муштарӣ", callback_data=f"ap:u:{order['user_id']}")]]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("ap:o:"))
async def cb_order(call: CallbackQuery):
    await send_order(call.message, int(call.data.split(":")[2]))
    await call.answer()


# ---------------------------------------------------------------- search & customer card
@router.callback_query(F.data == "ap:search")
async def cb_search(call: CallbackQuery, state: FSMContext):
    await state.set_state(PanelInput.search)
    await call.message.answer("🔍 Нависед яке аз инҳо:\n• рақами фармоиш: <code>ORD-1001</code> ё <code>1001</code>\n"
                              "• рақами пуркунӣ: <code>TOP-2601</code> ё <code>2601</code>\n• ID-и бозӣ (UID)\n"
                              "• ID-и Telegram ё @username"
                              + CANCEL_HINT)
    await call.answer()


@router.message(PanelInput.search, F.text, ~F.text.startswith("/"))
async def got_search(message: Message, state: FSMContext):
    """Finds anything a customer may quote: ORD-1234 / 1234, TOP-2650 / 2650, game ID, Telegram ID, @username."""
    raw = message.text.strip()
    q = raw.upper().replace(" ", "")
    await state.clear()
    if m := re.fullmatch(r"ORD-?(\d+)", q):
        return await send_order(message, int(m.group(1)) - 1000)
    if m := re.fullmatch(r"TOP-?(\d+)", q):
        return await send_receipt(message, int(m.group(1)) - 2600)
    rows = []
    if q.isdigit():
        n = int(q)
        if n > 1000 and (o := await db.get_order(n - 1000)):
            rows.append([B(text=f"📦 {order_code(o['id'])} · {o['title'][:28]} · {STATUS.get(o['status'], '')}",
                           callback_data=f"ap:o:{o['id']}")])
        if n > 2600 and (tp := await db.get_topup(n - 2600)):
            rows.append([B(text=f"🧾 {topup_code(tp['id'])} · {money(tp['amount'])} · {STATUS.get(tp['status'], '')}",
                           callback_data=f"ap:r:{tp['id']}")])
    for o in await db.orders_by_game_uid(raw.replace(" ", "")):
        rows.append([B(text=f"🎮 {order_code(o['id'])} · ID {o['game_uid']} · {money(o['amount'])} · "
                            f"{STATUS.get(o['status'], '')}", callback_data=f"ap:o:{o['id']}")])
    if user := await db.find_user(raw):
        rows.append([B(text=f"👤 {user.get('first_name') or ''} @{user.get('username') or '-'} · {user['id']}",
                       callback_data=f"ap:u:{user['id']}")])
    if not rows:
        return await message.answer("❌ Ҳеҷ чиз ёфт нашуд.", reply_markup=kb([B(text="🔍 Боз ҷустуҷӯ", callback_data="ap:search")], [BACK]))
    if len(rows) == 1:  # a single match: open it straight away
        data = rows[0][0].callback_data
        kind, ident = data.split(":")[1], int(data.split(":")[2])
        return await {"o": send_order, "r": send_receipt, "u": send_user}[kind](message, ident)
    rows.append([B(text="🔍 Боз ҷустуҷӯ", callback_data="ap:search"), BACK])
    await message.answer(f"🔍 Ёфт шуд: {len(rows) - 1}", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


# ---------------------------------------------------------------- receipt archive (30 days), one by one
ARCHIVE_FILTERS = {"rej": ("rejected", "❌ Радшуда"), "all": (None, "🧾 Ҳама")}


async def _archive_item(flt: str, pos: int):
    status, title = ARCHIVE_FILTERS[flt]
    items = await db.receipts_since(int(time.time()) - 30 * 86400, status)
    if not items:
        return None, title, 0
    pos = max(0, min(pos, len(items) - 1))
    return items[pos], title, len(items), pos


@router.callback_query(F.data == "ap:arch")
async def cb_archive_menu(call: CallbackQuery):
    since = int(time.time()) - 30 * 86400
    rej = len(await db.receipts_since(since, "rejected"))
    total = len(await db.receipts_since(since))
    await call.message.answer("🗂 <b>Архиви чекҳо — 30 рӯзи охир</b>\nЯк-як бо тугмаҳои ◀️ ▶️ дида мешаванд.",
                              reply_markup=kb([B(text=f"❌ Радшуда ({rej})", callback_data="ap:av:rej:0")],
                                              [B(text=f"🧾 Ҳамаи чекҳо ({total})", callback_data="ap:av:all:0")], [BACK]))
    await call.answer()


@router.callback_query(F.data.startswith("ap:av:"))
async def cb_archive_view(call: CallbackQuery):
    _, _, flt, pos = call.data.split(":")
    result = await _archive_item(flt, int(pos))
    if result[0] is None:
        return await call.answer("Дар 30 рӯз чек нест", show_alert=True)
    topup, title, total, pos = result
    caption = f"{title} · {pos + 1}/{total}\n\n" + await receipt_caption(topup)
    caption += f"\n📌 {STATUS.get(topup['status'], topup['status'])} · {_dt(topup['updated_at'])}"
    if topup.get("reject_reason"):
        caption += f"\n📝 {topup['reject_reason']}"
    nav = []
    if pos > 0:
        nav.append(B(text="◀️ Пеш", callback_data=f"ap:av:{flt}:{pos - 1}"))
    nav.append(B(text=f"{pos + 1}/{total}", callback_data="ap:noop"))
    if pos + 1 < total:
        nav.append(B(text="Баъд ▶️", callback_data=f"ap:av:{flt}:{pos + 1}"))
    rows = [nav]
    if topup["status"] in ("waiting", "review"):
        rows += receipt_kb(topup["id"]).inline_keyboard
    rows.append([B(text="👤 Муштарӣ", callback_data=f"ap:u:{topup['user_id']}"), B(text="🗂 Архив", callback_data="ap:arch")])
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    media = InputMediaPhoto(media=topup["receipt_file_id"], caption=caption[:1024])
    try:
        if call.message.photo:  # flip the same message
            await call.message.edit_media(media, reply_markup=markup)
        else:
            await call.message.answer_photo(topup["receipt_file_id"], caption=caption[:1024], reply_markup=markup)
    except Exception:
        await call.message.answer_photo(topup["receipt_file_id"], caption=caption[:1024], reply_markup=markup)
    await call.answer()


@router.callback_query(F.data == "ap:noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()


async def send_user(message: Message, user_id: int):
    u = await db.get_user(user_id)
    if not u:
        return await message.answer("Корбар ёфт нашуд")
    orders = await db.user_orders(user_id, 5)
    topups = await db.user_topups(user_id, 5)
    done = await db.fetchone("SELECT COUNT(*) c FROM orders WHERE user_id=? AND status='done'", user_id)
    lines = [f"👤 <b>Муштарӣ</b>\n\n{user_link(u)}",
             f"💰 Баланс: <b>{money(u['balance'])}</b>", f"🛍 Харидҳо: {done['c']} · {money(u['total_spent'])}",
             f"👥 Даъватшудагон: {await db.referrals_count(user_id)} · бонус {money(u['ref_earned'])}",
             f"🗓 Аз: {_dt(u['created_at'])}" + (" · 🚫 <b>БАН</b>" if u["banned"] else "")]
    if orders:
        lines.append("\n<b>Фармоишҳо:</b>")
        lines += [f"<code>{order_code(o['id'])}</code> {o['title'][:30]} · {money(o['amount'])} · "
                  f"{STATUS.get(o['status'], o['status'])}" for o in orders]
    if topups:
        lines.append("\n<b>Пуркуниҳо:</b>")
        lines += [f"<code>{topup_code(tp['id'])}</code> {money(tp['amount'])} · {STATUS.get(tp['status'], tp['status'])}"
                  for tp in topups]
    await message.answer("\n".join(lines), reply_markup=kb(
        [B(text="💬 Навиштан", callback_data=f"ap:um:{user_id}"), B(text="💰 Баланс", callback_data=f"ap:ub:{user_id}")],
        [B(text="📜 Таърихи пурра", callback_data=f"ap:uh:{user_id}:0"),
         B(text="✅ Анбан" if u["banned"] else "🚫 Бан", callback_data=f"ap:uban:{user_id}")],
        [BACK]))


@router.callback_query(F.data.startswith("ap:u:"))
async def cb_user(call: CallbackQuery):
    await send_user(call.message, int(call.data.split(":")[2]))
    await call.answer()


@router.callback_query(F.data.startswith("ap:uban:"))
async def cb_user_ban(call: CallbackQuery):
    uid = int(call.data.split(":")[2])
    u = await db.get_user(uid)
    if not u:
        return await call.answer("Ёфт нашуд", show_alert=True)
    await db.set_user_field(uid, "banned", 0 if u["banned"] else 1)
    await call.answer("✅ Анбан шуд" if u["banned"] else "🚫 Бан шуд", show_alert=True)
    await send_user(call.message, uid)


@router.callback_query(F.data.startswith("ap:um:"))
async def cb_user_message(call: CallbackQuery, state: FSMContext):
    await state.set_state(PanelInput.say)
    await state.update_data(user_id=int(call.data.split(":")[2]))
    await call.message.answer("💬 Паёмро ба муштарӣ нависед:" + CANCEL_HINT)
    await call.answer()


@router.message(PanelInput.say, F.text, ~F.text.startswith("/"))
async def got_say(message: Message, state: FSMContext, bot: Bot):
    uid = (await state.get_data())["user_id"]
    await state.clear()
    try:
        await bot.send_message(uid, f"💬 <b>Дастгирӣ:</b>\n{message.html_text}")
        await db.notify(uid, f"💬 Дастгирӣ: {message.text}")
        await message.answer("✅ Фиристода шуд")
    except Exception as e:
        await message.answer(f"❌ Фиристода нашуд: {e}")


@router.callback_query(F.data.startswith("ap:ub:"))
async def cb_user_balance(call: CallbackQuery, state: FSMContext):
    await state.set_state(PanelInput.balance)
    await state.update_data(user_id=int(call.data.split(":")[2]))
    await call.message.answer("💰 Чанд илова ё кам кунем? Масалан <code>50</code> ё <code>-20</code>" + CANCEL_HINT)
    await call.answer()


@router.message(PanelInput.balance, F.text, ~F.text.startswith("/"))
async def got_balance(message: Message, state: FSMContext):
    try:
        delta = round(float(message.text.replace(",", ".").replace(" ", "")), 2)
        assert delta != 0 and abs(delta) <= 100000
    except (ValueError, AssertionError):
        return await message.answer("Рақам нависед, масалан 50 ё -20")
    uid = (await state.get_data())["user_id"]
    await state.clear()
    if not await db.change_balance(uid, delta, "admin", f"admin {message.from_user.id}"):
        return await message.answer("❌ Баланс манфӣ мешавад")
    await send_user(message, uid)


# ---------------------------------------------------------------- payment details
async def pay_view() -> tuple[str, InlineKeyboardMarkup]:
    rows = []
    for m in config.all_payment_methods:
        on = config.method_enabled(m)
        state = "✅" if on else ("⚠️" if not m.card.strip() else "⏸")
        rows.append([B(text=f"{state} {m.title} · {m.card or 'рақам нест'}", callback_data=f"ap:pm:{m.id}")])
    rows.append([BACK])
    text = ("💳 <b>Реквизитҳо</b>\n\n✅ — фаъол, ⏸ — хомӯш, ⚠️ — рақам нест (муштарӣ намебинад).\n"
            "Тарзи пардохтро интихоб кунед:")
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "ap:pay")
async def cb_pay(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = await pay_view()
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


def _method_view(method_id: str) -> tuple[str, InlineKeyboardMarkup] | None:
    m = next((x for x in config.all_payment_methods if x.id == method_id), None)
    if not m:
        return None
    on = config.overrides.get(f"enabled:{m.id}", "1") == "1"
    text = (f"💳 <b>{m.title}</b>\n{m.subtitle}\n\n"
            f"Рақам: <code>{m.card or '—'}</code>\n"
            f"Линки пардохт: {'🔗 худкор pay.dc.tj (рақам + маблағ)' if m.id == 'dc' and config.dc_pay_link(m.card, 1, 'x') else (m.pay_url or '—')}\n"
            f"Ҳолат: {'✅ фаъол' if on else '⏸ хомӯш'}" + ("" if m.card.strip() else "\n\n⚠️ То рақам нагузоред, муштарӣ намебинад."))
    return text, kb(
        [B(text="✏️ Рақами корт", callback_data=f"ap:pmc:{m.id}"), B(text="🔗 Линк", callback_data=f"ap:pmu:{m.id}")],
        [B(text="⏸ Хомӯш кардан" if on else "▶️ Фаъол кардан", callback_data=f"ap:pmt:{m.id}")],
        [B(text="⬅️ Реквизитҳо", callback_data="ap:pay")])


@router.callback_query(F.data.startswith("ap:pm:"))
async def cb_method(call: CallbackQuery):
    view = _method_view(call.data.split(":")[2])
    if not view:
        return await call.answer("Ёфт нашуд", show_alert=True)
    await call.message.edit_text(view[0], reply_markup=view[1])
    await call.answer()


@router.callback_query(F.data.startswith("ap:pmt:"))
async def cb_method_toggle(call: CallbackQuery):
    mid = call.data.split(":")[2]
    on = config.overrides.get(f"enabled:{mid}", "1") == "1"
    await db.set_setting(f"enabled:{mid}", "0" if on else "1")
    view = _method_view(mid)
    await call.message.edit_text(view[0], reply_markup=view[1])
    await call.answer("⏸ Хомӯш" if on else "▶️ Фаъол")


@router.callback_query(F.data.startswith("ap:pmc:") | F.data.startswith("ap:pmu:"))
async def cb_method_edit(call: CallbackQuery, state: FSMContext):
    kind, mid = call.data.split(":")[1:]
    await state.set_state(PanelInput.card if kind == "pmc" else PanelInput.pay_url)
    await state.update_data(method_id=mid)
    hint = ("✏️ Рақами нави кортро нависед (масалан <code>927466963</code> ё <code>4444 5555 6666 7777</code>)."
            if kind == "pmc" else "🔗 Линки пардохтро нависед (https://...). Барои нест кардан: <code>-</code>")
    await call.message.answer(hint + CANCEL_HINT)
    await call.answer()


@router.message(PanelInput.card, F.text, ~F.text.startswith("/"))
async def got_card(message: Message, state: FSMContext):
    card = re.sub(r"[^\d +]", "", message.text).strip()
    if len(re.sub(r"\D", "", card)) < 6:
        return await message.answer("Рақам хеле кӯтоҳ аст. Боз нависед:")
    mid = (await state.get_data())["method_id"]
    await state.clear()
    await db.set_setting(f"card:{mid}", card)
    view = _method_view(mid)
    await message.answer("✅ Нигоҳ дошта шуд\n\n" + view[0], reply_markup=view[1])


@router.message(PanelInput.pay_url, F.text, ~F.text.startswith("/"))
async def got_pay_url(message: Message, state: FSMContext):
    url = message.text.strip()
    if url != "-" and not url.startswith("https://"):
        return await message.answer("Линк бояд бо https:// сар шавад. Ё <code>-</code> барои нест кардан.")
    mid = (await state.get_data())["method_id"]
    await state.clear()
    await db.set_setting(f"pay_url:{mid}", "" if url == "-" else url)
    view = _method_view(mid)
    await message.answer("✅ Нигоҳ дошта шуд\n\n" + view[0], reply_markup=view[1])


# ---------------------------------------------------------------- rate & broadcast
@router.callback_query(F.data == "ap:rate")
async def cb_rate(call: CallbackQuery, state: FSMContext):
    await state.set_state(PanelInput.rate)
    await call.message.answer(f"💱 Қурби ҳозира: 1 ₽ = <b>{config.rub_rate}</b> сомонӣ.\n"
                              "Қурби навро нависед, масалан <code>0.1073</code>" + CANCEL_HINT)
    await call.answer()


@router.message(PanelInput.rate, F.text, ~F.text.startswith("/"))
async def got_rate(message: Message, state: FSMContext):
    try:
        rate = float(message.text.replace(",", ".").strip())
        assert 0.01 <= rate <= 1
    except (ValueError, AssertionError):
        return await message.answer("Қурб бояд байни 0.01 ва 1 бошад, масалан 0.1073")
    await state.clear()
    await db.set_setting("rub_rate", str(rate))
    await message.answer(f"✅ Қурби нав: 1 ₽ = {rate} сомонӣ")


@router.callback_query(F.data == "ap:usd")
async def cb_usd(call: CallbackQuery, state: FSMContext):
    await state.set_state(PanelInput.usd)
    await call.message.answer(f"💵 Қурби ҳозира: 1 $ = <b>{config.usd_rate:g}</b> сомонӣ (нархи Donatix бо доллар аст).\n"
                              "Қурби навро нависед, масалан <code>10.95</code>. Барои қурби автоматии Donatix: <code>auto</code>"
                              + CANCEL_HINT)
    await call.answer()


@router.message(PanelInput.usd, F.text, ~F.text.startswith("/"))
async def got_usd(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if text == "auto":
        await db.execute("DELETE FROM settings WHERE key='usd_rate'")
        config.overrides.pop("usd_rate", None)
    else:
        try:
            rate = float(text.replace(",", "."))
            assert 5 <= rate <= 30
        except (ValueError, AssertionError):
            return await message.answer("Қурб бояд байни 5 ва 30 бошад, масалан 10.95")
        await db.set_setting("usd_rate", str(rate))
    await state.clear()
    await message.answer(f"✅ 1 $ = {config.usd_rate:g} сомонӣ. Нархҳо фавран нав шуданд.")


@router.callback_query(F.data == "ap:markup")
async def cb_markup(call: CallbackQuery, state: FSMContext):
    await state.set_state(PanelInput.markup)
    await call.message.answer(f"📈 Наценкаи ҳозира: <b>{config.markup:g}%</b> ба нархи таъминкунанда.\n"
                              "Наценкаи навро нависед, масалан <code>15</code>" + CANCEL_HINT)
    await call.answer()


@router.message(PanelInput.markup, F.text, ~F.text.startswith("/"))
async def got_markup(message: Message, state: FSMContext):
    try:
        markup = float(message.text.replace(",", ".").replace("%", "").strip())
        assert 0 <= markup <= 300
    except (ValueError, AssertionError):
        return await message.answer("Рақам байни 0 ва 300 нависед, масалан 15")
    await state.clear()
    await db.set_setting("markup", str(markup))
    await message.answer(f"✅ Наценка: {markup:g}%. Нархҳо фавран нав шуданд.")


@router.callback_query(F.data == "ap:sync")
async def cb_sync(call: CallbackQuery):
    await call.answer("⏳ Навсозии каталог…")
    try:
        report = await sync_supplier_catalog()
    except Exception as e:
        report = f"❌ {e}"
    await call.message.answer(f"🛒 Каталог: {report}")


# ---------------------------------------------------------------- reports
TZ = ZoneInfo(config.timezone)
PERIODS = {"today": "Имрӯз", "yesterday": "Дирӯз", "7d": "7 рӯз", "30d": "30 рӯз"}


def _period_bounds(key: str) -> tuple[int, int, str]:
    now = datetime.now(TZ)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if key == "yesterday":
        a, b = start_today - timedelta(days=1), start_today
    elif key == "7d":
        a, b = start_today - timedelta(days=6), now + timedelta(seconds=1)
    elif key == "30d":
        a, b = start_today - timedelta(days=29), now + timedelta(seconds=1)
    else:
        a, b = start_today, now + timedelta(seconds=1)
    return int(a.timestamp()), int(b.timestamp()), PERIODS.get(key, key)


async def report_text(since: int, until: int, title: str) -> str:
    r = await db.report(since, until)
    a = datetime.fromtimestamp(since, TZ).strftime("%d.%m.%Y")
    b = datetime.fromtimestamp(until - 1, TZ).strftime("%d.%m.%Y")
    cost = r["cost_usd"] * config.usd_rate
    lines = [f"📊 <b>Ҳисобот: {title}</b>", f"🗓 {a}" + (f" — {b}" if a != b else ""), "",
             f"✅ Фармоишҳои иҷрошуда: <b>{r['orders']}</b> ({r['buyers']} харидор)",
             f"💰 Гардиш: <b>{money(r['revenue'])}</b>"]
    if r["cost_usd"]:
        lines.append(f"💵 Хароҷоти Donatix: ${r['cost_usd']:.2f} ≈ {money(cost)}")
        lines.append(f"📈 Фоидаи тахминӣ: <b>{money(r['revenue'] - cost)}</b>"
                     + (" (баъзе фармоишҳо бе нарх)" if r["unknown_cost"] else ""))
    lines += [f"❌ Бекоршуда: {r['cancelled']}",
              f"🧾 Пуркуниҳо: {r['topups']['c']} · {money(r['topups']['s'])} · рад: {r['rejected']}",
              f"👥 Корбарони нав: {r['new_users']}"]
    if r["top"]:
        lines.append("\n🏆 <b>Маҳсулоти беҳтарин:</b>")
        lines += [f"{i + 1}. {name} — {qty} адад" for i, (name, qty) in enumerate(r["top"])]
    return "\n".join(lines)


def _report_kb() -> InlineKeyboardMarkup:
    return kb([B(text=v, callback_data=f"ap:rep:{k}") for k, v in list(PERIODS.items())[:2]],
              [B(text=v, callback_data=f"ap:rep:{k}") for k, v in list(PERIODS.items())[2:]],
              [B(text="📅 Давраи дилхоҳ", callback_data="ap:repc")], [BACK])


@router.callback_query(F.data.startswith("ap:rep:"))
async def cb_report(call: CallbackQuery):
    since, until, title = _period_bounds(call.data.split(":")[2])
    try:
        await call.message.edit_text(await report_text(since, until, title), reply_markup=_report_kb())
    except Exception:
        await call.message.answer(await report_text(since, until, title), reply_markup=_report_kb())
    await call.answer()


@router.callback_query(F.data == "ap:repc")
async def cb_report_custom(call: CallbackQuery, state: FSMContext):
    await state.set_state(PanelInput.period)
    await call.message.answer("📅 Давраро нависед: <code>01.10.2026 - 25.10.2026</code>\n"
                              "(ё як рӯз: <code>20.10.2026</code>)" + CANCEL_HINT)
    await call.answer()


@router.message(PanelInput.period, F.text, ~F.text.startswith("/"))
async def got_period(message: Message, state: FSMContext):
    dates = re.findall(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?", message.text)
    try:
        parsed = []
        for d, m, y in dates[:2]:
            year = int(y) + (2000 if y and len(y) == 2 else 0) if y else datetime.now(TZ).year
            parsed.append(datetime(year, int(m), int(d), tzinfo=TZ))
        assert parsed
    except (ValueError, AssertionError):
        return await message.answer("Санаро дуруст нависед, масалан 01.10.2026 - 25.10.2026")
    a, b = min(parsed), max(parsed) + timedelta(days=1)
    await state.clear()
    await message.answer(await report_text(int(a.timestamp()), int(b.timestamp()), "давраи интихобшуда"),
                         reply_markup=_report_kb())


# ---------------------------------------------------------------- customers
@router.callback_query(F.data.startswith("ap:cl:"))
async def cb_clients(call: CallbackQuery):
    page = int(call.data.split(":")[2])
    total = await db.count_users()
    users = await db.users_page(page * 10, 10)
    rows = [[B(text=f"{(u['first_name'] or '')[:14]} @{u['username'] or '-'} · {u['balance']:.2f} см · {u['done_orders']} 🛍"
                    + (" 🚫" if u["banned"] else ""), callback_data=f"ap:u:{u['id']}")] for u in users]
    nav = []
    if page > 0:
        nav.append(B(text="◀️", callback_data=f"ap:cl:{page - 1}"))
    nav.append(B(text=f"{page + 1}/{max(1, -(-total // 10))}", callback_data="ap:noop"))
    if (page + 1) * 10 < total:
        nav.append(B(text="▶️", callback_data=f"ap:cl:{page + 1}"))
    rows += [nav, [B(text="🔍 Ҷустуҷӯ (ID / @username)", callback_data="ap:search")], [BACK]]
    text = f"👥 <b>Мизоҷон</b> — ҳамагӣ {total}\nНав аввал. Барои карточка пахш кунед."
    try:
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


HISTORY_ICON = {"order": "📦", "topup": "🧾", "tx": "💰"}
TX_NAMES = {"topup": "пуркунӣ", "purchase": "харид", "refund": "бозгашт", "referral": "бонуси ҳамкорӣ",
            "admin": "аз ҷониби админ"}


@router.callback_query(F.data.startswith("ap:uh:"))
async def cb_user_history(call: CallbackQuery):
    _, _, uid, page = call.data.split(":")
    uid, page = int(uid), int(page)
    rows = await db.user_history(uid, page * 15, 16)
    more = len(rows) > 15
    lines = []
    for r in rows[:15]:
        when = _dt(r["ts"])
        if r["kind"] == "order":
            lines.append(f"📦 <code>{order_code(r['id'])}</code> {r['info'][:28]} · {money(r['amount'])} · "
                         f"{STATUS.get(r['status'], r['status'])} · {when}")
        elif r["kind"] == "topup":
            lines.append(f"🧾 <code>{topup_code(r['id'])}</code> {money(r['amount'])} · "
                         f"{STATUS.get(r['status'], r['status'])} · {when}")
        else:
            lines.append(f"💰 {'+' if r['amount'] > 0 else ''}{r['amount']:.2f} см · {TX_NAMES.get(r['status'], r['status'])}"
                         f" {r['info'] or ''} · {when}")
    nav = []
    if page > 0:
        nav.append(B(text="◀️", callback_data=f"ap:uh:{uid}:{page - 1}"))
    if more:
        nav.append(B(text="▶️", callback_data=f"ap:uh:{uid}:{page + 1}"))
    markup = InlineKeyboardMarkup(inline_keyboard=[*([nav] if nav else []),
                                                   [B(text="👤 Карточка", callback_data=f"ap:u:{uid}"),
                                                    B(text="💰 Баланс ±", callback_data=f"ap:ub:{uid}")]])
    text = f"📜 <b>Таърих</b> · <code>{uid}</code> · саҳ. {page + 1}\n\n" + ("\n".join(lines) or "Холӣ")
    await call.message.answer(text, reply_markup=markup)
    await call.answer()


# ---------------------------------------------------------------- admins
def _owner_id() -> int:
    claimed = config.overrides.get("owner_claimed", "")
    return int(claimed) if claimed.isdigit() else (config.admin_ids[0] if config.admin_ids else 0)


async def _admins_view(bot: Bot) -> tuple[str, InlineKeyboardMarkup]:
    env_admins = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()}
    rows, lines = [], []
    for aid in config.admin_ids:
        u = await db.get_user(aid)
        name = f"{u['first_name'] or ''} @{u['username'] or '-'}" if u else "ҳоло /start накардааст"
        tag = " 👑" if aid == _owner_id() else (" (.env)" if aid in env_admins else "")
        lines.append(f"• <code>{aid}</code> {name}{tag}")
        if aid != _owner_id() and aid not in env_admins:
            rows.append([B(text=f"➖ {aid}", callback_data=f"ap:admdel:{aid}")])
    rows += [[B(text="➕ Админи нав (ID)", callback_data="ap:admadd")], [BACK]]
    return "🛡 <b>Админҳо</b>\n\n" + "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "ap:adm")
async def cb_admins(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    text, markup = await _admins_view(bot)
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


@router.callback_query(F.data == "ap:admadd")
async def cb_admin_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(PanelInput.new_admin)
    await call.message.answer("➕ ID-и Telegram-и админи навро нависед (бо /id дар бот мегиранд):" + CANCEL_HINT)
    await call.answer()


@router.message(PanelInput.new_admin, F.text, ~F.text.startswith("/"))
async def got_admin(message: Message, state: FSMContext, bot: Bot):
    value = message.text.strip()
    if not re.fullmatch(r"\d{5,15}", value):
        return await message.answer("ID бояд танҳо рақам бошад, масалан 6735922033")
    await state.clear()
    await db.add_admin(int(value))
    try:
        await bot.send_message(int(value), "✅ Ба шумо дастрасии админ дода шуд. /start ва баъд «🛠 Панел».")
    except Exception:
        pass
    text, markup = await _admins_view(bot)
    await message.answer("✅ Илова шуд\n\n" + text, reply_markup=markup)


@router.callback_query(F.data.startswith("ap:admdel:"))
async def cb_admin_del(call: CallbackQuery, bot: Bot):
    aid = int(call.data.split(":")[2])
    if aid == _owner_id():
        return await call.answer("Соҳибро нест кардан мумкин нест", show_alert=True)
    await db.remove_admin(aid)
    text, markup = await _admins_view(bot)
    await call.message.edit_text("➖ Нест карда шуд\n\n" + text, reply_markup=markup)
    await call.answer()


# ---------------------------------------------------------------- prices: supplier cost, auto price, manual price
PRICE_GROUPS = [("featured", "⭐ Асосӣ"), ("ff_regions", "🔥 Free Fire — регионҳо"), ("games", "🎮 Бозиҳо"),
                ("services", "💠 Хизматрасониҳо"), ("telegram", "✈️ Telegram")]


def _price_parts(p: dict, overrides: dict) -> dict:
    o = overrides.get(p["id"])
    cost = p["price_usd"] * config.usd_rate if "price_usd" in p else None
    auto = tjs_price(p)
    manual = o["price"] if o and o["price"] is not None else None
    hidden = (o and not o["active"]) or (p.get("kind") == "other" and not o)
    return {"cost": cost, "auto": auto, "manual": manual, "price": manual if manual is not None else auto,
            "hidden": bool(hidden)}


@router.callback_query(F.data == "ap:pr")
async def cb_prices(call: CallbackQuery, state: FSMContext):
    await state.clear()
    rows = [[B(text=f"{title} ({sum(1 for c in CATEGORIES if c['group'] == g)})", callback_data=f"ap:prg:{g}:0")]
            for g, title in PRICE_GROUPS if any(c["group"] == g for c in CATEGORIES)]
    rows.append([BACK])
    await call.message.edit_text(f"🏷 <b>Нархҳо</b>\n\nҚурби $: {config.usd_rate:g} · наценка {config.markup:g}%\n"
                                 "Гурӯҳро интихоб кунед:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("ap:prg:"))
async def cb_prices_group(call: CallbackQuery):
    _, _, group, page = call.data.split(":")
    page = int(page)
    cats = [c for c in CATEGORIES if c["group"] == group]
    chunk = cats[page * 12:(page + 1) * 12]
    rows = [[B(text=f"{c['title']} ({len(c['products'])})", callback_data=f"ap:prc:{c['id']}:0")] for c in chunk]
    nav = []
    if page > 0:
        nav.append(B(text="◀️", callback_data=f"ap:prg:{group}:{page - 1}"))
    if (page + 1) * 12 < len(cats):
        nav.append(B(text="▶️", callback_data=f"ap:prg:{group}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([B(text="⬅️ Нархҳо", callback_data="ap:pr")])
    await call.message.edit_text("🏷 Бозиро интихоб кунед:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("ap:prc:"))
async def cb_prices_category(call: CallbackQuery):
    _, _, cat_id, page = call.data.split(":")
    page = int(page)
    cat = CATEGORY_BY_ID.get(cat_id)
    if not cat:
        return await call.answer("Ёфт нашуд", show_alert=True)
    overrides = await db.price_overrides()
    products = cat["products"]
    rows = []
    for i in range(page * 20, min(len(products), (page + 1) * 20)):
        parts = _price_parts(products[i], overrides)
        mark = "🚫 " if parts["hidden"] else ("✏️ " if parts["manual"] is not None else "")
        rows.append([B(text=f"{mark}{products[i]['title'][:30]} · {parts['price']:.2f}",
                       callback_data=f"ap:prp:{cat_id}:{i}")])
    nav = []
    if page > 0:
        nav.append(B(text="◀️", callback_data=f"ap:prc:{cat_id}:{page - 1}"))
    if (page + 1) * 20 < len(products):
        nav.append(B(text="▶️", callback_data=f"ap:prc:{cat_id}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([B(text="⬅️", callback_data=f"ap:prg:{cat['group']}:0")])
    await call.message.edit_text(f"🏷 <b>{cat['title']}</b>\n✏️ — нархи дастӣ, 🚫 — пинҳон.\nМаҳсулотро интихоб кунед:",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


async def _product_view(cat_id: str, idx: int) -> tuple[str, InlineKeyboardMarkup] | None:
    cat = CATEGORY_BY_ID.get(cat_id)
    if not cat or idx >= len(cat["products"]):
        return None
    p = cat["products"][idx]
    parts = _price_parts(p, await db.price_overrides())
    lines = [f"📦 <b>{p['title']}</b> ({cat['title']})", f"<code>{p['id']}</code>", ""]
    if parts["cost"] is not None:
        lines.append(f"💵 Нархи Donatix: <b>${p['price_usd']:.4f}</b> = {parts['cost']:.2f} см (қурби {config.usd_rate:g})")
    lines.append(f"📈 Нархи автоматӣ{f' (+{config.markup:g}%)' if parts['cost'] is not None else ''}: {parts['auto']:.2f} см")
    if parts["manual"] is not None:
        lines.append(f"✏️ Нархи дастӣ: <b>{parts['manual']:.2f} см</b>")
    lines.append(f"🏷 Муштарӣ мебинад: <b>{parts['price']:.2f} см</b>" + (" — 🚫 пинҳон" if parts["hidden"] else ""))
    if parts["cost"] is not None:
        profit = parts["price"] - parts["cost"]
        lines.append(f"💰 Фоида: <b>{profit:+.2f} см</b>" + ("  ⚠️ зиён!" if profit < 0 else ""))
    rows = [[B(text="✏️ Нархи дастӣ", callback_data=f"ap:prs:{cat_id}:{idx}")]]
    if parts["manual"] is not None:
        rows.append([B(text="🔄 Нархи автоматӣ", callback_data=f"ap:pra:{cat_id}:{idx}")])
    rows.append([B(text="👁 Нишон додан" if parts["hidden"] else "🚫 Пинҳон кардан", callback_data=f"ap:prh:{cat_id}:{idx}")])
    rows.append([B(text="⬅️", callback_data=f"ap:prc:{cat_id}:{idx // 20}")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("ap:prp:"))
async def cb_price_product(call: CallbackQuery):
    _, _, cat_id, idx = call.data.split(":")
    view = await _product_view(cat_id, int(idx))
    if not view:
        return await call.answer("Ёфт нашуд", show_alert=True)
    await call.message.edit_text(view[0], reply_markup=view[1])
    await call.answer()


@router.callback_query(F.data.startswith("ap:prs:"))
async def cb_price_set(call: CallbackQuery, state: FSMContext):
    _, _, cat_id, idx = call.data.split(":")
    cat = CATEGORY_BY_ID.get(cat_id)
    if not cat or int(idx) >= len(cat["products"]):
        return await call.answer("Ёфт нашуд", show_alert=True)
    await state.set_state(PanelInput.price)
    await state.update_data(cat_id=cat_id, idx=int(idx), product_id=cat["products"][int(idx)]["id"])
    await call.message.answer(f"✏️ Нархи навро барои <b>{cat['products'][int(idx)]['title']}</b> бо сомонӣ нависед, "
                              "масалан <code>45.50</code>" + CANCEL_HINT)
    await call.answer()


@router.message(PanelInput.price, F.text, ~F.text.startswith("/"))
async def got_price(message: Message, state: FSMContext):
    try:
        price = round(float(message.text.replace(",", ".").replace(" ", "")), 2)
        assert 0.1 <= price <= 100000
    except (ValueError, AssertionError):
        return await message.answer("Нархро дуруст нависед, масалан 45.50")
    data = await state.get_data()
    await state.clear()
    await db.set_price(data["product_id"], price=price)
    view = await _product_view(data["cat_id"], data["idx"])
    await message.answer("✅ Нарх нигоҳ дошта шуд\n\n" + view[0], reply_markup=view[1])


@router.callback_query(F.data.startswith("ap:pra:") | F.data.startswith("ap:prh:"))
async def cb_price_toggle(call: CallbackQuery):
    _, action, cat_id, idx = call.data.split(":")
    cat = CATEGORY_BY_ID.get(cat_id)
    if not cat or int(idx) >= len(cat["products"]):
        return await call.answer("Ёфт нашуд", show_alert=True)
    p = cat["products"][int(idx)]
    if action == "pra":
        await db.clear_price(p["id"])
    else:
        hidden = _price_parts(p, await db.price_overrides())["hidden"]
        await db.set_price(p["id"], active=1 if hidden else 0)
    view = await _product_view(cat_id, int(idx))
    await call.message.edit_text(view[0], reply_markup=view[1])
    await call.answer("✅")


# ---------------------------------------------------------------- settings: links, channel, API key
SETTING_PROMPTS = {
    "support_url": "📞 Линки дастгирӣ: <code>@username</code> ё <code>https://t.me/...</code>",
    "reviews_url": "⭐ Линки канал/шарҳҳо: <code>@channel</code> ё <code>https://t.me/...</code>",
    "sub_channel": ("📢 Канали обунаи ҳатмӣ: <code>@channel</code>\n"
                    "Аввал ботро ба канал ҳамчун <b>админ</b> илова кунед, вагарна санҷида наметавонад."),
    "shop_name": "🏷 Номи нави мағоза (масалан <code>NEMAT DONAT</code>), то 32 ҳарф",
    "supplier_api_key": "🔑 Калиди нави Donatix API (<code>dx_live_…</code>). Паём баъд аз сабт нест карда мешавад.",
}


def _settings_view() -> tuple[str, InlineKeyboardMarkup]:
    o = config.overrides
    sub_on = o.get("sub_required") == "1"
    key = o.get("supplier_api_key") or config.supplier_api_key
    cents = config.unique_cents
    text = ("⚙️ <b>Танзимот</b>\n\n"
            f"🏷 Ном: <b>{config.shop_name}</b>\n"
            f"🪙 Тиинҳои тасодуфӣ дар дархост: {'✅ фаъол (10.77)' if cents else '❌ хомӯш (10.00)'}\n"
            f"🛍 Тугмаи «Мағоза» (чапи майдони паём): {'✅ фаъол' if config.menu_button else '❌ хомӯш'}\n"
            f"📞 Дастгирӣ: {config.support_url}\n"
            f"⭐ Канал/шарҳҳо: {config.reviews_url}\n"
            f"📢 Обунаи ҳатмӣ: {('✅ ' + o.get('sub_channel', '')) if sub_on and o.get('sub_channel') else '❌ хомӯш'}\n"
            f"🔑 Donatix API: {('…' + key[-4:]) if key else 'нест'} · {supplier.name}")
    return text, kb(
        [B(text="📞 Дастгирӣ", callback_data="ap:sv:support_url"), B(text="⭐ Канал", callback_data="ap:sv:reviews_url")],
        [B(text="📢 Канали обуна", callback_data="ap:sv:sub_channel"),
         B(text="⏸ Обунаро хомӯш" if sub_on else "▶️ Обунаро фаъол", callback_data="ap:subt")],
        [B(text="🏷 Номи мағоза", callback_data="ap:sv:shop_name"),
         B(text="🪙 Тиинҳо: " + ("хомӯш кун" if cents else "фаъол кун"), callback_data="ap:cents")],
        [B(text="🛍 Мағоза: " + ("хомӯш кун" if config.menu_button else "фаъол кун"), callback_data="ap:menubtn")],
        [B(text="🔑 Donatix API", callback_data="ap:sv:supplier_api_key")],
        [BACK])


@router.callback_query(F.data == "ap:set")
async def cb_settings(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = _settings_view()
    await call.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    await call.answer()


@router.callback_query(F.data.startswith("ap:sv:"))
async def cb_setting_edit(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":", 2)[2]
    await state.set_state(PanelInput.setting)
    await state.update_data(key=key)
    await call.message.answer(SETTING_PROMPTS[key] + CANCEL_HINT)
    await call.answer()


def _tg_link(value: str) -> str | None:
    v = value.strip()
    if re.fullmatch(r"@[A-Za-z0-9_]{4,32}", v):
        return f"https://t.me/{v[1:]}"
    if re.fullmatch(r"https://[^\s<>\"']+", v):
        return v
    return None


@router.message(PanelInput.setting, F.text, ~F.text.startswith("/"))
async def got_setting(message: Message, state: FSMContext, bot: Bot):
    key = (await state.get_data())["key"]
    value = message.text.strip()
    if key == "shop_name":
        name = re.sub(r"\s+", " ", value)[:32]
        if len(name) < 2 or "<" in name or ">" in name:
            return await message.answer("Ном нодуруст. Боз нависед:")
        await db.set_setting("shop_name", name)
    elif key in ("support_url", "reviews_url"):
        link = _tg_link(value)
        if not link:
            return await message.answer("Линк нодуруст. Масалан @username ё https://t.me/username")
        await db.set_setting(key, link)
    elif key == "sub_channel":
        m = re.fullmatch(r"(?:https://t\.me/|@)?([A-Za-z0-9_]{4,32})", value)
        channel = f"@{m.group(1)}" if m else value if re.fullmatch(r"-100\d{6,}", value) else ""
        if not channel:
            return await message.answer("Канал нодуруст. Масалан @mychannel")
        try:
            me = await bot.me()
            member = await bot.get_chat_member(channel, me.id)
            if member.status not in ("administrator", "creator"):
                return await message.answer(f"⚠️ Бот дар {channel} админ нест. Ботро админ кунед ва боз фиристед.")
        except Exception as e:
            return await message.answer(f"⚠️ Каналро ёфта натавонистам ё бот админ нест: {str(e)[:120]}")
        await db.set_setting("sub_channel", channel)
        await db.set_setting("sub_required", "1")
    elif key == "supplier_api_key":
        try:
            await message.delete()  # don't leave the key in the chat
        except Exception:
            pass
        if not re.fullmatch(r"dx_[A-Za-z0-9_]{6,}", value):
            return await message.answer("Калид нодуруст. Бояд бо dx_ сар шавад.")
        old = supplier.impl
        supplier.configure(value)
        balance = await supplier.balance_usd()
        if balance is None:
            await supplier.impl.close()
            supplier.impl = old
            return await message.answer("❌ Donatix ин калидро қабул накард (ё дастрас нест). Калиди кӯҳна монд.")
        await old.close()
        await db.set_setting("supplier_api_key", value)
        await message.answer(f"✅ Калид сабт шуд. Баланси Donatix: {balance:.2f} USD. Каталог нав мешавад…")
        try:
            await message.answer(f"🛒 {await sync_supplier_catalog()}")
        except Exception as e:
            await message.answer(f"⚠️ Каталог: {str(e)[:150]}")
    await state.clear()
    text, markup = _settings_view()
    await message.answer("✅ Нигоҳ дошта шуд\n\n" + text, reply_markup=markup, disable_web_page_preview=True)


@router.callback_query(F.data == "ap:menubtn")
async def cb_menu_button(call: CallbackQuery, bot: Bot):
    if not config.menu_button and not config.webapp_url.startswith("https://"):
        return await call.answer("Мини-апп суроғаи https надорад", show_alert=True)
    await db.set_setting("menu_button", "0" if config.menu_button else "1")
    await apply_menu_button(bot)
    text, markup = _settings_view()
    await call.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    await call.answer("Барои дидан чатро аз нав кушоед")


@router.callback_query(F.data == "ap:cents")
async def cb_cents_toggle(call: CallbackQuery):
    await db.set_setting("unique_cents", "0" if config.unique_cents else "1")
    text, markup = _settings_view()
    await call.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    await call.answer()


@router.callback_query(F.data == "ap:subt")
async def cb_sub_toggle(call: CallbackQuery):
    if not config.overrides.get("sub_channel"):
        return await call.answer("Аввал канали обунаро гузоред", show_alert=True)
    on = config.overrides.get("sub_required") == "1"
    await db.set_setting("sub_required", "0" if on else "1")
    text, markup = _settings_view()
    await call.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    await call.answer("⏸ Хомӯш" if on else "▶️ Фаъол")


# ---------------------------------------------------------------- home-screen banners
BANNER_HINT = ("🖼 Расми баннерро барои <b>{title}</b> фиристед.\n\n"
               "• Андоза: <b>1600×500</b> (таносуби 16:5), ҷои матн — тарафи чап торик бошад\n"
               "• Беҳтар ҳамчун <b>файл</b> (📎 → Файл), то сифат паст нашавад\n"
               "• JPG / PNG / WEBP, то 5 МБ")


def _slot_view() -> tuple[str, InlineKeyboardMarkup]:
    rows = []
    for slot, title in FEATURED_TITLES.items():
        has = "🖼" if config.overrides.get(f"banner:{slot}") else "▫️"
        cat = CATEGORY_BY_ID.get(slot)
        rows.append([B(text=f"{has} {title}" + ("" if cat else " — ⚠️ нест"), callback_data=f"ap:bs:{slot}")])
    rows.append([BACK])
    text = ("🖼 <b>Баннерҳои саҳифаи асосӣ</b>\n\n🖼 — расми шумо, ▫️ — расми стандартии бот.\n"
            "⚠️ нест — категория худкор ёфт нашуд, онро дастӣ интихоб кунед.")
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "ap:ban")
async def cb_banners(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = _slot_view()
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


@router.callback_query(F.data.startswith("ap:bs:"))
async def cb_banner_slot(call: CallbackQuery):
    slot = call.data.split(":")[2]
    cat = CATEGORY_BY_ID.get(slot)
    text = (f"🖼 <b>{FEATURED_TITLES.get(slot, slot)}</b>\n\nКатегория: {cat['title'] + ' (' + str(len(cat['products'])) + ' маҳсулот)' if cat else '⚠️ интихоб нашудааст'}\n"
            f"Расм: {'гузошта шуд' if config.overrides.get(f'banner:{slot}') else 'стандартӣ'}")
    rows = [[B(text="📤 Расми нав", callback_data=f"ap:bu:{slot}")]]
    if config.overrides.get(f"banner:{slot}"):
        rows.append([B(text="🗑 Расмро нест кардан", callback_data=f"ap:bd:{slot}")])
    if SOURCE["name"].startswith("supplier"):
        rows.append([B(text="📌 Категорияро интихоб кардан", callback_data=f"ap:bp:{slot}:0")])
    rows.append([B(text="⬅️ Баннерҳо", callback_data="ap:ban")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("ap:bu:"))
async def cb_banner_upload(call: CallbackQuery, state: FSMContext):
    slot = call.data.split(":")[2]
    await state.set_state(PanelInput.banner)
    await state.update_data(slot=slot)
    await call.message.answer(BANNER_HINT.format(title=FEATURED_TITLES.get(slot, slot)) + CANCEL_HINT)
    await call.answer()


@router.message(PanelInput.banner, F.photo | F.document)
async def got_banner(message: Message, state: FSMContext, bot: Bot):
    if message.document:
        doc = message.document
        ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(doc.mime_type or "")
        if not ext:
            return await message.answer("Танҳо JPG, PNG ё WEBP. Боз фиристед:")
        if (doc.file_size or 0) > 5 * 1024 * 1024:
            return await message.answer("Файл аз 5 МБ калон аст. Хурдтар фиристед:")
        file_id = doc.file_id
    else:
        ext, file_id = "jpg", message.photo[-1].file_id
    slot = (await state.get_data())["slot"]
    await state.clear()
    MEDIA_DIR.mkdir(exist_ok=True)
    for old in MEDIA_DIR.glob(f"banner_{slot}.*"):
        old.unlink()
    path = MEDIA_DIR / f"banner_{slot}.{ext}"
    await bot.download(file_id, destination=path)
    await db.set_setting(f"banner:{slot}", f"/media/{path.name}?v={int(time.time())}")
    text, markup = _slot_view()
    await message.answer("✅ Баннер гузошта шуд. Мини-аппро аз нав кушоед.\n\n" + text, reply_markup=markup)


@router.callback_query(F.data.startswith("ap:bd:"))
async def cb_banner_delete(call: CallbackQuery):
    slot = call.data.split(":")[2]
    for old in MEDIA_DIR.glob(f"banner_{slot}.*"):
        old.unlink()
    await db.execute("DELETE FROM settings WHERE key=?", f"banner:{slot}")
    config.overrides.pop(f"banner:{slot}", None)
    text, markup = _slot_view()
    await call.message.edit_text("🗑 Нест карда шуд.\n\n" + text, reply_markup=markup)
    await call.answer()


@router.callback_query(F.data.startswith("ap:bp:"))
async def cb_banner_pick(call: CallbackQuery):
    """Choose which supplier category sits in a banner slot (when automatic matching guessed wrong)."""
    _, _, slot, page = call.data.split(":")
    page = int(page)
    words = FEATURED[slot][0]
    cats = [c for c in CATEGORIES if any(w in f"{c.get('raw_id', '')} {c['title']}".lower() for w in words)]
    chunk = cats[page * 10:(page + 1) * 10]
    rows = [[B(text=f"{'✅ ' if c['id'] == slot else ''}{c['title']} ({len(c['products'])})",
               callback_data=f"ap:bk:{slot}:{c.get('raw_id', c['id'])}")] for c in chunk]
    nav = []
    if page > 0:
        nav.append(B(text="◀️", callback_data=f"ap:bp:{slot}:{page - 1}"))
    if (page + 1) * 10 < len(cats):
        nav.append(B(text="▶️", callback_data=f"ap:bp:{slot}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([B(text="🔄 Худкор", callback_data=f"ap:bk:{slot}:auto"), B(text="⬅️", callback_data=f"ap:bs:{slot}")])
    await call.message.edit_text(f"📌 Кадом категория дар баннери <b>{FEATURED_TITLES[slot]}</b> бошад?",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("ap:bk:"))
async def cb_banner_pin(call: CallbackQuery):
    _, _, slot, raw_id = call.data.split(":", 3)
    if raw_id == "auto":
        await db.execute("DELETE FROM settings WHERE key=?", f"featured:{slot}")
        config.overrides.pop(f"featured:{slot}", None)
    else:
        for other in FEATURED:  # one category can sit in one slot only
            if config.overrides.get(f"featured:{other}") == raw_id:
                await db.execute("DELETE FROM settings WHERE key=?", f"featured:{other}")
                config.overrides.pop(f"featured:{other}", None)
        await db.set_setting(f"featured:{slot}", raw_id)
    await load_cached_supplier_catalog()
    text, markup = _slot_view()
    await call.message.edit_text("✅ Нигоҳ дошта шуд.\n\n" + text, reply_markup=markup)
    await call.answer()


@router.callback_query(F.data == "ap:bc")
async def cb_broadcast(call: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.waiting)
    await call.message.answer("📢 Паёмро фиристед (матн, расм, видео) — ба ҳамаи корбарон меравад." + CANCEL_HINT)
    await call.answer()
