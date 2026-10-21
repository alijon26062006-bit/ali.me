"""Product catalog.

Base prices live here (in somoni). Admins can override a price or hide a product
at runtime with /setprice and /hide (stored in the price_overrides table).
`sku` is the product code sent to the supplier API; fill it in once the supplier is known.
"""
from .db import db

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

PRODUCTS: dict[str, dict] = {}
for _c in CATEGORIES:
    for _p in _c["products"]:
        _p["category"] = _c["id"]
        PRODUCTS[_p["id"]] = _p
CATEGORY_BY_ID = {c["id"]: c for c in CATEGORIES}


async def get_catalog() -> list[dict]:
    """Catalog with admin price overrides applied and hidden products removed."""
    overrides = await db.price_overrides()
    result = []
    for cat in CATEGORIES:
        products = []
        for p in cat["products"]:
            o = overrides.get(p["id"])
            if o and not o["active"]:
                continue
            products.append({**p, "price": o["price"] if o and o["price"] is not None else p["price"]})
        if products:
            result.append({**cat, "products": products})
    return result


async def get_product(product_id: str) -> dict | None:
    base = PRODUCTS.get(product_id)
    if not base:
        return None
    o = (await db.price_overrides()).get(product_id)
    if o and not o["active"]:
        return None
    return {**base, "price": o["price"] if o and o["price"] is not None else base["price"]}
