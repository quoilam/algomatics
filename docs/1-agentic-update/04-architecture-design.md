# 04 系统架构与技术决策

**📍 位置**：[← 上一篇](03-iterative-roadmap.md) | [返回导航](design.md) | [下一篇 →](05-risks-mitigation.md)

---

## 系统架构演进方向

### 当前架构：Pipeline型编排

```
Frontend UI
    ↓
API Gateway (Flask)
    ↓
Controller (编排器)
    ├→ RetrievalAgent (搜索)
    ├→ CodeGenAgent (生成)
    ├→ ExecutionAgent (执行)
    └→ EvaluationAgent (评估)
    ↓
Response
```

**特点**：
- 流程固定：搜索 → 生成 → 执行 → 评估
- Agent按顺序调用，数据单向流动
- Controller是连接器而非决策者

### 目标架构：Agentic型决策与协作

```
Frontend UI
    ↓
API Gateway (Flask)
    ↓
┌─────────────────────────────────────┐
│     Enhanced Controller              │
├─────────────────────────────────────┤
│ ┌──────────────────────────────────┐ │
│ │  意图理解与任务分解               │ │
│ │  (Task Parser)                    │ │
│ │  - 识别任务类型                   │ │
│ │  - 提取约束条件                   │ │
│ └──────────────────────────────────┘ │
│ ┌──────────────────────────────────┐ │
│ │  策略规划与决策引擎               │ │
│ │  (Planning & Decision Engine)     │ │
│ │  - 选择执行策略                   │ │
│ │  - 确定Agent序列                  │ │
│ └──────────────────────────────────┘ │
│ ┌──────────────────────────────────┐ │
│ │  迭代驱动与流程控制               │ │
│ │  (Iteration Controller)           │ │
│ │  - 管理评分驱动的迭代             │ │
│ │  - 决定继续还是结束               │ │
│ └──────────────────────────────────┘ │
│ ┌──────────────────────────────────┐ │
│ │  Agent协作协调                    │ │
│ │  (Collaboration Coordinator)      │ │
│ │  - 中介Agent通信                  │ │
│ │  - 协商和决策                     │ │
│ └──────────────────────────────────┘ │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Agent 集群（增强能力）              │
├─────────────────────────────────────┤
│ Retrieval → CodeGen → Execution ↔   │
│            ↑         ↓    ↑         │
│            └─ Evaluation ←──────────┘
│                ↓
│         Knowledge Base (新增)
└─────────────────────────────────────┘
```

**特点**：
- Controller变成"大脑"，不仅编排还决策
- Agent间建立多向通信
- 引入知识库支持学习和推荐
- 反馈驱动迭代而非线性流程

---

## 新增系统组件详解

### 1. Task Parser（任务解析器）

**职责**：
- 输入：用户自然语言需求
- 输出：结构化任务表示（任务类型、优先级、约束等）
- 功能：将非结构化输入转换为系统可理解的形式

**输出数据结构**：
```python
class Task:
    task_type: str              # "simple", "medium", "complex", etc.
    keywords: List[str]         # 关键词列表
    constraints: Dict[str, Any] # 约束条件
    priority: str               # "quick", "standard", "quality"
    confidence: float           # 识别的置信度
    explanation: str            # 为什么做这个识别
```

**实现参考**：
- 初期：基于关键词的规则识别
- 后期：可升级到NLP分类器

---

### 2. Planning Engine（规划引擎）

**职责**：
- 输入：结构化任务
- 输出：执行计划（哪些Agent、什么顺序、什么策略）
- 功能：基于任务特征和系统状态制定最优计划

**输出数据结构**：
```python
class ExecutionPlan:
    strategy_name: str          # 使用的策略名称
    agent_sequence: List[str]   # 要执行的Agent列表
    skip_steps: List[str]       # 要跳过的步骤
    enable_iteration: bool      # 是否启用迭代
    max_iterations: int         # 最多迭代次数
    explanation: str            # 为什么选这个计划
```

**策略库数据结构**：
```python
class Strategy:
    name: str                   # 策略名称
    description: str            # 描述
    task_type_match: List[str]  # 适用的任务类型
    constraint_match: Dict      # 匹配的约束条件
    agent_sequence: List[str]   # Agent执行序列
    config: Dict                # 配置参数
```

