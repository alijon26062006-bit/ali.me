"""Product catalog.

Base prices live here (in somoni). Admins can override a price or hide a product
at runtime with /setprice and /hide (stored in the price_overrides table).
With a Donatix API key the catalog is replaced by the supplier's real products (see build_supplier_catalog);
this static list is the fallback for manual delivery.
"""
import asyncio
import json
import logging
import math
import re
import time
from pathlib import Path

from .config import config
from .db import db

log = logging.getLogger(__name__)

GROUPS = {
    "featured": "Асосӣ",
    "ff_regions": "Free Fire — дигар регионҳо",
    "games": "Ҳамаи бозиҳо",
    "services": "Хизматрасониҳо",
    "telegram": "Telegram",
}

GAME_UID = {"uid_label": "ID-и бозӣ", "uid_placeholder": "Мисол: 123456789"}


def _packs(prefix: str, unit: str, packs: list[tuple], tab: str = "main", art: str = "gem") -> list[dict]:
    out = []
    for p in packs:
        qty, price = p[0], p[1]
        subtitle = p[2] if len(p) > 2 else ""
        title = f"{qty} {unit}" if isinstance(qty, int) else str(qty)
        out.append({"id": f"{prefix}_{str(qty).lower().replace(' ', '_')}", "tab": tab, "title": title,
                    "subtitle": subtitle, "price": price, "sku": "", "art": art})
    return out


def _cat(cid, title, group, products, tabs=None, short="", colors=("#7c3aed", "#1e1b4b"), **extra):
    return {"id": cid, "title": title, "group": group, "short": short or title[:2].upper(),
            "colors": list(colors), "tabs": tabs or [{"id": "main", "title": "Маҳсулот", "icon": "gem"}],
            "products": products, **GAME_UID, **extra}


FF_TABS = [{"id": "main", "title": "Алмазҳо", "icon": "gem"}, {"id": "levelup", "title": "Level Up", "icon": "award"}]

CATEGORIES: list[dict] = [
    _cat("ff_cis", "Free Fire СНГ", "featured",
         _packs("ff_cis", "Алмазҳо", [(110, 8.20), (231, 17.20), (341, 25.20), (572, 44.20), (1166, 85.20),
                                      (2398, 169.20), (6160, 408.20)])
         + _packs("ff_cis_v", "", [("Ваучер Lite 90", 4.20, "Lite — 7 рӯз"),
                                   ("Ваучер ҳафта 450", 15.80, "Ҳафтаина — 7 рӯз"),
                                   ("Ваучер моҳона 2600", 58.90, "Моҳона — 30 рӯз")], art="voucher")
         + _packs("ff_cis_lvl", "", [("Level Up Package 6", 4.00), ("Level Up Package 10", 6.00),
                                     ("Level Up Package 15", 8.00), ("Level Up Package 20", 8.00),
                                     ("Level Up Package 25", 8.00), ("Level Up Package 30", 10.00)],
                  tab="levelup", art="ticket"),
         tabs=FF_TABS, short="FF", colors=("#7c3aed", "#1a1033"), banner="СНГ", banner_kicker="FREE FIRE"),
    _cat("ff_indo", "Free Fire Индонезия", "featured",
         _packs("ff_id", "Алмазҳо", [(5, 0.60), (12, 1.30), (50, 4.90), (70, 6.60), (140, 12.90), (355, 31.90),
                                     (720, 63.90), (1450, 127.90), (2180, 189.90), (3640, 315.90)])
         + _packs("ff_id_v", "", [("Member Mingguan", 16.50, "Ҳафтаина — 7 рӯз"),
                                  ("Member Bulanan", 62.00, "Моҳона — 30 рӯз")], art="voucher"),
         short="FF", colors=("#d4a017", "#1f1600"), banner="ИНДОНЕЗИЯ", banner_kicker="FREE FIRE"),
    _cat("pubg", "PUBG Mobile — UC", "featured",
         _packs("pubg", "UC", [(60, 6.90), (325, 33.90), (660, 66.90), (1800, 165.00), (3850, 330.00),
                               (8100, 660.00)], art="coin"),
         short="UC", colors=("#e0a526", "#1c1404"), banner="UC", banner_kicker="PUBG MOBILE"),
]

