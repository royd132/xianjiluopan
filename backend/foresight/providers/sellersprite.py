from __future__ import annotations

import json
import math
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SellerSpriteDataError(RuntimeError):
    """Raised when SellerSprite returns an unusable response."""


class SellerSpriteConnector:
    """Optional SellerSprite product-research adapter for Amazon marketplaces."""

    endpoint = "https://api.sellersprite.com/v1/product/research"
    source_url = "https://open.sellersprite.com/api/2"
    mcp_endpoint = "https://mcp.sellersprite.com/mcp"
    supported_markets = {"US", "JP", "UK", "DE", "FR", "IT", "ES", "CA", "IN", "MX"}
    currencies = {"US": "USD", "JP": "JPY", "UK": "GBP", "DE": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR", "CA": "CAD", "IN": "INR", "MX": "MXN"}
    queries = {
        "pet_feeder": "automatic pet feeder",
        "portable_blender": "portable blender",
        "noise_cancelling_headphones": "noise cancelling headphones",
        "coffee_grinder": "coffee grinder",
        "generic": "home kitchen product",
    }

    def __init__(self, cache_path: Path, secret_key: str | None = None, timeout: float = 20.0, transport: str | None = None) -> None:
        self.cache_path = cache_path
        self.secret_key = secret_key or os.getenv("SELLERSPRITE_SECRET_KEY", "").strip() or os.getenv("SELLERSPRITE_KEY", "").strip()
        self.timeout = timeout
        self.transport = (transport or os.getenv("SELLERSPRITE_TRANSPORT", "rest")).strip().lower()

    @property
    def configured(self) -> bool:
        return bool(self.secret_key)

    @property
    def mcp_enabled(self) -> bool:
        return self.configured and self.transport == "mcp"

    def supports(self, market: str) -> bool:
        return market.upper() in self.supported_markets

    def available(self, market: str | None = None, category_key: str | None = None) -> bool:
        if market and not self.supports(market):
            return False
        return self.configured or any(
            self._read_cache(category, site) is not None
            for site in ([market.upper()] if market else self.supported_markets)
            for category in ([category_key] if category_key else self.queries)
        )

    def search(self, category_key: str, market: str, keyword: str | None = None) -> dict[str, Any] | None:
        market_code = market.upper()
        if not self.supports(market_code):
            return None
        query = self.queries.get(category_key) if category_key != "generic" else keyword
        if not query:
            return None
        cache_key = category_key if category_key != "generic" else f"generic:{query}"
        if not self.configured:
            return self._read_cache(cache_key, market_code)
        if self.mcp_enabled:
            try:
                return self._search_mcp(cache_key, market_code, query)
            except SellerSpriteDataError:
                # Keep the API transport as an explicit, observable fallback
                # while MCP access is being configured or temporarily down.
                if os.getenv("SELLERSPRITE_MCP_FALLBACK_REST", "true").lower() not in {"1", "true", "yes", "on"}:
                    raise
        body = {
            "marketplace": market_code,
            "keyword": query,
            "matchType": 2,
            "variation": "N",
            "page": 1,
            "size": 50,
            "order": {"field": "total_units", "desc": True},
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "secret-key": self.secret_key,
                "Content-Type": "application/json;charset=utf-8",
                "x-request-id": f"foresight-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
                "User-Agent": "foresight-compass/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - live service path
            cached = self._read_cache(cache_key, market_code)
            if cached:
                cached["live_error"] = str(exc)
                return cached
            raise SellerSpriteDataError(f"SellerSprite request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise SellerSpriteDataError("SellerSprite returned a malformed response")
        if payload.get("code") != "OK":
            cached = self._read_cache(cache_key, market_code)
            if cached:
                cached["live_error"] = str(payload.get("message") or payload.get("code") or "unknown response")
                return cached
            raise SellerSpriteDataError(str(payload.get("message") or payload.get("code") or "unknown response"))
        data = payload.get("data") or {}
        items = data.get("items", []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            raise SellerSpriteDataError("SellerSprite returned invalid product items")
        listings = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                price = float(item.get("price"))
            except (TypeError, ValueError):
                continue
            currency = str(item.get("currency") or data.get("currency") or self.currencies[market_code]).upper()
            if not math.isfinite(price) or price <= 0 or currency != self.currencies[market_code]:
                continue
            listings.append({
                "asin": str(item.get("asin") or ""),
                "title": str(item.get("title") or ""),
                "price": price,
                "currency": currency,
                "bsr": item.get("bsr"),
                "units": item.get("units"),
                "rating": item.get("rating"),
                "reviews": item.get("reviews"),
            })
        if len(listings) < 3:
            cached = self._read_cache(cache_key, market_code)
            if cached:
                cached["live_error"] = "SellerSprite returned fewer than three priced listings"
                return cached
            raise SellerSpriteDataError("SellerSprite returned fewer than three priced listings")
        result = {
            "category": cache_key,
            "market": market_code,
            "query": body["keyword"],
            "prices": sorted(item["price"] for item in listings),
            "listings": listings,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "source": "SellerSprite Product Research API",
            "source_url": self.source_url,
            "data_mode": "live",
        }
        self._write_cache(cache_key, market_code, result)
        return result

    def _search_mcp(self, cache_key: str, market_code: str, query: str) -> dict[str, Any]:
        payload = SellerSpriteMcpClient(self.secret_key, self.timeout).call_tool(
            "product_research",
            {
                "marketplace": market_code,
                "keyword": query,
                "page": 1,
                "size": 50,
                "variation": "N",
            },
        )
        items = _find_items(payload)
        listings = self._normalize_listings(items, market_code)
        if len(listings) < 3:
            raise SellerSpriteDataError("SellerSprite MCP returned fewer than three priced listings")
        result = {
            "category": cache_key,
            "market": market_code,
            "query": query,
            "prices": sorted(item["price"] for item in listings),
            "listings": listings,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "source": "SellerSprite Product Research MCP",
            "source_url": self.mcp_endpoint,
            "data_mode": "mcp_live",
        }
        self._write_cache(cache_key, market_code, result)
        return result

    def _normalize_listings(self, items: list[Any], market_code: str) -> list[dict[str, Any]]:
        listings = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                price = float(item.get("price"))
            except (TypeError, ValueError):
                continue
            currency = str(item.get("currency") or self.currencies[market_code]).upper()
            if not math.isfinite(price) or price <= 0 or currency != self.currencies[market_code]:
                continue
            listings.append({
                "asin": str(item.get("asin") or ""),
                "title": str(item.get("title") or ""),
                "price": price,
                "currency": currency,
                "bsr": item.get("bsr"),
                "units": item.get("units"),
                "rating": item.get("rating"),
                "reviews": item.get("reviews"),
            })
        return listings

    def _read_cache(self, category_key: str, market: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            result = payload.get(f"{market}:{category_key}") if isinstance(payload, dict) else None
            if not isinstance(result, dict) or result.get("market") != market or result.get("category") != category_key:
                return None
            observed = datetime.fromisoformat(result["observed_at"])
            prices, listings = result["prices"], result["listings"]
            if (observed.tzinfo is None or observed > datetime.now(timezone.utc)
                    or len(prices) < 3 or len(prices) != len(listings)
                    or not all(not isinstance(price, bool) and math.isfinite(float(price)) and float(price) > 0 for price in prices)
                    or not all(row.get("currency") == self.currencies[market] for row in listings)
                    or sorted(prices) != sorted(row["price"] for row in listings)
                    or result.get("source_url") not in {self.source_url, self.mcp_endpoint}):
                return None
            return {**result, "data_mode": "cached"}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return None

    def _write_cache(self, category_key: str, market: str, result: dict[str, Any]) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {}
            if self.cache_path.is_file():
                payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                payload = {}
            payload[f"{market}:{category_key}"] = result
            self.cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            return


class SellerSpriteMcpClient:
    """Small streamable-HTTP MCP client for the official SellerSprite server."""

    def __init__(self, secret_key: str, timeout: float = 20.0) -> None:
        self.secret_key = secret_key
        self.timeout = timeout

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        initialized, session_id = self._post({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "foresight-compass", "version": "1.0"},
            },
        })
        if not initialized.get("result"):
            raise SellerSpriteDataError("SellerSprite MCP initialize failed")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, session_id=session_id, allow_empty=True)
        response, _ = self._post({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }, session_id=session_id)
        if response.get("error"):
            raise SellerSpriteDataError(str(response["error"].get("message") or response["error"]))
        return response.get("result", response)

    def _post(self, payload: dict[str, Any], session_id: str | None = None, allow_empty: bool = False) -> tuple[dict[str, Any], str | None]:
        headers = {
            "secret-key": self.secret_key,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "foresight-compass/1.0",
        }
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        request = urllib.request.Request(
            SellerSpriteConnector.mcp_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                response_headers = getattr(response, "headers", {})
                next_session = response_headers.get("Mcp-Session-Id") if hasattr(response_headers, "get") else None
        except Exception as exc:
            raise SellerSpriteDataError(f"SellerSprite MCP request failed: {exc}") from exc
        if not raw.strip() and allow_empty:
            return {}, next_session or session_id
        parsed = _parse_mcp_payload(raw)
        if not isinstance(parsed, dict):
            raise SellerSpriteDataError("SellerSprite MCP returned a malformed response")
        return parsed, next_session or session_id


def _parse_mcp_payload(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    candidates = []
    for line in raw.splitlines():
        if line.startswith("data:"):
            try:
                candidates.append(json.loads(line[5:].strip()))
            except json.JSONDecodeError:
                continue
    for item in reversed(candidates):
        if isinstance(item, dict):
            return item
    raise SellerSpriteDataError("SellerSprite MCP returned no JSON-RPC payload")


def _find_items(value: Any) -> list[Any]:
    if isinstance(value, dict):
        items = value.get("items")
        if isinstance(items, list):
            return items
        for nested in value.values():
            found = _find_items(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_items(nested)
            if found:
                return found
    elif isinstance(value, str):
        try:
            return _find_items(json.loads(value))
        except json.JSONDecodeError:
            return []
    return []
