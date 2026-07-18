# Hermes Agent Universal - PromptX 部署指南

## 一、导入方式

### 方式1: 直接激活角色
```
/monkey   - 激活灵猴角色
/horse    - 激活骏马角色
/keeper   - 激活司库角色
/scribe   - 激活书童角色
/verifier - 激活质检官角色
```

### 方式2: 使用SKILL.md作为System Prompt
将 SKILL.md 的内容作为System Prompt直接粘贴到任意AI对话中,
当前AI会自动扮演全部5个角色。

### 方式3: PromptX V2角色注册
``promptx
action("born", {{
  role: "monkey",
  name: "灵猴",
  source: "Feature: 灵猴...
}}
``

## 二、文件结构
```
hermes-agent-universal/
├── hermes_universal/          # Python源码
│   ├── core/                  # 五角色实现
│   ├── engine/                # 引擎+状态机+子链调度
│   ├── providers/             # AI厂商适配器
│   ├── messages/              # 消息内容模型
│   ├── desktop/               # Web UI
│   └── utils/                 # 工具
├── fingerprints/              # 11个指纹JSON
├── subchains/                 # 136条子链模板
├── validations/               # 4条验证链模板
├── store/                     # SQLite数据库
│   ├── rnd_engine.db          # 状态/任务/步骤/审核
│   └── hermes.db              # 认知/记忆/指纹
├── config.yaml                # 配置文件
├── SKILL.md                   # 通用提示词技能
├── pyproject.toml             # Python包定义
└── Dockerfile                 # Docker部署
```

## 三、快速启动
```bash
# Python安装
pip install hermes-agent-universal

# 或直接运行
python -m hermes_universal

# CLI模式
hermes run "你的问题"
hermes chat
hermes desktop
```

## 四、API配置 (config.yaml)
支持混搭模式:
- Monkey用OpenAI, Horse用Claude
- Monkey用DeepSeek, Horse用Ollama(本地)
- 全用Ollama(纯本地)
- 环境变量注入: OPENAI_API_KEY, DEEPSEEK_API_KEY等

## 五、核心验证理念
> 验证不是追求"多写分析", 而是判断合理性(不是正确性):
> - A推B, 反查B推A
> - 先看主观因素, 再看外部因素
> - 内外皆无 → 孤证失效 → 原结论不成立
> - 这是AI最常犯的错误: 想当然
