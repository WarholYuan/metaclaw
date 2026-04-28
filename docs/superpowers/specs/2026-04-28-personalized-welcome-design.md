# 个性化仪表盘欢迎页设计

**日期**: 2026-04-28
**状态**: 设计阶段
**作者**: MetaClaw

---

## 1. 背景与目标

当前 Web UI 的欢迎页是静态的通用界面（"今天想做什么？"+ 功能描述 + 6 张示例卡片），无法体现用户的实际使用价值和积累成果。

**目标**: 将欢迎页改造为个性化的仪表盘，基于用户历史对话自动生成总结文案和统计数据，让用户每次打开都能感受到 AI 为自己创造的价值，增强"获得感"。

**回退要求**: 用户可随时一键切换回经典视图，且切换状态持久化。

---

## 2. 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (chat.html)                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  WelcomeScreen 组件                                   │  │
│  │  ├─ DashboardView (新仪表盘视图)                       │  │
│  │  │   ├─ GreetingSection (问候语+AI总结)                │  │
│  │  │   ├─ StatsGrid (数据统计卡片网格)                   │  │
│  │  │   ├─ RecentTopics (最近话题快捷入口)                │  │
│  │  │   └─ QuickActions (常用功能示例卡片)                │  │
│  │  ├─ ClassicView (经典视图，原有实现保留)                │  │
│  │  └─ ViewToggle (视图切换按钮)                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                   │
│                    fetch /api/welcome-summary                 │
│                          │                                   │
├─────────────────────────────────────────────────────────────┤
│                      后端 (web_channel.py)                    │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  GET /api/welcome-summary                             │  │
│  │  ├─ 读取当前用户的对话历史                             │  │
│  │  ├─ 统计基础数据 (消息数、文件数等)                    │  │
│  │  ├─ 调用 LLM 生成个性化总结文案                        │  │
│  │  └─ 返回结构化 JSON                                    │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 后端设计

### 3.1 新增 API 端点

**`GET /api/welcome-summary?session_id=<sid>`**

返回当前用户的个性化欢迎数据。

**Response 结构**:

```json
{
  "status": "success",
  "data": {
    "greeting": "欢迎回来，老板 👋",
    "summary": "基于你的历史对话，我已经为你分析了 5 个主题，完成了 3 项任务，知识库新增了 12 篇文档。",
    "stats": {
      "conversation_count": 24,
      "message_count": 156,
      "files_analyzed": 12,
      "tasks_completed": 8,
      "skills_used": 5,
      "memory_entries": 45,
      "knowledge_docs": 12,
      "usage_duration_minutes": 127
    },
    "recent_topics": [
      {
        "id": "topic_1",
        "title": "分析飞书用户数据",
        "icon": "users",
        "color": "blue",
        "last_active": "2026-04-28T07:30:00Z"
      },
      {
        "id": "topic_2",
        "title": "生成知识库报告",
        "icon": "book",
        "color": "violet",
        "last_active": "2026-04-28T06:15:00Z"
      }
    ],
    "generated_at": "2026-04-28T08:00:00Z"
  }
}
```

### 3.2 数据统计逻辑

**基础统计**（直接从已有数据源计算，无需 AI）：

| 字段 | 数据来源 | 计算方式 |
|------|---------|---------|
| `conversation_count` | `user_datas.pkl` 或 Session 存储 | 该用户的历史 session 数量 |
| `message_count` | 消息历史数据库/存储 | 该用户发送+接收的消息总数 |
| `files_analyzed` | 历史消息中的文件附件记录 | 统计用户上传/分析的文件数 |
| `tasks_completed` | 历史消息中的任务完成标记 | 统计 agent 完成任务的数量 |
| `skills_used` | 历史消息中的技能调用记录 | 去重统计使用过的技能种类 |
| `memory_entries` | `memory/` 目录下该用户的记忆文件 | 统计记忆条目数 |
| `knowledge_docs` | `knowledge/` 目录 | 统计知识库文档数 |
| `usage_duration_minutes` | 消息时间戳计算 | 首次到最近消息的累计时长（估算） |

**AI 总结生成**:

- 从历史对话中抽取最近 20 条消息作为上下文
- 调用配置的 LLM（使用与对话相同的模型）生成一段自然语言的总结
- Prompt 模板：
  ```
  你是 MetaClaw 助手。请基于以下用户历史对话记录，生成一段简短的个性化欢迎总结（80字以内）。
  要体现用户的实际成果和 AI 为用户创造的价值，让用户有"获得感"。
  可用数据：{stats_json}
  最近对话摘要：{conversation_snippets}
  请直接输出总结文案，不要加引号或额外说明。
  ```

- 结果缓存 5 分钟，避免每次刷新都调用 LLM

### 3.3 实现位置

在 `channel/web/web_channel.py` 中新增路由处理器，复用现有的消息存储和 LLM 调用基础设施。

---

## 4. 前端设计

### 4.1 组件结构

保留现有的 `welcome-screen` DOM 容器，内部支持两种视图切换：

