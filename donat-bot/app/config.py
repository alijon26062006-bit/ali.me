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
    rub_rate: float = float(os.getenv("RUB_RATE", "0.1073"))  # 1 RUB = X TJS
    referral_percent: float = float(os.getenv("REFERRAL_PERCENT", "3"))
    topup_amounts: list[int] = field(default_factory=lambda: [10, 20, 50, 100, 300, 500, 700, 1000])
    # Supplier (auto-delivery) API
    supplier_api_url: str = os.getenv("SUPPLIER_API_URL", "").rstrip("/")
    supplier_api_key: str = os.getenv("SUPPLIER_API_KEY", "")

    @property
    def admin_targets(self) -> list[int]:
        return [self.admin_chat_id] if self.admin_chat_id else self.admin_ids

    @property
    def payment_methods(self) -> list[PaymentMethod]:
        return [
            PaymentMethod("alif", "Алиф", "Аз замимаи Alif Mobi", os.getenv("ALIF_CARD", "000000000"),
                          "Рақами картаи Алиф", "alif", pay_url=os.getenv("ALIF_PAY_URL", "")),
            PaymentMethod("dc", "Душанбе Сити", "Аз замимаи бонк", os.getenv("DC_CARD", "0000 0000 0000 0000"),
                          "Рақами картаи Душанбе Сити", "dc", pay_url=os.getenv("DC_PAY_URL", "")),
            PaymentMethod("other", "Дигар бонкҳо", "Алиф, Эсхата, Спитамен, Ориён ва дигар бонкҳо",
                          os.getenv("OTHER_CARD", "0000 0000 0000 0000"), "Рақами корт", "bank"),
            PaymentMethod("rus", "Интиқол аз Русия", "Аз Сбер, Тинькофф ва ғ. ба корти Душанбе Сити",
                          os.getenv("RUS_CARD", "0000 0000 0000 0000"), "Рақами корти Душанбе Сити", "rus",
                          currency="RUB"),
            PaymentMethod("atm", "Банкомат (ДС)", "Нақд ба банкомат ё терминали Душанбе Сити",
                          os.getenv("ATM_CARD", "0000 0000 0000 0000"), "Рақами корти Душанбе Сити", "dc"),
        ]

    def method(self, method_id: str) -> PaymentMethod | None:
        return next((m for m in self.payment_methods if m.id == method_id), None)


config = Config()
