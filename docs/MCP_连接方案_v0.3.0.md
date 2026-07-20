# 弼马温 MCP 连接方案 (v0.3.0)

> 更新: 新增指纹运行时挂载、多路径推理、第5验证链「禁止数值解」

---

## 一、快速接入

### 方式 1：Claude Desktop

编辑 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "bimawen-agent": {
      "command": "python3",
      "args": ["-m", "hermes_universal.mcp_server"]
    }
  }
}
```

### 方式 2：Claude Code

```bash
claude mcp add bimawen-agent -- python3 -m hermes_universal.mcp_server
```

### 方式 3：HTTP 模式 (OpenClaw/Cursor)

```bash
python3 -m hermes_universal.mcp_server --transport http --port 8000
```

---

## 二、工具清单 (13个)

### 🔍 巡逻系统 (3个)

| 工具 | 用途 | 返回 |
|:-----|:-----|:-----|
| `patrol_status` | 看巡逻状态 | 全部11门类 + 热度/名额/运行时间 |
| `patrol_trigger` | 手动触发指定门类巡逻 | 搜索+评分结果 |
| `patrol_categories` | 列出11个巡逻门类 | 名称/描述/热度 |

### 🛠 Skill 系统 (2个)

| 工具 | 用途 |
|:-----|:-----|
| `skill_list` | 列出所有可用 Skill (翻译/搜索/图片/文件/摘要/图表) |
| `skill_run` | 执行指定 Skill |

### 🕸 图谱 (1个)

| 工具 | 用途 |
|:-----|:-----|
| `graph_query` | 查询力导向图 (6种节点类型,全量/搜索/过滤) |

### ⚙️ 系统 (2个)

| 工具 | 用途 |
|:-----|:-----|
| `agent_status` | Agent 当前状态(任务/路由/验证链) |
| `agent_config` | 当前配置(验证链/指纹/领域) |

### 📁 **任务输出** (5个) — v0.3.0 核心

| 工具 | 用途 |
|:-----|:-----|
| `workspace_init` | 初始化 workspace/output/ |
| `task_output_save` | 保存任务输出(问题+推导+结果)到文件+表格 |
| `task_output_list` | 列出所有任务 |
| `task_output_read` | 读取指定任务某个版本的完整文件 |
| `task_output_iterate` | 迭代: 读旧版本→打包反馈→新问题 |

---

## 三、输出格式 — 任务工作流示例

### 初次执行

```
01_问题.md   ← "如何优化弼马温的冷启动速度"
02_推理过程.md  ← "第1步:分析当前瓶颈..."
03_输出结果.md  ← "## 方案\n1. 指纹预加载..."
```

### 不满意 → 迭代 (v2)

```
01_问题.md   ← 含v1旧推理 + 用户反馈
02_推理过程.md  ← 重新推理
03_输出结果.md  ← 修订方案
```

### 复杂任务 (PRD类)

```
01_思路.md  →  02_流程.md  →  03_执行方法.md  →  04_结果.md
```

---

## 四、核心变更归档

### v0.3.0 (当前)
| 变更 | 说明 |
|:-----|:-----|
| **指纹挂载修复** | subchain_weights 0→1291 条, 写入库 bug 修复 |
| **多路径推理** | 审核不过时双路径对比择优(修复路径+新鲜路径) |
| **第5验证链** | 禁止数值解链 — 检测数值评分/二元标签/模板化 |
| **cold-start 迭代** | task_output_iterate 读 v1 全量 → 打包反馈 → 新问题 |

### v0.2.0
| 变更 | 说明 |
|:-----|:-----|
| **冷监督开关** | `/aileran on/off` 冻结后台自治循环 |
| **输出引擎** | workspace/output/T{v}/v{n}/ 文件系统 |
| **MCP 工具** | 5 个任务输出工具 |

---

## 五、故障排查

| 问题 | 原因 | 解决 |
|:-----|:-----|:-----|
| `ModuleNotFoundError: No module named 'mcp'` | 缺 FastMCP SDK | `pip install mcp` |
| 巡逻返回空 | 无卡服务器未提供联网 | 检查 autodl 实例 |
| `workspace_init` 失败 | 输出目录权限 | 手动 `mkdir -p ~/workspace/output` |
| 指纹未加载 | 数据库未 seed | 手动 `python3 -c "from hermes_universal.engine import EngineDB, seed_fingerprints; seed_fingerprints(EngineDB(), 'fingerprints')"` |
| 工具调用超时 | MCP stdio 超时 | HTTP 模式: `--transport http --port 8000` |
