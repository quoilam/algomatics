# Agent对话前端 - 后端API需求文档

## 概述

本文档详细说明了新的React前端系统所需的后端API接口。前端采用现代化的架构，支持流式输出、实时状态更新、会话管理等功能。

---

## 核心API端点

### 1. 会话管理接口

#### 1.1 创建会话
**端点**: `POST /api/session/create`

**请求体**:
```json
{
  "user_id": "web",
  "initial_message": "optional初始消息"
}
```

**响应**:
```json
{
  "success": true,
  "session_id": "session_1234567890_abc",
  "created_at": 1715000000000,
  "message": "会话创建成功"
}
```

**错误响应**:
```json
{
  "success": false,
  "error": "创建会话失败的原因"
}
```

---

#### 1.2 获取会话状态和日志
**端点**: `GET /api/session/{session_id}`

**查询参数**:
- `limit` (可选): 返回日志的最大数量，默认100
- `offset` (可选): 分页偏移量

**响应**:
```json
{
  "session_id": "session_1234567890_abc",
  "status": "processing",
  "created_at": 1715000000000,
  "updated_at": 1715000001000,
  "messages": [
    {
      "id": "msg_001",
      "role": "user",
      "content": "用户消息",
      "timestamp": 1715000000000
    },
    {
      "id": "msg_002",
      "role": "assistant",
      "content": "助手响应",
      "timestamp": 1715000000500
    }
  ],
  "state_logs": [
    {
      "id": "log_001",
      "agent": "数据收集器",
      "action": "搜索Web",
      "status": "completed",
      "timestamp": 1715000000100,
      "data": {
        "query": "搜索关键词",
        "results_count": 10,
        "source": "Google"
      }
    },
    {
      "id": "log_002",
      "agent": "分析器",
      "action": "生成代码",
      "status": "running",
      "timestamp": 1715000000500,
      "data": {
        "language": "python",
        "partial_code": "def hello():"
      }
    }
  ],
  "current_agent": "分析器",
  "current_action": "生成代码",
  "output_image_base64": "data:image/png;base64,iVBORw0KG...",
  "final_response": "处理完成的最终响应"
}
```

**状态值**:
- `idle` - 待处理
- `processing` - 处理中
- `completed` - 已完成
- `accepted` - 已接受
- `needs_review` - 需要审查
- `error` - 错误

---

### 2. 消息处理接口

#### 2.1 发送消息（启用轮询模式）
**端点**: `POST /api/process`

**请求体** (JSON):
```json
{
  "session_id": "session_1234567890_abc",
  "request": "用户的提问或指令",
  "enable_search": true,
  "context": {
    "max_history_turns": 5,
    "system_prompt": "可选的系统提示"
  }
}
```

**请求体** (FormData - 带文件上传):
```
session_id: "session_1234567890_abc"
request: "用户的提问或指令"
image: [File对象]
enable_search: "true" 或 "false"
```

**立即响应** (HTTP 200):
```json
{
  "success": true,
  "session_id": "session_1234567890_abc",
  "text": "可选的立即响应摘要或确认信息",
  "status": "processing"
}
```

**错误响应**:
```json
{
  "success": false,
  "error": "处理失败的具体原因"
}
```

**后续操作**: 客户端应开始轮询 `GET /api/session/{session_id}` 来获取实时更新

---

#### 2.2 StateLog 数据结构详解

**StateLog项**:
```json
{
  "id": "log_unique_id",
  "agent": "执行该步骤的代理名称",
  "action": "执行的动作名称",
  "status": "started|running|completed|failed|paused",
  "timestamp": 1715000000000,
  "duration_ms": 500,
  "data": {
    "key1": "value1",
    "code": "def hello():\n    print('world')",
    "preview": "生成的内容预览",
    "output_path": "/path/to/output.txt",
    "image_base64": "base64编码的图片（可选）"
  },
  "output_path": "/path/to/generated/file",
  "output_image_base64": "data:image/png;base64,..."
}
```

**关键字段约定**:
- `code` - 源代码（自动以`<pre>`标签渲染）
- `preview` - 内容预览（自动以`<pre>`标签渲染）
- `improvement` - 改进建议（自动以`<pre>`标签渲染）
- `evaluation` - 评估结果（自动以`<pre>`标签渲染）
- `output_path` - 文件输出路径（显示为代码块）
- `*image*` 或 `*base64*` 包含的字段 - 图片（自动渲染为`<img>`）

---

### 3. 文件操作接口（可选）

#### 3.1 上传文件
**端点**: `POST /api/upload`

**请求**:
```
Content-Type: multipart/form-data
file: [File对象]
session_id: "session_id"
```

**响应**:
```json
{
  "success": true,
  "file_path": "/uploads/session_id/filename.ext",
  "file_size": 12345,
  "mime_type": "image/png"
}
```

---

#### 3.2 下载/查看输出
**端点**: `GET /api/session/{session_id}/output/{file_name}`

**说明**: 用于访问生成的文件或图片

---

## 前端集成说明

### 轮询策略

前端采用**定时轮询**策略（已实现）：

1. **发送消息**: `POST /api/process` → 立即获得 session_id
2. **开始轮询**: 每 **900ms** 调用 `GET /api/session/{session_id}`
3. **状态检查**: 获得新的 state_logs 和当前状态
4. **停止条件**: 当状态为以下值时停止轮询
   - `completed`
   - `accepted`
   - `needs_review`
   - `error`
5. **超时处理**: 轮询60次仍未完成时，前端自动停止

