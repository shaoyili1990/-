# Monkey Harness Agent (弼马温 Agent)

> 🐒 猴驭多源，AI自治巡逻 — 多模态智能体系统 · v0.3.1

---

## 更新日志

### v0.3.1 — 多模态自适应工作流 & TTS 语音合成 (2026-07-22)

| 变更 | 说明 |
|:-----|:------|
| **P1: ComfyUI 多模态底座** | 48GB L40 自适应工作流，生图/视频与推理引擎协同 |
| **P2: TTS 语音合成** | 基于 audio.cpp-webui 的中/英/日/韩 TTS，自适应兼容 API 降级 |
| **P3: 48GB 自适应框架** | 常规模式 ↔ 多模态模式自动切换，巡检者暂停派发至 DeepSeek Flash |
| **P4: 巡检者按需运行** | 支持 cron 定时运行（每天 1:00 自动巡检后退出），非常驻显存 |
| **P5: 修复默认模型** | `deepseek-chat` → `deepseek-v4-flash`，避免 pro 计费 |
| **P6: 自适应脚本** | `start-multimodal.sh` / `restore-normal.sh` 一键切换 |

> 详细方案见 [docs/48G_ADAPTIVE.md](docs/48G_ADAPTIVE.md) | TTS部署见 [docs/TTS_DEPLOY.md](docs/TTS_DEPLOY.md) | ComfyUI见 [docs/COMFYUI_DEPLOY.md](docs/COMFYUI_DEPLOY.md)

### v0.3.1 — TTS 语音底座 & ComfyUI 多模态 & 48GB 自适应工作流 (2026-07-22)

| 变更 | 说明 |
|:-----|:------|
| **TTS 语音合成** | 基于 audio.cpp-webui，支持中/英/日/韩四国语种实时语音 |
| **ComfyUI 多模态** | SDXL / FLUX 文生图、图编辑、无缝集成 Agent 推理 |
| **48GB 自适应工作流** | 智能模式切换：常规模式(骏马+巡检+TTS) ↔ 多模态模式(骏马+ComfyUI)，巡检任务降级到 DeepSeek Flash |
| **自适应切换脚本** | `installer/start-multimodal.sh` / `restore-normal.sh` — 一键切换模式，状态保存+恢复 |
| **OOM 安全机制** | 显存爆满时自动释放非核心组件，只保留骏马推理 |
| **弼马温 TTS 指南** | 无本地 GPU 版本通过 API 调用 TTS，提供配置示例 |

### v0.3.0 — 指纹运行时挂载 & 多路径推理 & 第5验证链 (2026-07-20)

| 变更 | 说明 |
|:-----|:------|
| **P1: 指纹运行时修复** | subchain_weights 从 0→**1,291 条**，10个领域指纹完整挂载到引擎库。原bug：种子数据写入了认知库而非引擎库 |
| **P2: 双路径收敛推理** | 审核不通过时自动运行两条路径（修复式重试 + 从零新鲜推理），对比择优返回 |
| **P3: 第5验证链「禁止数值解」** | 检测数值评分/二元标签/模板化填空/绝对化结论，要求解析解表述 |
| **P4: 冷监督开关** | `/aileran on/off` 冻结后台自治循环，控制token消耗 |
| **P5: 任务输出引擎** | `workspace/output/T001/v1/{问题,推导,结果}.md` — 文件存完整内容，表格仅存摘要用于检索 |
| **P6: 迭代工具** | `task_output_iterate` 读 v1 全量文件 → 打包反馈 → 构建新问题 → 存 v2 |
| **P7: 项目模板** | 新增"项目"输出模板: 01_思路→02_流程→03_执行方法→04_结果 |
| **MCP 13工具** | 完整注册巡逻/Skill/图谱/系统/输出5类工具 |

> 详细版本说明见 [CHANGELOG](CHANGELOG.md) | MCP连接方案见 [docs/MCP_连接方案_v0.3.0.md](docs/MCP_连接方案_v0.3.0.md)

### v0.2.0 — 冷监督 & 任务输出引擎 (2026-07-19)

- 冷监督模式（Aileran）：后台自治循环开关
- workspace/output 输出引擎：文件系统 + 多维表格双写
- MCP 输出工具：workspace_init / task_output_save / task_output_list / task_output_read