_FF_REGIONS = [("tr", "Туркия"), ("br", "Бразилия"), ("vn", "Ветнам"), ("th", "Таиланд"), ("my", "Малайзия"),
               ("sg", "Сингапур"), ("me", "Шарқи Наздик"), ("pk", "Покистон"), ("bd", "Бангладеш"),
               ("latam", "Амрикои Лотинӣ"), ("eu", "Аврупо"), ("global", "Глобал")]
for code, name in _FF_REGIONS:
    CATEGORIES.append(_cat(f"ff_{code}", f"Free Fire {name}", "ff_regions",
                           _packs(f"ff_{code}", "Алмазҳо", [(100, 8.90), (310, 26.90), (520, 43.90),
                                                            (1060, 86.90), (2180, 176.90)]),
                           short="FF", colors=("#f97316", "#1f0d02")))

_GAMES = [
    ("mlbb", "Mobile Legends", "Алмазҳо", [(86, 16.90), (172, 33.50), (257, 49.90), (706, 132.00)], "ML", "#2563eb"),
    ("genshin", "Genshin Impact", "Genesis", [(60, 10.90), (330, 54.90), (1090, 164.90), (2240, 329.00)], "GI", "#0ea5e9"),
    ("hsr", "Honkai: Star Rail", "Oneiric", [(60, 10.90), (330, 54.90), (1090, 164.90)], "HS", "#a855f7"),
    ("zzz", "Zenless Zone Zero", "Monochrome", [(60, 10.90), (330, 54.90), (1090, 164.90)], "ZZ", "#eab308"),
    ("coc", "Clash of Clans", "Gems", [(80, 10.90), (500, 54.90), (1200, 109.00)], "CC", "#f59e0b"),
    ("cr", "Clash Royale", "Gems", [(80, 10.90), (500, 54.90), (1200, 109.00)], "CR", "#3b82f6"),
    ("bs", "Brawl Stars", "Gems", [(30, 21.90), (80, 54.90), (170, 109.00)], "BS", "#facc15"),
    ("so2", "Standoff 2", "Голд", [(100, 9.90), (500, 44.90), (1000, 86.90)], "SO", "#64748b"),
    ("roblox", "Roblox", "Robux", [(80, 10.90), (400, 54.90), (800, 109.00)], "RB", "#ef4444"),
    ("codm", "Call of Duty Mobile", "CP", [(80, 10.90), (420, 54.90), (880, 109.00)], "CD", "#22c55e"),
    ("valorant", "Valorant", "VP", [(475, 54.90), (1000, 109.00), (2050, 219.00)], "VL", "#f43f5e"),
    ("fortnite", "Fortnite", "V-Bucks", [(1000, 98.00), (2800, 249.00)], "FN", "#6366f1"),
    ("abm", "Arena Breakout", "Bonds", [(60, 10.90), (310, 54.90), (630, 109.00)], "AB", "#84cc16"),
    ("delta", "Delta Force", "Coins", [(60, 10.90), (320, 54.90), (660, 109.00)], "DF", "#14b8a6"),
    ("hayday", "Hay Day", "Diamonds", [(55, 10.90), (300, 54.90)], "HD", "#fb923c"),
    ("stumble", "Stumble Guys", "Gems", [(250, 21.90), (1000, 76.90)], "SG", "#ec4899"),
]
for cid, title, unit, packs, short, color in _GAMES:
    CATEGORIES.append(_cat(cid, title, "games", _packs(cid, unit, packs), short=short, colors=(color, "#111114")))

