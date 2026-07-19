# Hermes Agent Universal

通用可移植 AI Agent 系统 — 猴驭马（Monkey-Horse）架构

> 🆔 **代码签名策略**  
> 本项目已向 SignPath Foundation 提交申请，免费签名 Windows 发布构件。  
> 证书签发方：SignPath Foundation  
> 源代码已验证：所有发布构件均从本仓库 CI 构建。  
>  
> **签名后**：Windows SmartScreen 不再警告，用户可验证二进制文件确系本仓库产出。  
> *详情见 [docs/windows_signing.md](docs/windows_signing.md)*

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

## 快速开始

### 独立可执行文件（推荐）

从 [Releases](https://github.com/shaoyili1990/-/releases) 下载对应平台的二进制：

```bash
# Linux
chmod +x hermes-agent
./hermes-agent

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
pip install hermes-agent-universal
hermes chat
```

### Docker

```bash
docker pull shaoyili1990/hermes-agent:latest
docker run -e OPENAI_API_KEY=$OPENAI_API_KEY -p 8080:8080 shaoyili1990/hermes-agent
```

## 资源

- **136条推理子链** — 4脑分类（逻辑链/因果链/思维链/推导法）
- **11个领域指纹** — 学术/商业/金融/政策/技术/产品/批判/混乱/作者/财务/全局
- **4条验证链** — 反证逻辑/反AI逻辑/反证思维/逆AI思维
- **8家AI厂商** — OpenAI/Anthropic/DeepSeek/Google/Ollama/OpenRouter/vLLM
