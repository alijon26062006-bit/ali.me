from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards as kb
from ..config import config
from ..db import db, topup_code
from ..services import level_info, money, cancel_topup, submit_receipt, safe_send
from ..texts import t

router = Router(name="user")


async def ensure_user(tg_user, ref_by: int | None = None) -> tuple[dict, bool]:
    return await db.upsert_user(tg_user.id, tg_user.username, tg_user.first_name, ref_by)


async def send_welcome(message: Message, lang: str):
    await message.answer(t(lang, "welcome"), reply_markup=kb.main_menu(lang))


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, bot: Bot, state: FSMContext):
    await state.clear()
    ref_by = None
    if command.args and command.args.startswith("ref_") and command.args[4:].isdigit():
        ref_by = int(command.args[4:])
    user, is_new = await ensure_user(message.from_user, ref_by)
    if user["banned"]:
        return
    if is_new and user["ref_by"]:
        referrer = await db.get_user(user["ref_by"])
        await safe_send(bot, user["ref_by"], t(referrer["lang"], "new_ref"))
    lang = user["lang"]
    await message.answer(t(lang, "menu_hint"), reply_markup=kb.reply_menu(lang))
    await send_welcome(message, lang)


@router.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(f"🆔 Telegram ID: <code>{message.from_user.id}</code>")


@router.message(F.text.endswith("Меню"))
async def menu_button(message: Message, state: FSMContext):
    await state.clear()
    user, _ = await ensure_user(message.from_user)
    await send_welcome(message, user["lang"])


@router.callback_query(F.data == "m:home")
async def cb_home(call: CallbackQuery):
    user, _ = await ensure_user(call.from_user)
    await call.message.edit_text(t(user["lang"], "welcome"), reply_markup=kb.main_menu(user["lang"]))
    await call.answer()


@router.callback_query(F.data == "m:donate")
async def cb_donate(call: CallbackQuery):
    user, _ = await ensure_user(call.from_user)
    await call.message.edit_text(t(user["lang"], "donate_title"), reply_markup=kb.donate_menu(user["lang"]))
    await call.answer()


@router.callback_query(F.data == "m:profile")
async def cb_profile(call: CallbackQuery, bot: Bot):
    user, _ = await ensure_user(call.from_user)
    me = await bot.me()
    orders = await db.fetchone("SELECT COUNT(*) c FROM orders WHERE user_id=? AND status='done'", user["id"])
    text = t(user["lang"], "profile", id=user["id"], balance=money(user["balance"], user["currency"]),
             orders=orders["c"], level=level_info(user["total_spent"])["title"], ref_pct=f"{config.referral_percent:g}",
             refs=await db.referrals_count(user["id"]), ref_earned=money(user["ref_earned"], user["currency"]),
             ref_link=f"https://t.me/{me.username}?start=ref_{user['id']}")
    await call.message.edit_text(text, reply_markup=kb.back_menu(user["lang"]))
    await call.answer()


@router.callback_query(F.data == "m:about")
async def cb_about(call: CallbackQuery):
    user, _ = await ensure_user(call.from_user)
    await call.message.edit_text(t(user["lang"], "about", users=await db.count_users()),
                                 reply_markup=kb.back_menu(user["lang"]))
    await call.answer()


@router.callback_query(F.data == "m:lang")
async def cb_lang(call: CallbackQuery):
    user, _ = await ensure_user(call.from_user)
    await call.message.edit_text(t(user["lang"], "lang_choose"), reply_markup=kb.lang_menu())
    await call.answer()


@router.callback_query(F.data == "m:cur")
async def cb_cur(call: CallbackQuery):
    user, _ = await ensure_user(call.from_user)
    await call.message.edit_text(t(user["lang"], "currency_choose"), reply_markup=kb.currency_menu())
    await call.answer()


@router.callback_query(F.data.startswith("set:lang:"))
async def cb_set_lang(call: CallbackQuery):
    lang = call.data.split(":")[2]
    if lang not in ("tj", "ru"):
        return await call.answer()
    await ensure_user(call.from_user)
    await db.set_user_field(call.from_user.id, "lang", lang)
    await call.answer(t(lang, "lang_set"))
    await call.message.answer(t(lang, "menu_hint"), reply_markup=kb.reply_menu(lang))
    await call.message.edit_text(t(lang, "welcome"), reply_markup=kb.main_menu(lang))


@router.callback_query(F.data.startswith("set:cur:"))
async def cb_set_cur(call: CallbackQuery):
    cur = call.data.split(":")[2]
    if cur not in ("TJS", "RUB"):
        return await call.answer()
    user, _ = await ensure_user(call.from_user)
    await db.set_user_field(user["id"], "currency", cur)
    await call.answer(t(user["lang"], "currency_set", cur="Сомонӣ" if cur == "TJS" else "Рубл ₽"))
    await call.message.edit_text(t(user["lang"], "welcome"), reply_markup=kb.main_menu(user["lang"]))


@router.callback_query(F.data == "m:nowebapp")
async def cb_no_webapp(call: CallbackQuery):
    await call.answer("Mini App ҳоло насб нашудааст (WEBAPP_URL).", show_alert=True)


@router.callback_query(F.data.startswith("top:cancel:"))
async def cb_cancel_topup(call: CallbackQuery, bot: Bot):
    topup = await db.get_topup(int(call.data.split(":")[2]))
    if not topup or topup["user_id"] != call.from_user.id:
        return await call.answer()
    if await cancel_topup(bot, topup["id"]):
        await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()


@router.message(F.photo)
async def receipt(message: Message, bot: Bot):
    user, _ = await ensure_user(message.from_user)
    topup = await submit_receipt(bot, user, message.photo[-1].file_id)
    if not topup:
        return await message.answer(t(user["lang"], "receipt_no_request"))
    await message.answer(t(user["lang"], "receipt_received", code=topup_code(topup["id"])))


@router.message(F.document)
async def receipt_as_file(message: Message):
    user, _ = await ensure_user(message.from_user)
    if await db.waiting_topup(user["id"]):
        await message.answer("📸 Чекро ҳамчун <b>расм</b> (скриншот) фиристед, на файл.")