### 数据流向

```
用户输入
   ↓
POST /api/process
   ↓
收到 session_id 和初始响应
   ↓
定时轮询 GET /api/session/{session_id}
   ↓
逐步收集 state_logs
   ↓
实时更新 UI
   ↓
检测终止状态，结束轮询
```

---

## 后端实现建议

### 关键要求

1. **会话隔离**: 每个 session_id 对应一个独立的处理流程，不同会话之间完全隔离

2. **State Logs 记录**: 后端需要为每个处理步骤生成详细的 state_log 记录

3. **实时状态更新**: `GET /api/session/{session_id}` 应返回最新的状态，包括所有已完成的步骤和当前进度

4. **错误处理**: 当处理失败时，状态应设为 `error`，并在适当的 state_log 中记录错误信息

5. **文件输出**: 如果生成了文件或图片，应在 state_log 的 `data` 字段中包含 `output_path` 或 `output_image_base64`

### 性能考虑

- 轮询间隔为 900ms，建议后端响应时间 < 100ms
- 避免在大量日志的情况下返回完整历史，考虑实现分页或增量更新
- 对于大型输出文件，考虑使用 base64 编码或分块传输

---

## 错误处理约定

### 客户端行为

1. **网络错误**: 自动重试（当前未实现，建议后续添加）
2. **API错误**: 显示错误消息并允许用户重试
3. **轮询超时**: 提示"处理超时，请稍后重试"
4. **无效 session_id**: 提示"会话已过期"

### 服务器端应保证

- 所有错误都返回 JSON 格式的错误响应
- 包含 `success: false` 和 `error` 字段
- 适当的 HTTP 状态码（400 验证失败, 404 资源不存在, 500 服务器错误）

---

## 示例工作流

### 场景：用户发送一个处理请求

1. **用户发送消息**: "请分析这个网页并生成总结"

2. **前端请求**:
```bash
POST /api/process
{
  "session_id": "session_123",
  "request": "请分析这个网页并生成总结",
  "enable_search": true
}
```

3. **后端响应**:
```json
{
  "success": true,
  "session_id": "session_123",
  "text": "正在处理中...",
  "status": "processing"
}
```

4. **前端开始轮询** (每900ms一次):
```bash
GET /api/session/session_123
```

5. **轮询响应示例** (第1次):
```json
{
  "status": "processing",
  "state_logs": [
    {
      "id": "log_1",
      "agent": "网页爬虫",
      "action": "获取网页内容",
      "status": "completed",
      "timestamp": 1715000000100,
      "data": {
        "url": "https://example.com",
        "content_length": 50000
      }
    }
  ]
}
```

6. **轮询响应示例** (第2次):
```json
{
  "status": "processing",
  "state_logs": [
    { /* 第一个日志 */ },
    {
      "id": "log_2",
      "agent": "摘要生成器",
      "action": "生成总结",
      "status": "running",
      "timestamp": 1715000000500,
      "data": {
        "progress": 50,
        "current_section": "第2段"
      }
    }
  ]
}
```

7. **轮询响应示例** (最终):
```json
{
  "status": "completed",
  "state_logs": [
    { /* 第一个日志 */ },
    {
      "id": "log_2",
      "agent": "摘要生成器",
      "action": "生成总结",
      "status": "completed",
      "timestamp": 1715000001000,
      "duration_ms": 500,
      "data": {
        "summary": "这个网页主要讲述了...",
        "key_points": ["要点1", "要点2"]
      }
    }
  ],
  "final_response": "总结完成"
}
```

8. **前端停止轮询** (检测到 status === 'completed')

---

## 可选增强功能

### 建议的后续改进

1. **WebSocket实时推送** (替代轮询)
   - 更低延迟
   - 更低流量
   - 双向通信

2. **流式响应 (Server-Sent Events)**
   - 实时推送数据
   - 保留后兼容性

3. **消息历史恢复**
   - `GET /api/session/{session_id}/history` 获取完整历史

4. **会话列表**
   - `GET /api/sessions?user_id=web` 获取用户的所有会话

5. **会话删除**
   - `DELETE /api/session/{session_id}` 删除会话

6. **搜索功能**
   - `GET /api/session/{session_id}/search?q=keyword` 搜索会话内容

---

## 测试建议

### 手动测试清单

- [ ] 创建新会话
- [ ] 发送简单文本消息
- [ ] 发送带图片的消息
- [ ] 观察 state_logs 实时更新
- [ ] 测试长时间处理流程
- [ ] 验证错误处理
- [ ] 测试会话切换
- [ ] 检查历史记录恢复

### 自动化测试

建议编写以下测试用例：
- 并发会话处理
- 大量日志处理
- 网络中断重连
- 超长请求处理
- 文件上传处理

---

## 兼容性说明

- **浏览器**: 要求支持 Fetch API、LocalStorage、EventSource
- **最低支持版本**: Chrome 45+, Firefox 40+, Safari 10+
- **移动浏览器**: iOS Safari 10+, Chrome Mobile 45+

---

## 部署注意事项

1. **CORS 配置**: 前端运行在 `http://localhost:5173`，后端需配置允许这个源的请求

2. **文件上传**: 配置合理的文件大小限制（建议 100MB）

3. **会话超时**: 建议服务端设置合理的会话过期时间（如 1小时）

4. **日志存储**: 考虑日志的长期存储和清理策略

---

## 联系和反馈

如有任何问题或建议，请与前端开发团队沟通。