_ACCOUNT = {"uid_label": "Почта ё логин", "uid_placeholder": "example@mail.com"}
CATEGORIES += [
    _cat("spotify", "Spotify Premium", "services",
         _packs("spotify", "", [("1 моҳ", 39.00), ("3 моҳ", 109.00)], art="star"),
         short="SP", colors=("#1db954", "#06140b"), **_ACCOUNT),
    _cat("youtube", "YouTube Premium", "services",
         _packs("youtube", "", [("1 моҳ", 39.00), ("12 моҳ", 389.00)], art="star"),
         short="YT", colors=("#ef4444", "#1a0505"), **_ACCOUNT),
    _cat("chatgpt", "ChatGPT Plus", "services",
         _packs("chatgpt", "", [("1 моҳ", 239.00)], art="star"),
         short="AI", colors=("#10a37f", "#04140f"), **_ACCOUNT),
    _cat("netflix", "Netflix", "services",
         _packs("netflix", "", [("1 моҳ", 89.00)], art="star"),
         short="NF", colors=("#e50914", "#1a0203"), **_ACCOUNT),
    _cat("telegram", "Telegram", "telegram",
         _packs("tg_stars", "Stars", [(50, 10.90), (100, 21.50), (250, 52.90), (500, 104.90), (1000, 207.90)],
                art="star")
         + _packs("tg_premium", "", [("Premium 3 моҳ", 139.00), ("Premium 6 моҳ", 189.00),
                                     ("Premium 12 моҳ", 339.00)], tab="premium", art="star"),
         tabs=[{"id": "main", "title": "Stars", "icon": "star"}, {"id": "premium", "title": "Premium", "icon": "crown"}],
         short="TG", colors=("#229ed9", "#04121a"), uid_label="Username", uid_placeholder="@username"),
]

STATIC_CATEGORIES = CATEGORIES

# ---------------------------------------------------------------- order fields (what the customer types)
FIELD_LABELS = {  # supplier field key -> (label, placeholder)
    "player_id": ("ID-и бозӣ", "Мисол: 123456789"),
    "telegram_username": ("Username", "@username"),
    "server": ("Сервер", "Сервер"),
    "zone": ("Зона", "Зона / Zone ID"),
    "zone_id": ("Зона", "Зона / Zone ID"),
    "account": ("Почта ё логин", "example@mail.com"),
}


def make_field(key: str, label: str = "", placeholder: str = "") -> dict:
    known = FIELD_LABELS.get(key)
    return {"key": key, "label": known[0] if known else (label or key),
            "placeholder": known[1] if known else (placeholder or label or key)}


def _static_fields(cat: dict) -> list[dict]:
    if cat["uid_label"] == "Username":
        return [make_field("telegram_username")]
    if cat["uid_label"] == "ID-и бозӣ":
        return [make_field("player_id")]
    return [make_field("account")]


for _c in STATIC_CATEGORIES:
    for _p in _c["products"]:
        _p["fields"] = _static_fields(_c)


# ---------------------------------------------------------------- catalog built from the supplier
FEATURED = {  # home-screen banner slot -> (keywords of the game, region words); admins can pick another category
    "ff_cis": (("free fire", "free_fire", "freefire"),
               ("cis", "снг", "sng", "ru", "rus", "russia", "россия", "рф", "kz", "kazakhstan", "казахстан", "eurasia")),
    "ff_indo": (("free fire", "free_fire", "freefire"), ("id", "idn", "indo", "indonesia", "индонезия", "индонезии")),
    "pubg": (("pubg",), ()),
}
FEATURED_TITLES = {"ff_cis": "Free Fire СНГ", "ff_indo": "Free Fire Индонезия", "pubg": "PUBG Mobile"}
STATIC_BY_ID = {c["id"]: c for c in STATIC_CATEGORIES}
PALETTE = ["#2563eb", "#0ea5e9", "#a855f7", "#eab308", "#f59e0b", "#3b82f6", "#facc15", "#64748b", "#ef4444",
           "#22c55e", "#f43f5e", "#6366f1", "#84cc16", "#14b8a6", "#fb923c", "#ec4899"]
STAR_PACKS = [50, 100, 250, 500, 1000, 2500, 5000, 10000]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:36] or "x"


