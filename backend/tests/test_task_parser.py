"""
测试 TaskParser 的任务分类和关键词提取功能。
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from controller.task_parser import TaskParser


def _check_env():
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")


@pytest.fixture(scope="module")
def parser():
    _check_env()
    return TaskParser()


# ── 启发式分类测试（不依赖 LLM） ──

def test_heuristic_simple_crop(parser):
    result = parser._heuristic_classify("帮我把图片裁剪一下")
    assert result["task_type"] == "simple"
    assert result["source"] == "heuristic"
    assert result["confidence"] > 0


def test_heuristic_simple_resize(parser):
    result = parser._heuristic_classify("缩放这张图片到800x600")
    assert result["task_type"] == "simple"
    assert any("缩放" in kw or "resize" in kw for kw in result["keywords"])


def test_heuristic_medium_denoise(parser):
    result = parser._heuristic_classify("对输入图像进行降噪处理")
    assert result["task_type"] == "medium"


def test_heuristic_medium_edge_detect(parser):
    result = parser._heuristic_classify("检测图像中的边缘")
    assert result["task_type"] == "medium"


def test_heuristic_complex_watermark(parser):
    result = parser._heuristic_classify("去除图片中的水印")
    assert result["task_type"] == "complex"
    assert any("水印" in kw for kw in result["keywords"])


def test_heuristic_complex_segmentation(parser):
    result = parser._heuristic_classify("对图像进行语义分割")
    assert result["task_type"] == "complex"


def test_heuristic_unknown_defaults_medium(parser):
    result = parser._heuristic_classify("帮我处理一下这张图")
    assert result["task_type"] == "medium"
    assert result["confidence"] <= 0.5


def test_heuristic_speed_constraint(parser):
    result = parser._heuristic_classify("快速裁剪这张图片", speed_detected=True)
    assert result["constraint"] == "speed"
    assert result["task_type"] == "simple"


def test_heuristic_simple_overrides_medium(parser):
    """简单关键词 + 中等关键词 → 应标为中等（避免跳过必要步骤）"""
    result = parser._heuristic_classify("裁剪并降噪处理")
    # 有 medium 关键词存在时应转为 medium
    assert result["task_type"] == "medium"


# ── Speed 检测 ──

def test_detect_speed(parser):
    assert parser._detect_speed("快速处理") is True
    assert parser._detect_speed("fast processing") is True
    assert parser._detect_speed("尽快给我结果") is True
    assert parser._detect_speed("帮我处理一下") is False


# ── JSON 解析 ──

def test_parse_valid_json(parser):
    result = parser._parse_json('{"task_type":"simple","keywords":["crop"],"constraint":"none","confidence":0.9,"explanation":"test"}')
    assert result is not None
    assert result["task_type"] == "simple"


def test_parse_json_in_text(parser):
    result = parser._parse_json('Some text {"task_type":"medium","keywords":["denoise"],"constraint":"none","confidence":0.7,"explanation":"test"} more text')
    assert result is not None
    assert result["task_type"] == "medium"


def test_parse_invalid_json(parser):
    result = parser._parse_json("not json at all")
    assert result is None


# ── LLM 分类测试（需要 API key） ──

def test_llm_parse_simple_request(parser):
    result = parser.parse("把图片裁剪成200x200")
    assert result["task_type"] in ("simple", "medium", "complex")
    assert "keywords" in result
    assert "constraint" in result
    assert "confidence" in result
    assert 0 <= result["confidence"] <= 1


def test_llm_parse_returns_valid_constraint(parser):
    result = parser.parse("降噪处理")
    assert result["constraint"] in ("speed", "quality", "none")


def test_llm_parse_handles_chinese(parser):
    result = parser.parse("帮我做一下高斯模糊")
    assert result["task_type"] in ("simple", "medium", "complex")
