# FilePilot Agent

基于 LLM Tool Calling 的自主文件操作 Agent。

Agent 接收自然语言任务指令，通过自主调用文件工具（列出、读取、搜索、写入、移动）完成任务。

## 架构

```
┌─────────────────────────────────────────────────────┐
│                      入口层                          │
│  agent.py (CLI)          main.py (FastAPI Web API)  │
├─────────────────────────────────────────────────────┤
│  api/routes.py    service/agent_service.py          │
│  schemas/agent.py (Pydantic 模型)                    │
├─────────────────────────────────────────────────────┤
│                     Agent 核心                       │
│  agent/agent.py      AgentRunner (Agent Loop)       │
│  agent/system_prompt.py   agent/trace.py            │
├─────────────────────────────────────────────────────┤
│              core/             │      tools/         │
│  config.py  llm_client.py      │  base.py  security │
│  (配置管理)  (OpenAI 封装)      │  5 个文件工具       │
└─────────────────────────────────────────────────────┘
```

### Agent Loop 执行流程

1. 初始化 messages（system_prompt + user task）
2. 调用 LLM，传入 tools schema
3. LLM 返回 tool_calls → 逐个执行工具 → 结果回填到 messages
4. 重复 2-3，直到 LLM 返回纯文本（无 tool_calls）或达到 max_steps

## 快速开始

