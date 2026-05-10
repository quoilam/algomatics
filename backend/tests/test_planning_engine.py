"""
测试 PlanningEngine 的策略选择和计划生成。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from controller.planning_engine import PlanningEngine


@pytest.fixture(scope="module")
def engine():
    return PlanningEngine()


# ── 策略名称 ──

def test_strategy_names(engine):
    assert set(engine.STRATEGIES.keys()) == {"fast", "standard", "quality", "conservative"}


# ── 任务类型 → 策略映射 ──

def test_simple_task_maps_to_fast(engine):
    plan = engine.plan({
        "task_type": "simple", "keywords": ["crop"], "constraint": "none",
        "confidence": 0.9, "explanation": "test"
    })
    assert plan["strategy"] == "fast"
    assert plan["enable_search"] is False
    assert plan["enable_iteration"] is False
    assert plan["max_iterations"] == 1
    assert "EvaluationAgent" in plan["skip_steps"]


def test_medium_task_maps_to_standard(engine):
    plan = engine.plan({
        "task_type": "medium", "keywords": ["denoise"], "constraint": "none",
        "confidence": 0.85, "explanation": "test"
    })
    assert plan["strategy"] == "standard"
    assert plan["enable_search"] is True
    assert plan["enable_iteration"] is True
    assert plan["max_iterations"] == 3


def test_complex_task_maps_to_quality(engine):
    plan = engine.plan({
        "task_type": "complex", "keywords": ["inpainting"], "constraint": "none",
        "confidence": 0.9, "explanation": "test"
    })
    assert plan["strategy"] == "quality"
    assert plan["enable_iteration"] is True
    assert plan["max_iterations"] == 5


# ── 置信度触发保守策略 ──

def test_low_confidence_triggers_conservative(engine):
    plan = engine.plan({
        "task_type": "simple", "keywords": [], "constraint": "none",
        "confidence": 0.3, "explanation": "low confidence"
    })
    assert plan["strategy"] == "conservative"


def test_medium_confidence_does_not_trigger(engine):
    plan = engine.plan({
        "task_type": "simple", "keywords": ["crop"], "constraint": "none",
        "confidence": 0.6, "explanation": "borderline"
    })
    # 0.6 is the threshold, < 0.6 triggers conservative
    assert plan["strategy"] == "fast"


# ── Speed 约束强制 fast ──

def test_speed_constraint_overrides_task_type(engine):
    plan = engine.plan({
        "task_type": "complex", "keywords": ["inpainting"], "constraint": "speed",
        "confidence": 0.9, "explanation": "complex but fast"
    })
    assert plan["strategy"] == "fast"


def test_speed_constraint_on_medium(engine):
    plan = engine.plan({
        "task_type": "medium", "keywords": ["denoise"], "constraint": "speed",
        "confidence": 0.8, "explanation": "fast denoise"
    })
    assert plan["strategy"] == "fast"


# ── 策略信息查询 ──

def test_get_strategy_info(engine):
    info = engine.get_strategy_info("standard")
    assert info is not None
    assert info["name"] == "standard"
    assert info["enable_iteration"] is True
    assert info["max_iterations"] == 3


def test_get_nonexistent_strategy(engine):
    info = engine.get_strategy_info("nonexistent")
    assert info is None


# ── 决策原因 ──

def test_plan_includes_decision_reason(engine):
    plan = engine.plan({
        "task_type": "simple", "keywords": ["crop"], "constraint": "none",
        "confidence": 0.9, "explanation": "test"
    })
    assert "decision_reason" in plan
    assert len(plan["decision_reason"]) > 0


def test_plan_decision_reason_mentions_skip(engine):
    plan = engine.plan({
        "task_type": "simple", "keywords": ["crop"], "constraint": "none",
        "confidence": 0.8, "explanation": "test"
    })
    # fast strategy should mention skipped steps
    assert "跳过" in plan["decision_reason"]


# ── 所有策略的可执行性 ──

def test_all_strategies_have_required_fields(engine):
    required = ["name", "description", "task_types", "agent_sequence",
                "skip_steps", "enable_iteration", "max_iterations", "enable_search"]
    for name, strategy in engine.STRATEGIES.items():
        for field in required:
            assert field in strategy, f"Strategy '{name}' missing field '{field}'"