```
#welcome-screen
├── .view-toggle-btn        (切换按钮，两种视图都显示)
├── #welcome-dashboard      (仪表盘视图，默认)
│   ├── .greeting-section
│   │   ├── .greeting-title      ("欢迎回来，老板 👋")
│   │   └── .greeting-summary    (AI 生成的总结文案)
│   ├── .stats-grid
│   │   └── .stat-card × 6       (数据卡片网格)
│   ├── .recent-topics
│   │   └── .topic-chip × N      (最近话题快捷入口)
│   └── .quick-actions
│       └── .example-card × 3    (精简的常用功能卡片)
└── #welcome-classic        (经典视图，原有内容)
    └── (原有内容完整保留)
```

### 4.2 仪表盘视图详细设计

**Greeting Section**:
- 大号 Logo（`w-20 h-20`，比经典视图稍大）
- 问候语：`text-2xl font-bold`，使用动态生成的 `greeting`
- 总结文案：`text-base text-slate-500 dark:text-slate-400 max-w-xl text-center`，使用 AI 生成的 `summary`

**Stats Grid**:
- 布局：`grid grid-cols-3 sm:grid-cols-4 gap-3 max-w-2xl`
- 卡片样式：
  ```
  bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10
  rounded-xl p-4 text-center hover:border-primary-300 dark:hover:border-primary-600
  transition-all duration-200
  ```
- 每个卡片内容：
  - 图标（emoji 或 FontAwesome）+ 数字（`text-2xl font-bold text-primary-500`）+ 标签（`text-xs text-slate-500`）

| 图标 | 字段 | 标签 |
|-----|------|------|
| 💬 | `message_count` | 对话消息 |
| 📁 | `files_analyzed` | 文件分析 |
| ⚡ | `skills_used` | 技能使用 |
| ✅ | `tasks_completed` | 任务完成 |
| 🧠 | `memory_entries` | 记忆积累 |
| 📚 | `knowledge_docs` | 知识文档 |

**Recent Topics**:
- 水平滚动的 chip 列表
- 每个 chip 显示话题名称 + 小图标
- 点击后发送对应话题的引导消息到输入框

**Quick Actions**:
- 保留 3 个最常用的示例卡片（系统管理、编程助手、知识库）
- 布局：`grid grid-cols-3 gap-3`

### 4.3 视图切换机制

- 切换按钮位于欢迎屏幕右上角（`absolute top-4 right-4`）
- 按钮样式：小图标按钮，hover 时显示 tooltip "切换经典视图"/"切换仪表盘视图"
- 状态保存在 `localStorage`：`metaclaw_welcome_view = 'dashboard' | 'classic'`
- 默认值为 `'dashboard'`（新视图）

### 4.4 加载与错误处理

**加载状态**:
- 仪表盘视图首次加载时显示骨架屏（skeleton），数据到达后淡入显示
- 如果 API 请求超过 3 秒，降级显示基础统计数据（不需要 AI 总结的部分）

**错误处理**:
- API 失败时自动回退到经典视图，并记录错误日志
- 用户仍可手动切回仪表盘视图重试

### 4.5 无历史数据状态

如果用户是首次使用（`conversation_count === 0`）：
- 仪表盘视图显示简化版：问候语改为"欢迎使用 MetaClaw！"，总结文案改为功能介绍引导
- 统计数据区域显示占位符 "0" 和引导文案
- 底部显示完整的 6 张示例卡片（与经典视图相同）

---

## 5. 数据流

```
用户打开聊天页面
        │
        ▼
前端检查 localStorage 中的视图偏好
        │
        ├── dashboard (默认) ──► 显示仪表盘骨架屏
        │                              │
        │                              ▼
        │                    调用 GET /api/welcome-summary
        │                              │
        │                    ┌─────────┴─────────┐
        │                    ▼                   ▼
        │              成功 (<3s)           超时/失败
        │                    │                   │
        │                    ▼                   ▼
        │           填充数据渲染            降级显示基础统计
        │           淡入动画                或自动切回经典视图
        │
        └── classic ──► 直接显示经典欢迎页
```

---

## 6. 关键文件变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `channel/web/static/js/console.js` | 修改 | 新增仪表盘视图渲染逻辑、视图切换、API 调用 |
| `channel/web/chat.html` | 修改 | 调整 welcome-screen 结构，兼容两种视图 |
| `channel/web/web_channel.py` | 修改 | 新增 `/api/welcome-summary` 端点 |
| `channel/web/static/css/console.css` | 修改（可能）| 新增仪表盘相关的样式（优先用 Tailwind 内联） |

---

## 7. 性能考虑

1. **AI 总结缓存**: 后端缓存 AI 生成的总结文案 5 分钟，减少 LLM 调用开销
2. **基础统计预计算**: 对话次数、消息数等基础统计可定期预计算或增量更新
3. **前端骨架屏**: 避免空白等待，提升 perceived performance
4. **降级策略**: API 超时后自动降级，不影响用户正常使用

---

## 8. 安全与隐私

1. `/api/welcome-summary` 端点与现有 API 使用相同的 session 认证机制
2. AI 总结仅基于当前用户自己的对话历史，不会跨用户泄露数据
3. 敏感信息（API key、密码等）在总结生成时会被过滤

---

## 9. 后续可扩展

1. **时间维度统计**: 本周/本月/总计 的切换 Tab
2. **成就徽章系统**: 达成特定里程碑时解锁徽章（如"首次使用技能""分析 100 个文件"）
3. **趋势图表**: 使用 Chart.js 展示对话频率、知识增长等趋势
4. **周/日报**: 定期生成"本周总结"推送
