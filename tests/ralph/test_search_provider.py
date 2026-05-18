"""Search provider abstraction tests."""

from unittest.mock import MagicMock

from ralph.search_provider import SearchProviderManager


def test_search_provider_disabled_returns_empty():
    cfg = MagicMock()
    cfg.get_search_providers.return_value = {"enabled": False, "providers": []}
    search = SearchProviderManager(cfg)
    assert search.search("fastapi") == []


def test_search_provider_static_results_to_evidence():
    cfg = MagicMock()
    cfg.get_search_providers.return_value = {
        "enabled": True,
        "providers": [
            {
                "id": "github",
                "type": "github",
                "enabled": True,
                "static_results": {
                    "fastapi github": [
                        {
                            "title": "FastAPI",
                            "url": "https://github.com/fastapi/fastapi",
                            "snippet": "Modern Python web framework",
                            "confidence": 0.9,
                        }
                    ]
                },
            }
        ],
    }

    results = SearchProviderManager(cfg).search("fastapi github")
    assert len(results) == 1
    assert results[0].title == "FastAPI"
    evidence = results[0].evidence_ref()
    assert evidence.source_type == "github"
    assert evidence.url == "https://github.com/fastapi/fastapi"
