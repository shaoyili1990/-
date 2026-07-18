#!/data/data/com.termux/files/usr/bin/bash
# Hermes Agent Universal - Android Termux Installer
# 在 Termux 中运行: bash install_android.sh
# 或: curl -fsSL https://hermes-agent.dev/install_android.sh | bash

set -euo pipefail

echo "================================================"
echo " Hermes Agent Universal - Android 安装程序"
echo " 需要 Termux (F-Droid 版本)"
echo "================================================"
echo ""

# 检查 Termux 环境
if [ ! -d "/data/data/com.termux" ] && [ ! -d "/data/data/com.termux.fdroid" ]; then
    echo "[警告] 未检测到 Termux 环境"
    echo "请从 F-Droid 安装 Termux:"
    echo "  https://f-droid.org/packages/com.termux/"
    echo ""
    echo "[5秒后继续...]"
    sleep 5
fi

echo "[1/6] 更新包管理器..."
pkg update -y

echo ""
echo "[2/6] 安装 Python 和依赖..."
pkg install -y python clang openssl git binutils

echo ""
echo "[3/6] 升级 pip..."
pip install --upgrade pip

echo ""
echo "[4/6] 安装 Hermes Agent Universal..."
pip install hermes-agent-universal 2>/dev/null || {
    echo "  pip安装失败,尝试从源码安装..."
    if [ -f "pyproject.toml" ]; then
        pip install .
    else
        echo "  下载源码..."
        pkg install -y wget
        wget https://github.com/hermes-agent/universal/archive/main.zip
        unzip main.zip
        cd universal-main
        pip install .
        cd ..
        rm -rf universal-main main.zip
    fi
}

echo ""
echo "[5/6] 配置存储权限..."
termux-setup-storage 2>/dev/null || true

echo ""
echo "[6/6] 验证安装..."
python -c "from hermes_universal import __version__; print(f'Hermes Agent v{__version__}')"

echo ""
echo "================================================"
echo " 安装完成!"
echo "================================================"
echo ""
echo "使用方法:"
echo "  hermes run \"你的问题\"           # 单次对话"
echo "  hermes chat                        # 交互模式"
echo ""
echo "  # 桌面Web UI 需要 Termux:X11:"
echo "  #   pkg install x11-repo"
echo "  #   pkg install termux-x11"
echo "  #   hermes desktop"
echo ""
echo "配置API Key (编辑 ~/.bashrc 添加):"
echo "  export OPENAI_API_KEY=sk-xxx"
echo "  export DEEPSEEK_API_KEY=sk-xxx"
echo ""
echo "或使用本地模型 (需要安装 Ollama):"
echo "  pkg install ollama"
echo "  export HERMES_HORSE_PROVIDER=ollama"
echo ""
echo "================================================"