def _short(name: str) -> str:
    words = re.findall(r"[A-Za-zА-Яа-я0-9]+", name)
    return ("".join(w[0] for w in words[:2]) if len(words) > 1 else name[:2]).upper()


# ---------------------------------------------------------------- Free Fire pack order and pictures
FF_KIND_ORDER = {"diamond": 0, "voucher_lite": 1, "voucher_week": 2, "voucher_month": 3, "other": 4, "levelup": 5}
PRODUCTS_DIR = Path(__file__).resolve().parent.parent / "webapp" / "static" / "products"


def ff_kind(name: str) -> str:
    """Diamonds, Lite / weekly / monthly voucher, Level Up or something else — from the pack name."""
    n = name.lower()
    if "level" in n:
        return "levelup"
    if re.search(r"lite|лайт", n):
        return "voucher_lite"
    if re.search(r"week|недел|ҳафта|mingguan", n):
        return "voucher_week"
    if re.search(r"month|месяц|месяч|моҳ|bulanan", n):
        return "voucher_month"
    if re.search(r"diamond|алмаз|💎", n) or re.fullmatch(r"\s*\d[\d\s]*", n):
        return "diamond"
    return "other"


def kind_image(kind: str) -> str:
    """Picture shipped for a pack kind (webapp/static/products/<kind>.jpg), if there is one."""
    for ext in ("jpg", "png", "webp"):
        if (PRODUCTS_DIR / f"{kind}.{ext}").exists():
            return f"/static/products/{kind}.{ext}"
    return ""


def amount(p: dict) -> int:
    """Number in a pack name; bonuses are added up: '300 + 25 UC' -> 325, '1 060 💎' -> 1060."""
    m = re.search(r"\d[\d ]*(?:\s*\+\s*\d[\d ]*)*", p["title"])
    return sum(int(re.sub(r"\s", "", x)) for x in m.group().split("+")) if m else 0


def arrange_pubg(products: list[dict]) -> list[dict]:
    """PUBG Mobile: UC packs first (60, 180, 325 …) with their own pictures, then everything else by price."""
    for p in products:
        is_uc = re.search(r"\buc\b", f"{p['title']} {p.get('name', '')}".lower()) and amount(p)
        p["kind"] = "uc" if is_uc else "pubg_other"
        if is_uc:
            p["art"] = "coin"
            p["image"] = kind_image(f"uc_{amount(p)}") or p.get("image", "")
    return sorted(products, key=lambda p: (p["kind"] != "uc", amount(p) if p["kind"] == "uc" else 0,
                                           p.get("price_usd", p.get("price", 0))))


def arrange_free_fire(products: list[dict]) -> list[dict]:
    """Free Fire, every region: diamonds (smallest first), then Lite, weekly, monthly vouchers, then the rest.
    Shipped pictures for a kind replace the supplier's picture."""
    for p in products:
        p["kind"] = ff_kind(f"{p['title']} {p.get('name', '')}")
        if p["kind"] == "levelup":
            p["tab"] = "levelup"
        if p["kind"].startswith("voucher"):
            p["art"] = "voucher"
        own = kind_image(f"levelup_{amount(p)}") if p["kind"] == "levelup" else ""  # Level Up 6, 10, 15 …
        p["image"] = own or kind_image(p["kind"]) or p.get("image", "")
    return sorted(products, key=lambda p: (FF_KIND_ORDER[p["kind"]],
                                           amount(p) if p["kind"] in ("diamond", "levelup") else 0,
                                           p.get("price_usd", p.get("price", 0))))


def _art(name: str) -> str:
    n = name.lower()
    if "level" in n:
        return "ticket"
    if re.search(r"\buc\b|coin|cp\b", n):
        return "coin"
    if re.search(r"voucher|ваучер|member|weekly|monthly|pass|подписк|ҳафта|моҳ", n):
        return "voucher"
    return "gem"


def _featured_key(cat_text: str, region_text: str) -> str | None:
    words = set(re.findall(r"[a-zа-яё0-9]+", f"{cat_text} {region_text}".lower()))
    for key, (names, regions) in FEATURED.items():
        if any(n in cat_text for n in names) and (not regions or words & set(regions)):
            return key
    return None


