"""Supplier (auto-delivery) adapter.

Every supplier has its own API. This module keeps that in one place: the rest of the bot
only calls `supplier.deliver()` and `supplier.check()`. `HttpSupplier` is a generic
implementation (JSON over HTTPS, API key in a header) — adjust the request/response
mapping to your supplier's docs. Without SUPPLIER_API_URL / SUPPLIER_API_KEY the bot uses
`ManualSupplier`, and orders go to admins for manual delivery.
"""
import logging
from dataclasses import dataclass

import aiohttp

from .config import config

log = logging.getLogger(__name__)


@dataclass
class DeliveryResult:
    status: str          # done | pending | failed | manual
    ref: str = ""        # supplier order id
    message: str = ""


class ManualSupplier:
    enabled = False

    async def deliver(self, sku: str, player_id: str, quantity: int, order_code: str) -> DeliveryResult:
        return DeliveryResult("manual", message="Supplier API is not configured")

    async def check(self, ref: str) -> DeliveryResult:
        return DeliveryResult("manual")

    async def balance(self) -> str:
        return "—"


class HttpSupplier:
    enabled = True

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}", "X-API-Key": self.api_key}
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(method, self.base_url + path, headers=headers, **kwargs) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    raise RuntimeError(f"HTTP {resp.status}: {data}")
                return data or {}

    @staticmethod
    def _parse(data: dict) -> DeliveryResult:
        raw = str(data.get("status", "")).lower()
        ref = str(data.get("order_id") or data.get("id") or "")
        if raw in {"success", "completed", "done", "delivered"}:
            return DeliveryResult("done", ref, data.get("message", ""))
        if raw in {"pending", "processing", "queued", "in_progress"}:
            return DeliveryResult("pending", ref, data.get("message", ""))
        return DeliveryResult("failed", ref, data.get("message") or str(data))

    async def deliver(self, sku: str, player_id: str, quantity: int, order_code: str) -> DeliveryResult:
        if not sku:
            return DeliveryResult("manual", message="Product has no supplier SKU")
        try:
            data = await self._request("POST", "/order", json={
                "product": sku, "player_id": player_id, "quantity": quantity, "external_id": order_code})
            return self._parse(data)
        except Exception as e:  # network or supplier error — let admins decide
            log.exception("Supplier deliver failed")
            return DeliveryResult("failed", message=str(e)[:300])

    async def check(self, ref: str) -> DeliveryResult:
        try:
            return self._parse(await self._request("GET", f"/order/{ref}"))
        except Exception as e:
            return DeliveryResult("pending", ref, str(e)[:300])

    async def balance(self) -> str:
        try:
            data = await self._request("GET", "/balance")
            return f"{data.get('balance', '?')} {data.get('currency', '')}".strip()
        except Exception as e:
            return f"хато: {str(e)[:100]}"


supplier = (HttpSupplier(config.supplier_api_url, config.supplier_api_key)
            if config.supplier_api_url and config.supplier_api_key else ManualSupplier())
