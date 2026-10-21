"""Supplier (auto-delivery) adapter for Donatix (https://donatix.tj/api/v1).

The rest of the bot only calls `supplier.deliver()`, `supplier.check()`, `supplier.check_account()`
and `supplier.products()`. Without SUPPLIER_API_KEY the bot uses `ManualSupplier` and orders go to
admins for manual delivery.
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

import aiohttp

from .config import config

log = logging.getLogger(__name__)

# Donatix error codes that mean "the customer typed a wrong account" — refunded automatically.
WRONG_ACCOUNT_CODES = {"player_not_found", "account_not_found", "invalid_field", "missing_field"}


@dataclass
class DeliveryResult:
    status: str          # done | pending | failed | manual
    ref: str = ""        # supplier order id (dx-…)
    message: str = ""
    code: str = ""       # supplier error code
    delivery: list = field(default_factory=list)  # codes/keys for gift cards, if any


class SupplierError(Exception):
    def __init__(self, message: str, code: str = "", status: int = 0):
        super().__init__(message)
        self.code = code
        self.status = status


class ManualSupplier:
    enabled = False
    name = "дастӣ"

    async def deliver(self, sku: str, fields: dict, quantity: int | None, order_code: str) -> DeliveryResult:
        return DeliveryResult("manual", message="Supplier API is not configured")

    async def check(self, ref: str) -> DeliveryResult:
        return DeliveryResult("manual")

    async def check_account(self, sku: str, fields: dict) -> dict:
        return {"supported": False}

    async def products(self, kind: str) -> list[dict]:
        return []

    async def usd_rate(self) -> float | None:
        return None

    async def balance(self) -> str:
        return "—"


class DonatixSupplier:
    enabled = True
    name = "Donatix API"

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session: aiohttp.ClientSession | None = None
        self._account_cache: dict[tuple, tuple[float, dict]] = {}

    async def _http(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40),
                                                  headers={"X-API-Key": self.api_key, "Accept": "application/json"})
        return self._session

    async def request(self, method: str, path: str, *, json: dict | None = None, params: dict | None = None,
                      idempotency_key: str | None = None) -> dict:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        for attempt in range(3):
            session = await self._http()
            async with session.request(method, self.base_url + path, json=json, params=params, headers=headers) as r:
                data = await r.json(content_type=None) if r.content_length != 0 else {}
                data = data if isinstance(data, dict) else {}
                if r.status == 429 and attempt < 2:  # rate limited: wait as told, then retry
                    await asyncio.sleep(min(int(r.headers.get("Retry-After", "5") or 5), 30))
                    continue
                if r.status >= 400 or data.get("ok") is False:
                    raise SupplierError(data.get("error") or f"HTTP {r.status}", data.get("code", ""), r.status)
                return data
        raise SupplierError("rate limited", "rate_limited", 429)

    # ---------------- catalog
    async def products(self, kind: str) -> list[dict]:
        items, offset = [], 0
        while True:
            data = await self.request("GET", "/products", params={"kind": kind, "limit": 500, "offset": offset})
            page = data.get("items") or []
            items += page
            if len(page) < 500:
                return items
            offset += 500

    async def usd_rate(self) -> float | None:
        """Somoni per 1 USD as published in /payments/methods (format not fixed in the docs, so search for it)."""
        try:
            data = await self.request("GET", "/payments/methods")
        except Exception as e:
            log.warning("usd rate: %s", e)
            return None
        return _find_rate(data)

    # ---------------- orders
    @staticmethod
    def _parse(order: dict) -> DeliveryResult:
        status = str(order.get("status", "")).lower()
        ref = str(order.get("order_id") or order.get("id") or "")
        delivery = order.get("delivery") or []
        if isinstance(delivery, (str, dict)):
            delivery = [delivery]
        if status == "completed":
            return DeliveryResult("done", ref, delivery=delivery)
        if status == "failed":
            return DeliveryResult("failed", ref, str(order.get("error") or "failed"))
        return DeliveryResult("pending", ref)

    async def deliver(self, sku: str, fields: dict, quantity: int | None, order_code: str) -> DeliveryResult:
        if not sku:
            return DeliveryResult("manual", message="Product has no supplier product_id")
        body = {"product_id": sku, "fields": fields}
        if quantity:
            body["quantity"] = quantity
        try:
            data = await self.request("POST", "/orders", json=body,
                                      idempotency_key=f"{order_code}-{sku}-{uuid.uuid4().hex[:12]}")
            return self._parse(data.get("order") or {})
        except SupplierError as e:
            log.warning("Donatix order %s failed: %s (%s)", order_code, e, e.code)
            return DeliveryResult("failed", message=str(e)[:300], code=e.code)
        except Exception as e:  # network error: the order may or may not exist — admins decide
            log.exception("Donatix order %s", order_code)
            return DeliveryResult("failed", message=f"network: {str(e)[:200]}", code="network")

    async def check(self, ref: str) -> DeliveryResult:
        try:
            data = await self.request("GET", f"/orders/{ref}")
            return self._parse(data.get("order") or {})
        except SupplierError as e:
            if e.status == 404:
                return DeliveryResult("failed", ref, str(e), e.code)
            return DeliveryResult("pending", ref, str(e))
        except Exception as e:
            return DeliveryResult("pending", ref, str(e)[:200])

    async def check_account(self, sku: str, fields: dict) -> dict:
        """{'supported': bool, 'valid': bool, 'player_name': str}; cached 10 min to respect rate limits."""
        key = (sku, tuple(sorted(fields.items())))
        cached = self._account_cache.get(key)
        if cached and cached[0] > time.time():
            return cached[1]
        try:
            data = await self.request("POST", "/accounts/check", json={"product_id": sku, "fields": fields})
            result = {"supported": bool(data.get("supported", True)), "valid": bool(data.get("valid", True)),
                      "player_name": data.get("player_name") or ""}
        except SupplierError as e:
            if e.code in WRONG_ACCOUNT_CODES:
                result = {"supported": True, "valid": False, "player_name": ""}
            else:
                return {"supported": False, "error": str(e)}
        except Exception as e:
            return {"supported": False, "error": str(e)[:200]}
        self._account_cache[key] = (time.time() + 600, result)
        return result

    async def balance(self) -> str:
        try:
            data = await self.request("GET", "/balance")
            return f"{float(data.get('balance', 0)):.2f} {data.get('currency', 'USD')}"
        except Exception as e:
            return f"хато: {str(e)[:80]}"


def _find_rate(obj, depth: int = 0) -> float | None:
    """Looks for a somoni-per-dollar number (5..30) under a key that mentions rate/курс/tjs."""
    if depth > 5:
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(w in kl for w in ("rate", "курс", "tjs", "somoni")) and not isinstance(v, (dict, list)):
                try:
                    num = float(v)
                    if 5 <= num <= 30:
                        return num
                except (TypeError, ValueError):
                    pass
        for v in obj.values():
            found = _find_rate(v, depth + 1)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_rate(v, depth + 1)
            if found:
                return found
    return None


def _make_supplier():
    key = config.supplier_api_key
    if not key:
        return ManualSupplier()
    return DonatixSupplier(config.supplier_api_url or "https://donatix.tj/api/v1", key)


supplier = _make_supplier()
