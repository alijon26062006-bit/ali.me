"""/panel — button-driven admin panel: receipts, orders, search, customer card, payment details, rate."""
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..config import config
from ..db import db, order_code, topup_code
from ..services import admin_order_kb, any_method, money, receipt_caption, receipt_kb, user_link
from .admin import Broadcast, stats_text

router = Router(name="panel")
router.message.filter(F.from_user.id.in_(config.admin_ids))
router.callback_query.filter(F.from_user.id.in_(config.admin_ids))
B = InlineKeyboardButton

STATUS = {"unpaid": "⏳ интизори пардохт", "processing": "🔄 дар раванд", "done": "✅ иҷро шуд",
          "cancelled": "❌ бекор", "waiting": "⏳ интизори чек", "review": "🧾 дар санҷиш",
          "approved": "✅ тасдиқ", "rejected": "❌ рад"}


class PanelInput(StatesGroup):
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


@router.callback_query(F.data == "ap:bc")
async def cb_broadcast(call: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.waiting)
    await call.message.answer("📢 Паёмро фиристед (матн, расм, видео) — ба ҳамаи корбарон меравад." + CANCEL_HINT)
    await call.answer()
