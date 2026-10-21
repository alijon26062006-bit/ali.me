"""Business logic shared by the bot handlers and the Mini App API."""
import asyncio
import json
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .catalog import CATEGORY_BY_ID, get_product
from .config import config
from .db import db, order_code, topup_code
from .supplier import supplier
from .texts import t

log = logging.getLogger(__name__)

LEVELS = [  # (min total spent, key, title, cashback-like referral percent)
    (0, "none", "Бе сатҳ"),
    (100, "bronze", "🥉 Харидори нав"),
    (500, "silver", "🥈 Харидори доимӣ"),
    (2000, "gold", "🥇 Харидори VIP"),
    (5000, "diamond", "💎 Легенда"),
]


class ShopError(Exception):
    """Error shown to the user as-is."""


def money(amount: float, currency: str = "TJS") -> str:
    if currency == "RUB":
        return f"{amount / config.rub_rate:,.0f} ₽".replace(",", " ")
    return f"{amount:,.2f} см".replace(",", " ")


def level_info(total_spent: float) -> dict:
    current = LEVELS[0]
    nxt = None
    for lvl in LEVELS:
        if total_spent >= lvl[0]:
            current = lvl
        elif nxt is None:
            nxt = lvl
    progress = 100 if not nxt else int((total_spent - current[0]) / (nxt[0] - current[0]) * 100)
    return {"key": current[1], "title": current[2], "progress": progress,
            "next_title": nxt[2] if nxt else None, "next_left": round(nxt[0] - total_spent, 2) if nxt else 0}


async def safe_send(bot: Bot, chat_id: int, text: str, **kw):
    try:
        return await bot.send_message(chat_id, text, **kw)
    except Exception as e:
        log.warning("send to %s failed: %s", chat_id, e)


async def notify_user(bot: Bot, user_id: int, key: str, **kw):
    user = await db.get_user(user_id)
    lang = user["lang"] if user else "tj"
    text = t(lang, key, **kw)
    await db.notify(user_id, text)
    await safe_send(bot, user_id, text)


async def notify_admins(bot: Bot, text: str, markup: InlineKeyboardMarkup | None = None, photo: str | None = None):
    for chat_id in config.admin_targets:
        try:
            if photo:
                await bot.send_photo(chat_id, photo, caption=text, reply_markup=markup)
            else:
                await bot.send_message(chat_id, text, reply_markup=markup)
        except Exception as e:
            log.warning("admin notify %s failed: %s", chat_id, e)


def user_link(user: dict) -> str:
    name = user.get("first_name") or "user"
    uname = f" @{user['username']}" if user.get("username") else ""
    return f'<a href="tg://user?id={user["id"]}">{name}</a>{uname} (<code>{user["id"]}</code>)'


# ---------------------------------------------------------------- orders
async def build_items(raw_items: list[dict]) -> tuple[list[dict], float, str]:
    if not raw_items:
        raise ShopError("Маҳсулот интихоб нашудааст")
    items, total, category = [], 0.0, None
    for raw in raw_items[:20]:
        product = await get_product(str(raw.get("product_id")))
        qty = max(1, min(int(raw.get("qty", 1)), 50))
        if not product:
            raise ShopError("Маҳсулот ёфт нашуд ё дастрас нест")
        category = category or product["category"]
        items.append({"product_id": product["id"], "title": product["title"], "sku": product["sku"],
                      "price": product["price"], "qty": qty})
        total += product["price"] * qty
    title = ", ".join(f"{i['title']}" + (f" ×{i['qty']}" if i["qty"] > 1 else "") for i in items)
    cat = CATEGORY_BY_ID.get(category)
    if cat:
        title = f"{title} ({cat['title']})"
    return items, round(total, 2), title


async def create_order(bot: Bot, user: dict, raw_items: list[dict], game_uid: str, method: str) -> dict:
    if user.get("banned"):
        raise ShopError("⛔")
    game_uid = (game_uid or "").strip()
    if not 3 <= len(game_uid) <= 64:
        raise ShopError("ID-и бозиро дуруст ворид кунед")
    items, total, title = await build_items(raw_items)

    if method == "balance":
        order_id = await db.create_order(user["id"], items, title, total, game_uid, "balance", "unpaid")
        if not await db.change_balance(user["id"], -total, "purchase", order_code(order_id)):
            await db.set_order_status(order_id, "cancelled", note="insufficient balance")
            raise ShopError("Баланс нокифоя аст")
        await db.set_order_status(order_id, "processing", only_from="unpaid")
        asyncio.create_task(start_fulfillment(bot, order_id))
        return {"order": order_code(order_id), "status": "processing"}

    pm = config.method(method)
    if not pm:
        raise ShopError("Тарзи пардохт нодуруст")
    order_id = await db.create_order(user["id"], items, title, total, game_uid, method, "unpaid")
    topup = await create_topup(bot, user, total, method, order_id=order_id)
    return {"order": order_code(order_id), "topup": topup["code"], "status": "unpaid", "amount": topup["amount"]}


