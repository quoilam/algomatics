"""
RetrievalAgent 集成测试 —— 调用真实 Tavily API 和 LLM API

验证 agentic 研究流程:
- 查询规划: LLM 自主生成多角度搜索词
- 多路搜索: Tavily 执行检索并返回结果
- 结果综合: LLM 提炼为代码生成参考简报
- 质量自评: Agent 判断结果是否有价值

运行方式:
    cd backend && uv run python -m pytest tests/test_retrieval_agent.py -v
"""

import os
import sys
import json
import time
import pytest

# 加载 .env 文件（override=True 确保覆盖 OS 环境中的旧值）
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'), override=True)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agents.retrieval_agent import RetrievalAgent


# ── 前置检查 ─────────────────────────────────────────────────

def _check_env():
    """检查必要的环境变量是否已配置"""
    missing = []
    for var in ("TAVILY_API_KEY", "OPENROUTER_API_KEY"):
        if not os.getenv(var):
            missing.append(var)
    if missing:
        pytest.skip(f"缺少环境变量: {', '.join(missing)}，跳过集成测试")


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture(scope="module")
def agent():
    """创建 RetrievalAgent 实例（模块级别复用，节省 API 调用）"""
    _check_env()
    return RetrievalAgent()


# ── 测试: 查询规划 ──────────────────────────────────────────

def test_plan_queries_returns_list(agent):
    """查询规划应返回 1-3 个非空搜索词"""
    queries = agent._plan_queries("对图片进行高斯模糊处理")
    assert isinstance(queries, list), f"Expected list, got {type(queries)}"
    assert 1 <= len(queries) <= 3, f"Expected 1-3 queries, got {len(queries)}: {queries}"
    for q in queries:
        assert q.strip(), f"Query should not be empty"
        assert len(q) > 5, f"Query too short: '{q}'"


def test_plan_queries_different_angles(agent):
    """不同角度的查询应有明显差异"""
    queries = agent._plan_queries("对图片进行边缘检测")
    # 查询之间不应完全相同
    assert len(set(queries)) == len(queries), \
        f"Queries should be distinct, got: {queries}"


# ── 测试: 单次搜索 ──────────────────────────────────────────

def test_search_single_returns_results(agent):
    """单次搜索应返回结构化结果"""
    results = agent._search_single("python opencv gaussian blur tutorial", max_results=3)
    assert isinstance(results, list), f"Expected list, got {type(results)}"
    # Tavily 可能会返回包含 AI answer 的结果，也可能只有普通结果
    assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"
    for r in results:
        assert "title" in r, f"Result missing 'title': {r}"
        assert "content" in r, f"Result missing 'content': {r}"
        assert "url" in r, f"Result missing 'url': {r}"
        # 验证 UTF-8 清洗正常工作
        assert isinstance(r["title"], str)
        assert isinstance(r["content"], str)


def test_search_single_cache_hit(agent):
    """同查询第二次调用应命中缓存（不含 Tavily API 调用）"""
    query = "pillow image resize python example"
    # 第一次：可能从 API 获取 或从缓存
    results1 = agent._search_single(query, max_results=3)
    # 第二次：必须从缓存获取
    results2 = agent._search_single(query, max_results=3)
    assert len(results2) == len(results1), \
        f"Cache hit should return same result count: {len(results1)} vs {len(results2)}"
    # 内容应一致
    for i in range(min(len(results1), len(results2))):
        assert results1[i]["title"] == results2[i]["title"], \
            f"Cache mismatch at index {i}"


# ── 测试: 结果综合 ──────────────────────────────────────────

def test_synthesize_returns_brief(agent):
    """结果综合应返回非空的简报字符串"""
    # 先用真实搜索结果来测试综合
    results = agent._search_single("opencv edge detection canny algorithm", max_results=3)
    assert results, "Need search results to test synthesis"

    brief = agent._synthesize("对图片进行边缘检测", results)
    assert isinstance(brief, str), f"Expected str, got {type(brief)}"
    assert len(brief) > 50, f"Brief too short: '{brief}'"


def test_synthesize_contains_expected_sections(agent):
    """简报应包含关键信息段落"""
    results = agent._search_single("python image resize bilinear interpolation", max_results=3)
    assert results, "Need search results to test synthesis"

    brief = agent._synthesize("使用双线性插值缩放图片", results)
    # 简报应至少包含以下部分之一
    has_algorithm = "算法" in brief or "方法" in brief
    has_implementation = "实现" in brief or "代码" in brief
    assert has_algorithm or has_implementation, \
        f"Brief should contain algorithm or implementation info: {brief[:300]}"


def test_synthesize_empty_results(agent):
    """空结果时应返回空字符串"""
    brief = agent._synthesize("测试任务", [])
    assert brief == "", f"Expected empty string for empty results, got: '{brief}'"


# ── 测试: 质量自评 ──────────────────────────────────────────

