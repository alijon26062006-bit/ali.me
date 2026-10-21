import os
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
    shop_name: str = os.getenv("SHOP_NAME", "ALI DONAT TJ")
    webapp_url: str = os.getenv("WEBAPP_URL", "").rstrip("/")
    web_host: str = os.getenv("WEB_HOST", "0.0.0.0")
    web_port: int = int(os.getenv("WEB_PORT", "8080"))
    admin_ids: list[int] = field(default_factory=lambda: _ids(os.getenv("ADMIN_IDS", "")))
    admin_chat_id: int = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)
    support_url: str = os.getenv("SUPPORT_URL", "https://t.me/")
    reviews_url: str = os.getenv("REVIEWS_URL", "https://t.me/")
    db_path: str = os.getenv("DB_PATH", str(BASE_DIR / "data.db"))
    rub_rate_env: float = float(os.getenv("RUB_RATE", "0.1073"))  # 1 RUB = X TJS
    referral_percent: float = float(os.getenv("REFERRAL_PERCENT", "3"))
    topup_amounts: list[int] = field(default_factory=lambda: [10, 20, 50, 100, 300, 500, 700, 1000])
    # Supplier (auto-delivery) API
    supplier_api_url: str = os.getenv("SUPPLIER_API_URL", "").rstrip("/")
    supplier_api_key: str = os.getenv("SUPPLIER_API_KEY", "")
    # Values changed by admins in /panel (loaded from the settings table, override .env)
    overrides: dict[str, str] = field(default_factory=dict)

    @property
    def rub_rate(self) -> float:
        try:
            return float(self.overrides.get("rub_rate") or self.rub_rate_env)
        except ValueError:
            return self.rub_rate_env

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