async def pay_order_from_balance(bot: Bot, order_id: int) -> bool:
    order = await db.get_order(order_id)
    if not order or order["status"] != "unpaid":
        return False
    if not await db.change_balance(order["user_id"], -order["amount"], "purchase", order_code(order_id)):
        return False
    if not await db.set_order_status(order_id, "processing", only_from="unpaid"):
        await db.change_balance(order["user_id"], order["amount"], "refund", order_code(order_id))
        return False
    asyncio.create_task(start_fulfillment(bot, order_id))
    return True


async def start_fulfillment(bot: Bot, order_id: int, notify: bool = True):
    order = await db.get_order(order_id)
    if not order or order["status"] != "processing":
        return
    items = json.loads(order["items"])
    code = order_code(order_id)
    if notify:
        await notify_user(bot, order["user_id"], "order_processing", code=code, title=order["title"],
                          uid=order["game_uid"])

    results = []
    for item in items:
        results.append(await supplier.deliver(item["sku"], order["game_uid"], item["qty"], code))

    refs = ",".join(r.ref for r in results if r.ref)
    if results and all(r.status == "done" for r in results):
        await db.set_order_status(order_id, "processing", supplier_ref=refs)
        await complete_order(bot, order_id)
        return
    if all(r.status in ("done", "pending") for r in results):
        await db.set_order_status(order_id, "processing", supplier_ref=refs, note="pending at supplier")
        return  # supplier_poller will finish it

    reason = "; ".join(r.message for r in results if r.status in ("failed", "manual") and r.message)
    await db.set_order_status(order_id, "processing", supplier_ref=refs or None, note=reason[:300])
    user = await db.get_user(order["user_id"])
    await notify_admins(
        bot,
        f"🛍 <b>Фармоиш барои иҷрои дастӣ</b> <code>{code}</code>\n\n"
        f"👤 {user_link(user)}\n📦 {order['title']}\n🎮 ID: <code>{order['game_uid']}</code>\n"
        f"💰 {money(order['amount'])}\n"
        + (f"\n⚠️ {reason}" if reason and supplier.enabled else ""),
        admin_order_kb(order_id),
    )


def admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Иҷро шуд", callback_data=f"ord:done:{order_id}", style="success"),
        InlineKeyboardButton(text="🔁 API", callback_data=f"ord:retry:{order_id}"),
        InlineKeyboardButton(text="↩️ Бозгашт", callback_data=f"ord:refund:{order_id}", style="danger"),
    ]])


async def complete_order(bot: Bot, order_id: int) -> bool:
    if not await db.set_order_status(order_id, "done", only_from="processing"):
        return False
    order = await db.get_order(order_id)
    await db.add_spent(order["user_id"], order["amount"])
    await notify_user(bot, order["user_id"], "order_done", code=order_code(order_id),
                      title=order["title"], uid=order["game_uid"])
    user = await db.get_user(order["user_id"])
    if user and user["ref_by"] and config.referral_percent > 0:
        bonus = round(order["amount"] * config.referral_percent / 100, 2)
        if bonus > 0 and await db.change_balance(user["ref_by"], bonus, "referral", order_code(order_id)):
            await db.add_ref_earned(user["ref_by"], bonus)
            await notify_user(bot, user["ref_by"], "ref_bonus", amount=money(bonus))
    return True


async def refund_order(bot: Bot, order_id: int) -> bool:
    order = await db.get_order(order_id)
    if not order or not await db.set_order_status(order_id, "cancelled", only_from="processing"):
        return False
    await db.change_balance(order["user_id"], order["amount"], "refund", order_code(order_id))
    await notify_user(bot, order["user_id"], "order_refunded", code=order_code(order_id), amount=money(order["amount"]))
    return True


