from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MarketplaceDataError(RuntimeError):
    """Raised when a marketplace response cannot be used as evidence."""


class MercadoLivreConnector:
    """Optional current Brazilian listing connector.

    The public search endpoint is documented by Mercado Livre, but access is
    still subject to an application token and platform rate limits. A failed
    live request never fabricates a price; callers can fall back to the local
    historical snapshots already in the project.
    """

    endpoint = "https://api.mercadolibre.com/sites/MLB/search"
    source_url = "https://developers.mercadolivre.com.br/itens-e-buscas"
    queries = {
        "pet_feeder": "comedouro automatico para cachorro gato",
        "portable_blender": "mini liquidificador portatil",
        "noise_cancelling_headphones": "fone cancelamento de ruido",
        "coffee_grinder": "moedor de cafe eletrico",
        "generic": "produto utilidade domestica",
    }

    def __init__(self, cache_path: Path, token: str | None = None, timeout: float = 15.0) -> None:
        self.cache_path = cache_path
        self.token = token or os.getenv("MERCADO_LIVRE_ACCESS_TOKEN", "").strip()
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def available(self, category_key: str | None = None) -> bool:
        return self.configured or any(self._read_cache(category) is not None
                                     for category in ([category_key] if category_key else self.queries))

    def search(self, category_key: str, market: str, keyword: str | None = None) -> dict[str, Any] | None:
        if market.upper() != "BR":
            return None
        query = self.queries.get(category_key) if category_key != "generic" else keyword
        if not query:
            return None
        cache_key = category_key if category_key != "generic" else f"generic:{query}"
        if not self.configured:
            return self._read_cache(cache_key)
        params = urllib.parse.urlencode({"q": query, "limit": 50})
        request = urllib.request.Request(
            f"{self.endpoint}?{params}",
            headers={"Authorization": f"Bearer {self.token}", "User-Agent": "foresight-compass/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - exercised against live service
            cached = self._read_cache(cache_key)
            if cached:
                cached["live_error"] = str(exc)
                return cached
            raise MarketplaceDataError(f"Mercado Livre request failed: {exc}") from exc
        items = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise MarketplaceDataError("Mercado Livre returned invalid product items")
        rows = []
        for item in items:
            if not isinstance(item, dict) or isinstance(item.get("price"), bool):
                continue
            try:
                price = float(item.get("price"))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(price) or price <= 0 or item.get("currency_id", "BRL") != "BRL":
                continue
            rows.append({
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "price": price,
                "currency": "BRL",
                "url": str(item.get("permalink") or ""),
                "condition": str(item.get("condition") or ""),
                "sold_quantity": item.get("sold_quantity"),
            })
        if len(rows) < 3:
            cached = self._read_cache(cache_key)
            if cached:
                cached["live_error"] = "Mercado Livre returned fewer than three priced listings"
                return cached
            raise MarketplaceDataError("Mercado Livre returned fewer than three priced listings")
        result = {
            "category": cache_key,
            "market": "BR",
            "query": query,
            "prices": sorted(row["price"] for row in rows),
            "listings": rows,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "source": "Mercado Livre API",
            "source_url": self.source_url,
            "data_mode": "live",
        }
        self._write_cache(cache_key, result)
        return result

    def _read_cache(self, category_key: str) -> dict[str, Any] | None:
        if not self.cache_path.is_file():
            return None
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            result = payload.get(category_key) if isinstance(payload, dict) else None
            if not isinstance(result, dict) or result.get("market") != "BR" or result.get("category") != category_key:
                return None
            observed = datetime.fromisoformat(result["observed_at"])
            prices, listings = result["prices"], result["listings"]
            if (observed.tzinfo is None or observed > datetime.now(timezone.utc)
                    or len(prices) < 3 or len(prices) != len(listings)
                    or not all(not isinstance(price, bool) and math.isfinite(float(price)) and float(price) > 0 for price in prices)
                    or not all(row.get("currency") == "BRL" for row in listings)
                    or sorted(prices) != sorted(row["price"] for row in listings)
                    or result.get("source_url") != self.source_url):
                return None
            return {**result, "data_mode": "cached"}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return None

    def _write_cache(self, category_key: str, result: dict[str, Any]) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {}
            if self.cache_path.is_file():
                payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                payload = {}
            payload[category_key] = result
            self.cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            # The live response is still usable when the cache is read-only.
            return
