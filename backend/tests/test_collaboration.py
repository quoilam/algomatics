"""
测试协作协议和协调器 — Stage 4。
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agents.collaboration_protocol import CollaborationMessage, MessageType
from controller.collaboration_coordinator import CollaborationCoordinator


# ── 协议消息测试 ──

def test_pre_evaluation_message():
    msg = CollaborationMessage.pre_evaluation(
        speaker="EvaluationAgent",
        listener="CodeGenerationAgent",
        code="import cv2\nimg = cv2.imread(input_image_path)",
        issues=["未使用 output_path"],
        quick_score=3.0,
        suggestion="添加保存逻辑",
    )
    assert msg.message_type == MessageType.PRE_EVALUATION
    assert msg.speaker == "EvaluationAgent"
    assert msg.listener == "CodeGenerationAgent"
    assert msg.payload["quick_score"] == 3.0
    assert len(msg.payload["issues"]) == 1
    assert msg.payload["should_revise"] is True  # score < 4 触发
    assert msg.priority == 1  # 低分 → 高优先级


def test_pre_evaluation_high_score():
    msg = CollaborationMessage.pre_evaluation(
        speaker="EvaluationAgent",
        listener="CodeGenerationAgent",
        code="import cv2\nimg = cv2.imread(input_image_path)\ncv2.imwrite(output_path, img)",
        issues=[],
        quick_score=9.0,
    )
    assert msg.payload["should_revise"] is False
    assert msg.priority == 2  # 高分 → 普通优先级


def test_pre_evaluation_single_issue_ok_score():
    """单个问题 + 中等评分 (>=4) 不应触发 revise"""
    msg = CollaborationMessage.pre_evaluation(
        speaker="EvaluationAgent",
        listener="CodeGenerationAgent",
        code="import cv2\nimg = cv2.imread(input_image_path)",
        issues=["未使用 output_path"],
        quick_score=5.0,
    )
    assert msg.payload["should_revise"] is False  # score >= 4 且 issue < 2


def test_pre_evaluation_two_issues_triggers():
    """两个问题即使评分高也应触发 revise"""
    msg = CollaborationMessage.pre_evaluation(
        speaker="EvaluationAgent",
        listener="CodeGenerationAgent",
        code="img = Image.open(input_image_path)",
        issues=["未使用 output_path", "缺少导入"],
        quick_score=6.0,
    )
    assert msg.payload["should_revise"] is True  # issues >= 2


def test_quality_report_message():
    msg = CollaborationMessage.quality_report(
        speaker="RetrievalAgent",
        listener="CodeGenerationAgent",
        quality_score=3.0,
        verdict="搜索结果质量低",
        should_skip=True,
        queries_used=["python image denoise"],
    )
    assert msg.message_type == MessageType.QUALITY_REPORT
    assert msg.payload["should_skip"] is True
    assert msg.payload["quality_score"] == 3.0


def test_error_feedback_message():
    msg = CollaborationMessage.error_feedback(
        speaker="ExecutionAgent",
        listener="CodeGenerationAgent",
        error_type="import_error",
        error_message="No module named 'cv2'",
        error_context={"missing_import": "cv2"},
        repair_hints=["检查 cv2 是否已安装"],
    )
    assert msg.message_type == MessageType.ERROR_FEEDBACK
    assert msg.payload["error_type"] == "import_error"
    assert msg.priority == 1  # 错误反馈 → 最高优先级


def test_message_to_dict():
    msg = CollaborationMessage.quality_report(
        speaker="RetrievalAgent",
        listener="CodeGenerationAgent",
        quality_score=7.0,
        verdict="搜索结果良好",
        should_skip=False,
    )
    d = msg.to_dict()
    assert d["speaker"] == "RetrievalAgent"
    assert d["message_type"] == "quality_report"
    assert "timestamp" in d


# ── 协调器测试 ──

@pytest.fixture
def coordinator():
    return CollaborationCoordinator()


def test_send_pre_evaluation(coordinator):
    msg = coordinator.send_pre_evaluation(
        code="import cv2",
        quick_score=6.0,
        issues=["缺少 output_path"],
        suggestion="需要保存图片",
    )
    assert msg.message_type == MessageType.PRE_EVALUATION
    assert len(coordinator.get_log()) == 1


def test_send_quality_report(coordinator):
    msg = coordinator.send_quality_report(
        quality_score=5.0,
        verdict="质量一般",
        should_skip=False,
    )
    assert msg.message_type == MessageType.QUALITY_REPORT
    assert len(coordinator.get_log()) == 1


def test_send_error_feedback(coordinator):
    msg = coordinator.send_error_feedback(
        error_type="syntax_error",
        error_message="invalid syntax",
    )
    assert msg.message_type == MessageType.ERROR_FEEDBACK


def test_coordinator_log_accumulates(coordinator):
    coordinator.send_quality_report(5.0, "test", False)
    coordinator.send_error_feedback("type_error", "type mismatch")
    assert len(coordinator.get_log()) == 2

    # 第二条消息应包含正确的字段
    last = coordinator.get_log()[-1]
    assert last["message_type"] == "error_feedback"


def test_coordinator_clear_log(coordinator):
    coordinator.send_quality_report(5.0, "test", False)
    coordinator.clear_log()
    assert len(coordinator.get_log()) == 0


def test_scenario_enabled_defaults(coordinator):
    assert coordinator.is_scenario_enabled("pre_evaluation") is True
    assert coordinator.is_scenario_enabled("quality_report") is True
    assert coordinator.is_scenario_enabled("error_feedback") is True


def test_fallback_strategy(coordinator):
    assert coordinator.get_fallback("pre_evaluation") == "skip_pre_eval"
    assert coordinator.get_fallback("error_feedback") == "use_default_repair"


def test_multiple_collaboration_rounds(coordinator):
    """模拟完整的一次协作流程"""
    # 1. Retrieval 发送质量报告
    q_msg = coordinator.send_quality_report(
        quality_score=4.0,
        verdict="质量偏低",
        should_skip=True,
    )
    # 2. Evaluation 发送前置评估
    p_msg = coordinator.send_pre_evaluation(
        code="import cv2",
        quick_score=3.0,
        issues=["语法错误"],
    )
    # 3. Execution 发送错误反馈
    e_msg = coordinator.send_error_feedback(
        error_type="import_error",
        error_message="No module named 'cv2'",
    )

    log = coordinator.get_log()
    assert len(log) == 3
    assert log[0]["message_type"] == "quality_report"
    assert log[1]["message_type"] == "pre_evaluation"
    assert log[2]["message_type"] == "error_feedback"
