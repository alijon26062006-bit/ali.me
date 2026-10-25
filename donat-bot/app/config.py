import os
import re
from urllib.parse import quote
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _ids(raw: str) -> list[int]:
    return [int(x) for x in raw.replace(" ", "").split(",") if x]


@dataclass
class PaymentMethod:
    id: str
    title: str
    subtitle: str
    card: str
    card_label: str
    icon: str
    currency: str = "TJS"  # TJS or RUB
    pay_url: str = ""


@dataclass
class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    shop_name_env: str = os.getenv("SHOP_NAME", "NEMAT DONAT")
    webapp_url: str = os.getenv("WEBAPP_URL", "").rstrip("/")
    web_host: str = os.getenv("WEB_HOST", "0.0.0.0")
    web_port: int = int(os.getenv("WEB_PORT", "8080"))
    admin_ids: list[int] = field(default_factory=lambda: _ids(os.getenv("ADMIN_IDS", "")))
    admin_chat_id: int = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)
    support_url_env: str = os.getenv("SUPPORT_URL", "https://t.me/")
    reviews_url_env: str = os.getenv("REVIEWS_URL", "https://t.me/")
    dc_pay_f1: str = os.getenv("DC_PAY_F1", "133")  # service field of pay.dc.tj links
    db_path: str = os.getenv("DB_PATH", str(BASE_DIR / "data.db"))
    rub_rate_env: float = float(os.getenv("RUB_RATE", "0.1073"))  # 1 RUB = X TJS
    referral_percent: float = float(os.getenv("REFERRAL_PERCENT", "3"))
    topup_amounts: list[int] = field(default_factory=lambda: [10, 20, 50, 100, 300, 500, 700, 1000])
    # Supplier (auto-delivery) API
    supplier_api_url: str = os.getenv("SUPPLIER_API_URL", "").rstrip("/")
    supplier_api_key: str = os.getenv("SUPPLIER_API_KEY", "")
    timezone: str = os.getenv("TIMEZONE", "Asia/Dushanbe")  # day boundaries in reports
    owner_code: str = os.getenv("OWNER_CODE", "")  # one-time secret: /start owner_<code> makes you admin
    usd_rate_env: float = float(os.getenv("USD_RATE", "11.0"))   # somoni per 1 USD (supplier prices are USD)
    markup_env: float = float(os.getenv("MARKUP_PERCENT", "15"))
    # Values changed by admins in /panel (loaded from the settings table, override .env)
    overrides: dict[str, str] = field(default_factory=dict)

    @property
    def rub_rate(self) -> float:
        try:
            return float(self.overrides.get("rub_rate") or self.rub_rate_env)
        except ValueError:
            return self.rub_rate_env

    def _num(self, key: str, default: float) -> float:
        try:
            return float(self.overrides.get(key) or default)
        except ValueError:
            return default

    @property
    def shop_name(self) -> str:
        return self.overrides.get("shop_name") or self.shop_name_env

    @property
    def menu_button(self) -> bool:
        """'Мағоза' button left of the message field (opens the Mini App). Off until the shop has a stable domain."""
        return self.overrides.get("menu_button", os.getenv("MENU_BUTTON", "0")) == "1" and \
            self.webapp_url.startswith("https://")

    @property
    def unique_cents(self) -> bool:
        """Add random cents to request amounts (helps matching transfers once auto-payment exists). Off by default."""
        return self.overrides.get("unique_cents", os.getenv("UNIQUE_CENTS", "0")) == "1"

    @property
    def support_url(self) -> str:
        return self.overrides.get("support_url") or self.support_url_env

    @property
    def reviews_url(self) -> str:
        return self.overrides.get("reviews_url") or self.reviews_url_env

    @property
    def sub_channel(self) -> str:
        """Channel customers must join before buying (@name or -100… id); empty = no requirement."""
        return self.overrides.get("sub_channel", "") if self.overrides.get("sub_required") == "1" else ""

    def dc_pay_link(self, card: str, amount: float, comment: str) -> str:
        """Dushanbe City payment link: opens the DC app with the card and the exact amount filled in."""
        digits = re.sub(r"\D", "", card)
        if len(digits) < 12:
            return ""
        return (f"https://pay.dc.tj/?a={digits}&c={quote(comment)}&f1={self.dc_pay_f1}&s={amount:.2f}")

    @property
    def usd_rate(self) -> float:
        """Admin value wins, then the rate the supplier publishes, then .env."""
        return self._num("usd_rate", self._num("usd_rate_auto", self.usd_rate_env))

    @property
    def markup(self) -> float:
        return self._num("markup", self.markup_env)

    @property
    def admin_targets(self) -> list[int]:
        return [self.admin_chat_id] if self.admin_chat_id else self.admin_ids

    @property
    def all_payment_methods(self) -> list[PaymentMethod]:
        """Every method with admin overrides applied, including disabled ones (for /panel)."""
        methods = [
            PaymentMethod("alif", "Алиф", "Аз замимаи Alif Mobi", os.getenv("ALIF_CARD", ""),
                          "Рақами картаи Алиф", "alif", pay_url=os.getenv("ALIF_PAY_URL", "")),
            PaymentMethod("dc", "Душанбе Сити", "Аз замимаи бонк", os.getenv("DC_CARD", ""),
                          "Рақами картаи Душанбе Сити", "dc", pay_url=os.getenv("DC_PAY_URL", "")),
            PaymentMethod("other", "Дигар бонкҳо", "Алиф, Эсхата, Спитамен, Ориён ва дигар бонкҳо",
                          os.getenv("OTHER_CARD", ""), "Рақами корт", "bank"),
            PaymentMethod("rus", "Интиқол аз Русия", "Аз Сбер, Тинькофф ва ғ. ба корти Душанбе Сити",
                          os.getenv("RUS_CARD", ""), "Рақами корти Душанбе Сити", "rus", currency="RUB"),
            PaymentMethod("atm", "Банкомат (ДС)", "Нақд ба банкомат ё терминали Душанбе Сити",
                          os.getenv("ATM_CARD", ""), "Рақами корти Душанбе Сити", "dc"),
        ]
        for m in methods:
            m.card = self.overrides.get(f"card:{m.id}", m.card)
            m.pay_url = self.overrides.get(f"pay_url:{m.id}", m.pay_url)
        return methods

    def method_enabled(self, m: PaymentMethod) -> bool:
        """A method is shown to customers when it has a card number and an admin hasn't switched it off."""
        return bool(m.card.strip()) and self.overrides.get(f"enabled:{m.id}", "1") == "1"

    @property
    def payment_methods(self) -> list[PaymentMethod]:
        return [m for m in self.all_payment_methods if self.method_enabled(m)]

    def method(self, method_id: str) -> PaymentMethod | None:
        return next((m for m in self.payment_methods if m.id == method_id), None)


config = Config()
