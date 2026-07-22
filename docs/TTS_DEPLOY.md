# TTS 语音合成部署指南

## 概述

基于 [audio.cpp-webui](https://github.com/kigner/audio.cpp-webui) 构建的轻量 TTS 底座，提供低延迟、高质量的中/英/日/韩语音合成能力。

## 架构

```
用户输入 → Agent (Qwen3.6) → TTS WebUI (audio.cpp) → 音频输出
                ↓
        DeepSeek Flash (fallback)
```

- **赛博猴**：本地 Qwen3.6 推理 → TTS 生成本地音频 ✅
- **弼马温**：无本地模型 → TTS 需单独部署或调用云端 TTS API

## 支持的语种

| 语种 | 质量 | 说明 |
|:-----|:-----|:------|
| 🇨🇳 中文 | 最佳 | CosyVoice / ChatTTS 原生优化 |
| 🇬🇧 英文 | 优秀 | 标准 TTS 支持 |
| 🇯🇵 日文 | 良好 | GPT-SoVITS 等模型覆盖 |
| 🇰🇷 韩文 | 良好 | 部分模型支持 |
| 其他 | 需自行配置 | 用户可选装对应模型 |

## 赛博猴部署

### 快速安装

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 下载模型
python webui/download_models.py

# 3. 启动服务
python webui/webui.py --listen 0.0.0.0 --port 7899
```

### 自适应工作流

赛博猴的 TTS 遵循 48GB 自适应策略（详见 `48G_ADAPTIVE.md`）：

- **常规模式**：TTS 常驻（~1GB 显存），与骏马推理共存
- **多模态模式**：TTS 暂停（释放显存给 ComfyUI），用 DeepSeek Flash API 替代
- **恢复**：ComfyUI 完成后自动重启本地 TTS 服务

## 弼马温部署

弼马温默认无本地 GPU，TTS 建议以下方案：

### 方案 A：云端 TTS API（推荐）

```yaml
# config.yaml
tts:
  provider: deepseek  # 或 azure / openai
  model: tts-1
  voice: alloy
```

无需本地部署，直接用 API 调用。

### 方案 B：自建 TTS 服务

如果弼马温运行在有 GPU 的服务器上：

```bash
# 参照赛博猴安装步骤
# 将 TTS 部署为独立微服务
python webui/webui.py --listen 0.0.0.0 --port 7899 --share
```

然后在 config.yaml 中指向该服务：

```yaml
tts:
  provider: self-hosted
  endpoint: http://localhost:7899
```

## TTS 配置（赛博猴完整版）

### config.yaml

```yaml
tts:
  enabled: true
  provider: local
  engine: audio-cpp
  port: 7899
  
  # 语种配置
  languages:
    zh: { default: true, model: cosyvoice }
    en: { model: default }
    ja: { model: gpt-sovits }
    ko: { model: default }
  
  # 自适应策略
  adaptive:
    suspend_on_multimodal: true     # 多模态时暂停
    fallback_provider: deepseek     # 降级到 API
    resume_after_multimodal: true   # 完成后恢复
```

### 环境变量

| 变量 | 说明 | 默认 |
|:-----|:------|:------|
| `TTS_PORT` | TTS 服务端口 | 7899 |
| `TTS_MODEL` | 默认 TTS 模型 | cosyvoice |
| `TTS_LANGUAGE` | 默认语种 | zh |
| `TTS_FALLBACK_API` | 降级 API key | deepseek key |

## 验证

```bash
# 测试 TTS
curl -X POST http://localhost:7899/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "你好，我是赛博猴", "language": "zh"}'

# 应返回 WAV 音频
```
