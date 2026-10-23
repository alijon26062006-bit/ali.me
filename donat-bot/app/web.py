"""HTTP server: serves the Mini App and its JSON API.

Every API call is authenticated with Telegram WebApp initData (header `Authorization: tma <initData>`),
validated with the bot token, so a user can only act as themselves.
"""
import hashlib
import hmac
import json
import logging
import os

from aiogram import Bot
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiohttp import web

from .catalog import GROUPS, get_catalog, get_product
from .config import BASE_DIR, config
from .db import db, order_code, topup_code
from .services import ShopError, check_supplier_order, clean_fields, create_order, create_topup, level_info
from .supplier import supplier

log = logging.getLogger(__name__)
WEBAPP_DIR = BASE_DIR / "webapp"
MEDIA_DIR = BASE_DIR / "media"  # banners uploaded by admins (not in git)
DEV_USER_ID = int(os.getenv("DEV_USER_ID", "0") or 0)  # local testing without Telegram only


def pin_hash(user_id: int, pin: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), f"donat:{user_id}".encode(), 100_000).hex()


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if not request.path.startswith("/api/") or request.path == "/api/donatix-hook":
        return await handler(request)
    auth = request.headers.get("Authorization", "")
    tg_user = None
    if auth.startswith("tma "):
        try:
            data = safe_parse_webapp_init_data(config.bot_token, auth[4:])
            tg_user = data.user
        except ValueError:
            return web.json_response({"error": "unauthorized"}, status=401)
    if tg_user:
        user, _ = await db.upsert_user(tg_user.id, tg_user.username, tg_user.first_name)
    elif DEV_USER_ID:
        user, _ = await db.upsert_user(DEV_USER_ID, "dev", "Dev")
    else:
        return web.json_response({"error": "unauthorized"}, status=401)
    if user["banned"]:
        return web.json_response({"error": "banned"}, status=403)
    request["user"] = user
    request["photo"] = getattr(tg_user, "photo_url", None) if tg_user else None
    try:
        return await handler(request)
    except ShopError as e:
        return web.json_response({"error": str(e)}, status=400)


async def user_payload(request: web.Request) -> dict:
    user = await db.get_user(request["user"]["id"])
    bot: Bot = request.app["bot"]
    me = await bot.me()
    orders = await db.fetchone("SELECT COUNT(*) c, COALESCE(SUM(amount),0) s FROM orders"
                               " WHERE user_id=? AND status='done'", user["id"])
    return {
        "id": user["id"], "username": user["username"], "first_name": user["first_name"],
        "photo_url": request.get("photo"),
        "balance": user["balance"], "total_spent": user["total_spent"], "lang": user["lang"],
        "currency": user["currency"], "theme": user["theme"], "has_pin": bool(user["pin_hash"]),
        "level": level_info(user["total_spent"]), "orders_done": orders["c"],
        "referrals": await db.referrals_count(user["id"]), "ref_earned": user["ref_earned"],
        "ref_link": f"https://t.me/{me.username}?start=ref_{user['id']}",
        "unread": await db.unread_count(user["id"]), "created_at": user["created_at"],
    }


async def bootstrap(request: web.Request):
    bot: Bot = request.app["bot"]
    me = await bot.me()
    return web.json_response({
        "shop_name": config.shop_name, "bot_username": me.username,
        "support_url": config.support_url, "reviews_url": config.reviews_url,
        "rub_rate": config.rub_rate, "topup_amounts": config.topup_amounts,
        "referral_percent": config.referral_percent,
        "methods": [{"id": m.id, "title": m.title, "subtitle": m.subtitle, "icon": m.icon, "currency": m.currency}
                    for m in config.payment_methods],
        "groups": GROUPS, "catalog": await get_catalog(), "user": await user_payload(request),
    })


async def me(request: web.Request):
    return web.json_response(await user_payload(request))


async def post_order(request: web.Request):
    body = await request.json()
    fields = body.get("fields") if isinstance(body.get("fields"), dict) else None
    result = await create_order(request.app["bot"], request["user"], body.get("items") or [],
                                str(body.get("uid", "")), str(body.get("method", "")), fields=fields)
    return web.json_response({"ok": True, **result})


async def post_topup(request: web.Request):
    body = await request.json()
    try:
        amount = float(body.get("amount", 0))
    except (TypeError, ValueError):
        raise ShopError("Маблағ нодуруст")
    result = await create_topup(request.app["bot"], request["user"], amount, str(body.get("method", "")))
    return web.json_response({"ok": True, **result})


