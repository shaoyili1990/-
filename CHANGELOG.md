# 更新日志

## v0.3.1 — TTS 语音底座 & ComfyUI 多模态 & 48GB 自适应工作流 (2026-07-22)

### ✨ 新功能

#### TTS 语音合成（audio.cpp-webui）
- 支持中/英/日/韩四国语种实时 TTS
- 赛博猴：本地模型推理 → 直接生成语音输出
- 弼马温：提供云端 API 替代方案（DeepSeek/Azure TTS）
- TTS 配置文档：`docs/TTS_DEPLOY.md`

#### ComfyUI 多模态底座
- SDXL / FLUX fp8 文生图引擎
- 与骏马推理引擎无缝集成（ToolImage 调用）
- ComfyUI 蓝图为多模态场景预置
- 部署文档：`docs/COMFYUI_DEPLOY.md`

#### 48GB 自适应工作流
- 两种模式智能切换：常规(骏马+巡检+TTS) ↔ 多模态(骏马+ComfyUI)
- 巡检任务在切换时降级到 DeepSeek Flash API（共享赛博猴 Key）
- OOM 安全机制：显存爆满时自动释放非核心组件
- 状态保存/恢复：切换前保存巡检者状态，恢复后续接
- 一键切换脚本：`installer/start-multimodal.sh` / `restore-normal.sh`
- 完整原理文档：`docs/48G_ADAPTIVE.md`

### ♻️ 改进

- `docs/` 新增完整文档体系（TTS/ComfyUI/工作流/部署）
- 赛博意识流路线图更新：P4 多模态基础完成
- 安装脚本增加显存检查和自动适配逻辑

### 📦 文件变更

| 文件 | 说明 |
|:-----|:------|
| `docs/TTS_DEPLOY.md` | 🆕 TTS 部署指南（赛博猴完整 / 弼马温 API） |
| `docs/COMFYUI_DEPLOY.md` | 🆕 ComfyUI 部署指南 |
| `docs/48G_ADAPTIVE.md` | 🆕 48GB 自适应工作流原理与切换逻辑 |
| `installer/start-multimodal.sh` | 🆕 一键切换多模态模式 |
| `installer/restore-normal.sh` | 🆕 一键恢复常规模式 |
| `README.md` | 📝 更新 v0.3.1 版本信息、产品线规划、路线图 |
| `CHANGELOG.md` | 🆕 本文件 |

---

## v0.3.0 — 指纹运行时挂载 & 多路径推理 & 第5验证链 (2026-07-20)

| 变更 | 说明 |
|:-----|:------|
| **P1: 指纹运行时修复** | subchain_weights 从 0→**1,291 条**，10个领域指纹完整挂载到引擎库 |
| **P2: 双路径收敛推理** | 审核不通过时自动运行两条路径（修复式重试 + 从零新鲜推理） |
| **P3: 第5验证链「禁止数值解」** | 检测数值评分/二元标签/模板化填空/绝对化结论 |
| **P4: 冷监督开关** | `/aileran on/off` 冻结后台自治循环 |
| **P5: 任务输出引擎** | `workspace/output/T001/v1/{问题,推导,结果}.md` |
| **P6: 迭代工具** | `task_output_iterate` 读 v1 → 包反馈 → 构建新问题 → 存 v2 |
| **P7: 项目模板** | 新增"项目"输出模板: 01_思路→02_流程→03_执行方法→04_结果 |
| **MCP 13工具** | 完整注册巡逻/Skill/图谱/系统/输出5类工具 |

## v0.2.0 — 冷监督 & 任务输出引擎 (2026-07-19)

- 冷监督模式（Aileran）：后台自治循环开关
- workspace/output 输出引擎：文件系统 + 多维表格双写
- MCP 输出工具：workspace_init / task_output_save / task_output_list / task_output_read

## v0.1.0 — 弼马温品牌发布 (2026-07-18)

- 品牌升级：Hermes → Monkey Harness Agent (弼马温)
- 136子链 + 4验证链 + 11领域指纹
- MCP 服务器 + AgentReach 多源巡逻
- 跨平台部署 + GitHub Actions CI/CD
