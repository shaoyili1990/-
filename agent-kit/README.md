# Monkey Harness Agent (弼马温) - Agent Kit

通用可移植 AI Agent 系统，基于猴驭马(Monkey-Horse)四角色架构。

## 目录结构

```
agent-kit/
├── SKILL.md              # 核心系统提示词（纯文本，无需代码）
├── manifest.json         # Agent平台兼容性清单
├── config/
│   ├── monkey-harness.json       # Monkey Harness平台配置
│   ├── openclaw.json     # OpenClaw平台配置
│   └── universal.json    # 通用配置
├── fingerprints/         # 领域指纹（11个JSON）
└── subchains/            # 136条推理子链（Markdown）
```

## 使用方法

### 纯提示词模式（无需代码）
直接将 `SKILL.md` 作为 System Prompt 使用。

### Python包模式
```bash
pip install monkey-harness-agent
monkey-harness run "你的问题"
```

### Docker模式
```bash
docker build -t monkey-harness-agent .
docker run -p 8080:8080 monkey-harness-agent
```

## 架构

| 角色 | 职责 |
|------|------|
| 灵猴(Monkey) | 路由与审核 - 领域匹配/深度判定 |
| 骏马(Horse) | 推理与执行 - 4脑全参与/136子链 |
| 司库(Keeper) | 状态机守护 - 9状态/版本控制 |
| 书童(Scribe) | 记忆管家 - 10认知库 |

## 许可证

MIT
