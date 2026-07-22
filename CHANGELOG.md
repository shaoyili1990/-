# 更新日志

## v0.3.1 — 天道系统 (2026-07-23)

### ✨ 新功能

#### 天道系统（叙事逻辑与人物演化引擎）
- 天道引擎：小说人物Y值驱动的情绪/欲望演化系统，完整公式01-10链
- `tiandao_bridge.py` — 状态机↔天道联动接口：trigger_event / get_character_state / get_event_roles / update_after_god_intervention
- `y_engine.py` — Y值计算引擎：基础设定→情绪波动→击穿阈值→补偿机制→回弹效应→欲望演化→多人物联动
- `harness.py` — 马的双通道Harness：子链通道（逻辑/结构）+ 天道通道（情绪/心理）整合层，按任务生成专属临时脚本
- `rnd_tiandao.db` — 天道专用库：5张P0表（tiandao_novels / tiandao_characters / tiandao_states / tiandao_events / tiandao_event_roles）

#### 仓库结构迭代
- 天道模块纳入 `harness_core/tiandao/` 包，imports 统一为相对路径
- 测试文件迁入 `tests/` 统一管理
- 移除所有 TTS 相关文档和配置（TTS 已废弃）

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