IMAGE_KEYS = ("image", "image_url", "img", "icon", "icon_url", "logo", "logo_url", "picture", "photo",
              "thumbnail", "thumb", "cover", "banner", "banner_url", "preview", "avatar")
SAFE_URL = re.compile(r"^https?://[^\s\"'<>()]+$")


def find_image(obj: dict, origin: str = "") -> str:
    """First picture URL in a supplier object. Relative paths get the supplier origin; only https
    (or the supplier's own origin) is accepted so the page can't be pointed at something unsafe."""
    for key in IMAGE_KEYS:
        v = obj.get(key)
        if isinstance(v, dict):  # {"url": ...} or sizes
            v = v.get("url") or v.get("original") or v.get("large") or v.get("medium") or next(iter(v.values()), "")
        if not isinstance(v, str) or not v.strip():
            continue
        v = v.strip()
        if v.startswith("//"):
            v = "https:" + v
        elif v.startswith("/") and origin:
            v = origin + v
        if SAFE_URL.match(v) and (v.startswith("https://") or (origin and v.startswith(origin))):
            return v
    return ""


def _category_images(raw: dict) -> dict[str, str]:
    """category id / name (lower case) -> picture, from /categories and /v2/topups."""
    origin = raw.get("image_origin", "")
    images: dict[str, str] = {}
    for c in raw.get("categories", []):
        img = find_image(c, origin)
        if not img:
            continue
        for key in ("category_id", "id", "slug", "code", "name", "title"):
            if c.get(key):
                images.setdefault(str(c[key]).lower(), img)
    return images


