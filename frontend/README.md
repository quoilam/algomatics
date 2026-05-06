# Agent 对话前端系统

一个现代化的React + TypeScript + Vite前端，为Agent系统提供完整的对话UI体验。

## 🌟 核心功能

### ✨ 流式输出支持
- 实时消息流式更新（基于轮询）
- "正在输入..."动画反馈
- 支持长时间处理流程

### 📊 详细状态显示
- **详细视图**: 显示每个步骤的完整信息和数据
- **简化视图**: 快速概览步骤执行流程
- 实时进度条和步骤计数
- 颜色编码的状态指示（成功、处理中、错误、警告）

### 💾 历史记录管理
- LocalStorage 本地缓存（最近20个会话）
- 会话搜索和过滤
- 会话重命名和删除
- 会话消息计数显示

### 🔄 多轮对话支持
- 完整的会话上下文管理
- 消息历史保存
- 后端自动管理对话历史
- 会话隔离

### 🎨 现代化UI设计
- 响应式两栏布局（侧边栏 + 主区域）
- 深度定制的CSS变量系统
- 平滑的过渡动画
- 可访问的无障碍设计

---

## 🚀 快速开始

### 前置要求
- Node.js 16+
- pnpm 8+

### 安装依赖
```bash
cd frontend
pnpm install
```

### 开发模式
```bash
pnpm dev
```

访问 http://localhost:5173

### 生产构建
```bash
pnpm build
```

---

## 📁 项目结构

```
frontend/
├── src/
│   ├── components/          # React 组件
│   ├── styles/              # 组件样式
│   ├── types.ts             # TypeScript 类型
│   ├── store.ts             # Zustand 状态管理
│   ├── api.ts               # API 接口
│   ├── App.tsx              # 主应用
│   └── ...
├── index.html               # HTML 模板
├── vite.config.ts           # Vite 配置
├── BACKEND_REQUIREMENTS.md  # 后端API文档
└── README.md                # 本文件
```

---

## 🔌 API 集成

详见 [BACKEND_REQUIREMENTS.md](./BACKEND_REQUIREMENTS.md)