**实现参考**：
- 初期：硬编码规则
- 后期：可使用配置文件或简单DSL

---

### 3. Iteration Controller（迭代控制）

**职责**：
- 输入：评估结果（评分、反馈）
- 输出：迭代决策（继续/停止、改进方向）
- 功能：管理迭代循环，确保收敛和质量

**核心逻辑**：
```
if score >= 7:
    return CONTINUE_TO_NEXT  # 流程完成
elif 5 <= score < 7:
    if iteration_count < max_iterations:
        return CONTINUE_ITERATION  # 自动优化
    else:
        return STOP_AND_WARN  # 超出次数上限
else:  # score < 5
    if iteration_count < max_iterations:
        return CONTINUE_ITERATION  # 重新开始
    else:
        return MANUAL_REVIEW  # 需人工审查
```

**历史记录**：
```python
class IterationRecord:
    iteration_num: int
    agent: str
    action: str
    score: float
    timestamp: datetime
    feedback: str
```

---

### 4. Collaboration Coordinator（协作协调）

**职责**：
- 输入：Agent协作请求
- 输出：协作结果或代理决策
- 功能：中介Agent间的通信和协商

**协作消息类型**：
```python
class CollaborationMessage:
    speaker: str                # 发送方Agent
    listener: str               # 接收方Agent
    message_type: str           # 消息类型（quality_report, feedback, request等）
    payload: Dict               # 具体内容
    priority: int               # 优先级
    timeout: int                # 超时时间（秒）
```

**协作场景管理**：
```python
class CollaborationScenario:
    name: str                   # 场景名称
    initiator: str              # 发起方
    target: str                 # 目标方
    trigger_condition: str      # 触发条件
    message_format: Dict        # 消息格式
    expected_response: Dict     # 期望响应
    fallback_action: str        # 失败时降级
```

---

### 5. Knowledge Base（知识库）

**职责**：
- 存储：问题模式、最佳实践、失败案例
- 接口：查询相似问题、存储成功案例、更新知识
- 功能：积累和提供领域知识

**数据结构**：
```python
class ProblemPattern:
    problem_id: str
    description: str
    keywords: List[str]
    features: Dict              # 问题特征
    created_at: datetime
    usage_count: int
    
class Solution:
    solution_id: str
    problem_id: str
    approach: str
    parameters: Dict
    evaluation: Dict            # 评分、成功率等
    created_at: datetime
    last_used_at: datetime
```

**查询和推荐**：
```python
def recommend_solutions(new_problem: Problem) -> List[Recommendation]:
    """
    根据新问题推荐最佳实践
    """
    similar_problems = find_similar(new_problem)
    solutions = []
    for problem in similar_problems:
        for solution in problem.solutions:
            score = similarity_score + popularity_score + quality_score
            solutions.append((solution, score))
    return sorted(solutions, key=lambda x: x[1], reverse=True)[:5]
```

---

## 关键技术决策点

### 决策1：Controller的新角色定位

**问题**：Controller应该如何升级？

**选项A**：在现有Controller基础上扩展
- 优点：改动最小，向后兼容
- 缺点：代码复杂度增加，边界不清

**选项B**：重构Controller，引入新的中间层（选中）
- 优点：架构清晰，职责分离，易于测试和维护
- 缺点：工作量大，需要充分测试

**决策**：采用选项B，但分阶段实现
- 阶段1：在现有Controller中增加迭代逻辑（迭代控制）
- 阶段3：逐步抽象出TaskParser和PlanningEngine
- 最终：形成完整的分层架构

---

### 决策2：迭代反馈的激活机制

**问题**：如何让评估结果自动驱动迭代？

**选项A**：EvaluationAgent直接返回迭代指令
- 优点：简单直接
- 缺点：耦合度高

**选项B**：Controller读取评分，根据规则决定（选中）
- 优点：解耦，规则可调
- 缺点：需要维护决策规则

**决策**：
- EvaluationAgent返回评分 + 反馈
- Controller在迭代控制器中根据评分做出决策
- 阈值可配置，初期：score ≥ 7 结束，5-7 迭代，<5 需审查

---

### 决策3：错误修复 vs 功能优化的策略分化