def build_supplier_catalog(raw: dict) -> list[dict]:
    """Turns Donatix /products items into the shop's categories. Prices stay in USD here and are
    converted at read time, so a new rate or markup applies immediately."""
    groups: dict[tuple, list] = {}
    for item in raw.get("topup", []):
        key = (item.get("category_id") or item.get("category_name") or "game", item.get("region") or "")
        groups.setdefault(key, []).append(item)
    regions_per_cat: dict[str, int] = {}
    for cid, _region in groups:
        regions_per_cat[cid] = regions_per_cat.get(cid, 0) + 1

    origin = raw.get("image_origin", "")
    cat_images = _category_images(raw)
    cats, used_featured = [], set()
    for idx, ((cid, region), items) in enumerate(sorted(groups.items(), key=lambda kv: str(kv[0]))):
        first = items[0]
        name = first.get("category_name") or cid
        region_title = first.get("region_title") or region
        title = f"{name} {region_title}".strip() if regions_per_cat[cid] > 1 and region_title else name
        text = f"{cid} {name}".lower()
        raw_id = f"dx_{_slug(cid)}_{_slug(region)}"[:44]
        pinned = {v: k for k, v in config.overrides.items() if k.startswith("featured:") and v}
        fkey = pinned[raw_id].split(":", 1)[1] if raw_id in pinned else _featured_key(text, f"{region} {region_title}")
        if fkey in used_featured or (raw_id not in pinned and config.overrides.get(f"featured:{fkey}")):
            fkey = None  # slot already taken, or an admin pinned another category to it
        is_ff = any(n in text for n in FEATURED["ff_cis"][0])
        group = "featured" if fkey else ("ff_regions" if is_ff else "games")
        products = []
        for it in items:
            pname = it.get("title") or it.get("name") or it.get("product_id")
            products.append({
                "id": it["product_id"], "sku": it["product_id"], "title": pname, "name": it.get("name") or "",
                "subtitle": "",
                "tab": "levelup" if "level" in pname.lower() else "main", "art": _art(f"{name} {pname}"),
                "price_usd": float(it.get("price_usd") or 0),
                "image": find_image(it, origin),
                "fields": [make_field(f.get("key", ""), f.get("label", ""), f.get("placeholder", ""))
                           for f in (it.get("fields") or [{"key": "player_id"}])],
            })
        products = [p for p in products if p["price_usd"] > 0]
        if not products:
            continue
        if is_ff:
            products = arrange_free_fire(products)
        elif "pubg" in text:
            products = arrange_pubg(products)
        else:
            products.sort(key=lambda p: p["price_usd"])
        main_title = "Алмазҳо" if is_ff else ("UC" if "pubg" in text else "Маҳсулот")
        tabs = [{"id": "main", "title": main_title, "icon": "gem"}]
        if any(p["tab"] == "levelup" for p in products):
            tabs.append({"id": "levelup", "title": "Level Up", "icon": "award"})
        look = STATIC_BY_ID.get(fkey, {}) if fkey else {}
        color = PALETTE[idx % len(PALETTE)]
        cat = {"id": fkey or raw_id, "raw_id": raw_id, "title": title, "group": group,
               "short": look.get("short") or _short(name), "colors": look.get("colors") or [color, "#111127"],
               "tabs": tabs, "products": products, "uid_label": products[0]["fields"][0]["label"],
               "uid_placeholder": products[0]["fields"][0]["placeholder"],
               "image": cat_images.get(str(cid).lower()) or cat_images.get(str(name).lower())
               or next((p["image"] for p in products if p["image"]), "")}
        if fkey:
            used_featured.add(fkey)
            big = "UC" if fkey == "pubg" else (region_title or region or look.get("banner", "")).upper()
            cat.update(banner=big, banner_kicker=name.upper())
        cats.append(cat)

    tg_products = []
    for it in raw.get("telegram_stars", []):
        per_star = float(it.get("price_usd") or 0)
        lo, hi = int(it.get("min_quantity") or 50), int(it.get("max_quantity") or 10000)
        for n in STAR_PACKS:
            if lo <= n <= hi and per_star > 0:
                tg_products.append({"id": f"{it['product_id']}:{n}", "sku": it["product_id"], "dx_quantity": n,
                                    "title": f"{n} Stars", "subtitle": "", "tab": "main", "art": "star",
                                    "price_usd": per_star * n, "fields": [make_field("telegram_username")]})
    for it in raw.get("telegram_premium", []):
        months = re.search(r"(\d+)", it.get("product_id", ""))
        tg_products.append({"id": it["product_id"], "sku": it["product_id"], "tab": "premium", "art": "star",
                            "title": f"Premium {months.group(1)} моҳ" if months else (it.get("name") or "Premium"),
                            "subtitle": "", "price_usd": float(it.get("price_usd") or 0),
                            "fields": [make_field("telegram_username")]})
    tg_products = [p for p in tg_products if p["price_usd"] > 0]
    if tg_products:
        tabs = [{"id": "main", "title": "Stars", "icon": "star"}]
        if any(p["tab"] == "premium" for p in tg_products):
            tabs.append({"id": "premium", "title": "Premium", "icon": "crown"})
        if not any(p["tab"] == "main" for p in tg_products):
            tabs = tabs[1:]
        cats.append({"id": "telegram", "title": "Telegram", "group": "telegram", "short": "TG",
                     "image": cat_images.get("telegram") or cat_images.get("telegram_stars") or "",
                     "colors": ["#229ed9", "#04121a"], "tabs": tabs, "products": tg_products,
                     "uid_label": "Username", "uid_placeholder": "@username"})
    # featured first, in the fixed order of the home screen
    order = {k: i for i, k in enumerate(FEATURED)}
    cats.sort(key=lambda c: (c["group"] != "featured", order.get(c["id"], 99)))
    return cats


for _c in STATIC_CATEGORIES:
    if _c["id"].startswith("ff_"):
        _c["products"] = arrange_free_fire(_c["products"])
    elif _c["id"] == "pubg":
        _c["products"] = arrange_pubg(_c["products"])


# ---------------------------------------------------------------- active catalog
CATEGORIES: list[dict] = []
PRODUCTS: dict[str, dict] = {}
CATEGORY_BY_ID: dict[str, dict] = {}
SOURCE = {"name": "static", "synced_at": 0}