async def supplier_poller(bot: Bot):
    """Finishes orders that the supplier accepted as 'pending'."""
    while True:
        await asyncio.sleep(60)
        if not supplier.enabled:
            continue
        try:
            for order in await db.orders_by_status("processing", limit=50):
                if order["note"] != "pending at supplier" or not order["supplier_ref"]:
                    continue
                checks = [await supplier.check(ref) for ref in order["supplier_ref"].split(",")]
                if all(c.status == "done" for c in checks):
                    await complete_order(bot, order["id"])
                elif any(c.status == "failed" for c in checks):
                    await db.set_order_status(order["id"], "processing", note="supplier failed")
                    user = await db.get_user(order["user_id"])
                    await notify_admins(bot, f"⚠️ Таъминкунанда фармоиши <code>{order_code(order['id'])}</code>-ро"
                                             f" иҷро накард\n👤 {user_link(user)}\n📦 {order['title']}\n"
                                             f"🎮 <code>{order['game_uid']}</code>", admin_order_kb(order["id"]))
        except Exception:
            log.exception("supplier poller")


# ---------------------------------------------------------------- top-ups
async def create_topup(bot: Bot, user: dict, base_amount: float, method: str, order_id: int | None = None) -> dict:
    if user.get("banned"):
        raise ShopError("⛔")
    pm = config.method(method)
    if not pm:
        raise ShopError("Тарзи пардохт нодуруст")
    if not 1 <= base_amount <= 50000:
        raise ShopError("Маблағ нодуруст")
    if order_id is None and base_amount not in config.topup_amounts:
        raise ShopError("Танҳо ин маблағҳо дастрасанд")
    old = await db.waiting_topup(user["id"])
    if old:  # one open request at a time
        await cancel_topup(bot, old["id"], silent=True)
    amount = await db.unique_amount(base_amount)
    topup_id = await db.create_topup(user["id"], amount, method, order_id)
    await send_payment_message(bot, user, topup_id)
    return {"code": topup_code(topup_id), "amount": amount}


async def send_payment_message(bot: Bot, user: dict, topup_id: int):
    topup = await db.get_topup(topup_id)
    pm = any_method(topup["method"])
    lang = user["lang"]
    amount = money(topup["amount"])
    if pm.currency == "RUB":
        amount = f"{money(topup['amount'], 'RUB')} ({amount})"
    order_line = ""
    if topup["order_id"]:
        order = await db.get_order(topup["order_id"])
        order_line = t(lang, "pay_order_line", title=order["title"], uid=order["game_uid"])
    text = t(lang, "pay_request", code=topup_code(topup_id), order_line=order_line, amount=amount,
             method=pm.title, card_label=pm.card_label, card=pm.card)
    rows = []
    if pm.pay_url:
        rows.append([InlineKeyboardButton(text=t(lang, "btn_pay"), url=pm.pay_url)])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_cancel_topup"), callback_data=f"top:cancel:{topup_id}",
                                      style="danger")])
    await safe_send(bot, user["id"], text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def cancel_topup(bot: Bot, topup_id: int, silent: bool = False) -> bool:
    topup = await db.get_topup(topup_id)
    if not topup or not await db.set_topup_status(topup_id, "cancelled", ("waiting",)):
        return False
    if topup["order_id"]:
        await db.set_order_status(topup["order_id"], "cancelled", only_from="unpaid")
    if not silent:
        await notify_user(bot, topup["user_id"], "topup_cancelled", code=topup_code(topup_id))
    return True


def any_method(method_id: str):
    """Payment method by id, even if an admin switched it off after the request was created."""
    return next((m for m in config.all_payment_methods if m.id == method_id), None)


REJECT_REASONS = {  # code -> {lang: text}; the admin sees Tajik, the customer their own language
    "amount": {"tj": "Маблағ нодуруст", "ru": "Неверная сумма"},
    "notfound": {"tj": "Пардохт ёфт нашуд", "ru": "Платёж не найден"},
    "fake": {"tj": "Чеки қалбакӣ", "ru": "Поддельный чек"},
    "unreadable": {"tj": "Чек хонда намешавад", "ru": "Чек не читается"},
    "old": {"tj": "Чеки кӯҳна / такрорӣ", "ru": "Старый / повторный чек"},
}


def receipt_kb(topup_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [b(text="✅ Тасдиқ", callback_data=f"top:ok:{topup_id}", style="success"),
         b(text="❌ Рад", callback_data=f"top:no:{topup_id}", style="danger")],
        [b(text="✏️ Маблағи дигар", callback_data=f"top:amt:{topup_id}")],
    ])


