"""ToolDiscoveryService 测试"""
import pytest
from unittest.mock import MagicMock

from ralph.tool_discovery import ToolDiscoveryService
from ralph.schema.brainstorm_record import ToolCandidate, ToolDiscoveryResult, ToolEvaluation


@pytest.fixture
def service():
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": "[]"}}]}}
    yield ToolDiscoveryService(config_manager=mock_config)


def test_discover_returns_results(service):
    """测试工具发现返回结果"""
    from ralph.schema.brainstorm_record import ToolCandidate, ToolEvaluation
    svc = service
    # Patch internal methods to return controlled data
    svc._generate_queries = lambda need: ["fastapi github"]
    svc._search_candidate = lambda q: [
        ToolCandidate(
            candidate_id="tc-1", name="FastAPI",
            source="github", url="https://github.com/tiangolo/fastapi",
            description="Modern web framework", license="MIT", stars=70000,
            last_updated="2026-01-15", package_name="fastapi",
        )
    ]
    svc._evaluate_candidate = lambda c, need: ToolEvaluation(
        candidate_id="tc-1", functional_fit=5, maintenance_health=5,
        license_fit=5, stack_compatibility=5,
        security_risk="low", integration_cost="low",
        summary="优秀", recommendation="adopt",
    )

    results = svc.discover(["Web 框架"])
    assert len(results) == 1
    result = results[0]
    assert result.tool_need == "Web 框架"
    assert len(result.queries) >= 1
    assert len(result.candidates) == 1
    assert result.candidates[0].name == "FastAPI"


def test_discover_no_config():
    """测试无 config 时的降级行为"""
    svc = ToolDiscoveryService(config_manager=None)
    results = svc.discover(["Web 框架"])
    assert len(results) == 1
    assert results[0].tool_need == "Web 框架"
    assert results[0].candidates == []
    assert results[0].evaluations == []


def test_generate_queries_fallback(service):
    """测试 query 生成在 LLM 失败时的 fallback"""
    queries = service._generate_queries("数据库 ORM")
    assert isinstance(queries, list)
    assert len(queries) >= 1


def test_evaluate_candidate_no_config():
    """测试无 config 时评估降级"""
    svc = ToolDiscoveryService(config_manager=None)
    candidate = ToolCandidate(
        candidate_id="tc-1", name="FastAPI",
        source="github", url="https://github.com/tiangolo/fastapi",
        description="Fast web framework",
    )
    ev = svc._evaluate_candidate(candidate, "Web 框架")
    assert ev.security_risk == "unknown"
    assert ev.recommendation == "compare"


def test_candidate_defaults():
    """测试 ToolCandidate 创建"""
    c = ToolCandidate(
        candidate_id="tc-1", name="Test",
        source="github", url="https://example.com",
        description="Test tool",
    )
    assert c.stars is None
    assert c.license == ""


def test_evaluation_defaults():
    """测试 ToolEvaluation 创建"""
    ev = ToolEvaluation(
        candidate_id="tc-1", functional_fit=5, maintenance_health=5,
        license_fit=5, stack_compatibility=5,
        security_risk="low", integration_cost="low",
        summary="好", recommendation="adopt",
    )
    assert ev.recommendation == "adopt"


def test_discover_empty_needs():
    """测试空工具需求"""
    svc = ToolDiscoveryService(config_manager=None)
    results = svc.discover([])
    assert results == []


def test_discover_multiple_needs():
    """测试多个工具需求"""
    svc = ToolDiscoveryService(config_manager=None)
    results = svc.discover(["Web 框架", "数据库 ORM"])
    assert len(results) == 2
    assert results[0].tool_need == "Web 框架"
    assert results[1].tool_need == "数据库 ORM"


def test_search_provider_results_are_used_before_llm_search():
    """有搜索 provider 结果时，工具发现候选应带证据链。"""
    mock_config = MagicMock()
    mock_config.get_search_providers.return_value = {
        "enabled": True,
        "providers": [
            {
                "id": "github",
                "type": "github",
                "enabled": True,
                "static_results": {
                    "FastAPI github": [
                        {
                            "title": "FastAPI",
                            "url": "https://github.com/fastapi/fastapi",
                            "snippet": "Modern Python web framework",
                        }
                    ]
                },
            }
        ],
    }
    svc = ToolDiscoveryService(config_manager=mock_config)
    candidates = svc._search_candidate("FastAPI github")
    assert len(candidates) == 1
    assert candidates[0].name == "FastAPI"
    assert candidates[0].evidence_refs[0].source_type == "github"
    mock_config.resolve_agent_provider.assert_not_called()


def test_llm_candidate_search_skips_non_object_items():
    """LLM 返回脏数据时不应抛 500。"""
    mock_config = MagicMock()
    mock_config.get_search_providers.return_value = {"enabled": False, "providers": []}
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4"}
    mock_config.proxy_request.return_value = {
        "ok": True,
        "data": {"choices": [{"message": {"content": '["bad candidate"]'}}]},
    }
    svc = ToolDiscoveryService(config_manager=mock_config)
    assert svc._search_candidate("auth github") == []


def test_llm_candidate_search_adds_evidence_refs():
    """LLM 候选也应保留结构化证据链。"""
    mock_config = MagicMock()
    mock_config.get_search_providers.return_value = {"enabled": False, "providers": []}
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4"}
    mock_config.proxy_request.return_value = {
        "ok": True,
        "data": {"choices": [{"message": {"content": '[{"name":"Casbin","source":"github","url":"https://github.com/casbin/casbin","description":"Authorization library"}]'}}]},
    }
    svc = ToolDiscoveryService(config_manager=mock_config)
    candidates = svc._search_candidate("auth github")
    assert len(candidates) == 1
    assert candidates[0].evidence_refs[0].title == "Casbin"
