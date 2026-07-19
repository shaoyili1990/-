# Monkey Harness Agent (弼马温 Agent)

> 🐒 猴驭多源，AI自治巡逻 — 多模态智能体系统

## 代码签名策略

本项目签名发布 Windows 构件。

✅ 免费代码签名由 [SignPath.io](https://signpath.io) 提供，证书来自 [SignPath Foundation](https://signpath.org)
✅ 维护团队: [@shaoyili1990](https://github.com/shaoyili1990)（仓库Owner）
✅ 审批者: [@shaoyili1990](https://github.com/shaoyili1990)
✅ 隐私政策: [PRIVACY.md](PRIVACY.md) — 本程序不会将任何信息传输到其他联网系统，除非用户明确请求或操作需要

*详情见 [docs/windows_signing.md](docs/windows_signing.md)*

## 架构

```
灵猴(Monkey) → 路由审核 → 骏马(Horse) → 推理执行
                                                ↓
         书童(Scribe) ← 记忆管理 ← 司库(Keeper) ← 状态驱动
```

- **灵猴** — 路由与审核，判断任务交由哪条子链处理
- **骏马** — 推理与执行，136条子链 + 4条验证链
- **司库** — 9状态状态机，驱动研发流程的每一步
- **书童** — 认知与记忆，SQLite多维表格持久化
- **质检官** — 4条验证链审查产出（反证逻辑/反AI逻辑/反证思维/逆AI思维）
- **采购员** — 采买与巡检，AgentReach 多源搜索通道 + 11门类自治巡逻

## 快速开始

### 独立可执行文件（推荐）

从 [Releases](https://github.com/shaoyili1990/-/releases) 下载对应平台的二进制：

```bash
# Linux
chmod +x monkey-harness-agent
./monkey-harness-agent

# 设置API Key
export OPENAI_API_KEY=sk-xxx
export DEEPSEEK_API_KEY=sk-xxx

# Web UI（浏览器访问 http://localhost:8080）
hermes desktop

# CLI 对话
hermes chat
```

### 混搭模式

```bash
export HERMES_MONKEY_PROVIDER=openai   # 灵猴用 OpenAI
export HERMES_MONKEY_KEY=sk-xxx
export HERMES_HORSE_PROVIDER=deepseek   # 骏马用 DeepSeek
export HERMES_HORSE_KEY=sk-xxx

hermes desktop
```

### pip 安装

```bash
pip install monkey-harness-agent
hermes chat
```

### Docker

```bash
docker pull shaoyili1990/monkey-harness-agent:latest
docker run -e OPENAI_API_KEY=$OPENAI_API_KEY -p 9090:9090 shaoyili1990/monkey-harness-agent
```

## 资源

- **136条推理子链** — 4脑分类（逻辑链/因果链/思维链/推导法）
- **11个领域指纹** — 学术/商业/金融/政策/技术/产品/批判/混乱/作者/财务/全局
- **4条验证链** — 反证逻辑/反AI逻辑/反证思维/逆AI思维
- **8家AI厂商** — OpenAI/Anthropic/DeepSeek/Google/Ollama/OpenRouter/vLLM