> 前端项目仓库：[FilePilotFront](https://github.com/moty1111/FilePilotFront)

### 1. 环境配置

创建并激活虚拟环境：

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

创建 `.env` 文件：

```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=glm-5.2
```

### 2. CLI 模式

```bash
python agent.py --task "找出所有提到 Project Falcon 的文件"
```

可选参数：

```bash
python agent.py \
  --workspace ./workspace \
  --task "搜索包含 budget 的文件并生成摘要" \
  --max-steps 30
```

### 3. Web API 模式

```bash
uvicorn main:app --reload --port 8000
# 或
python main.py
```

API 文档自动生成在 `http://localhost:8000/docs`。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/tasks` | 提交 Agent 任务（异步执行） |
| `GET` | `/api/tasks` | 列出所有任务 |
| `GET` | `/api/tasks/{task_id}` | 查询任务状态与结果 |
| `GET` | `/api/tasks/{task_id}/trace` | 获取任务执行 Trace |
| `GET` | `/api/workspace` | 列出 workspace 目录树（支持 `?path=` 和 `?recursive=true`） |
| `GET` | `/api/workspace/files/{file_path}` | 读取 workspace 文件内容 |
| `POST` | `/api/workspace/reset` | 重置 workspace 到初始状态（从 `workspace2/` 恢复） |
| `GET` | `/health` | 健康检查 |

### 使用示例

**提交任务：**

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"task": "找出所有提到 Project Falcon 的文件"}'
```

响应（202 Accepted）：

```json
{
  "task_id": "a1b2c3d4e5f6",
  "status": "pending",
  "created_at": "2025-01-01T12:00:00+00:00"
}
```

**查询状态：**

```bash
curl http://localhost:8000/api/tasks/a1b2c3d4e5f6
```

响应：

```json
{
  "task_id": "a1b2c3d4e5f6",
  "task": "找出所有提到 Project Falcon 的文件",
  "status": "completed",
  "result": "找到了 3 个文件提到 Project Falcon...",
  "error": null,
  "created_at": "2025-01-01T12:00:00+00:00",
  "completed_at": "2025-01-01T12:01:30+00:00",
  "workspace_path": "/path/to/workspace",
  "token_usage": {
    "prompt_tokens": 5200,
    "completion_tokens": 800,
    "total_tokens": 6000,
    "total_calls": 5
  },
  "steps": 4
}
```

**获取 Trace：**

```bash
curl http://localhost:8000/api/tasks/a1b2c3d4e5f6/trace
```

**浏览 workspace 目录树：**

```bash
# 列出根目录
curl http://localhost:8000/api/workspace

# 列出子目录
curl http://localhost:8000/api/workspace?path=meetings

# 递归列出所有文件（含 trace 文件）
curl http://localhost:8000/api/workspace?recursive=true
```

**读取文件内容：**

```bash
curl http://localhost:8000/api/workspace/files/notes/meeting.md
```

**重置 workspace：**

```bash
curl -X POST http://localhost:8000/api/workspace/reset
```

## 工具集

Agent 可调用以下 5 个文件操作工具：

| 工具 | 功能 |
|------|------|
| `list_files` | 列出 workspace 目录结构 |
| `read_file` | 读取文件内容（支持分块，防止大文件撑爆上下文） |
| `search_files` | 关键词搜索文件内容 |
| `write_file` | 写入/创建文件 |
| `move_file` | 移动/重命名文件 |

## 安全设计

- **路径越界防护**：所有文件操作经过 `security.validate_path()` 校验，防止 `../../` 逃逸攻击
- **Prompt Injection 防护**：System Prompt 明确声明文件内容是不可信数据，Agent 不会执行文件中的指令
- **大文件限制**：`read_file` 单次返回最大 20000 字符，`search_files` 最多返回 20 条匹配
- **最大步数限制**：Agent Loop 超过 `max_steps` 后强制终止，防止无限循环
- **隐藏文件**：`trace_*.jsonl` 等基础设施文件对 Agent 不可见（`is_hidden_file()` 模式匹配），但通过 Web API workspace 浏览器对前端可见，便于展示 Agent 执行流程

## 公网部署与防滥用

Demo 部署到公网后，API Key 会暴露在公网服务之后。当前采取的防滥用措施：`max_steps`（默认 20）与 `max_file_chars`（20000）从资源侧限制单次任务成本，线程池 `max_workers=4` 限制并发，workspace 重置需无运行中任务。并在.gitignore 排除 .env文件，防止密钥泄露。生产环境还应在网关层加简单口令 / 限流 / 单日花费上限（如 API 侧设置 spending limit），这也是本 demo 未覆盖的已知缺口。

## 可观测性

每个任务执行过程以 JSONL 格式写入 trace 文件，每行一条记录：

- **CLI 模式**：写入 `<workspace>/trace.jsonl`（固定文件名，每次运行清空重写）
- **Web API 模式**：写入 `<workspace>/trace_{task_id}.jsonl`（每个任务独立隔离）

示例：

```json
{"step": 1, "type": "llm_thinking", "content": "我需要先搜索哪些文件提到了 Project Falcon...", "timestamp": "2025-01-01T12:00:01+00:00"}
{"step": 1, "type": "tool_call", "tool": "search_files", "args": {"keyword": "Falcon"}, "result_summary": "Found 5 matches", "timestamp": "2025-01-01T12:00:02+00:00"}
{"step": 2, "type": "llm_thinking", "content": "找到了 5 个匹配，让我逐个读取关键文件...", "timestamp": "2025-01-01T12:00:05+00:00"}
{"step": 2, "type": "tool_call", "tool": "read_file", "args": {"path": "notes/meeting.md"}, "result_summary": "Read 1200 chars", "timestamp": "2025-01-01T12:00:06+00:00"}
{"step": 3, "type": "final", "result_summary": "找到了 3 个文件...", "timestamp": "2025-01-01T12:00:10+00:00"}
```

Trace 记录类型：

| 类型 | 说明 |
|------|------|
| `llm_thinking` | LLM 的思考/推理文本（返回 tool_calls 时的 content） |
| `tool_call` | 工具调用（工具名 + 参数 + 结果摘要） |
| `final` | Agent 最终回复 |
| `max_steps_reached` | 超过最大步数强制终止 |

前端可通过 `GET /api/tasks/{task_id}/trace` 获取完整时间线，也可通过 `GET /api/workspace/files/trace_{task_id}.jsonl` 直接读取原始 trace 文件。

## 项目结构

```
FilePilot/
├── agent.py              # CLI 入口（python agent.py --workspace ... --task ...）
├── main.py               # FastAPI Web API 入口
├── requirements.txt
├── .env                  # 环境变量（需自行创建）
├── NOTES.md              # 设计取舍说明
│
├── core/                 # 核心配置
│   ├── config.py         # 全局配置（Settings 单例）
│   └── llm_client.py     # LLM 客户端封装（原生 OpenAI API）
│
├── agent/                # Agent 核心
│   ├── agent.py          # AgentRunner - Agent Loop 实现
│   ├── system_prompt.py  # System Prompt 模板
│   └── trace.py          # Trace 记录器
│
├── tools/                # 工具集
│   ├── __init__.py       # create_tool_registry 工厂
│   ├── base.py           # Tool 基类 + ToolRegistry
│   ├── security.py       # 路径安全校验 + trace 文件隐藏
│   ├── list_files.py     # 列出目录
│   ├── read_file.py      # 读取文件（分块）
│   ├── search_files.py   # 搜索文件
│   ├── write_file.py     # 写入文件
│   └── move_file.py      # 移动文件
│
├── schemas/              # API 数据模型
│   ├── __init__.py
│   └── agent.py          # Pydantic 请求/响应模型
│
├── service/              # 业务逻辑层
│   ├── __init__.py
│   └── agent_service.py  # 异步任务管理（线程池）
│
├── api/                  # API 路由层
│   ├── __init__.py
│   ├── routes.py         # FastAPI 路由定义（tasks + workspace）
│   └── deps.py           # 依赖注入
│
├── workspace/            # Agent 工作目录（含 CLI 产出的 trace.jsonl）
└── workspace2/           # workspace 备份（重置功能的数据源）
```