async def check_account(request: web.Request):
    """Shows the player's nickname before paying (Donatix /accounts/check)."""
    body = await request.json()
    product = await get_product(str(body.get("product_id", "")))
    fields = body.get("fields") if isinstance(body.get("fields"), dict) else {}
    if not product or not supplier.enabled or not product.get("sku"):
        return web.json_response({"supported": False})
    try:
        clean = clean_fields([{"field_keys": [f["key"] for f in product["fields"]]}], fields, "")
    except ShopError:
        return web.json_response({"supported": True, "valid": False})
    result = await supplier.check_account(product["sku"], clean)
    return web.json_response({k: result.get(k) for k in ("supported", "valid", "player_name")})


async def donatix_hook(request: web.Request):
    """Optional webhook (Donatix panel → API): speeds up delivery notifications. Signed with HMAC-SHA256."""
    secret = os.getenv("DONATIX_WEBHOOK_SECRET", "")
    body = await request.read()
    ts = request.headers.get("X-Donatix-Timestamp", "")
    sig = request.headers.get("X-Donatix-Signature", "")
    mac = hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    if not secret or not hmac.compare_digest(mac, sig):
        return web.json_response({"ok": False}, status=401)
    try:
        ref = str(json.loads(body)["order"]["order_id"])
    except (ValueError, KeyError, TypeError):
        return web.json_response({"ok": True})
    for order in await db.orders_by_status("processing", 200):
        if f'"{ref}"' in order["items"]:
            await check_supplier_order(request.app["bot"], order["id"])
    return web.json_response({"ok": True})


async def history(request: web.Request):
    uid = request["user"]["id"]
    orders = [{"code": order_code(o["id"]), "title": o["title"], "amount": o["amount"], "uid": o["game_uid"],
               "method": o["method"], "status": o["status"], "created_at": o["created_at"],
               "items": json.loads(o["items"])}
              for o in await db.user_orders(uid)]
    topups = [{"code": topup_code(t["id"]), "amount": t["amount"], "method": t["method"], "status": t["status"],
               "created_at": t["created_at"]}
              for t in await db.fetchall("SELECT * FROM topups WHERE user_id=? ORDER BY id DESC LIMIT 100", uid)]
    txs = await db.user_transactions(uid)
    return web.json_response({"orders": orders, "topups": topups, "transactions": txs})


async def notifications(request: web.Request):
    return web.json_response({"items": await db.notifications(request["user"]["id"])})


async def notifications_read(request: web.Request):
    await db.mark_read(request["user"]["id"])
    return web.json_response({"ok": True})


async def settings(request: web.Request):
    body = await request.json()
    uid = request["user"]["id"]
    allowed = {"lang": ("tj", "ru"), "currency": ("TJS", "RUB"), "theme": ("dark", "light", "auto")}
    for key, values in allowed.items():
        if body.get(key) in values:
            await db.set_user_field(uid, key, body[key])
    return web.json_response(await user_payload(request))


async def set_pin(request: web.Request):
    body = await request.json()
    uid = request["user"]["id"]
    user = await db.get_user(uid)
    if user["pin_hash"] and not hmac.compare_digest(user["pin_hash"], pin_hash(uid, str(body.get("old", "")))):
        raise ShopError("PIN нодуруст")
    pin = body.get("pin")
    if pin is None:
        await db.set_user_field(uid, "pin_hash", None)
    elif isinstance(pin, str) and pin.isdigit() and len(pin) == 4:
        await db.set_user_field(uid, "pin_hash", pin_hash(uid, pin))
    else:
        raise ShopError("PIN бояд 4 рақам бошад")
    return web.json_response({"ok": True})


async def verify_pin(request: web.Request):
    body = await request.json()
    user = request["user"]
    ok = not user["pin_hash"] or hmac.compare_digest(user["pin_hash"], pin_hash(user["id"], str(body.get("pin", ""))))
    return web.json_response({"ok": ok})


async def index(request: web.Request):
    return web.FileResponse(WEBAPP_DIR / "index.html", headers={"Cache-Control": "no-cache"})


def create_app(bot: Bot) -> web.Application:
    app = web.Application(middlewares=[auth_middleware], client_max_size=64 * 1024)
    app["bot"] = bot
    app.router.add_get("/", index)
    app.router.add_get("/api/bootstrap", bootstrap)
    app.router.add_get("/api/me", me)
    app.router.add_post("/api/order", post_order)
    app.router.add_post("/api/topup", post_topup)
    app.router.add_get("/api/history", history)
    app.router.add_post("/api/check", check_account)
    app.router.add_post("/api/donatix-hook", donatix_hook)
    app.router.add_get("/api/notifications", notifications)
    app.router.add_post("/api/notifications/read", notifications_read)
    app.router.add_post("/api/settings", settings)
    app.router.add_post("/api/pin", set_pin)
    app.router.add_post("/api/pin/verify", verify_pin)
    app.router.add_static("/static", WEBAPP_DIR / "static")
    MEDIA_DIR.mkdir(exist_ok=True)
    app.router.add_static("/media", MEDIA_DIR)
    return app
