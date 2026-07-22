# Monkey Harness Agent (弼马温 Agent)

> 🐒 猴驭多源，AI自治巡逻 — 多模态智能体系统 · v0.3.1

---

## 更新日志

### v0.3.1 — 天道系统 (2026-07-23)

| 变更 | 说明 |
|:-----|:------|
| **天道引擎** | 小说人物Y值驱动的情绪/欲望演化引擎，基于天道公式01-10 |
| **Bridge接口** | `tiandao_bridge.py` — 状态机↔天道联动，`trigger_event` / `get_character_state` / `get_event_roles` / `update_after_god_intervention` |
| **Y值计算链** | `y_engine.py` — 完整公式链：Y值基础→情绪波动→击穿阈值→补偿机制→回弹效应→欲望演化→多人物联动 |
| **Harness双通道** | `harness.py` — 子链通道（逻辑/结构）+ 天道通道（情绪/心理）整合，按任务生成专属临时脚本 |
| **rnd_tiandao.db** | 天道系统专用数据库，5张P0表（小说/人物/状态快照/事件/事件-人物分配） |
| **仓库结构重组** | 天道模块纳入 `harness_core/tiandao/` 包；tests/ 统一管理；`store/` 仅保留运行时数据 |

> 详细设计见 [docs/TIANDOO_ARCH.md](docs/TIANDOO_ARCH.md) | 天道公式见 `harness_core/tiandao/y_engine.py` | Harness用法见 `harness_core/tiandao/harness.py`

### v0.3.0 — 指纹运行时挂载 & 多路径推理 & 第5验证链 (2026-07-20)

| 变更 | 说明 |
|:-----|:------|
| **P1: 指纹运行时修复** | subchain_weights 从 0→**1,291 条**，10个领域指纹完整挂载到引擎库。原bug：种子数据写入了认知库而非引擎库 |
| **P2: 双路径收敛推理** | 审核不通过时自动运行两条路径（修复式重试 + 从零新鲜推理），对比择优返回 |
| **P3: 第5验证链「禁止数值解」** | 检测数值评分/二元判断/绝对否定/情绪化标签，强制替换为因果链推理 |
| **P4: agent.py 拆分** | 262行→36行骨架，行为注入到对应模块，去重工具类移至 utils/ |

### v0.2.20 — 骏马（马）响应工具升级 + 厂商流控适配 (2026-07-17)

| 变更 | 说明 |
|:-----|:------|
| **骏马响应工具** | ToolImage → 生图指令直达ComfyUI，ToolOutput → 执行感知型自主操作 |
| **DeepSeek流控** | 419/429自动降级备用API，滑动窗口速率限制 |
| **Monkey工具重构** | `subchain` → `script` 重命名，`confirm` → `assessment` 重设计，`output` 整合到 `user` |

> 完整历史见 [CHANGELOG.md](CHANGELOG.md)

---

## 目录结构

```
/root/bimawen/
├── harness_core/           # 核心包
│   ├── core/               # 核心角色：monkey/horse/keeper/patrol/scribe/purchaser/verifier
│   ├── engine/             # 引擎：state_machine / subchain
│   ├── tiandao/            # 天道系统
│   │   ├── tiandao_bridge.py    # 状态机↔天道联动接口
│   │   ├── y_engine.py          # Y值计算引擎（公式01-10）
│   │   ├── harness.py           # 双通道Harness主控
│   │   └── db_init.py           # 数据库DDL初始化
│   ├── providers/          # 模型供应商 (openai/anthropic/local)
│   ├── tools/              # 工具集
│   ├── desktop/            # 桌面应用
│   └── messages/           # 消息协议
├── subchains/              # 136条认知模板（markdown）
├── tests/                  # 测试
├── store/                  # 运行时数据 (SQLite)
├── docs/                   # 文档
├── config.yaml             # 配置文件
├── pyproject.toml          # 项目配置
└── SKILL.md                # 技能文档
```

---

## 快速开始

### 前置要求
- Python >= 3.11
- 本地运行需要 LLM API Key（DeepSeek / OpenAI / Anthropic）

### 安装

```bash
pip install -e .
```

### 配置

编辑 `config.yaml`，设置 API key 和模型参数：

```yaml
monkey:
  provider: openai
  model: deepseek-v4-flash
  api_key: your-api-key-here
```

### 运行

```bash
# CLI模式
monkey-harness

# MCP服务器（IDE/Tool使用）
monkey-harness-mcp
```

---

## 模块说明

### 天道系统 (`harness_core/tiandao/`)

天道系统是弼马温的叙事逻辑与人物演化引擎，面向小说创作场景。

| 模块 | 文件 | 说明 |
|:-----|:-----|:------|
| Bridge接口 | `tiandao_bridge.py` | 事件触发、人物状态查询、事件角色查询、老天爷干预 |
| Y值引擎 | `y_engine.py` | 天道公式01-10：Y值→情绪→击穿→补偿→回弹→欲望→多人物联动 |
| Harness | `harness.py` | 双通道整合层：接收子链（逻辑结构）+天道（情绪心理），输出叙事指令+人物状态 |

**核心流程：** 事件发生 → `trigger_event()` → Y值波动计算 → 情绪状态映射 → 击穿/补偿检查 → 欲望演化 → 状态持久化

### 核心角色

| 角色 | 职责 |
|:-----|:------|
| 🐒 **Monkey（猴子）** | 导演/调度/品质把控 — 任务拆分与审核 |
| 🐎 **Horse（马）** | 执行者/实现者 — Harness操作与代码实现 |
| 👁️ **Keeper（看守）** | 状态机引擎 — 多智能体通信 |
| 🔄 **Patrol（巡检）** | 定时/按需联网巡查 — 知识更新 |
| 🏪 **Purchaser（采办）** | 第三方工具/依赖采购 |

### 引擎

- **`state_machine.py`** — 9状态状态机，管理多智能体协作流程
- **`subchain.py`** — 子链调度引擎，支持 136 条认知模板的按需加载

---

## 开发

### 运行测试

```bash
# 所有测试
python3 -m unittest discover tests -v

# 天道系统测试
python3 -m unittest tests.test_bridge tests.test_y_engine tests.test_harness -v

# 单模块
python3 -m unittest tests.test_harness -v
```

### 提交

```bash
git add -A
git commit -m "feat: 描述变更 (v0.3.1)"
git push
```

---

## 许可

MIT
