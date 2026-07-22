# ComfyUI 多模态部署指南

## 概述

ComfyUI 是赛博猴的多模态底座，提供文生图、图生图、图编辑等功能。
通过自适应工作流与骏马推理引擎协同工作。

> **ComfyUI 部署本身不占用显存（VRAM=0）。**
> 只有加载模型执行生图时才消耗显存。

## 部署

```bash
cd /root

# 克隆
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# 安装依赖
pip install -r requirements.txt

# 下载模型（SDXL 基线）
# 将 SDXL 模型放到 models/checkpoints/
# 可选：FLUX.1-dev fp8 用于更高质量

# 启动服务
python main.py --listen 0.0.0.0 --port 8188 --force-fp16
```

## 模型配置

### 推荐模型栈

| 用途 | 模型 | 显存 | 速度 |
|:-----|:------|:-----|:------|
| 快速出图 | SDXL | ~8 GB | 3-5 秒/图 |
| 高质量 | FLUX.1-dev fp8 | ~14 GB | 10-15 秒/图 |
| 图编辑 | SDXL + ControlNet | ~10 GB | 5-8 秒/图 |
| 视频 | AnimateDiff | ~12 GB | 慢 |

### 自动适配

赛博猴根据当前显存自动选择模型：

```yaml
comfyui:
  auto_model_selection: true
  models:
    fast: { name: sdxl, vram: 8, priority: 10 }
    quality: { name: flux-fp8, vram: 14, priority: 5 }
  
  # 自动选择逻辑
  selection:
    - if_free_gt: 36   # 剩余 > 36GB → 用 FLUX
      model: quality
    - else:            # 默认 SDXL
      model: fast
```

## 与 Agent 集成

### API 调用

```python
# harness_core/providers/comfyui.py
class ComfyUIProvider:
    def __init__(self, endpoint="http://localhost:8188"):
        self.endpoint = endpoint
    
    async def text_to_image(self, prompt: str, model="sdxl"):
        """文生图"""
        # 调用 ComfyUI API
        workflow = self._build_workflow(prompt, model)
        result = await self._execute(workflow)
        return result.images[0]
    
    async def image_to_image(self, image, prompt: str):
        """图生图"""
        pass
    
    async def unload_models(self):
        """释放显存"""
        await self._api_post("/api/unload_all_models")
```

### 自适应调用

```python
class AdaptiveMultimodal:
    """
    48GB 自适应多模态管理器
    自动在常规模式与多模态模式间切换
    """
    
    async def generate_image(self, prompt: str):
        if self._is_multimodal_needed(prompt):
            # 1. 暂停巡检者 + TTS
            await self.suspend_patrol()
            await self.suspend_tts()
            self.patrol_fallback = "deepseek-flash"
            
            # 2. 确保 ComfyUI 已启动
            await self.ensure_comfyui_running()
            
            # 3. 执行生图
            result = await self.comfyui.text_to_image(prompt)
            
            # 4. 恢复
            await self.comfyui.unload_models()
            await self.resume_patrol()
            await self.resume_tts()
            
            return result
```

## 赛博猴 ComfyUI Workflow Blueprints

赛博猴预置了 ComfyUI 工作流蓝图，用于常见多模态场景：

```
ComfyUI/blueprints/
├── text_to_image.json        # 文生图（SDXL）
├── text_to_image_flux.json   # 文生图（FLUX fp8）
├── image_edit.json           # 图编辑
├── image_inpainting.json     # 图修补
└── image_to_layers.json      # 图分层
```

## 验证

```bash
# 测试 ComfyUI 可用性
curl -s http://localhost:8188/api/object_info | python3 -c "import sys,json; d=json.load(sys.stdin); print('ComfyUI OK:', len(d), 'nodes')"

# 测试简单生图
curl -s -X POST http://localhost:8188/api/prompt \
  -d '{"prompt": {"3": {"class_type": "KSampler", ...}}}'
```