def reject_kb(topup_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    rows = [[b(text=titles["tj"], callback_data=f"top:rs:{topup_id}:{code}")] for code, titles in REJECT_REASONS.items()]
    rows.append([b(text="✍️ Сабаби дигар", callback_data=f"top:rs:{topup_id}:custom")])
    rows.append([b(text="⬅️ Бозгашт", callback_data=f"top:back:{topup_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def receipt_caption(topup: dict) -> str:
    user = await db.get_user(topup["user_id"])
    pm = any_method(topup["method"])
    order_line = ""
    if topup["order_id"]:
        order = await db.get_order(topup["order_id"])
        order_line = f"\n🛍 {order['title']}\n🎮 ID: <code>{order['game_uid']}</code>"
    rub = f" ≈ {money(topup['amount'], 'RUB')}" if pm and pm.currency == "RUB" else ""
    text = (f"🧾 <b>Чек</b> <code>{topup_code(topup['id'])}</code>\n\n👤 {user_link(user)}\n"
            f"💰 <b>{money(topup['amount'])}</b>{rub}\n🏦 {pm.title if pm else topup['method']}{order_line}")
    if topup.get("receipt_unique_id"):
        dups = await db.receipt_duplicates(topup["receipt_unique_id"], topup["id"])
        if dups:
            refs = ", ".join(f"{topup_code(d['id'])} ({d['status']})" for d in dups[:5])
            text += f"\n\n⚠️ <b>ДИҚҚАТ: ин чек пештар фиристода шуда буд!</b>\n{refs}"
    return text


async def submit_receipt(bot: Bot, user: dict, file_id: str, unique_id: str | None = None) -> dict | None:
    topup = await db.waiting_topup(user["id"])
    if not topup or not await db.set_topup_status(topup["id"], "review", ("waiting",), receipt_file_id=file_id,
                                                  receipt_unique_id=unique_id):
        return None
    topup = await db.get_topup(topup["id"])
    await notify_admins(bot, await receipt_caption(topup), receipt_kb(topup["id"]), photo=file_id)
    return topup


async def approve_topup(bot: Bot, topup_id: int, amount: float | None = None, admin_id: int | None = None) -> bool:
    if amount is not None and amount <= 0:
        return False
    if not await db.set_topup_status(topup_id, "approved", ("waiting", "review"), handled_by=admin_id,
                                     amount=round(amount, 2) if amount is not None else None):
        return False
    topup = await db.get_topup(topup_id)
    await db.change_balance(topup["user_id"], topup["amount"], "topup", topup_code(topup_id))
    await notify_user(bot, topup["user_id"], "topup_approved", amount=money(topup["amount"]), code=topup_code(topup_id))
    if topup["order_id"] and not await pay_order_from_balance(bot, topup["order_id"]):
        order = await db.get_order(topup["order_id"])
        if order and await db.set_order_status(order["id"], "cancelled", only_from="unpaid", note="underpaid"):
            await notify_user(bot, topup["user_id"], "order_underpaid", code=order_code(order["id"]),
                              need=money(order["amount"]))
    return True


async def reject_topup(bot: Bot, topup_id: int, reason: str = "", admin_id: int | None = None) -> bool:
    """`reason` is a REJECT_REASONS code or the admin's own text."""
    topup = await db.get_topup(topup_id)
    if not topup:
        return False
    user = await db.get_user(topup["user_id"])
    lang = user["lang"] if user else "tj"
    reason_text = REJECT_REASONS[reason].get(lang, REJECT_REASONS[reason]["tj"]) if reason in REJECT_REASONS else reason
    if not await db.set_topup_status(topup_id, "rejected", ("waiting", "review"), reject_reason=reason_text or None,
                                     handled_by=admin_id):
        return False
    if topup["order_id"]:
        await db.set_order_status(topup["order_id"], "cancelled", only_from="unpaid")
    text = t(lang, "topup_rejected", code=topup_code(topup_id))
    if reason_text:
        text += "\n\n" + t(lang, "reject_reason", reason=reason_text)
    await db.notify(topup["user_id"], text)
    await safe_send(bot, topup["user_id"], text)
    return True


async def receipt_reminder(bot: Bot):
    """Reminds admins about receipts waiting too long: after 10 and again after 30 minutes."""
    while True:
        await asyncio.sleep(60)
        try:
            for level, age in ((1, 600), (2, 1800)):
                for topup in await db.topups_to_remind(age, level):
                    await db.mark_reminded(topup["id"], level)
                    minutes = age // 60
                    await notify_admins(bot, f"⏰ <b>Чек {minutes}+ дақиқа интизор аст!</b>\n\n" + await receipt_caption(topup),
                                        receipt_kb(topup["id"]), photo=topup["receipt_file_id"])
        except Exception:
            log.exception("receipt reminder")
