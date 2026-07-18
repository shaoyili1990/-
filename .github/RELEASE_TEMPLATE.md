# Hermes Agent Universal v${{ github.ref_name }}

通用可移植 AI Agent 系统 — 猴驭马（Monkey-Horse）架构

## 下载

| 平台 | 文件 | 说明 |
|------|------|------|
| Linux | `hermes-agent` | 独立可执行二进制 |
| Linux | `*.deb` | Debian/Ubuntu 安装包 |
| Linux | `*.AppImage` | 通用 Linux 运行格式 |
| macOS | `*.dmg` | macOS 安装映像 |
| Windows | `*.exe` | Windows 可执行文件 |
| pip | `*.whl` | Python pip 包 |

## 快速开始

```bash
# Linux 独立二进制
chmod +x hermes-agent
./hermes-agent

# 或 DEB 安装
sudo dpkg -i *.deb

# 设置 API Key
export OPENAI_API_KEY=sk-xxx
export DEEPSEEK_API_KEY=sk-xxx

# 启动 Web UI
hermes desktop
```

## 架构

- **灵猴(Monkey)** — 路由与审核
- **骏马(Horse)** — 推理与执行，136条子链
- **司库(Keeper)** — 9状态状态机
- **书童(Scribe)** — 认知与记忆
- **质检官** — 4条验证链审查

## 变更

_由 GitHub Actions 自动生成_
