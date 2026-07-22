# MCP 部署指南 — Monkey Harness Agent (弼马温 Agent)

> 📅 最后更新: 2026-07-19
> 技术栈: MCP Streamable HTTP + stdio 双模式

## 概述

Monkey Harness Agent 通过 **MCP (Model Context Protocol)** 暴露其核心能力，支持两种连接模式：

| 模式 | 传输层 | 适用场景 | 连接方式 |
|:-----|:-------|:---------|:---------|
| **stdio** | 标准输入输出 (子进程) | Claude Desktop、Cursor 等本地 AI 客户端 | 子进程启动 |
| **Streamable HTTP** | HTTP POST 单端点 | OpenClaw、远程服务器、其他 MCP 客户端 | `http://host:8000/mcp` |

---

## 一、安装

### 方式 A: pip 安装（推荐）

```bash
pip install monkey-harness-agent
```

### 方式 B: 从源码安装

```bash
git clone https://github.com/shaoyili1990/-
cd -
pip install -e .
```

### 验证安装

```bash
monkey-harness-mcp --help
# 或
bimawen-mcp --help
```

---

## 二、stdio 模式（Claude Desktop 集成）

### 配置 Claude Desktop

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "monkey-harness-agent": {
      "command": "monkey-harness-mcp",
      "args": ["--transport", "stdio"]
    }
  }
}
```

重启 Claude Desktop 后，会自动加载以下工具：

| 工具名 | 说明 |
|:-------|:-----|
| `patrol_status` | 查看巡逻系统状态 |
| `patrol_trigger` | 触发一轮完整巡逻 |
| `patrol_categories` | 查看11门类评分 |
| `skill_list` | 列出可用 Skill |
| `skill_run` | 执行指定 Skill |
| `graph_query` | 查询知识图谱 |
| `agent_status` | 系统整体状态 |
| `agent_config` | 查看配置（脱敏） |

### 命令行测试

```bash
# stdio 模式启动（用 --debug 看日志）
monkey-harness-mcp --debug
```

---

## 三、Streamable HTTP 模式（远程直连）

像访问网页一样直连 MCP 服务端：

```bash
# 启动 HTTP 服务
monkey-harness-mcp --transport http --port 8000
```

### 测试连接

```bash
# 列出可用工具
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":"1"}'

# 查看巡逻状态
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"patrol_status","arguments":{}},"id":"2"}'
```

### 浏览器测试（MCP Inspector）

```bash
# 开一个终端跑 MCP 服务
monkey-harness-mcp --transport http --port 8000

# 另一个终端启动 Inspector
npx @modelcontextprotocol/inspector

# 浏览器打开 http://localhost:6274
# 选择 Streamable HTTP → 填入 http://localhost:8000/mcp → Connect
```

---

## 四、Docker 部署

```bash
# 构建镜像
docker build -t monkey-harness-agent .

# 运行（HTTP 模式）
docker run -d \
  --name monkey-harness \
  -p 8000:8000 \
  -e MCP_TRANSPORT=http \
  -e MCP_PORT=8000 \
  -v monkey-data:/store \
  monkey-harness-agent

# 测试
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":"1"}'
```

---

## 五、OpenClaw 集成

在 OpenClaw 中添加 MCP 连接：

```yaml
# openclaw/config/mcp.yaml
connections:
  monkey-harness-agent:
    type: streamable-http
    url: http://你的服务器IP:8000/mcp
    description: "弼马温 Agent — 巡逻搜索+知识图谱"
```

---

## 六、导出暴露的工具一览

| MCP 工具 | 输入 | 输出 | 用途 |
|:---------|:-----|:-----|:-----|
| `patrol_status` | 无 | JSON | 巡逻系统健康检查 |
| `patrol_trigger` | force? | JSON | 执行巡逻并评分 |
| `patrol_categories` | 无 | JSON | 11门类热度排名 |
| `skill_list` | 无 | JSON | 列出6+内置 Skill |
| `skill_run` | skill_id, params | JSON | 调用翻译/搜索/图片等 |
| `graph_query` | type?, search? | JSON | 知识图谱搜索 |
| `agent_status` | 无 | JSON | 系统资源状态 |
| `agent_config` | 无 | JSON | 脱敏配置查看 |

---

## 七、完整部署示例

### 单机部署（推荐）

```bash
# 1. 安装
pip install monkey-harness-agent

# 2. 配置 API Key（可选）
export MONKEY_KEY=sk-xxx
export MONKEY_HORSE_KEY=sk-xxx

# 3. 启动 HTTP 服务
monkey-harness-mcp --transport http --host 0.0.0.0 --port 8000

# 4. 后台运行（用 systemd / supervisor）
```

### systemd 服务单元

```ini
[Unit]
Description=Monkey Harness Agent MCP Server
After=network.target

[Service]
Type=simple
User=monkey-harness
ExecStart=/usr/local/bin/monkey-harness-mcp --transport http --host 0.0.0.0 --port 8000
Restart=always
Environment=MONKEY_KEY=sk-xxx
Environment=MONKEY_HORSE_KEY=sk-xxx

[Install]
WantedBy=multi-user.target
```

---

## 八、从旧版迁移

如果之前安装了旧版，迁移方式：

```bash
pip uninstall monkey-harness-agent-universal
pip install monkey-harness-agent

# CLI 兼容：旧命令仍可用（通过别名）
monkey-harness desktop   # 启动桌面Web UI
bimawen desktop          # 中文名命令
monkey-harness-mcp       # 启动MCP服务器
```
