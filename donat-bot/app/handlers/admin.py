import asyncio

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ..catalog import PRODUCTS
from ..config import config
from ..db import db, order_code, topup_code
from ..services import approve_topup, complete_order, money, refund_order, reject_topup, start_fulfillment
from ..supplier import supplier

router = Router(name="admin")
router.message.filter(F.from_user.id.in_(config.admin_ids))
router.callback_query.filter(F.from_user.id.in_(config.admin_ids))

HELP = (
    "🛠 <b>Панели админ</b>\n\n"
    "{stats}\n\n"
    "<b>Фармонҳо:</b>\n"
    "/stats — статистика\n"
    "/pending — фармоишҳои интизор\n"
    "/setprice <code>id нарх</code> — нархро иваз кардан\n"
    "/hide <code>id</code> · /show <code>id</code> — пинҳон / нишон додан\n"
    "/products <code>калима</code> — ҷустуҷӯи id\n"
    "/balance <code>user_id ±маблағ</code> — тағйири баланс\n"
    "/ban <code>user_id</code> · /unban <code>user_id</code>\n"
    "/say <code>user_id матн</code> — ҷавоб ба муштарӣ\n"
    "/broadcast — паёмнависии оммавӣ"
)


class Broadcast(StatesGroup):
    waiting = State()


async def stats_text() -> str:
    s = await db.stats()
    return (f"👥 Корбарон: <b>{s['users']}</b> (+{s['users_today']} имрӯз)\n"
            f"✅ Иҷрошуда: <b>{s['orders_done']}</b> · ⏳ Дар раванд: <b>{s['orders_processing']}</b>\n"
            f"🧾 Чекҳо дар санҷиш: <b>{s['topups_review']}</b>\n"
            f"💰 Гардиш: <b>{money(s['revenue'])}</b> (имрӯз {money(s['revenue_today'])})\n"
            f"👛 Балансҳои корбарон: <b>{money(s['balances'])}</b>\n"
            f"🔌 Таъминкунанда: <b>{'API' if supplier.enabled else 'дастӣ'}</b> · баланс {await supplier.balance()}")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer(HELP.format(stats=await stats_text()))


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    await message.answer(await stats_text())


@router.message(Command("pending"))
async def cmd_pending(message: Message):
    orders = await db.orders_by_status("processing", 30)
    if not orders:
        return await message.answer("Фармоиши интизор нест ✅")
    lines = [f"<code>{order_code(o['id'])}</code> · {o['title']} · <code>{o['game_uid']}</code> · {money(o['amount'])}"
             for o in orders]
    await message.answer("⏳ <b>Дар раванд:</b>\n\n" + "\n".join(lines))


@router.message(Command("products"))
async def cmd_products(message: Message, command: CommandObject):
    q = (command.args or "").lower()
    found = [p for p in PRODUCTS.values() if q in p["id"] or q in p["title"].lower()][:40]
    await message.answer("\n".join(f"<code>{p['id']}</code> — {p['title']}" for p in found) or "Ёфт нашуд")


@router.message(Command("setprice"))
async def cmd_setprice(message: Message, command: CommandObject):
    try:
        pid, price = (command.args or "").split()
        price = round(float(price.replace(",", ".")), 2)
    except ValueError:
        return await message.answer("Формат: /setprice ff_cis_572 44.20")
    if pid not in PRODUCTS:
        return await message.answer("id ёфт нашуд. /products")
    await db.set_price(pid, price=price)
    await message.answer(f"✅ {PRODUCTS[pid]['title']}: {money(price)}")


@router.message(Command("hide", "show"))
async def cmd_hide(message: Message, command: CommandObject):
    pid = (command.args or "").strip()
    if pid not in PRODUCTS:
        return await message.answer("id ёфт нашуд. /products")
    await db.set_price(pid, active=0 if command.command == "hide" else 1)
    await message.answer("✅ Тайёр")


