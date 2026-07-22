#!/bin/bash
# 切换到多模态模式（赛博猴 48GB 自适应工作流）
# 暂停巡检者和 TTS，释放显存给 ComfyUI
# 巡检任务临时挂载到 DeepSeek Flash API

set -e

echo "=========================================="
echo "  切换到多模态模式"
echo "  48GB 自适应工作流 v2"
echo "=========================================="

# === 1. 检查骏马是否运行 ===
if ! curl -s http://localhost:6006/health > /dev/null 2>&1; then
    echo "[WARN] 骏马 (6006) 未运行！请先启动骏马"
fi
echo "[OK] 骏马运行中"

# === 2. 保存巡检者状态 ===
if curl -s http://localhost:6008/patrol/status > /tmp/patrol_snapshot.json 2>/dev/null; then
    echo "[OK] 巡检者状态已保存 → /tmp/patrol_snapshot.json"
else
    echo "[INFO] 巡检者未运行，跳过状态保存"
fi

# === 3. 暂停巡检者 ===
PIDS=$(pgrep -f "llama-server.*6008" 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    kill $PIDS 2>/dev/null
    echo "[OK] 巡检者已暂停 (PID: $PIDS)"
else
    echo "[INFO] 巡检者未运行"
fi

# === 4. 暂停 TTS ===
PIDS_TTS=$(pgrep -f "audio-cpp.*7899" 2>/dev/null || true)
PIDS_TTS2=$(pgrep -f "webui.py.*7899" 2>/dev/null || true)
if [ -n "$PIDS_TTS" ]; then
    kill $PIDS_TTS 2>/dev/null
    echo "[OK] TTS (audio-cpp) 已暂停"
fi
if [ -n "$PIDS_TTS2" ]; then
    kill $PIDS_TTS2 2>/dev/null
    echo "[OK] TTS (webui.py) 已暂停"
fi

# === 5. 设置降级环境变量 ===
export PATROL_FALLBACK="deepseek-flash"
export TTS_FALLBACK="deepseek-flash"
echo "[OK] 巡检+TTS 降级到 DeepSeek Flash API"

# === 6. 启动 ComfyUI ===
if pgrep -f "ComfyUI/main.py" > /dev/null 2>&1; then
    echo "[OK] ComfyUI 已在运行"
else
    echo "[START] 启动 ComfyUI (端口 8188)..."
    cd /root/ComfyUI 2>/dev/null || cd ~/ComfyUI 2>/dev/null || {
        echo "[ERROR] 找不到 ComfyUI 目录"
        exit 1
    }
    python main.py --listen 0.0.0.0 --port 8188 --force-fp16 &
    COM_PID=$!
    echo "[OK] ComfyUI 启动中 (PID: $COM_PID)"
    # 等待就绪
    for i in $(seq 1 30); do
        if curl -s http://localhost:8188/api/object_info > /dev/null 2>&1; then
            echo "[OK] ComfyUI 已就绪"
            break
        fi
        sleep 2
    done
fi

# === 7. 检查显存 ===
mem_used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
echo "[INFO] 当前显存: ${mem_used}MB / 49152MB"

if [ "$mem_used" -gt 40000 ]; then
    echo "[WARN] 显存用量较高！注意不要超出 48GB"
fi

echo ""
echo "=========================================="
echo "  多模态模式已激活"
echo "  骏马:     :6006"
echo "  ComfyUI:  :8188"
echo "  巡检者:   降级 → DeepSeek Flash"
echo "  TTS:      降级 → DeepSeek Flash"
echo "=========================================="
