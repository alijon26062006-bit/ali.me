"""/panel — button-driven admin panel: receipts, orders, search, customer card, payment details, rate."""
import re
import time

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..catalog import (CATEGORIES, CATEGORY_BY_ID, FEATURED, FEATURED_TITLES, SOURCE, load_cached_supplier_catalog,
                       sync_supplier_catalog)
from ..config import config
from ..db import db, order_code, topup_code
from ..services import admin_order_kb, any_method, money, receipt_caption, receipt_kb, user_link
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
        [B(text=f"🧾 Чекҳо ({receipts})", callback_data="ap:receipts"),
         B(text=f"📦 Фармоишҳо ({orders})", callback_data="ap:orders")],
        [B(text="🔍 Ҷустуҷӯ", callback_data="ap:search"), B(text="💳 Реквизитҳо", callback_data="ap:pay")],
        [B(text="📢 Рассылка", callback_data="ap:bc"), B(text=f"💱 Қурби рубл: {config.rub_rate}", callback_data="ap:rate")],
        [B(text=f"💵 Қурби $: {config.usd_rate:g}", callback_data="ap:usd"),
         B(text=f"📈 Наценка: {config.markup:g}%", callback_data="ap:markup")],
        [B(text=f"🛒 Каталог: {SOURCE['name']}", callback_data="ap:sync"), B(text="🖼 Баннерҳо", callback_data="ap:ban")],
        [B(text="🔄 Навсозӣ", callback_data="ap:main")],
    )


@router.message(Command("panel", "admin"))
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
    await call.message.answer("🔍 Нависед: <code>ORD-1001</code>, <code>TOP-2601</code>, ID-и Telegram ё @username"
                              + CANCEL_HINT)
    await call.answer()


@router.message(PanelInput.search, F.text, ~F.text.startswith("/"))
async def got_search(message: Message, state: FSMContext):
    q = message.text.strip().upper()
    await state.clear()
    if m := re.fullmatch(r"(?:ORD-?)(\d+)", q):
        return await send_order(message, int(m.group(1)) - 1000)
    if m := re.fullmatch(r"(?:TOP-?)(\d+)", q):
        return await send_receipt(message, int(m.group(1)) - 2600)
    user = await db.find_user(message.text)
    if not user:
        return await message.answer("Ёфт нашуд. Боз /panel → 🔍")
    await send_user(message, user["id"])


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
        [B(text="✅ Анбан" if u["banned"] else "🚫 Бан", callback_data=f"ap:uban:{user_id}")],
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
            f"Рақам: <code>{m.card or '—'}</code>\nЛинки пардохт: {m.pay_url or '—'}\n"
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
