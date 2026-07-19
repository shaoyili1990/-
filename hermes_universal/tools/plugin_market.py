"""
弼马温 Agent — 平台插件集成指南
==================================

采购员(采购员)职责之一：将系统能力接入外部AI平台生态。
本文档描述如何将 Monkey Harness Agent 暴露为 LangChain Tool、CrewAI Tool、OpenClaw Skill、及其他MCP平台集成。

核心原则：所有对外集成统一通过 MCP Streamable HTTP 端点，不重复实现。
"""

"""
# Monkey Harness Agent — 插件市场集成指南

> 📅 最后更新: 2026-07-19
> 出口渠道: MCP Streamable HTTP（统一端点）+ 各平台适配层

## 集成架构

```
┌─────────────────────────────────────────────┐
│             Monkey Harness Agent             │
│  ┌─────────┐  ┌─────────┐  ┌──────────────┐ │
│  │ 巡逻引擎 │  │ Skill池 │  │ 知识图谱    │ │
│  └────┬────┘  └────┬────┘  └──────┬───────┘ │
│       └────────────┼──────────────┘          │
│                    ▼                         │
│           MCP Streamable HTTP                │
│           http://host:8000/mcp               │
└────────────────────┬─────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     ▼               ▼               ▼
┌─────────┐  ┌────────────┐  ┌──────────────┐
│LangChain│  │   CrewAI   │  │   OpenClaw   │
│  Tool   │  │   Tool     │  │   Skill      │
└─────────┘  └────────────┘  └──────────────┘
```

---

## 一、LangChain 集成

作为 LangChain Tool 注册，供 LLM Agent 调用：

```python
from langchain.tools import BaseTool
from langchain_core.tools import StructuredTool
import requests
import json

class MonkeyHarnessPatrolTool(StructuredTool):
    \"\"\"查询弼马温巡逻系统状态\"\"\"
    name = "monkey_harness_patrol"
    description = "获取AI前沿/科技/时事等11门类自治巡逻搜索结果和评分"
    
    def _run(self):
        resp = requests.post(
            "http://localhost:8000/mcp",
            json={"jsonrpc":"2.0","method":"tools/call",
                  "params":{"name":"patrol_status","arguments":{}},"id":"1"},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        return resp.json()["result"]["content"][0]["text"]
    
    async def _arun(self):
        return self._run()

# 注册到 LangChain Agent
from langchain.agents import initialize_agent, AgentType
tools = [MonkeyHarnessPatrolTool()]
agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)
```

### LangChain MCP 适配器（更推荐）

LangChain 官方支持 MCP Tool：

```python
from langchain_mcp import McpToolCollection

# 直连 MCP 端点，自动发现所有工具
tools = McpToolCollection.from_url("http://localhost:8000/mcp")
# tools 包含: patrol_status, patrol_trigger, skill_run, graph_query ...
```

---

## 二、CrewAI 集成

作为 CrewAI Tool 注册：

```python
from crewai_tools import BaseTool
import requests, json

class PatrolSearchTool(BaseTool):
    name: str = "Patrol Search"
    description: str = "自治巡逻搜索11个门类的最新内容"
    
    def _run(self) -> str:
        resp = requests.post(
            "http://localhost:8000/mcp",
            json={"jsonrpc":"2.0","method":"tools/call",
                  "params":{"name":"patrol_categories","arguments":{}},"id":"1"},
            timeout=30
        )
        return resp.json()["result"]["content"][0]["text"]

class SkillExecuteTool(BaseTool):
    name: str = "Execute Skill"
    description: str = "执行内置Skill（翻译/搜索/图片/文件分析等）"
    
    def _run(self, skill_id: str, params: str = "{}"):
        resp = requests.post(
            "http://localhost:8000/mcp",
            json={"jsonrpc":"2.0","method":"tools/call",
                  "params":{"name":"skill_run",
                           "arguments":{"skill_id":skill_id,"params":params}},
                  "id":"1"},
            timeout=60
        )
        return resp.json()["result"]["content"][0]["text"]
```

---

## 三、OpenClaw 集成

作为 OpenClaw Skill 注册：

```yaml
# openclaw-skills/monkey-harness.yaml
name: monkey-harness-agent
display_name: "弼马温 Agent（自治巡逻系统）"
type: mcp
transport: streamable-http
endpoint: http://localhost:8000/mcp
description: |
  AI自治巡逻系统，具备11门类多源搜索、技能执行和知识图谱能力。
  
  可用工具:
  - patrol_status: 查看巡逻系统状态
  - patrol_trigger: 触发完整巡逻
  - skill_list: 查看可用Skill
  - skill_run: 执行Skill
  - graph_query: 知识图谱查询
```

### 从 OpenClaw Skill 市场安装

如果部署在远程服务器：

```yaml
# openclaw-skills/monkey-harness-remote.yaml
name: monkey-harness-remote
type: mcp
transport: streamable-http
endpoint: http://你的服务器IP:8000/mcp
```

---

## 四、其他 MCP 客户端集成

任何支持 MCP Streamable HTTP 的客户端都可直连：

| 平台 | 连接方式 | 配置 |
|:-----|:---------|:-----|
| **Claude Desktop** | stdio (子进程) | `{"command":"monkey-harness-mcp"}` |
| **Cursor** | stdio | `{"command":"monkey-harness-mcp"}` |
| **Windsurf** | stdio | `{"command":"monkey-harness-mcp"}` |
| **OpenClaw** | HTTP | `url: http://host:8000/mcp` |
| **ChatGPT (Custom GPT)** | HTTP | Action → OpenAPI spec |
| **任何 HTTP 客户端** | POST | `curl -X POST http://host:8000/mcp` |

---

## 五、采购员(采购员)工作流

系统内由 采购员 角色负责对外集成：

```
采购员指令:
  discover_platforms    → 发现可用平台（LangChain/CrewAI/OpenClaw）
  register_service      → 在目标平台注册 MCP 端点
  check_status          → 检查各平台连接状态
  sync_skills           → 同步 Skill 列表到外部平台
  collect_feedback      → 收集使用数据辅助迭代
```

---

## 六、关键配置

```bash
# MCP 服务器配置
MCP_HOST=0.0.0.0        # 监听所有网卡（远程访问）
MCP_PORT=8000           # HTTP 端口
MCP_TRANSPORT=http       # Streamable HTTP 模式
```

---

## 附录：现有对接工具（agent-kit）

`agent-kit/config/` 目录包含各平台预配置模板：

| 文件 | 平台 | 
|:-----|:-----|
| `monkey-harness.json` | 弼马温自身平台格式 |
| `openclaw.json` | OpenClaw Skill 配置 |
| `universal.json` | 通用 MCP 配置 |
"""

if __name__ == "__main__":
    print("✅ 插件市场集成指南已加载")
    print("支持平台: LangChain, CrewAI, OpenClaw, Claude, Cursor, ChatGPT, 通用MCP")