@router.message(Command("balance"))
async def cmd_balance(message: Message, command: CommandObject):
    try:
        uid, amount = (command.args or "").split()
        uid, amount = int(uid), round(float(amount.replace(",", ".")), 2)
    except ValueError:
        return await message.answer("Формат: /balance 123456789 50  (ё -50)")
    if not await db.get_user(uid):
        return await message.answer("Корбар ёфт нашуд")
    if not await db.change_balance(uid, amount, "admin", f"admin {message.from_user.id}"):
        return await message.answer("Баланс манфӣ мешавад")
    user = await db.get_user(uid)
    await message.answer(f"✅ Баланси нав: {money(user['balance'])}")


@router.message(Command("ban", "unban"))
async def cmd_ban(message: Message, command: CommandObject):
    if not (command.args or "").strip().isdigit():
        return await message.answer("Формат: /ban 123456789")
    await db.set_user_field(int(command.args), "banned", 1 if command.command == "ban" else 0)
    await message.answer("✅ Тайёр")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    await state.set_state(Broadcast.waiting)
    await message.answer("📢 Паёмро фиристед (матн, расм, видео). /cancel — бекор.")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Бекор шуд")


@router.message(Broadcast.waiting)
async def do_broadcast(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    ids = await db.all_user_ids()
    status = await message.answer(f"⏳ Фиристодан ба {len(ids)} корбар...")
    sent = 0
    for uid in ids:
        try:
            await message.copy_to(uid)
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.04)  # stay under Telegram's ~30 msg/s limit
    await status.edit_text(f"✅ Фиристода шуд: {sent}/{len(ids)}")


async def _mark(call: CallbackQuery, suffix: str):
    who = call.from_user.first_name
    try:
        if call.message.caption is not None:
            await call.message.edit_caption(caption=f"{call.message.html_text}\n\n{suffix} — {who}")
        else:
            await call.message.edit_text(f"{call.message.html_text}\n\n{suffix} — {who}")
    except Exception:
        await call.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("top:ok:") | F.data.startswith("top:no:"))
async def cb_topup(call: CallbackQuery, bot: Bot):
    _, action, tid = call.data.split(":")
    tid = int(tid)
    ok = await (approve_topup(bot, tid) if action == "ok" else reject_topup(bot, tid))
    if not ok:
        return await call.answer("Аллакай коркард шудааст", show_alert=True)
    await _mark(call, f"✅ Тасдиқ {topup_code(tid)}" if action == "ok" else f"❌ Рад {topup_code(tid)}")
    await call.answer()


@router.callback_query(F.data.startswith("ord:"))
async def cb_order(call: CallbackQuery, bot: Bot):
    _, action, oid = call.data.split(":")
    oid = int(oid)
    if action == "done":
        ok = await complete_order(bot, oid)
        label = "✅ Иҷро шуд"
    elif action == "refund":
        ok = await refund_order(bot, oid)
        label = "↩️ Пул баргардонида шуд"
    else:
        order = await db.get_order(oid)
        if not order or order["status"] != "processing":
            return await call.answer("Аллакай коркард шудааст", show_alert=True)
        await call.answer("🔁 Аз нав ба API фиристода шуд")
        await call.message.edit_reply_markup(reply_markup=None)
        return await start_fulfillment(bot, oid, notify=False)
    if not ok:
        return await call.answer("Аллакай коркард шудааст", show_alert=True)
    await _mark(call, label)
    await call.answer()


@router.message(Command("say"))
async def cmd_say(message: Message, command: CommandObject, bot: Bot):
    """/say user_id text — reply to a customer from the bot."""
    try:
        uid, text = (command.args or "").split(maxsplit=1)
        await bot.send_message(int(uid), f"💬 <b>Дастгирӣ:</b>\n{text}")
        await db.notify(int(uid), f"💬 Дастгирӣ: {text}")
        await message.answer("✅ Фиристода шуд")
    except Exception as e:
        await message.answer(f"Формат: /say 123456789 матн\n{e}")
