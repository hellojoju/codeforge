"""TechnicalRouteService 测试"""
import pytest
import tempfile
from unittest.mock import MagicMock

from ralph.technical_route_service import TechnicalRouteService
from ralph.schema.brainstorm_record import (
    BrainstormRecord, FeatureNode, FeatureTree, TechnicalRoute,
)


@pytest.fixture
def service():
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {
        "ok": True,
        "data": {"choices": [{"message": {
            "content": '{"architecture_summary":"前后端分离","frontend_stack":["React"],"backend_stack":["FastAPI"],"data_storage":["PostgreSQL"],"integrations":[],"non_functional_requirements":[],"key_risks":[],"tool_needs":["Web框架"]}'
        }}]}
    }
    yield TechnicalRouteService(config_manager=mock_config)


@pytest.fixture
def confirmed_record():
    record = BrainstormRecord(record_id="bs-tr", project_name="协作系统")
    root = FeatureNode(node_id="fn-root", name="协作系统", level="product", status="confirmed")
    root.vision = "在线协作"
    root.target_users = ["团队"]
    root.roles = ["管理员", "成员"]
    fn1 = FeatureNode(
        node_id="fn-001", name="文档编辑", level="function", status="confirmed",
        user_stories=["作为用户可以编辑文档"],
    )
    record.feature_tree = FeatureTree(
        root_id="fn-root",
        nodes={"fn-root": root, "fn-001": fn1},
    )
    return record


def test_generate_route(service, confirmed_record):
    """测试技术路线生成"""
    route = service.generate_route(confirmed_record)
    assert route.route_id.startswith("tr-")
    assert route.frontend_stack == ["React"]
    assert route.backend_stack == ["FastAPI"]
    assert route.tool_needs == ["Web框架"]


def test_generate_route_no_config(confirmed_record):
    """测试无 config 时返回默认空路线"""
    svc = TechnicalRouteService(config_manager=None)
    route = svc.generate_route(confirmed_record)
    assert route.architecture_summary == "待分析"
    assert route.tool_needs == []


def test_render_spec_text(service, confirmed_record):
    """测试 Spec 文本渲染"""
    spec = service._render_spec_text(confirmed_record)
    assert "协作系统" in spec
    assert "文档编辑" in spec
    assert "在线协作" in spec


def test_render_spec_text_empty():
    """测试空记录的 Spec 渲染"""
    record = BrainstormRecord(record_id="bs-empty", project_name="空项目")
    svc = TechnicalRouteService(config_manager=None)
    spec = svc._render_spec_text(record)
    assert "空项目" in spec


def test_render_spec_text_skips_unconfirmed():
    """测试未确认节点被跳过"""
    record = BrainstormRecord(record_id="bs-skip", project_name="跳过")
    root = FeatureNode(node_id="fn-root", name="跳过", level="product")
    fn1 = FeatureNode(
        node_id="fn-001", name="未确认功能", level="function", status="exploring",
        user_stories=["作为用户..."],
    )
    fn2 = FeatureNode(
        node_id="fn-002", name="已确认功能", level="function", status="confirmed",
        user_stories=["作为管理员..."],
    )
    record.feature_tree = FeatureTree(
        root_id="fn-root",
        nodes={"fn-root": root, "fn-001": fn1, "fn-002": fn2},
    )
    svc = TechnicalRouteService(config_manager=None)
    spec = svc._render_spec_text(record)
    assert "未确认功能" not in spec
    assert "已确认功能" in spec
