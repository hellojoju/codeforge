"""ProactiveAnalysisService 测试"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from ralph.proactive_service import ProactiveAnalysisService
from ralph.schema.brainstorm_record import BrainstormRecord, FeatureNode, FeatureTree


@pytest.fixture
def service():
    mock_config = MagicMock()
    mock_config.resolve_agent_provider.return_value = {"provider_id": "test", "model": "gpt-4", "source": "test"}
    mock_config.proxy_request.return_value = {"ok": True, "data": {"choices": [{"message": {"content": '{"items": [{"item_id": "pa-1", "category": "product_type", "content": "SaaS 产品", "confidence": 0.8}]}'}}]}}
    yield ProactiveAnalysisService(config_manager=mock_config)


@pytest.fixture
def empty_record():
    record = BrainstormRecord(record_id="bs-test", project_name="测试项目")
    record.user_message = "我想做一个在线协作文档系统"
    root = FeatureNode(node_id="fn-root", name="测试项目", level="product")
    record.feature_tree = FeatureTree(root_id="fn-root", nodes={"fn-root": root}, current_exploring_id="fn-root")
    return record


def test_service_analyze_with_mock(service, empty_record):
    """测试 analyze 方法生成分析结果"""
    analysis = service.analyze(empty_record)
    assert analysis.analysis_id.startswith("pa-")
    assert analysis.created_at != ""
    assert empty_record.proactive_analysis is analysis


def test_service_analyze_no_config():
    """测试无 config 时 graceful 降级"""
    svc = ProactiveAnalysisService(config_manager=None)
    record = BrainstormRecord(record_id="bs-noconfig", project_name="Test")
    record.user_message = "做一个博客"
    root = FeatureNode(node_id="fn-root", name="Test", level="product")
    record.feature_tree = FeatureTree(root_id="fn-root", nodes={"fn-root": root}, current_exploring_id="fn-root")
    analysis = svc.analyze(record)
    # LLM 不可用时应创建空 analysis
    assert analysis is not None
    assert analysis.items == []


def test_parse_items_invalid_json(service):
    """测试无效 JSON 输入的容错"""
    items = service._parse_items("not json at all")
    assert items == []


def test_parse_items_from_markdown_block(service):
    """测试从 markdown code fence 中提取 JSON"""
    content = '''```json
{"items": [{"item_id": "pa-1", "category": "module", "content": "用户管理", "confidence": 0.8}]}
```'''
    items = service._parse_items(content)
    assert len(items) == 1
    assert items[0].content == "用户管理"
    assert items[0].confidence == 0.8


def test_build_summary(service):
    """测试摘要生成"""
    from ralph.schema.brainstorm_record import ProactiveAnalysisItem
    items = [
        ProactiveAnalysisItem(item_id="1", category="module", content="用户管理", confidence=0.8),
        ProactiveAnalysisItem(item_id="2", category="risk", content="并发问题", confidence=0.5),
        ProactiveAnalysisItem(item_id="3", category="question", content="目标用户是谁？", confidence=0.9),
    ]
    summary = service._build_summary(items)
    assert "用户管理" in summary
    assert "并发问题" in summary
    assert "目标用户" in summary


def test_parse_items_empty_input(service):
    """测试空字符串输入"""
    items = service._parse_items("")
    assert items == []


def test_build_summary_empty_items(service):
    """测试空列表摘要"""
    summary = service._build_summary([])
    assert "分析完成" in summary