def set_active(categories: list[dict], source: str):
    CATEGORIES[:] = categories
    PRODUCTS.clear()
    for c in categories:
        for p in c["products"]:
            p["category"] = c["id"]
            PRODUCTS[p["id"]] = p
    CATEGORY_BY_ID.clear()
    CATEGORY_BY_ID.update({c["id"]: c for c in categories})
    SOURCE.update(name=source, synced_at=int(time.time()))


set_active(STATIC_CATEGORIES, "static")


def tjs_price(p: dict) -> float:
    """Shop price in somoni: static price, or supplier USD price x rate x (1 + markup), rounded up to 0.10."""
    if "price_usd" not in p:
        return p["price"]
    return math.ceil(p["price_usd"] * config.usd_rate * (1 + config.markup / 100) * 10 - 1e-9) / 10


def _priced(p: dict, overrides: dict) -> dict | None:
    o = overrides.get(p["id"])
    if o and not o["active"]:
        return None
    if p.get("kind") == "other" and not o:  # Free Fire bundles / Evo access: hidden until an admin runs /show <id>
        return None
    return {**p, "price": o["price"] if o and o["price"] is not None else tjs_price(p)}


DEFAULT_BANNERS = {  # built-in pictures shipped in webapp/static/banners (an admin upload replaces them)
    slot: f"/static/banners/{slot}.jpg" for slot in ("ff_cis", "ff_indo", "pubg")
    if (Path(__file__).resolve().parent.parent / "webapp" / "static" / "banners" / f"{slot}.jpg").exists()
}


async def get_catalog() -> list[dict]:
    """Catalog with prices in somoni, admin price overrides applied and hidden products removed."""
    overrides = await db.price_overrides()
    result = []
    for cat in CATEGORIES:
        products = [x for x in (_priced(p, overrides) for p in cat["products"]) if x]
        if products:
            banner = config.overrides.get(f"banner:{cat['id']}", "") or DEFAULT_BANNERS.get(cat["id"], "")
            result.append({**cat, "products": products, **({"banner_image": banner} if banner else {})})
    return result


async def get_product(product_id: str) -> dict | None:
    base = PRODUCTS.get(product_id)
    return _priced(base, await db.price_overrides()) if base else None


async def load_cached_supplier_catalog():
    """On startup use the last synced supplier catalog until a fresh sync finishes."""
    raw = await db.fetchone("SELECT value FROM settings WHERE key='supplier_catalog'")
    if raw:
        try:
            cats = build_supplier_catalog(json.loads(raw["value"]))
            if cats:
                set_active(cats, "supplier (cache)")
        except Exception:
            log.exception("cached supplier catalog")


async def sync_supplier_catalog() -> str:
    """Downloads the supplier catalog; returns a short report for admins."""
    from .supplier import supplier
    if not supplier.enabled:
        return "Таъминкунанда пайваст нест"
    raw = {kind: await supplier.products(kind) for kind in ("topup", "telegram_stars", "telegram_premium")}
    raw["categories"] = await supplier.categories()
    raw["image_origin"] = supplier.origin
    cats = build_supplier_catalog(raw)
    if not cats:
        return "Таъминкунанда ягон маҳсулот надод"
    rate = await supplier.usd_rate()
    if rate:
        await db.set_setting("usd_rate_auto", str(rate))
    await db.set_setting("supplier_catalog", json.dumps(raw, ensure_ascii=False))
    set_active(cats, "supplier")
    with_img = sum(1 for c in cats if c.get("image"))
    return f"{len(cats)} категория ({with_img} бо расм), {sum(len(c['products']) for c in cats)} маҳсулот"


async def catalog_sync_loop():
    from .supplier import supplier
    while True:
        try:
            if supplier.enabled:
                log.info("catalog sync: %s", await sync_supplier_catalog())
        except Exception:
            log.exception("catalog sync")
        await asyncio.sleep(600)  # docs: cache the catalog for 5-15 minutes
