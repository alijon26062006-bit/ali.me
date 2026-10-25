"""Purchase receipt picture in the shop's colors (violet → cyan), sent to the buyer after each completed order."""
import io
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)
try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # Pillow missing: the buyer still gets the text message
    Image = None

FONTS = Path(__file__).parent / "fonts"
STATIC = Path(__file__).resolve().parent.parent / "webapp"
W, PAD, ROW = 1080, 72, 58
VIOLET, CYAN = (124, 58, 237), (34, 211, 238)
BG_TOP, BG_BOTTOM = (26, 11, 61), (10, 7, 22)
CARD, LINE = (255, 255, 255, 14), (255, 255, 255, 34)
DIVIDER = (72, 60, 112)
MUTED, TEXT = (176, 166, 214), (246, 244, 255)

LABELS = {
    "tj": {"title": "Харид анҷом ёфт", "order": "Фармоиш", "date": "Сана", "buyer": "Харидор", "product": "Маҳсулот",
           "game": "Бозӣ", "uid": "ID-и аккаунт", "nick": "Никнейм", "pay": "Пардохт", "total": "Ҳамагӣ",
           "thanks": "Ташаккур барои харид!", "sub": "Боз меоед — мо ҳамеша дар хизматем", "balance": "аз баланс"},
    "ru": {"title": "Покупка завершена", "order": "Заказ", "date": "Дата", "buyer": "Покупатель", "product": "Товар",
           "game": "Игра", "uid": "ID аккаунта", "nick": "Никнейм", "pay": "Оплата", "total": "Итого",
           "thanks": "Спасибо за покупку!", "sub": "Ждём вас снова — мы всегда на связи", "balance": "с баланса"},
}


def _font(weight: str, size: int):
    return ImageFont.truetype(str(FONTS / f"Inter-{weight}.otf"), size)


def _mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def _gradient(w, h, a, b, horizontal=False):
    line = Image.new("RGB", (w, 1) if horizontal else (1, h))
    n = w if horizontal else h
    for i in range(n):
        line.putpixel((i, 0) if horizontal else (0, i), _mix(a, b, i / max(1, n - 1)))
    return line.resize((w, h))


def _fit(draw, text, font_weight, size, max_w, min_size=26):
    while size > min_size and draw.textlength(text, font=_font(font_weight, size)) > max_w:
        size -= 2
    font = _font(font_weight, size)
    while draw.textlength(text, font=font) > max_w and len(text) > 2:
        text = text[:-2] + "…"
    return text, font


def _product_picture(image: str):
    if not image or not image.startswith("/static/"):
        return None
    path = STATIC / image.lstrip("/")
    try:
        return Image.open(path).convert("RGB") if path.is_file() else None
    except Exception:
        return None


