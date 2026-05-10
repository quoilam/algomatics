"""
Agent 协作消息协议 — Stage 4 MVP。

定义 Agent 间通信的标准格式，支持:
- pre_evaluation:  代码生成后的快速前置评估
- quality_report:  Retrieval 质量信号传递给 CodeGen
- error_feedback:  Execution 错误反馈给 CodeGen 修复
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, Optional, List


class MessageType:
    PRE_EVALUATION = "pre_evaluation"
    QUALITY_REPORT = "quality_report"
    ERROR_FEEDBACK = "error_feedback"


@dataclass
class CollaborationMessage:
    speaker: str
    listener: str
    message_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 2  # 1=critical, 2=normal, 3=info
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "speaker": self.speaker,
            "listener": self.listener,
            "message_type": self.message_type,
            "payload": self.payload,
            "priority": self.priority,
            "timestamp": self.timestamp,
        }

    @classmethod
    def pre_evaluation(cls, speaker: str, listener: str,
                       code: str, issues: List[str],
                       quick_score: float,
                       suggestion: str = "") -> "CollaborationMessage":
        return cls(
            speaker=speaker,
            listener=listener,
            message_type=MessageType.PRE_EVALUATION,
            payload={
                "code_snippet": code[:2000],
                "issues": issues,
                "quick_score": quick_score,
                "suggestion": suggestion,
                "should_revise": quick_score < 4 or len(issues) >= 2,
            },
            priority=1 if quick_score < 4 else 2,
        )

    @classmethod
    def quality_report(cls, speaker: str, listener: str,
                       quality_score: float, verdict: str,
                       should_skip: bool,
                       queries_used: List[str] = None) -> "CollaborationMessage":
        return cls(
            speaker=speaker,
            listener=listener,
            message_type=MessageType.QUALITY_REPORT,
            payload={
                "quality_score": quality_score,
                "verdict": verdict,
                "should_skip": should_skip,
                "queries_used": queries_used or [],
            },
            priority=2,
        )

    @classmethod
    def error_feedback(cls, speaker: str, listener: str,
                       error_type: str, error_message: str,
                       error_context: Dict[str, Any] = None,
                       repair_hints: List[str] = None) -> "CollaborationMessage":
        return cls(
            speaker=speaker,
            listener=listener,
            message_type=MessageType.ERROR_FEEDBACK,
            payload={
                "error_type": error_type,
                "error_message": error_message,
                "error_context": error_context or {},
                "repair_hints": repair_hints or [],
            },
            priority=1,
        )
