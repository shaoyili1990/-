# Hermes Agent Universal ${{ github.ref_name }}

## 📦 下载

| 平台 | 安装包 | 说明 |
|------|--------|------|
| **Linux (通用)** | `hermes-agent` | 独立可执行二进制文件，下载后 `chmod +x` 即可运行 |
| **Debian/Ubuntu** | `*.deb` | `sudo dpkg -i *.deb` 系统安装 |
| **Linux (通用AppImage)** | `*.AppImage` | 双击运行，无需安装 |
| **macOS** | `*.dmg` | 打开 DMG 拖入 Applications |
| **Windows** | `hermes-agent.exe` | 直接运行 |
| **Docker** | `shaoyili/hermes-agent:latest` | `docker run -p 8080:8080 shaoyili/hermes-agent` |
| **PyPI** | `pip install hermes-agent-universal` | Python 包安装 |

## 🚀 快速开始

```bash
# 1. 设置 API Key（任选一种）
export OPENAI_API_KEY=sk-xxx          # Monkey 用 OpenAI
export DEEPSEEK_API_KEY=sk-xxx        # Horse 用 DeepSeek

# 2. 运行
./hermes-agent                         # CLI 模式
hermes chat                           # 对话模式
hermes desktop                        # Web UI (http://localhost:8080)
```

### 混搭模式（Monkey 和 Horse 用不同厂商）
```bash
export HERMES_MONKEY_PROVIDER=openai
export HERMES_MONKEY_KEY=sk-xxx
export HERMES_HORSE_PROVIDER=deepseek
export HERMES_HORSE_KEY=sk-xxx
hermes desktop
```

## 🧠 架构

灵猴(Monkey) → 路由审核 → 骏马(Horse) → 推理执行 → 司库(Keeper) → 状态驱动 → 书童(Scribe) → 记忆管理

- **136条推理子链**（4脑：逻辑链/因果链/思维链/推导法）
- **9状态状态机** + **4级审核**
- **10认知库** + **SQLite多维表格存储**
- **4条验证链**（反证逻辑/反AI逻辑/反证思维/逆AI思维）