def render(order: dict, lang: str = "tj") -> bytes | None:
    """order: shop, code, ts, buyer, product, game, uid, nick, method, amount (text), image (/static/... or '')."""
    if Image is None:
        return None
    L = LABELS.get(lang, LABELS["tj"])
    rows = [(L["uid"], order["uid"])]
    if order.get("nick"):
        rows.append((L["nick"], order["nick"]))
    rows += [(L["buyer"], order["buyer"]), (L["pay"], order["method"]), (L["date"], order["ts"]),
             (L["order"], order["code"])]
    top = 640
    bottom = top + 44 + 176 + 26 + len(rows) * ROW + 34 + 90
    H = bottom + 210
    img = _gradient(W, H, BG_TOP, BG_BOTTOM).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse((-260, -300, 620, 520), fill=VIOLET + (120,))
    g.ellipse((560, 900, 1360, 1700), fill=CYAN + (60,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(140)))
    d = ImageDraw.Draw(img)

    # brand row
    shop = (order.get("shop") or "NEMAT DONAT").strip()
    initials = "".join(w[0] for w in shop.split()[:2]).upper() or "ND"
    d.rounded_rectangle((PAD, 70, PAD + 84, 154), 24, fill=VIOLET)
    d.text((PAD + 42, 112), initials, font=_font("ExtraBold", 36), fill=TEXT, anchor="mm")
    shop, font = _fit(d, shop, "ExtraBold", 38, W - 2 * PAD - 108)
    d.text((PAD + 108, 92), shop, font=font, fill=TEXT)
    d.text((PAD + 108, 136), order["code"], font=_font("SemiBold", 26), fill=MUTED)

    # success badge
    cx, cy, r = W // 2, 330, 92
    ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((cx - r - 40, cy - r - 40, cx + r + 40, cy + r + 40), fill=CYAN + (70,))
    img.alpha_composite(ring.filter(ImageFilter.GaussianBlur(30)))
    disc = _gradient(2 * r, 2 * r, VIOLET, CYAN, horizontal=True)
    mask = Image.new("L", (2 * r, 2 * r), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=255)
    img.paste(disc, (cx - r, cy - r), mask)
    d = ImageDraw.Draw(img)
    d.line([(cx - 40, cy + 2), (cx - 10, cy + 32), (cx + 44, cy - 28)], fill=TEXT, width=16, joint="curve")
    d.text((cx, 480), L["title"], font=_font("ExtraBold", 58), fill=TEXT, anchor="mm")
    d.text((cx, 560), order["amount"], font=_font("ExtraBold", 84), fill=CYAN, anchor="mm")

    # details card
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle((PAD, top, W - PAD, bottom), 40, fill=CARD, outline=LINE, width=2)
    img.alpha_composite(card)
    d = ImageDraw.Draw(img)
    x0, x1, y = PAD + 44, W - PAD - 44, top + 44
    pic = _product_picture(order.get("image", ""))
    title_x = x0
    if pic:
        side = 132
        pic = pic.resize((side, side))
        pm = Image.new("L", (side, side), 0)
        ImageDraw.Draw(pm).rounded_rectangle((0, 0, side - 1, side - 1), 28, fill=255)
        img.paste(pic, (x0, y), pm)
        title_x = x0 + side + 32
    d = ImageDraw.Draw(img)
    name, font = _fit(d, order["product"], "ExtraBold", 44, x1 - title_x)
    d.text((title_x, y + 22), name, font=font, fill=TEXT)
    game, font = _fit(d, order.get("game") or "", "SemiBold", 30, x1 - title_x)
    d.text((title_x, y + 84), game, font=font, fill=MUTED)
    y += 176
    d.line((x0, y, x1, y), fill=DIVIDER, width=2)
    y += 26

    label_font = _font("SemiBold", 30)
    for label, value in rows:
        d.text((x0, y), label, font=label_font, fill=MUTED)
        value, font = _fit(d, str(value), "SemiBold", 32, x1 - x0 - 300)
        d.text((x1, y), value, font=font, fill=TEXT, anchor="ra")
        y += ROW
    y += 4
    for xx in range(x0, x1, 26):  # dashed tear line
        d.line((xx, y, min(xx + 14, x1), y), fill=DIVIDER, width=3)
    y += 30
    d.text((x0, y + 6), L["total"], font=_font("ExtraBold", 38), fill=TEXT)
    d.text((x1, y), order["amount"], font=_font("ExtraBold", 46), fill=CYAN, anchor="ra")

    # thanks
    bar = _gradient(W - 2 * PAD, 6, VIOLET, CYAN, horizontal=True)
    img.paste(bar, (PAD, bottom + 40))
    d.text((W // 2, bottom + 104), L["thanks"], font=_font("ExtraBold", 46), fill=TEXT, anchor="mm")
    d.text((W // 2, bottom + 160), L["sub"], font=_font("Regular", 28), fill=MUTED, anchor="mm")

    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=92, optimize=True)
    return out.getvalue()


def safe_render(order: dict, lang: str = "tj") -> bytes | None:
    try:
        return render(order, lang)
    except Exception:
        log.exception("receipt image")
        return None


def stamp(ts: int, tz: str) -> str:
    return datetime.fromtimestamp(ts, ZoneInfo(tz)).strftime("%d.%m.%Y · %H:%M")
