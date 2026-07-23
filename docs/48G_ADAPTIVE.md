# 48GB 自适应多模态工作流

## 背景

赛博猴运行在 **NVIDIA L40 (48GB VRAM)** 服务器上，需要同时承载：
- 骏马（Qwen3.6-27B Q4_K_M 推理）~22GB
- 巡检者（11 门类巡逻）~20GB  
- ComfyUI（SDXL / FLUX 生图）~8-14GB
- 语音合成（已废弃）（audio.cpp）~1GB

**48GB 不够同时运行全部。** 因此设计自适应工作流。

---

## 显存精算

| 组件 | 常规模式 | 多模态模式 | 说明 |
|:-----|:---------|:-----------|:------|
| 骏马（Qwen3.6） | **~22 GB** | **~22 GB** | 模型 17G + KV cache 131k ctx 5G |
| 巡检者（Patrol） | **~20 GB** | **暂停 0 GB** | 模型 17G + cache 3G |
| ComfyUI（SDXL） | 0 GB | **~8 GB** | 仅生图时加载 |
| ComfyUI（FLUX fp8） | 0 GB | **~14 GB** | 更高质量 |
 **暂停 0 GB** | 实时语音 |
| **合计** | **~43 GB ✅** | **~30-36 GB ✅** | |

---

## 两种工作模式

### 模式 A：常规模式（日常工作）

```
骏马(22G) + 巡检者(20G) ```

- 骏马常驻提供 Qwen 推理
- 巡检者后台巡逻 11 个门类
- **不加载 ComfyUI**

### 模式 B：多模态模式（生图/视频）

```
骏马(22G) + ComfyUI(8-14G) + API 替代巡检 = 30-36G ✅
```

触发条件：
- 用户请求"画图""配图""图片"等
- 代码中调用 ToolImage 或 ComfyUI API
- Agent 决策需要视觉输出

动作：
1. **暂停巡检者**（kill 6008 进程）
3. **记录恢复点**（保存巡检者/任务状态）
4. **巡检任务临时挂载到 DeepSeek Flash API**（共享赛博猴 Key）
5. **启动 ComfyUI**（加载 SDXL 或 FLUX 模型）
6. 执行多模态任务
7. 完成后 ComfyUI 卸载模型
8. **恢复巡检者**（启动 6008）

---

## 切换脚本

### 切换到多模态模式

```bash
#!/bin/bash
# start-multimodal.sh

echo "=== 切换到多模态模式 ==="

# 1. 保存巡检者状态
curl -s http://localhost:6008/patrol/status > /tmp/patrol_snapshot.json 2>/dev/null
echo "  巡检者状态已保存"

# 2. 暂停巡检者
PIDS=$(pgrep -f "llama-server.*6008" 2>/dev/null)
if [ -n "$PIDS" ]; then
  kill $PIDS
  echo "  巡检者已暂停"
fi

fi

# 4. 设置巡检降级模式
export PATROL_FALLBACK="deepseek-flash"

# 5. 启动 ComfyUI
cd /root/ComfyUI
python main.py --listen 0.0.0.0 --port 8188 --force-fp16 &
echo "  ComfyUI 启动中 (端口 8188)"

echo "=== 多模态模式已激活 ==="
```

### 恢复到常规模式

```bash
#!/bin/bash
# restore-normal.sh

echo "=== 恢复常规模式 ==="

# 1. 卸载 ComfyUI 模型
curl -s http://localhost:8188/api/unload_all_models -X POST > /dev/null 2>&1
echo "  ComfyUI 模型已卸载"

# 2. 停止 ComfyUI
PIDS_COM=$(pgrep -f "ComfyUI/main.py" 2>/dev/null)
if [ -n "$PIDS_COM" ]; then
  kill $PIDS_COM
  echo "  ComfyUI 已停止"
fi

# 3. 取消降级模式
unset PATROL_FALLBACK

# 4. 恢复巡检者
cd /root/work/cyber-monkey
python -m harness_core agent horse --port 6006 &
echo "  巡检者启动中 (端口 6008)"

cd /root/audio-cpp/webui
python webui.py --listen 0.0.0.0 --port 7899 &

sleep 3
echo "=== 常规模式已恢复 ==="
```

---

## 故障恢复（OOM 安全）

如果显存爆了（OOM），自动进入安全模式：

```yaml
safety:
  oom_detection: true
  oom_action: "emergency_release"   # 释放非关键组件
  emergency_keep: ["horse"]         # 只保留骏马
  auto_recover: true                # 3分钟后尝试恢复
```

---

## 状态机

```
                    ┌─────────────┐
                    │   常规模式   │
                    │ Horse+Patrol │
                    │                        └──────┬──────┘
                           │ 用户请求多模态
                           ▼
                    ┌─────────────┐
                    │  切换中... │
                    │ 暂停 Patrol │
                    │ 保存快照    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  多模态模式  │
                    │ Horse+Comfy  │
                    │ API 替代其他 │
                    └──────┬──────┘
                           │ 任务完成
                           ▼
                    ┌─────────────┐
                    │  恢复中... │
                    │ Comfy 卸载  │
                    │ 恢复 Patrol │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   常规模式   │
                    └─────────────┘
```

---

## 原理说明

### 为什么这样设计？

48GB L40 是赛博猴的硬件基线。这个基线决定了：
- **不能同时跑所有组件** → 需要模式切换
- **骏马必须常驻** → 它是核心推理引擎，重启模型加载耗时 ~30 秒
- **巡检者可重启** → 非实时任务，启动快（~5 秒）
- **ComfyUI 按需加载** → 生图任务结束后立即释放

### 原则

1. **优先保骏马** — 核心推理不可中断
2. **巡检者可用 API 替代** — DeepSeek Flash 作为降级链路
3. **ComfyUI 用完即释放** — 不常驻模型
5. **状态持久化** — 切换前保存，切换后恢复，不丢上下文

---

## 赛博猴 vs 弼马温

| 维度 | 赛博猴（48GB L40） | 弼马温（无本地 GPU） |
|:-----|:-------------------|:---------------------|
 API 调用（DeepSeek / Azure） |
| ComfyUI | 本地部署 | 无，或配置远程 ComfyUI |
| 巡检者 | 本地常驻 | 云端 API |
| 自适应策略 | 显存感知模式切换 | 无此需求 |
