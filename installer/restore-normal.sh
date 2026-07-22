#!/bin/bash
# 恢复常规模式（赛博猴 48GB 自适应工作流）
# 卸载 ComfyUI 模型，恢复巡检者和 TTS

set -e

echo "=========================================="
echo "  恢复常规模式"
echo "=========================================="

# === 1. 卸载 ComfyUI 模型释放显存 ===
if curl -s http://localhost:8188/api/unload_all_models -X POST > /dev/null 2>&1; then
    echo "[OK] ComfyUI 模型已卸载（显存已释放）"
else
    echo "[INFO] ComfyUI 未运行，跳过卸载"
fi

# === 2. 停止 ComfyUI ===
PIDS_COM=$(pgrep -f "ComfyUI/main.py" 2>/dev/null || true)
if [ -n "$PIDS_COM" ]; then
    kill $PIDS_COM 2>/dev/null
    sleep 2
    echo "[OK] ComfyUI 已停止"
else
    echo "[INFO] ComfyUI 未运行"
fi

# === 3. 取消降级模式 ===
unset PATROL_FALLBACK
unset TTS_FALLBACK
echo "[OK] 取消降级模式"

# === 4. 恢复巡检者 ===
if [ -f /tmp/patrol_snapshot.json ]; then
    echo "[START] 恢复巡检者 (端口 6008)..."
    # 在赛博猴目录启动巡检者
    MONKEY_DIR="/root/work/cyber-monkey"
    if [ -d "$MONKEY_DIR" ]; then
        cd "$MONKEY_DIR"
        python -m harness_core agent monkey --patrol --port 6008 &
        echo "[OK] 巡检者已启动 (端口 6008)"
    else
        echo "[WARN] 找不到赛博猴目录: $MONKEY_DIR"
        echo "[INFO] 请手动启动巡检者"
    fi
else
    echo "[INFO] 无巡检者快照，跳过恢复"
fi

# === 5. 恢复 TTS ===
AUDIO_DIR="/root/audio-cpp"
if [ -d "$AUDIO_DIR/webui" ]; then
    echo "[START] 恢复 TTS (端口 7899)..."
    cd "$AUDIO_DIR/webui"
    python webui.py --listen 0.0.0.0 --port 7899 &
    echo "[OK] TTS 已启动 (端口 7899)"
else
    echo "[WARN] 找不到 audio-cpp 目录"
    echo "[INFO] 请手动启动 TTS"
fi

# === 6. 等待服务就绪 ===
sleep 3

# === 7. 验证 ===
echo ""
echo "=== 服务状态 ==="

# 骏马
curl -s http://localhost:6006/health > /dev/null 2>&1 && echo "[OK] 骏马 (6006)" || echo "[--] 骏马 (6006) 离线"

# 巡检者
curl -s http://localhost:6008/patrol/status > /dev/null 2>&1 && echo "[OK] 巡检者 (6008)" || echo "[--] 巡检者 (6008) 离线"

# TTS
curl -s http://localhost:7899/tts > /dev/null 2>&1 && echo "[OK] TTS (7899)" || echo "[--] TTS (7899) 离线"

echo ""
echo "=========================================="
echo "  常规模式已恢复"
echo "=========================================="
