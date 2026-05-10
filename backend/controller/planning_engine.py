"""
PlanningEngine: 基于任务特征选择最优执行策略。

职责:
- 维护策略库（fast / standard / quality / conservative）
- 根据 TaskParser 的输出选择策略
- 输出执行计划（Agent 序列、跳过步骤、迭代配置）

策略选择规则:
- simple 任务 → fast 策略（跳过检索和评估）
- medium 任务 → standard 策略（完整流程 + 3 次迭代上限）
- complex 任务 → quality 策略（完整流程 + 5 次迭代上限）
- 低置信度 → conservative 策略
- 用户要求快速 → 提升至 fast
"""

from typing import Dict, Any, List, Optional


class PlanningEngine:
    """策略规划引擎，将任务特征映射为执行计划"""

    # 策略库定义
    STRATEGIES = {
        "fast": {
            "name": "fast",
            "description": "快速策略：跳过检索和详细评估，直接生成代码并执行",
            "task_types": ["simple"],
            "agent_sequence": ["CodeGenerationAgent", "ExecutionAgent"],
            "skip_steps": ["RetrievalAgent", "EvaluationAgent"],
            "enable_iteration": False,
            "max_iterations": 1,
            "enable_search": False,
        },
        "standard": {
            "name": "standard",
            "description": "标准策略：完整流程（检索→生成→执行→评估→迭代）",
            "task_types": ["medium"],
            "agent_sequence": ["RetrievalAgent", "CodeGenerationAgent", "ExecutionAgent", "EvaluationAgent"],
            "skip_steps": [],
            "enable_iteration": True,
            "max_iterations": 3,
            "enable_search": True,
        },
        "quality": {
            "name": "quality",
            "description": "高质量策略：完整流程 + 更多迭代次数",
            "task_types": ["complex"],
            "agent_sequence": ["RetrievalAgent", "CodeGenerationAgent", "ExecutionAgent", "EvaluationAgent"],
            "skip_steps": [],
            "enable_iteration": True,
            "max_iterations": 5,
            "enable_search": True,
        },
        "conservative": {
            "name": "conservative",
            "description": "保守策略：完整流程 + 标准迭代，用于不确定性高的场景",
            "task_types": ["unknown"],
            "agent_sequence": ["RetrievalAgent", "CodeGenerationAgent", "ExecutionAgent", "EvaluationAgent"],
            "skip_steps": [],
            "enable_iteration": True,
            "max_iterations": 3,
            "enable_search": True,
        },
    }

    # 任务类型 → 默认策略映射
    TASK_TO_STRATEGY = {
        "simple": "fast",
        "medium": "standard",
        "complex": "quality",
    }

    # 置信度阈值：低于此值使用保守策略
    CONFIDENCE_THRESHOLD = 0.6

    def plan(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据任务特征生成执行计划。

        Args:
            task: TaskParser.parse() 的输出

        Returns:
            执行计划字典:
            {
                "strategy": str,           # 策略名称
                "description": str,        # 策略描述
                "agent_sequence": [str],   # Agent 执行序列
                "skip_steps": [str],       # 跳过的步骤
                "enable_iteration": bool,  # 是否启用迭代
                "max_iterations": int,     # 最大迭代次数
                "enable_search": bool,     # 是否启用检索
                "decision_reason": str,    # 决策原因
            }
        """
        task_type = task.get("task_type", "medium")
        confidence = task.get("confidence", 0.5)
        constraint = task.get("constraint", "none")
        keywords = task.get("keywords", [])
        explanation = task.get("explanation", "")

        reasons = []

        # 规则1: 用户明确要求快速 → 强制 fast
        if constraint == "speed":
            strategy_name = "fast"
            reasons.append("用户要求快速处理，采用快速策略")
        # 规则2: 低置信度 → 保守
        elif confidence < self.CONFIDENCE_THRESHOLD:
            strategy_name = "conservative"
            reasons.append(f"分类置信度较低 ({confidence:.2f} < {self.CONFIDENCE_THRESHOLD})，采用保守策略")
        # 规则3: 正常映射
        else:
            strategy_name = self.TASK_TO_STRATEGY.get(task_type, "standard")
            reasons.append(f"任务类型: {task_type}，{explanation}")

        strategy = self.STRATEGIES[strategy_name]

        # 补充决策理由
        if strategy["skip_steps"]:
            reasons.append(f"跳过步骤: {', '.join(strategy['skip_steps'])}")
        if strategy["enable_iteration"]:
            reasons.append(f"启用自动迭代，最多 {strategy['max_iterations']} 轮")

        decision_reason = "；".join(reasons)

        return {
            "strategy": strategy_name,
            "description": strategy["description"],
            "agent_sequence": list(strategy["agent_sequence"]),
            "skip_steps": list(strategy["skip_steps"]),
            "enable_iteration": strategy["enable_iteration"],
            "max_iterations": strategy["max_iterations"],
            "enable_search": strategy["enable_search"],
            "decision_reason": decision_reason,
        }

    def get_strategy_info(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """获取策略的完整定义"""
        return self.STRATEGIES.get(strategy_name)
