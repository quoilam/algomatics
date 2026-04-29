# 多 Agent 图像算法自动化系统

基于大模型的智能图像算法生成与执行系统，采用多 Agent 架构实现动态编排和调度。

## 项目结构

```
/workspace
├── backend/                    # 后端代码
│   ├── agents/                 # 各个 Agent 实现
│   │   ├── __init__.py
│   │   ├── retrieval_agent.py      # 检索 Agent (Tavily API)
│   │   ├── code_generation_agent.py # 代码生成 Agent (OpenRouter API)
│   │   ├── evaluation_agent.py     # 评估 Agent (多模态大模型)
│   │   └── execution_agent.py      # 执行 Agent (代码执行)
│   ├── controller/             # 控制器
│   │   ├── __init__.py
│   │   └── controller.py       # 主控制器 Agent
│   ├── app.py                  # Flask Web 服务
│   └── __init__.py
├── frontend/                   # 前端代码
│   ├── templates/
│   │   └── index.html          # 主页面
│   └── static/                 # 静态资源
├── docs/                       # 设计文档
│   ├── design.md               # 总体设计
│   ├── controller-impl.md      # Controller 设计
│   ├── agents-impl.md          # Agent 编排设计
│   ├── project-impl.md         # 项目实现要求
│   └── biz-impl.md             # 业务流程要求
├── requirements.txt            # Python 依赖
└── README.md                   # 本文件
```

## 系统架构

### 核心组件

1. **Controller Agent** - 系统核心控制器
   - 任务理解与分发
   - 结果汇总与整合
   - 会话状态管理
   - 错误处理与恢复

2. **Retrieval Agent** - 检索 Agent
   - 调用 Tavily API 进行联网搜索
   - 本地搜索缓存
   - 结构化结果输出

3. **Code Generation Agent** - 代码生成 Agent
   - 基于 OpenRouter API (GPT-4o)
   - 系统上下文感知
   - 对话历史管理
   - 支持迭代优化

4. **Evaluation Agent** - 评估 Agent
   - 多模态大模型评估图片质量
   - 代码质量评估
   - 多维度评分

5. **Execution Agent** - 执行 Agent
   - 安全执行生成的代码
   - 图像处理库支持 (OpenCV, PIL)
   - 执行日志记录

## 功能特性

- ✅ 多 Agent 动态编排和调度
- ✅ 联网搜索获取外部知识
- ✅ 智能代码生成
- ✅ 代码自动执行
- ✅ 多模态图像评估
- ✅ 用户反馈循环
- ✅ 实时状态展示 (Mermaid 流程图)
- ✅ 聊天历史记录
- ✅ 图片上传与展示

## 安装步骤

### 1. 安装依赖

```bash
cd /workspace
pip install -r requirements.txt
```

### 2. 配置环境变量

确保设置以下环境变量：

```bash
export TAVILY_API_KEY="your_tavily_api_key"
export OPENROUTER_API_KEY="your_openrouter_api_key"
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
```

### 3. 启动服务

```bash
cd /workspace/backend
python app.py
```

服务将在 http://localhost:5000 启动

## 使用流程

1. **访问网页** - 打开浏览器访问 http://localhost:5000

2. **输入需求** - 在对话框中输入图像处理需求，例如：
   - "把这张图卡通化"
   - "将图片转换为素描风格"
   - "给图片添加复古滤镜"

3. **上传图片** (可选) - 点击"上传图片"按钮选择示例图片

4. **查看执行过程** - 右侧边栏实时显示 Agent 调用状态图

5. **查看结果** - 系统会返回：
   - 生成的算法代码
   - 执行后的输出图片
   - 专业评估结果

6. **提供反馈** - 对结果选择：
   - ✅ 接受 - 完成任务
   - ❌ 需要改进 - 提供建议，系统会自动重新生成

## API 接口

### POST /api/session/create
创建新会话

### POST /api/process
处理用户请求

### POST /api/feedback
提交用户反馈

### GET /api/state-diagram/<session_id>
获取状态流程图

### GET /api/history
获取聊天历史

## 技术栈

- **后端**: Python, Flask
- **AI 集成**: OpenAI (兼容 OpenRouter), Tavily
- **图像处理**: OpenCV, Pillow, NumPy
- **前端**: HTML5, CSS3, JavaScript
- **可视化**: Mermaid.js, Marked.js

## 注意事项

- 本项目主要用于验证设计思路，未考虑生产环境的工程化问题
- 代码执行未做沙箱隔离，请勿在生产环境直接使用
- 需要有效的 Tavily 和 OpenRouter API Key