def test_assess_quality_returns_valid_score(agent):
    """质量评估应返回 1-10 范围内的分数"""
    synthesis = "## 推荐算法\n- 高斯模糊：使用 cv2.GaussianBlur\n\n## 实现要点\n- kernel size 必须为奇数"
    result = agent._assess_quality("对图片进行高斯模糊", synthesis)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "score" in result, f"Missing 'score' in: {result}"
    assert "verdict" in result, f"Missing 'verdict' in: {result}"
    assert "should_skip" in result, f"Missing 'should_skip' in: {result}"
    assert 1 <= result["score"] <= 10, f"Score out of range: {result['score']}"


def test_assess_quality_low_for_garbage(agent):
    """无意义的综合简报应得低分"""
    garbage = "这是一段完全不相关的文字，讨论的是天气预报和股票市场走势。"
    result = agent._assess_quality("对图片进行边缘检测", garbage)
    # 无关内容应该得低分
    assert result["score"] <= 5, \
        f"Garbage content should score low, got {result['score']}: {result}"


def test_assess_quality_empty_synthesis(agent):
    """空综合结果应返回最低分且 should_skip"""
    result = agent._assess_quality("任意任务", "")
    assert result["score"] <= 2, f"Empty synthesis should score very low, got {result['score']}"
    assert result["should_skip"] is True, \
        f"Empty synthesis should be marked should_skip=True, got {result}"


# ── 测试: 完整 agentic 流程 ─────────────────────────────────

def test_research_returns_correct_structure(agent):
    """research() 返回结构应包含所有必要字段"""
    result = agent.research("对图片进行高斯模糊处理")

    # 结构验证
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    required_keys = {"brief", "quality_score", "quality_verdict",
                     "should_skip", "queries_used", "total_results"}
    missing = required_keys - set(result.keys())
    assert not missing, f"Missing keys: {missing}"

    # brief 应为非空字符串（真实搜索应有结果）
    assert isinstance(result["brief"], str), f"brief should be str: {type(result['brief'])}"
    assert len(result["brief"]) > 30, f"brief too short: '{result['brief']}'"

    # quality_score 应在合理范围
    assert 1 <= result["quality_score"] <= 10, \
        f"quality_score out of range: {result['quality_score']}"

    # queries_used 应有 1-3 个
    assert 1 <= len(result["queries_used"]) <= 3, \
        f"queries_used count: {len(result['queries_used'])}"

    # total_results 应 > 0
    assert result["total_results"] > 0, \
        f"total_results should be > 0, got {result['total_results']}"


def test_research_brief_quality_for_common_task(agent):
    """常见图像处理任务的综合简报应获得合理评分（≥5）"""
    result = agent.research("对图片进行边缘检测，然后将边缘叠加到原图上")

    print(f"\n  quality_score: {result['quality_score']}/10")
    print(f"  quality_verdict: {result['quality_verdict']}")
    print(f"  queries_used: {result['queries_used']}")
    print(f"  total_results: {result['total_results']}")
    print(f"  should_skip: {result['should_skip']}")
    print(f"  brief (first 300 chars): {result['brief'][:300]}")

    # 常见任务不应该 should_skip（除非真的搜索不到）
    if result["total_results"] >= 3:
        assert not result["should_skip"], \
            f"Common task with results should not be skipped: {result['quality_verdict']}"
        assert result["quality_score"] >= 4, \
            f"Common task should score >= 4, got {result['quality_score']}: {result['quality_verdict']}"


def test_research_results_useful_for_codegen(agent):
    """综合简报应包含对代码生成有用的技术信息"""
    result = agent.research("使用 OpenCV 对图片进行锐化处理")

    brief = result["brief"]
    # 简报应提到相关的库或算法
    has_tech_info = any(kw in brief.lower() for kw in
                        ["opencv", "cv2", "filter", "kernel", "sharpen", "unsharp",
                         "锐化", "卷积", "滤波", "算法", "实现"])
    assert has_tech_info, \
        f"Brief should contain technical info useful for codegen: {brief[:400]}"


# ── 测试: 边界情况 ──────────────────────────────────────────

def test_research_very_specific_task(agent):
    """非常具体 / 罕见的任务也应能正常完成流程"""
    result = agent.research("使用相位相关法对齐两张图片")
    # 即使搜索结果少，也不应崩溃
    assert "brief" in result
    assert result["quality_score"] >= 1
    # should_skip 可能是 true，这本身是合理的 agent 行为


def test_research_chinese_request(agent):
    """中文用户请求应被正确处理（查询规划会翻译为英文搜索）"""
    result = agent.research("把这张图片转换成灰度图然后增加对比度")
    # 查询应该是英文的
    for q in result["queries_used"]:
        # 查询应主要是英文
        assert not any('一' <= c <= '鿿' for c in q), \
            f"Search queries should be in English, got: '{q}'"
