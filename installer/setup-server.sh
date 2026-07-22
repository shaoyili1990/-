#!/bin/bash
# 赛博猴 一键部署脚本
# 安装 TTS (audio.cpp-webui) + ComfyUI + 自适应工作流
# 用于服务器首次部署或重建

set -e

PIP="/root/miniconda3/bin/pip"

echo "=========================================="
echo "  赛博猴 服务器部署脚本"
echo "  TTS + ComfyUI + 自适应工作流"
echo "=========================================="

# === 1. 检查环境 ===
echo ""
echo "=== [1/6] 检查环境 ==="

if ! command -v nvidia-smi &>/dev/null; then
    echo "[ERROR] 无 NVIDIA GPU"
    exit 1
fi

GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | tr -d ' MiB')
echo "[OK] GPU 显存: ${GPU_MEM}MB"

if [ "$GPU_MEM" -lt 48000 ]; then
    echo "[WARN] 显存 < 48GB，自适应策略可能不适用"
fi

# === 2. 安装 Python 依赖 ===
echo ""
echo "=== [2/6] 安装 Python 依赖 ==="

DEPS="fastapi uvicorn gradio huggingface_hub pydub safetensors pyyaml requests tqdm einops aiohttp yarl psutil alembic SQLAlchemy filelock av simpleeval blake3"

for pkg in $DEPS; do
    echo "  pip install $pkg..."
    $PIP install -q "$pkg" 2>&1 | tail -1
done
echo "[OK] 基础依赖安装完成"

# === 3. 安装 ComfyUI 专用包 ===
echo ""
echo "=== [3/6] 安装 ComfyUI 专用包 ==="

COMFY_PKGS="comfyui-frontend-package==1.45.21 comfyui-workflow-templates==0.11.12 comfyui-embedded-docs==0.5.8 comfy-kitchen==0.2.22 comfy-aimdo==0.4.10 transformers>=4.50.3"

for pkg in $COMFY_PKGS; do
    echo "  pip install $pkg..."
    $PIP install -q "$pkg" 2>&1 | tail -1
done
echo "[OK] ComfyUI 依赖安装完成"

# === 4. 部署 audio.cpp-webui (TTS) ===
echo ""
echo "=== [4/6] 部署 TTS (audio.cpp-webui) ==="

cd /root

if [ -f "/root/audio-cpp/webui/webui.py" ]; then
    echo "[OK] audio-cpp 已存在"
else
    echo "[DOWNLOAD] 下载 audio.cpp-webui..."
    rm -rf audio-cpp tmp_au 2>/dev/null; mkdir -p tmp_au
    curl -sL --max-time 300 \
        "https://github.com/kigner/audio.cpp-webui/archive/refs/heads/release-0.2.tar.gz" \
        -o /tmp/au_src.tar.gz || \
    curl -sL --max-time 300 \
        "https://ghproxy.com/https://github.com/kigner/audio.cpp-webui/archive/refs/heads/release-0.2.tar.gz" \
        -o /tmp/au_src.tar.gz

    if [ -f "/tmp/au_src.tar.gz" ] && [ $(stat -c%s /tmp/au_src.tar.gz) -gt 100000 ]; then
        tar xzf /tmp/au_src.tar.gz -C tmp_au
        srcdir=$(ls tmp_au/)
        mv "tmp_au/$srcdir" audio-cpp
        rm -rf tmp_au /tmp/au_src.tar.gz
        echo "[OK] audio-cpp 下载完成: $(ls /root/audio-cpp/webui/webui.py)"
    else
        echo "[WARN] 下载失败，请手动克隆:"
        echo "  cd /root && git clone https://github.com/kigner/audio.cpp-webui.git"
    fi
fi

# === 5. 部署 ComfyUI ===
echo ""
echo "=== [5/6] 部署 ComfyUI ==="

cd /root

if [ -f "/root/ComfyUI/main.py" ]; then
    echo "[OK] ComfyUI 已存在"
else
    echo "[DOWNLOAD] 下载 ComfyUI..."
    curl -sL --max-time 300 \
        "https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.tar.gz" \
        -o /tmp/co_src.tar.gz || \
    curl -sL --max-time 300 \
        "https://ghproxy.com/https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.tar.gz" \
        -o /tmp/co_src.tar.gz

    if [ -f "/tmp/co_src.tar.gz" ] && [ $(stat -c%s /tmp/co_src.tar.gz) -gt 100000 ]; then
        tar xzf /tmp/co_src.tar.gz
        srcdir=$(ls -d ComfyUI-*/)
        mv "$srcdir" ComfyUI
        rm -f /tmp/co_src.tar.gz
        echo "[OK] ComfyUI 下载完成: $(ls /root/ComfyUI/main.py)"
    else
        echo "[WARN] 下载失败，请手动克隆:"
        echo "  cd /root && git clone https://github.com/comfyanonymous/ComfyUI.git"
    fi
fi

# === 6. 最终验证 ===
echo ""
echo "=== [6/6] 验证 ==="

echo "  Python依赖:"
$PIP list 2>/dev/null | grep -iE "comfy|transform|einops|safetensors|filelock|gradio|fastapi|uvicorn" | head -10

echo ""
echo "  TTS:  $( [ -f /root/audio-cpp/webui/webui.py ] && echo '✅' || echo '❌' ) audio-cpp"
echo "  Comfy: $( [ -f /root/ComfyUI/main.py ] && echo '✅' || echo '❌' ) ComfyUI"
echo "  骏马:  $( pgrep -f llama-server && echo '✅' || echo '❌' ) :6006"

echo ""
echo "=========================================="
echo "  部署完成"
echo ""
echo "  启动 TTS:      python /root/audio-cpp/webui/webui.py --listen 0.0.0.0 --port 7899"
echo "  启动 ComfyUI:  python /root/ComfyUI/main.py --listen 0.0.0.0 --port 8188 --force-fp16"
echo "  常规模式:     bash start-multimodal.sh (暂停→多模态)"
echo "  恢复模式:     bash restore-normal.sh (恢复→常规)"
echo "=========================================="