### v0.1.0 — 弼马温品牌发布 (2026-07-18)

- 品牌升级：Hermes → Monkey Harness Agent (弼马温)
- 136子链 + 4验证链 + 11领域指纹
- MCP 服务器 + AgentReach 多源巡逻
- 跨平台部署 + GitHub Actions CI/CD

---

## 架构

```
┌─────────┐    路由/审核    ┌─────────┐    推理执行    ┌──────────┐
│ 灵猴    │ ─────────────→ │ 骏马    │ ─────────────→ │ 验证链   │
│ (Monkey)│ ←──协商/重试── │ (Horse) │ ←──修复指引── │ (Verifier)│
└────┬────┘                └────┬────┘                └────┬─────┘
     │                          │                          │
     │      ┌─────────┐         │         ┌──────────┐     │
     └─────→│ 司库    │ ←───────┘ ←──────│ 书童     │←────┘
            │ (Keeper)│                  │ (Scribe)  │
            │ 9状态机  │                  │ 多维表格   │
            └─────────┘                  └──────────┘
                                            ↑
                                     ┌──────────┐
                                     │ 采购员    │
                                     │ (Purchaser)│
                                     │ 11门类巡逻 │
                                     └──────────┘
```

### 角色分工

| 角色 | 职责 | 核心能力 |
|:-----|:-----|:---------|
| **灵猴** Monkey | 路由与审核 | 任务分类、指纹匹配(10领域)、四级审核、协商修复、**双路径收敛** |
| **骏马** Horse | 推理与执行 | 136子链(4脑)、单链/双链推理、混搭Provider |
| **司库** Keeper | 状态驱动 | 9状态状态机（待构思→验证通过/未通过）、合法转换表硬编码 |
| **书童** Scribe | 认知与记忆 | SQLite多维表格(22+表)、认知10库、对话记录 |
| **质检官** Verifier | 验证审查 | **5条验证链**: 反证逻辑/反AI逻辑/反证思维/逆AI思维/**禁止数值解** |
| **采购员** Purchaser | 采买与巡检 | AgentReach多源搜索、11门类自治巡逻、Tier评分 |

---

## 赛博意识流 — 开发总纲

> **赛博意识流（Cyber Consciousness Stream）** 是弼马温 Agent 的顶层设计理念，也是后续衍生产品（赛博猴 Cyber Monkey Agent）的核心架构纲领。

### 核心理念

```
┌─────────────────────────────────────────────────────────┐
│              赛博意识流 — 开发总纲                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  多维表格 = 永久存储基质（长期碎片化记忆库）              │
│      ↓                                                  │
│  任务触发 → 读取表格碎片 → 动态关联 → 形成单次思考流     │
│      ↓                                                  │
│  AI = 临时涌现的意识流（用完即销毁）                     │
│      ↓                                                  │
│  动态生成临时代码 → 执行 → 归档回表格 → 自生长闭环       │
│      ↓                                                  │
│  后续同类任务自动读取历史经验碎片，自主迭代优化            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 产品线规划

| 产品 | 性质 | 定位 | 差异化 |
|:-----|:-----|:------|:--------|
| **弼马温** | **开源**（MIT） | 开发者自部署版 | 中英文双语，核心推理引擎全开放 |
| **赛博猴** | **闭源**（Steam 35元买断） | 开箱即用完整生态版 | 多语言UI（中/英/日/韩）、多模态(ComfyUI)、TTS语音(audio.cpp)、48GB自适应工作流 |

### 核心原则

1. **内部统一中文推理**：136 子链基于中文理念体系，输入多语言→自动转中文推理→结果输出对应语言
2. **自生长经验闭环**：历史任务归档→沉淀为记忆碎片→后续任务自动复用改良→无需人工预制模板
3. **分层权限保护**：底层子链、验证链、指纹规则仅可读，AI不可篡改核心推理底座
4. **解析解优先**：所有推理结果必须经过验证链合法性校验，拒绝无依据的数值拟合输出

### 路线图

| 阶段 | 目标 | 时间 |
|:-----|:------|:------|
| **P0** 状态机数据化 | 状态流转从代码迁入多维表格，改表格不改代码 | 当前 |
| **P1** 子链/指纹数据化 | 推理权重迁入表格，在线调整实时生效 | 后续 |
| **P2** 碎片化记忆归档 | 任务全链路记录存入表格，按需检索复用 | 后续 |
| **P3** 动态临时代码 | AI 自主生成单次任务代码→归档→自生长 | 远期 |
| **P4** 赛博猴发布 | 多语言TTS、ComfyUI多模态、48GB自适应流 | **v0.3.1** ✅ |
| **P5** 多模态深化 | 视频生成、实时流媒体、3D 内容 | 远期 |

---

## 核心能力

### 1. 推理体系 — 136子链 + 10领域指纹

```
4脑 × 34链 = 136条原子推理算子

因果链(34)  一因一果→一因多果→多因一果→直接诱因→深层因果...
逻辑链(31)  主次→互补→因果→传承→依存→互斥→取舍→拆分→时序...
思维链(33)  主次优先级→正反权衡→类比对照→分层拆解→演化推演...
推导法(35)  二分判定→要素考量→条件筛选→动态评估→收敛排除...
```

每个指纹含 **102~134 条** 活跃子链权重 + Tier分级(T1-T5)：

| 领域指纹 | 活跃链数 | 场景 |
|:---------|:---------|:-----|
| ACADEMIC | 134 | 学术研究与科学验证 |
| TECH | 134 | 技术架构与系统工程 |
| PRODUCT | 134 | 产品管理与用户洞察 |
| BUSINESS | 134 | 商业分析与战略决策 |
| FINANCE | 134 | 金融投资与风险管控 |
| POLICY | 134 | 公共政策与社会治理 |
| AUTHOR | 127 | 网络文学创作 |
| CRITIQUE | 124 | 哲学批判与概念分析 |
| CHAOS | 102 | 乐子人/混沌创作 |
| thinker | 134 | 通用底座（所有领域引用） |

### 2. 验证体系 — 5条验证链（v0.3.0新增第5条）

| 链 | 功能 |
|:---|:-----|
| ① 反证逻辑链 | 逻辑关系反证验证：A→B，反查B→A |
| ② 反AI逻辑链 | 反AI式逻辑错误：机械逻辑/脱离材料/偷换概念 |
| ③ 反证思维链 | 因果路径反证：倒果为因/伪相关/忽略共因 |
| ④ 逆AI思维链 | 反AI式思维过程：机械推理/空泛套壳 |
| **⑤ 禁止数值解链** 🆕 | **禁止数值评分/二元标签/模板化输出，要求解析解表述** |

### 3. 任务输出引擎（v0.3.0核心）

```
workspace/output/
  T001/                     ← 任务编号
    v1/                     ← 初版
      01_问题.md            ← 问题/需求/构思
      02_推理过程.md         ← 推理/推导（136子链）
      03_输出结果.md         ← 最终输出（人话/结构化）
      _迭代说明.md
    v2/                     ← 迭代版（用户不满意→修订）
      01_问题.md            ← 新问题（含旧推理+用户反馈上下文）
      02_推理过程.md
      03_输出结果.md
  T002/
    ...
```

**设计原则：**
- 文件存**完整内容**（保留完整推理证据）
- 表格只存**摘要**(≤500字)用于检索（物理切割上下文、规避幻觉）
- 版本**不覆盖**（v1→v2→v3精确回滚）
- 迭代**传上下文**（旧推理+新反馈→新问题，不需要AI瞎猜）

支持输出模板（从数据库读取，可扩展）：

| 模板 | 文件数 | 格式 |
|:-----|:------:|:-----|
| 创作/分析/推理 | 3 | 01_问题→02_推理过程→03_输出结果 |
| 编程 | 4 | 01_需求→02_设计方案→03_代码实现→04_测试验证 |
| 研究 | 4 | 01_研究问题→02_方法论→03_发现→04_结论 |
| **项目** 🆕 | **4** | **01_思路→02_流程→03_执行方法→04_结果** |
| 默认 | 3 | 三文件制 |

### 4. 自治巡逻系统

11门类 AI 自治联网搜索评分：

```
AI前沿/科技/时事/人文/商业/产业/设计/金融/政策/开源/游戏
```

评分体系：基础分(60) + 内容质量(40) + 连贯性(30) + AgentReach因子(20) = 150分
Tier分级：T1(≥100) / T2(≥75) / T3(≥50) / T4(≥25) / T5(<25)
每日 1:00 重置Tier名额

### 5. 冷监督（Aileran Mode） 🆕 v0.3.0

```
/aileron on    → 允许后台自治循环（20分钟整理+10分钟巡检）
/aileron off   → 冻结后台循环，省token
```

---

## 快速开始

### MCP 连接（推荐）

**方式1：Claude Desktop**

编辑 `claude_desktop_config.json`：
```json
{
  "mcpServers": {
    "bimawen-agent": {
      "command": "python3",
      "args": ["-m", "harness_core.mcp_server"]
    }
  }
}
```

**方式2：Claude Code**
```bash
claude mcp add bimawen-agent -- python3 -m harness_core.mcp_server
```

**方式3：HTTP 模式**
```bash
python3 -m harness_core.mcp_server --transport http --port 8000
```

### MCP 工具一览（13个）

| 工具 | 用途 |
|:-----|:------|
| `patrol_status` | 巡逻系统整体状态 |
| `patrol_trigger` | 触发一轮巡逻 |
| `patrol_categories` | 11个门类评分详情 |
| `skill_list` | 列出已安装 Skill |
| `skill_run` | 执行 Skill |
| `graph_query` | 知识图谱查询（6种节点） |
| `agent_status` | Agent 状态 |
| `agent_config` | 配置查看（API Key 脱敏） |
| `workspace_init` | 初始化 workspace/output |
| `task_output_save` | 保存任务输出（文件+表格） |
| `task_output_list` | 列出所有任务 |
| `task_output_read` | 读取版本输出 |
| `task_output_iterate` 🆕 | 迭代：读旧版→打包反馈→新版 |

### CLI

```bash
pip install -e .
monkey-harness mcp                     # MCP服务器(stdin/stdout)
monkey-harness mcp --transport http     # HTTP模式
monkey-harness status                   # 系统状态
monkey-harness config                   # 查看配置
```

### 混搭模式

```bash
export MONKEY_MONKEY_PROVIDER=openai   # 灵猴用 OpenAI
export MONKEY_HORSE_PROVIDER=deepseek  # 骏马用 DeepSeek
monkey-harness mcp
```

### 支持的 AI 厂商

OpenAI / Anthropic / DeepSeek / Google Gemini / Ollama / OpenRouter / vLLM / 本地模型

---

## 测试

```bash
# 全部测试（33项，v0.3.0全部通过）
python3 -m pytest tests/ -v

# 单项
python3 -m pytest tests/test_output.py -v    # 输出引擎
python3 -m pytest tests/test_fingerprints.py -v  # 指纹/子链
python3 -m pytest tests/test_patrol.py -v       # 巡逻
python3 -m pytest tests/test_system.py -v       # 系统/冷监督
```

| 测试套件 | 数量 | 覆盖 |
|:---------|:----:|:-----|
| test_fingerprints | 7 | 指纹加载、子链结构、thinker引用、领域数 |
| test_output | 10 | 文件引擎、版本迭代、表格双写、模板种子 |
| test_patrol | 6 | AgentReach搜索、评分引擎、Tier分布 |
| test_system | 10 | CLI、MCP导入、冷监督4参数 |
| **总计** | **33** | **全通过** |

---

## 项目文档

| 文档 | 说明 |
|:-----|:------|
| [docs/MCP_连接方案_v0.3.0.md](docs/MCP_连接方案_v0.3.0.md) | MCP完整配置 + 13工具 + 故障排查 |
| [docs/WORKSPACE_OUTPUT.md](docs/WORKSPACE_OUTPUT.md) | 任务输出引擎 + 迭代机制 + Obsidian |
| [docs/windows_signing.md](docs/windows_signing.md) | Windows代码签名配置 |
| [PRIVACY.md](PRIVACY.md) | 隐私政策 |
| [CHANGELOG](CHANGELOG.md) | 完整版本历史 |

---

## 代码签名

✅ 免费代码签名由 [SignPath.io](https://signpath.io) 提供，证书来自 [SignPath Foundation](https://signpath.org)
✅ 隐私政策: [PRIVACY.md](PRIVACY.md) — 本程序不会将任何信息传输到其他联网系统，除非用户明确请求或操作需要

*详情见 [docs/windows_signing.md](docs/windows_signing.md)*
