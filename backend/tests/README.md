# Agent 单元测试说明

本目录包含对所有 Agent 的单元测试，用于单独测试每个 API 的功能。

## 测试文件

- `test_agents.py` - 包含所有 Agent 的单元测试

## 测试覆盖的 Agent

1. **RetrievalAgent** - 检索 Agent（联网搜索）
2. **CodeGenerationAgent** - 代码生成 Agent
3. **EvaluationAgent** - 评估 Agent（图片和代码质量评估）
4. **ExecutionAgent** - 执行 Agent（代码执行）

## 运行测试

### 方式 1：使用 unittest（推荐，无需额外安装）

```bash
# 运行所有测试
python -m unittest backend.tests.test_agents -v

# 运行特定测试类
python -m unittest backend.tests.test_agents.TestCodeGenerationAgent -v
python -m unittest backend.tests.test_agents.TestEvaluationAgent -v
python -m unittest backend.tests.test_agents.TestExecutionAgent -v
python -m unittest backend.tests.test_agents.TestRetrievalAgent -v

# 运行单个测试方法
python -m unittest backend.tests.test_agents.TestCodeGenerationAgent.test_generate_code_success -v
```

### 方式 2：使用 pytest（需要安装 pytest）

```bash
# 安装 pytest
pip install pytest

# 运行所有测试
pytest backend/tests/test_agents.py -v

# 运行特定测试类
pytest backend/tests/test_agents.py::TestCodeGenerationAgent -v

# 运行单个测试
pytest backend/tests/test_agents.py::TestCodeGenerationAgent::test_generate_code_success -v

# 生成覆盖率报告
pytest backend/tests/test_agents.py --cov=backend/agents --cov-report=html
```

## 测试说明

### TestCodeGenerationAgent（代码生成 Agent 测试）

| 测试方法 | 说明 |
|---------|------|
| `test_generate_code_success` | 测试成功生成代码 |
| `test_generate_code_with_search_results` | 测试带搜索结果生成代码 |
| `test_generate_code_string_response` | 测试 API 返回字符串错误时的处理 |
| `test_generate_code_no_choices` | 测试 API 响应没有 choices 属性时的处理 |
| `test_generate_code_exception` | 测试生成代码时的异常处理 |
| `test_extract_code_block` | 测试从文本中提取代码块 |
| `test_conversation_history` | 测试对话历史管理 |

### TestEvaluationAgent（评估 Agent 测试）

| 测试方法 | 说明 |
|---------|------|
| `test_evaluate_image_success` | 测试成功评估图片 |
| `test_evaluate_image_string_response` | 测试 API 返回字符串错误时的处理 |
| `test_evaluate_image_no_choices` | 测试 API 响应没有 choices 属性时的处理 |
| `test_evaluate_code_success` | 测试成功评估代码 |
| `test_evaluate_code_string_response` | 测试评估代码时 API 返回字符串 |
| `test_evaluate_code_exception` | 测试评估代码时的异常处理 |

### TestExecutionAgent（执行 Agent 测试）

| 测试方法 | 说明 |
|---------|------|
| `test_execute_simple_code` | 测试执行简单代码 |
| `test_execute_code_with_error` | 测试执行出错代码 |
| `test_summarize_execution` | 测试执行总结 |
| `test_summarize_failed_execution` | 测试失败执行的总结 |

### TestRetrievalAgent（检索 Agent 测试）

| 测试方法 | 说明 |
|---------|------|
| `test_missing_api_key` | 测试缺少 API Key 的情况 |

> 注意：由于 tavily 模块可能未安装，RetrievalAgent 的其他测试被简化了。如果需要完整测试，请先安装 tavily：
> ```bash
> pip install tavily-python
> ```

### TestIntegration（集成测试）

| 测试方法 | 说明 |
|---------|------|
| `test_code_generation_and_evaluation` | 测试代码生成和评估的完整流程 |

## Mock 说明

所有测试都使用了 `unittest.mock` 来模拟外部 API 调用，因此：

1. **不需要真实的 API Key** - 测试会自动设置临时的测试 API Key
2. **不会实际调用外部服务** - 所有 API 调用都被 mock 了
3. **测试快速且可重复** - 不依赖网络或外部服务状态

## 常见问题

### Q: 为什么有些测试显示警告信息？
A: 这是正常的日志输出，显示 Agent 在处理各种错误情况时的行为。例如：
- `[CodeGenerationAgent] API returned a string instead of response object` - 测试错误处理逻辑
- `[ExecutionAgent] Error executing code: Test error` - 测试故意制造的错误

### Q: 如何添加新的测试？
A: 在对应的测试类中添加新的测试方法，方法名以 `test_` 开头：

```python
def test_new_feature(self):
    """测试新功能"""
    # 设置 mock
    # 调用被测试的方法
    # 断言结果
```

### Q: 测试失败了怎么办？
A: 
1. 查看错误信息和堆栈跟踪
2. 确认是否是代码变更导致的问题
3. 检查 mock 是否正确设置
4. 运行单个测试进行调试

## 持续集成

可以将测试添加到 CI/CD 流程中：

```yaml
# GitHub Actions 示例
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python -m unittest backend.tests.test_agents -v
```
