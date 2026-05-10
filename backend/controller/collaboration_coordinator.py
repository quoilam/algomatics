"""
协作协调器 — Stage 4 MVP。

职责:
- 中介 Agent 间的通信消息
- 管理协作场景的触发和降级
- 记录协作日志用于可观测性

MVP 实现的三个关键协作点:
1. CodeGen 后置快速评估 → 预检代码问题再执行
2. Retrieval 质量信号 → 调整 CodeGen 生成策略
3. Execution 错误 → 反馈给 CodeGen 定向修复
"""

from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from agents.collaboration_protocol import CollaborationMessage, MessageType


class CollaborationCoordinator:
    """轻量级协作协调器，中介 Agent 间消息"""

    def __init__(self):
        self.message_log: List[Dict[str, Any]] = []
        self._scenarios = {
            "pre_evaluation": {
                "enabled": True,
                "timeout_seconds": 5,
                "fallback": "skip_pre_eval",
            },
            "quality_report": {
                "enabled": True,
                "fallback": "ignore_quality",
            },
            "error_feedback": {
                "enabled": True,
                "fallback": "use_default_repair",
            },
        }

    def send(self, message: CollaborationMessage) -> Dict[str, Any]:
        """发送协作消息并记录"""
        entry = message.to_dict()
        entry["delivered"] = True
        self.message_log.append(entry)
        return entry

    def is_scenario_enabled(self, scenario: str) -> bool:
        entry = self._scenarios.get(scenario, {})
        return entry.get("enabled", True)

    def get_fallback(self, scenario: str) -> str:
        entry = self._scenarios.get(scenario, {})
        return entry.get("fallback", "skip")

    def get_log(self) -> List[Dict[str, Any]]:
        return list(self.message_log)

    def clear_log(self):
        self.message_log.clear()

    # ── 便捷方法: 触发各协作场景 ──

    def send_pre_evaluation(self,
                            code: str,
                            quick_score: float,
                            issues: List[str],
                            suggestion: str = "") -> CollaborationMessage:
        msg = CollaborationMessage.pre_evaluation(
            speaker="EvaluationAgent",
            listener="CodeGenerationAgent",
            code=code,
            issues=issues,
            quick_score=quick_score,
            suggestion=suggestion,
        )
        self.send(msg)
        return msg

    def send_quality_report(self,
                            quality_score: float,
                            verdict: str,
                            should_skip: bool,
                            queries_used: List[str] = None) -> CollaborationMessage:
        msg = CollaborationMessage.quality_report(
            speaker="RetrievalAgent",
            listener="CodeGenerationAgent",
            quality_score=quality_score,
            verdict=verdict,
            should_skip=should_skip,
            queries_used=queries_used,
        )
        self.send(msg)
        return msg

    def send_error_feedback(self,
                            error_type: str,
                            error_message: str,
                            error_context: Dict[str, Any] = None,
                            repair_hints: List[str] = None) -> CollaborationMessage:
        msg = CollaborationMessage.error_feedback(
            speaker="ExecutionAgent",
            listener="CodeGenerationAgent",
            error_type=error_type,
            error_message=error_message,
            error_context=error_context,
            repair_hints=repair_hints,
        )
        self.send(msg)
        return msg
