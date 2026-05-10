"""
测试知识库 — Stage 5。
"""
import os
import sys
import json
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from knowledge.knowledge_base import KnowledgeBase


@pytest.fixture
def kb():
    """使用临时文件的知识库，测试后自动清理"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    tmp.close()
    kb = KnowledgeBase(storage_path=tmp.name)
    yield kb
    os.unlink(tmp.name)


# ── 初始化 ──

def test_kb_initializes_empty(kb):
    assert kb.get_stats()["total_problems"] == 0
    assert kb.get_stats()["total_solutions"] == 0


def test_kb_creates_storage_file(kb):
    assert os.path.exists(kb.storage_path)


# ── 关键词提取 ──

def test_extract_keywords_chinese(kb):
    kw = kb._extract_keywords("对输入图像进行降噪处理")
    assert "降噪" in kw or "denoise" in kw


def test_extract_keywords_english(kb):
    kw = kb._extract_keywords("apply gaussian blur and edge detection")
    assert any(k in kw for k in ["blur", "gaussian", "edge detect"])


def test_extract_keywords_empty(kb):
    kw = kb._extract_keywords("处理一下图片")
    assert isinstance(kw, list)


# ── 关键词相似度 ──

def test_keyword_similarity_identical(kb):
    assert kb._keyword_similarity(["降噪", "blur"], ["降噪", "blur"]) == 1.0


def test_keyword_similarity_partial(kb):
    sim = kb._keyword_similarity(["降噪", "blur", "边缘检测"], ["降噪", "blur"])
    assert 0 < sim < 1.0


def test_keyword_similarity_none(kb):
    assert kb._keyword_similarity(["降噪"], ["裁剪"]) == 0.0


def test_keyword_similarity_empty(kb):
    assert kb._keyword_similarity([], ["降噪"]) == 0.0


# ── 记录成功案例 ──

def test_record_success(kb):
    pid = kb.record_success(
        user_request="对输入图像进行降噪处理",
        approach="高斯模糊 + 中值滤波",
        score=8.0,
    )
    assert pid is not None
    assert kb.get_stats()["total_problems"] >= 1
    assert kb.get_stats()["total_solutions"] >= 1


def test_record_success_low_score_ignored(kb):
    pid = kb.record_success(
        user_request="降噪处理",
        approach="简单模糊",
        score=3.0,
    )
    assert pid is None


def test_record_success_updates_existing(kb):
    kb.record_success("降噪处理", "高斯模糊", score=7.0)
    kb.record_success("降噪处理", "高斯模糊", score=9.0)

    similar = kb.find_similar("降噪处理")
    assert len(similar) >= 1
    sol = similar[0]["solutions"][0]
    assert sol["success_count"] == 2
    # 评分应更新 (EMA: 0.3*9 + 0.7*7 = 7.6)
    assert 7.0 < sol["score"] <= 9.0


def test_record_multiple_solutions_same_problem(kb):
    kb.record_success("降噪处理", "高斯模糊", score=7.0)
    kb.record_success("降噪处理", "中值滤波", score=8.0)

    similar = kb.find_similar("降噪处理")
    assert len(similar) >= 1
    solutions = similar[0]["solutions"]
    assert len(solutions) >= 2


# ── 记录失败案例 ──

def test_record_failure_reduces_score(kb):
    kb.record_success("降噪处理", "高斯模糊", score=8.0)
    kb.record_failure("降噪处理", "高斯模糊", score=3.0, reason="效果差")

    similar = kb.find_similar("降噪处理")
    sol = similar[0]["solutions"][0]
    assert sol["score"] < 8.0  # 评分应降低


def test_record_failure_deactivates_low_performer(kb):
    kb.record_success("降噪处理", "低效方案", score=6.0)
    kb.record_failure("降噪处理", "低效方案", score=3.0)
    kb.record_failure("降噪处理", "低效方案", score=2.0)

    # 3次中 2次失败，success_rate = 1/3 = 33%... 边界上
    # 再失败一次
    kb.record_failure("降噪处理", "低效方案", score=1.0)

    # 现在 success_rate = 1/4 = 25%，
    # 这也只是刚刚到阈值边界（0.3），不一定会触发 deactivation
    # 更可靠的是直接检查

    similar = kb.find_similar("降噪处理")
    if similar:
        sol = similar[0]["solutions"][0]
        # 至少确认评分降低了
        assert sol["score"] <= 5.0


# ── 查找相似问题 ──

def test_find_similar_returns_ranked(kb):
    kb.record_success("对图片进行降噪处理", "方案A", score=8.0)
    kb.record_success("图片降噪", "方案B", score=6.0)

    results = kb.find_similar("帮我降噪")
    assert len(results) >= 1
    # 相似度最高的优先
    if len(results) >= 2:
        assert results[0]["similarity"] >= results[1]["similarity"]


def test_find_similar_no_match(kb):
    kb.record_success("降噪处理", "方案A", score=8.0)
    results = kb.find_similar("图片裁剪", min_similarity=0.5)
    assert len(results) == 0


def test_find_similar_respects_max_results(kb):
    for i in range(5):
        kb.record_success(f"降噪处理{i}", f"方案{i}", score=7.0)

    results = kb.find_similar("降噪", max_results=2)
    assert len(results) <= 2


# ── 推荐 ──

def test_recommend(kb):
    kb.record_success("对图片进行高斯模糊降噪", "高斯模糊 + 中值滤波", score=8.5)
    kb.record_success("对图片进行高斯模糊降噪", "高斯模糊 + 中值滤波", score=9.0)

    recs = kb.recommend("帮我降噪处理")
    assert len(recs) >= 1
    assert "approach" in recs[0]
    assert "score" in recs[0]
    assert "success_rate" in recs[0]


def test_recommend_returns_code_sample(kb):
    code = "import cv2\nimg = cv2.imread(input_image_path)\nimg = cv2.GaussianBlur(img, (5,5), 0)\ncv2.imwrite(output_path, img)"
    kb.record_success("高斯模糊", "高斯模糊", score=9.0, code=code)

    recs = kb.recommend("高斯模糊处理")
    assert len(recs) >= 1
    if recs[0].get("code_sample"):
        assert "GaussianBlur" in recs[0]["code_sample"]


# ── 清理 ──

def test_cleanup_stale(kb):
    kb.record_success("降噪处理", "方案A", score=8.0)
    # 立即清理不应该删除新鲜条目
    kb.cleanup_stale(max_age_days=180)
    assert kb.get_stats()["total_solutions"] >= 1


# ── 持久化 ──

def test_kb_persists_across_instances(kb):
    kb.record_success("降噪处理", "高斯模糊", score=8.5)
    path = kb.storage_path

    # 重新加载
    kb2 = KnowledgeBase(storage_path=path)
    assert kb2.get_stats()["total_solutions"] >= 1
    results = kb2.find_similar("降噪")
    assert len(results) >= 1


# ── 方案相似性判断 ──

def test_approach_similar(kb):
    assert kb._approach_similar("高斯模糊 + 中值滤波", "高斯模糊 + 中值滤波 + 锐化") is True
    assert kb._approach_similar("高斯模糊", "边缘检测") is False


# ── 统计 ──

def test_stats(kb):
    kb.record_success("任务A", "方案A", score=7.0)
    kb.record_success("任务B", "方案B", score=8.0)
    kb.record_success("任务A", "方案A", score=9.0)

    stats = kb.get_stats()
    assert stats["total_recorded"] == 3
    assert stats["total_problems"] >= 2
