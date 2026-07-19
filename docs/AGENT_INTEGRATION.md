# Agent / Skill 集成指南 — Monkey Harness Agent

> 让 Monkey Harness Agent 作为外部 AI 系统的 Agent 或 Skill 接入

## 集成方式对比

| 方式 | 协议 | 适合场景 | 复杂度 |
|:-----|:-----|:---------|:------:|
| **MCP stdio** | stdin/stdout | Claude Desktop、Cursor | ⭐ 低 |
| **MCP Streamable HTTP** | HTTP POST | OpenClaw、远程服务 | ⭐ 低 |
| **REST API** | HTTP | 自定义集成、Webhook | ⭐⭐ 中 |
| **命令行调用** | Shell | 脚本化、自动化 | ⭐ 低 |

---

## 方式一：MCP stdio（推荐本地集成）

### 给 Claude Desktop

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "monkey-harness": {
      "command": "monkey-harness-mcp"
    }
  }
}
```

重启 → Claude 自动获得巡逻搜索+知识图谱能力。

### 给 Cursor

```json
{
  "mcpServers": {
    "monkey-harness": {
      "command": "monkey-harness-mcp"
    }
  }
}
```

---

## 方式二：MCP HTTP（推荐远程集成）

### 作为 OpenClaw Agent

```yaml
# openclaw-skills/monkey-harness.yaml
name: monkey-harness-agent
type: mcp
transport: streamable-http
url: http://你的服务器:8000/mcp
description: "弼马温 Agent — 多源巡逻搜索系统"
```

### 作为 Hermes 系统 Skill

在 Hermes 的 Skill 配置中注册：

```json
{
  "id": "monkey-harness",
  "name": "弼马温 Agent",
  "type": "mcp",
  "endpoint": "http://localhost:8000/mcp",
  "description": "自治巡逻搜索与知识图谱"
}
```

---

## 方式三：REST API 调用

MCP 本质上就是 HTTP JSON-RPC：

```bash
# 列出工具
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":"1"}' | jq .

# 调用巡逻
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"tools/call",
    "params":{"name":"patrol_trigger","arguments":{"force":true}},
    "id":"2"
  }' | jq .

# 查询图谱
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"tools/call",
    "params":{"name":"graph_query","arguments":{"type":"patrol"}},
    "id":"3"
  }' | jq .
```

---

## 方式四：命令行调用（零依赖）

```bash
# 查看巡逻状态
monkey-harness mcp-call patrol_status

# 触发巡逻
monkey-harness mcp-call patrol_trigger '{"force":true}'

# 列出 Skill
monkey-harness mcp-call skill_list
```

---

## 快速测试：一键启动并连接

```bash
# 终端 1: 启动 MCP 服务
monkey-harness-mcp --transport http --port 8000

# 终端 2: 用 MCP Inspector 可视化测试
npx @modelcontextprotocol/inspector
# → 浏览器打开 http://localhost:6274
# → 选 Streamable HTTP → http://localhost:8000/mcp → Connect
```

---

## 环境变量参考

| 变量 | 用途 | 默认值 |
|:-----|:-----|:-------|
| `HERMES_MONKEY_KEY` | 灵猴 API Key | — |
| `HERMES_HORSE_KEY` | 骏马 API Key | — |
| `HERMES_MONKEY_PROVIDER` | 灵猴厂商 | openai |
| `HERMES_HORSE_PROVIDER` | 骏马厂商 | deepseek |
| `MCP_TRANSPORT` | MCP 传输协议 | stdio |
| `MCP_PORT` | MCP HTTP 端口 | 8000 |
