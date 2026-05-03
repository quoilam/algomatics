# 🚀 MVP快速启动指南

## 前置要求

1. **虚拟环境**：项目已有 `.venv`（使用 uv 创建）
2. **API密钥**：需要在 `.env` 中配置
   - `OPENROUTER_API_KEY` ✅（已有）
   - `TAVILY_API_KEY` ✅（已有）

## 验证API连接

```bash
cd /Users/quoilam/Documents/cprp/impl

# 验证OpenRouter API
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
export OPENROUTER_MODEL="qwen/qwen-turbo"
.venv/bin/python test_api_connectivity.py
```

## 运行MVP端到端测试

```bash
cd /Users/quoilam/Documents/cprp/impl

# 配置环境变量
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
export OPENROUTER_MODEL="qwen/qwen-turbo"

# 运行测试（验证自动迭代能力）
.venv/bin/python test_mvp_e2e.py
```

## 启动Web服务

```bash
cd /Users/quoilam/Documents/cprp/impl

# 配置环境变量
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
export OPENROUTER_MODEL="qwen/qwen-turbo"

# 启动Flask服务
.venv/bin/python -m backend.app

# 访问：http://localhost:5000
```

## 核心变更概览

### 1️⃣ EvaluationAgent - 结构化评分

```python
result = evaluation_agent.evaluate_code(code=..., user_request=...)
# 返回：{
#   "success": True,
#   "score": 5,              ← 0-10分的量化评分
#   "evaluation_text": "...",
#   "improvements": "..."     ← 改进建议用于下轮迭代
# }
```

### 2️⃣ CodeGenerationAgent - 迭代反馈

```python
iteration_info = {
    "iteration_count": 2,
    "previous_score": 5,
    "improvements": "需要优化代码可读性"
}
code = code_gen.generate_code(
    user_request=...,
    iteration_info=iteration_info  # ← 迭代上下文
)
```

### 3️⃣ Controller - 自动迭代

```python
# 自动迭代循环（评分驱动）
# 评分≥7 → 接受 | 5≤评分<7 → 继续优化 | 评分<5 → 人工审查
result = controller.process_user_request(
    session_id=...,
    user_request="对图像进行降噪处理",
    enable_search=True
)
# 返回：{
#   "success": True,
#   "total_iterations": 3,
#   "final_score": 5,
#   "iteration_reason": "达到最大迭代次数，最终评分 5/10",
#   "steps": [...]  # 详细步骤记录
# }
```

## 预期输出示例

```
================================================================================
MVP端到端测试 - 自动迭代能力
================================================================================

[Controller] === 迭代第 1 次 ===
[CodeGenerationAgent] Code generated successfully
[EvaluationAgent] Code evaluation completed - Score: 5/10
[Controller] 第 1 次迭代 - 评分: 5/10
[Controller] 评分 5/10，继续优化... (第 1/3 次)

[Controller] === 迭代第 2 次 ===
[CodeGenerationAgent] Code generated successfully
[EvaluationAgent] Code evaluation completed - Score: 5/10
[Controller] 第 2 次迭代 - 评分: 5/10
[Controller] 评分 5/10，继续优化... (第 2/3 次)

[Controller] === 迭代第 3 次 ===
[CodeGenerationAgent] Code generated successfully
[EvaluationAgent] Code evaluation completed - Score: 5/10
[Controller] 第 3 次迭代 - 评分: 5/10
[Controller] 达到最大迭代次数 (3)，停止迭代

🎉 所有测试通过！MVP自动迭代能力已验证
```

## 关键文件位置

| 文件 | 功能 |
|------|------|
| `backend/agents/evaluation_agent.py` | 评估Agent - 返回结构化评分 |
| `backend/agents/code_generation_agent.py` | 代码生成Agent - 支持迭代反馈 |
| `backend/controller/controller.py` | 控制器 - 评分驱动的自动迭代逻辑 |
| `test_mvp_e2e.py` | MVP端到端测试脚本 |
| `docs/MVP_IMPLEMENTATION_REPORT.md` | 详细实现报告 |

## 故障排除

### ❌ "API returned a string" 错误

**原因**：BASE_URL或MODEL配置不正确

**解决**：确保环境变量正确
```bash
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
export OPENROUTER_MODEL="qwen/qwen-turbo"
```

### ❌ "No module named tavily"

**原因**：依赖未安装

**解决**：
```bash
.venv/bin/pip install -r requirements.txt
```

### ❌ 评分始终为 0/10

**原因**：ExecutionAgent执行失败

**检查**：
1. 输入图片存在：`output_images/test_input.png`
2. Python库已安装：`opencv-python`, `Pillow`, `numpy`
3. 查看详细错误日志

## 成功标志 ✅

运行 `test_mvp_e2e.py` 后看到：
- ✅ 创建测试图片成功
- ✅ 进行多轮迭代（2-3次）
- ✅ 每轮都有评分返回
- ✅ 最后显示 "所有测试通过"

## 下一步

1. **修复多模态评估**：实现图片质量评分（当前回退到代码评估）
2. **阶段2 - 错误自修复**：当代码执行失败时自动修复
3. **阶段3 - 主动规划**：根据任务类型选择不同策略
4. **阶段4 - Agent协作**：Agent间双向通信

---

详细实现说明见：[MVP_IMPLEMENTATION_REPORT.md](MVP_IMPLEMENTATION_REPORT.md)