**问题**：两种迭代应该如何区分？

**选项A**：混在一起处理
- 优点：逻辑简单
- 缺点：修复失败可能浪费功能迭代的机会

**选项B**：分开处理，修复优先级更高（选中）
- 优点：保证代码能执行后再评估
- 缺点：需要两套流程

**决策**：
```
代码执行
├─→ 失败？
│   ├─→ 是 → 尝试修复（最多3次）
│   │       ├─→ 成功 → 进入功能评估和迭代
│   │       └─→ 失败 → 上报给用户
│   └─→ 否 → 进行评估和功能迭代
```

---

### 决策4：Agent协作的最小化原则

**问题**：应该在哪些点启用协作？

**选项A**：所有关键点都启用协作
- 优点：通信完整
- 缺点：延迟增加，复杂度高

**选项B**：只在高价值点启用，逐步扩展（选中）
- 优点：收益 > 成本
- 缺点：初期功能有限

**决策**：
- **必须** CodeGen + Evaluation（前置反馈）：避免执行明显有问题的代码
- **应该** Execution + Evaluation（错误反馈）：提高修复成功率
- **可选** Retrieval + CodeGen（质量反馈）：在搜索结果差时降低依赖

---

### 决策5：知识库的初期简化设计

**问题**：知识库应该如何设计？

**选项A**：一上来就用向量数据库+ML
- 优点：功能完整，精度高
- 缺点：过度工程化，维护成本高

**选项B**：从轻量级开始，逐步演进（选中）
- 优点：快速落地，学习曲线平缓
- 缺点：初期功能有限

**决策**：
- **存储**：JSON或SQLite（本地）
- **更新**：简单的评分加权，不用ML
- **检索**：关键词匹配 + 基本相似度，不用embedding
- **后期演进**：根据数据量和需求再考虑升级

---

## 向后兼容性

### 现有API保持不变
- `/api/session/create` - 创建会话
- `/api/process` - 处理请求
- `/api/feedback` - 提交反馈
- 返回数据结构保持兼容

### 新增功能通过新字段
```json
{
  // 现有字段
  "success": true,
  "steps": [...],
  
  // 新增字段（可选）
  "decision": {
    "strategy": "standard",
    "explanation": "..."
  },
  "collaboration_log": [...],
  "knowledge_base_suggestion": [...]
}
```

### 特性开关
- 通过环境变量或配置启用/禁用新特性
- 便于灰度发布和A/B测试

---

## 性能和可扩展性

### 性能目标
- 平均响应时间：不超过当前2倍（包括迭代）
- API调用成本：降低30%+（跳过不必要搜索）
- 并发数：支持当前10倍（通过优化）

### 可扩展性考虑
- **任务类型增加**：通过配置而非代码改动
- **策略增加**：支持热加载新策略
- **Agent增加**：Controller通过注册机制支持新Agent
- **知识库扩大**：分表或分库策略

---

## 依赖和兼容性

### 保持现有依赖
- OpenAI客户端
- Tavily搜索
- Flask框架
- Pillow图像库

### 可能新增的轻量级依赖
- 配置管理：Python内置 configparser 或 YAML
- 数据库：SQLite（内置）或 simple JSON
- 日志：Python内置 logging + 可视化工具

### 避免的重依赖
- ❌ Vector数据库（向量化）
- ❌ 大型框架（AutoGen、LangChain等）
- ❌ 复杂的ML模型

---

## 监测和可观测性

### 系统日志增强
```
[TASK_PARSE] 输入: "...", 识别类型: "simple", 置信度: 0.9
[PLANNING] 选定策略: "fast", Agent序列: [CodeGen, Execution]
[EXECUTION] Agent: CodeGen, 耗时: 2.3s, 成功
[ITERATION] 评分: 6.5, 决策: 优化
[COLLABORATION] Retrieval → CodeGen: 质量反馈
[KNOWLEDGE_BASE] 推荐3个相似案例
```

### 可视化仪表板
- 系统决策过程
- Agent协作关系
- 知识库使用统计
- 性能指标

---

**📍 位置**：[← 上一篇](03-iterative-roadmap.md) | [返回导航](design.md) | [下一篇 →](05-risks-mitigation.md)
