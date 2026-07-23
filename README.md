# 弼马温 Agent（Monkey Harness Agent）

> 没有大脑的记忆 — 一个单细胞如何用黏液记住整个世界

**当前版本: v0.3.1**（2026-07-23） | 许可: MIT

---

## 核心哲学

**解析解（Analytic Solution） · 离线优先 · 多维表格=本体**

- **解析解原则**: 一切决策使用可能性/倾向性/合理性，禁止二元判定
- **离线优先**: 本地化运行，零token消耗冷启动，数据主权归用户
- **多维表格=本体**: SQLite表存储一切，表即Agent的大脑

## 角色系统

| 角色 | 代号 | 职责 |
|------|------|------|
| **Monkey** 🐒 | 灵猴 | 路由与审核官 — 定题、分类、深度判断、质量审查 |
| **Horse** 🐴 | 骏马 | 推理与执行者 — 4脑全部参与（逻辑/因果/思维/推导）|
| **Keeper** 🔐 | 司库 | 监督与守护者 — 宪法执行、权限验证、状态机守护 |
| **Patrol** 👁️ | 巡检者 | 自主联网巡检 — 知识爬取、生态探索、收录审核 |
| **Purchaser** 💳 | 采购者 | 外部服务采购与额度管控 |
| **Scribe** 📝 | 书记官 | 输出文档生成与版本管理 |
| **Verifier** ✅ | 验证官 | 输出质量审核与标准校验 |

## 防御体系

### Keeper 权限监督
- 29条权限表控制所有角色操作
- 14条宪法硬编码框架规则
- 二元判断关键词前置检测
- 状态机9步流转全链路追踪

### 哈希自愈 + 标准副本
- 哈希自愈引擎：每次执行后自动扫描所有输出文档
- 标准副本守护：8核心表一致性自愈
- error_memories：篡改/异常/越权全记录

## 系统要求

- Python 3.11+
- SQLite 3.x
- 支持 Windows / Linux / macOS

## 快速开始

```bash
# 克隆
git clone https://github.com/shaoyili1990/-.git

# 安装
pip install requests pyyaml

# 冷启动（零token）
python3 -m harness_core cold_boot

# 启动CLI
python3 local_cli.py

# 启动GUI（桌面环境）
python3 pc_launcher.py
```

## 项目结构

```
bimawen/
├── harness_core/       # 核心框架
│   ├── core/           # 角色模块
│   ├── engine/         # 状态机引擎
│   ├── desktop/        # 桌面GUI
│   ├── tiandao/        # 天道系统（叙事引擎）
│   └── providers/      # AI提供商接口
├── engine/             # 引擎脚本
├── store/              # 运行时数据库
├── tests/              # 测试
└── docs/               # 文档
```

## 技术栈

- Python 3.11+
- SQLite（多维表格本体）
- DeepSeek API / 本地Qwen（可选）
- MCP Server（外部工具接入）

---

## 版本迭代

| 版本 | 日期 | 说明 |
|------|------|------|
| **v0.3.1** | 2026-07-23 | 天道系统（Y值驱动叙事引擎）+ 仓库结构迭代 |
| v0.3.0 | 2026-07-20 | 指纹运行时挂载 + 双路径推理 + 第5验证链 |
| v0.2.0 | 2026-07-19 | 冷监督 + 任务输出引擎 |
| v0.1.0 | 2026-07-18 | 弼马温品牌发布（Hermes → Monkey Harness） |

> 详细变更日志见 [CHANGELOG.md](CHANGELOG.md)

## 许可

MIT License © 2026 邵以利
