"""Search provider abstraction for tool discovery.

The first implementation is deliberately conservative: it normalizes configured
search providers, supports deterministic static results for tests/local demos,
and fails closed when no real provider is configured. Network-backed providers
can plug into this surface without changing ToolDiscoveryService.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

from ralph.schema.brainstorm_record import EvidenceRef, _now_iso


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    source_type: str = "web"
    metadata: dict[str, Any] = field(default_factory=dict)

    def evidence_ref(self) -> EvidenceRef:
        return EvidenceRef(
            source_type=self.source_type,
            title=self.title,
            url=self.url,
            quote_or_summary=self.snippet,
            captured_at=_now_iso(),
            confidence=float(self.metadata.get("confidence", 0.7)),
        )


class SearchProviderManager:
    """Loads search-provider config and returns normalized search results."""

    def __init__(self, config_manager: Any = None):
        self._config = config_manager
        self._cache: dict[str, tuple[float, list[SearchResult]]] = {}

    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        if not query.strip():
            return []

        cfg = self._load_config()
        if not cfg.get("enabled"):
            return []

        cache_key = self._cache_key(query, limit)
        ttl = int(cfg.get("cache_ttl_seconds", 86400))
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[0] <= ttl:
            return cached[1]

        results: list[SearchResult] = []
        for provider in cfg.get("providers", []):
            if not provider.get("enabled", True):
                continue
            results.extend(self._search_provider(provider, query, limit - len(results)))
            if len(results) >= limit:
                break

        results = results[:limit]
        self._cache[cache_key] = (time.time(), results)
        return results

    def _load_config(self) -> dict:
        if self._config is None:
            return {"enabled": False, "providers": []}
        if hasattr(self._config, "get_search_providers"):
            cfg = self._config.get_search_providers()
            if isinstance(cfg, dict):
                return cfg
        return {"enabled": False, "providers": []}

    def _search_provider(self, provider: dict, query: str, limit: int) -> list[SearchResult]:
        if limit <= 0:
            return []

        provider_type = provider.get("type", provider.get("id", "web"))

        # Static results are useful for offline development and deterministic tests.
        static_results = provider.get("static_results", {})
        matched = static_results.get(query) or static_results.get("*")
        if matched:
            return [self._from_dict(item, provider_type) for item in matched[:limit]]

        try:
            timeout = float(provider.get("timeout_seconds", 10))
            if provider_type == "github":
                return self._search_github(provider, query, limit, timeout)
            if provider_type == "package_registry":
                return self._search_package_registry(provider, query, limit, timeout)
            if provider.get("endpoint_url"):
                return self._search_json_endpoint(provider, query, limit, timeout)
        except Exception:
            return []

        return []

    def _from_dict(self, item: dict, provider_type: str) -> SearchResult:
        metadata = dict(item.get("metadata", {}))
        if "confidence" in item:
            metadata["confidence"] = item["confidence"]
        return SearchResult(
            title=item.get("title", item.get("name", "")),
            url=item.get("url", ""),
            snippet=item.get("snippet", item.get("description", "")),
            source_type=item.get("source_type", provider_type),
            metadata=metadata,
        )

    @staticmethod
    def _cache_key(query: str, limit: int) -> str:
        raw = f"{query}\0{limit}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _search_github(self, provider: dict, query: str, limit: int, timeout: float) -> list[SearchResult]:
        url = f"https://api.github.com/search/repositories?q={quote_plus(query)}&sort=stars&order=desc&per_page={limit}"
        data = self._fetch_json(url, provider, timeout)
        items = data.get("items", []) if isinstance(data, dict) else []
        results = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            results.append(SearchResult(
                title=item.get("full_name") or item.get("name", ""),
                url=item.get("html_url", ""),
                snippet=item.get("description") or "",
                source_type="github",
                metadata={
                    "stars": item.get("stargazers_count"),
                    "license": (item.get("license") or {}).get("spdx_id", ""),
                    "last_updated": item.get("updated_at", ""),
                    "confidence": 0.8,
                },
            ))
        return results

    def _search_package_registry(self, provider: dict, query: str, limit: int, timeout: float) -> list[SearchResult]:
        registry = provider.get("registry", "npm")
        if registry != "npm":
            return []
        params = urlencode({"text": query, "size": limit})
        data = self._fetch_json(f"https://registry.npmjs.org/-/v1/search?{params}", provider, timeout)
        objects = data.get("objects", []) if isinstance(data, dict) else []
        results = []
        for obj in objects[:limit]:
            pkg = obj.get("package", {}) if isinstance(obj, dict) else {}
            if not isinstance(pkg, dict):
                continue
            name = pkg.get("name", "")
            results.append(SearchResult(
                title=name,
                url=pkg.get("links", {}).get("npm", f"https://www.npmjs.com/package/{name}" if name else ""),
                snippet=pkg.get("description", ""),
                source_type="package_registry",
                metadata={"confidence": 0.7, "package_name": name},
            ))
        return results

    def _search_json_endpoint(self, provider: dict, query: str, limit: int, timeout: float) -> list[SearchResult]:
        endpoint = provider.get("endpoint_url", "")
        separator = "&" if "?" in endpoint else "?"
        url = f"{endpoint}{separator}{urlencode({'q': query, 'limit': limit})}"
        data = self._fetch_json(url, provider, timeout)
        items = data.get("results", data.get("items", [])) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        return [self._from_dict(item, provider.get("type", "web")) for item in items[:limit] if isinstance(item, dict)]

    def _fetch_json(self, url: str, provider: dict, timeout: float) -> Any:
        req = Request(url, method="GET")
        req.add_header("Accept", "application/json")
        token = provider.get("token") or provider.get("api_key")
        if token:
            scheme = "token" if "api.github.com" in url else "Bearer"
            req.add_header("Authorization", f"{scheme} {token}")
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
