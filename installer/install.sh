#!/usr/bin/env bash
# Monkey Harness Agent Universal - Linux/macOS 安装脚本
# 用法: curl -fsSL https://monkey-harness-agent.dev/install.sh | bash
#       或: chmod +x install.sh && ./install.sh

set -euo pipefail

MONKEY_VERSION="0.3.0"
MONKEY_PKG="monkey-harness-agent-universal"

echo "================================================"
echo " Monkey Harness Agent Universal v${MONKEY_VERSION} 安装程序"
echo " 支持: Linux / macOS / WSL"
echo "================================================"
echo ""

# 检测系统
detect_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *)          echo "unknown";;
    esac
}

OS=$(detect_os)
echo "[检测] 操作系统: $OS"

# 检查 Python
check_python() {
    if command -v python3 &>/dev/null; then
        PYTHON=python3
    elif command -v python &>/dev/null; then
        PYTHON=python
    else
        echo "[错误] 未找到 Python3，请先安装: https://python.org"
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON --version 2>&1 | grep -oP '\d+\.\d+')
    echo "[检测] Python: $($PYTHON --version)"

    if [ "$(echo "$PYTHON_VERSION >= 3.11" | bc -l 2>/dev/null || echo 0)" = "0" ]; then
        # bc not available, do string comparison
        MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
        MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
        if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 11 ]; }; then
            echo "[错误] 需要 Python >= 3.11，当前为 $PYTHON_VERSION"
            exit 1
        fi
    fi
}

check_python

# 安装依赖
echo ""
echo "[1/3] 安装系统依赖..."
case "$OS" in
    linux)
        if command -v apt-get &>/dev/null; then
            sudo apt-get update -qq
            sudo apt-get install -y -qq python3-pip python3-venv build-essential 2>/dev/null || true
        elif command -v yum &>/dev/null; then
            sudo yum install -y python3-pip python3-devel 2>/dev/null || true
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm python-pip 2>/dev/null || true
        fi
        ;;
    macos)
        if ! command -v brew &>/dev/null; then
            echo "  Homebrew 未安装，跳过系统依赖安装"
        fi
        ;;
esac

# 安装 Monkey Harness Agent
echo ""
echo "[2/3] 安装 Monkey Harness Agent Universal..."
$PYTHON -m pip install --upgrade pip
$PYTHON -m pip install $MONKEY_PKG 2>/dev/null || {
    echo "  pip安装失败，尝试从源码安装..."
    if [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
        $PYTHON -m pip install .
    else
        echo "  [错误] 请先下载源码或检查网络连接"
        echo "  手动安装: pip install $MONKEY_PKG"
        exit 1
    fi
}

# 验证安装
echo ""
echo "[3/3] 验证安装..."
if command -v monkey-harness &>/dev/null || command -v hermes &>/dev/null; then
    echo "  $(monkey-harness --version 2>/dev/null || echo 'monkey-harness CLI installed')"
else
    echo "  请确保 ~/.local/bin 在 PATH 中"
    echo "  或运行: $PYTHON -m harness_core"
fi

# 配置指引
echo ""
echo "================================================"
echo " 安装完成!"
echo "================================================"
echo ""
echo "快速开始:"
echo "  monkey-harness run \"你好\"                          # 简单对话"
echo "  monkey-harness chat                                 # 交互模式"
echo "  monkey-harness desktop                              # 桌面Web UI"
echo ""
echo "配置API Key (任选一种):"
echo "  export OPENAI_API_KEY=sk-xxx                # OpenAI"
echo "  export DEEPSEEK_API_KEY=sk-xxx              # DeepSeek"
echo "  export ANTHROPIC_API_KEY=sk-ant-xxx         # Claude"
echo ""
echo "混搭模式示例:"
echo "  export MONKEY_MONKEY_PROVIDER=openai"
echo "  export MONKEY_HORSE_PROVIDER=deepseek"
echo "  monkey-harness chat"
echo ""
echo "详细文档: https://github.com/monkey-harness-agent/universal"
echo "================================================"
