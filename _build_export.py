"""构建 Monkey Harness Agent (弼马温) 导出包"""
import os, json, shutil

TARGET = r'D:\\跑马\\留档'
PROJECT = r'D:\\爱马仕工作区\\monkey-harness-agent'


def read_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return ''


def main():
    # ========== 1. 获取文件列表 ==========
    subchain_files = sorted(os.listdir(os.path.join(PROJECT, 'subchains'))) if os.path.isdir(os.path.join(PROJECT, 'subchains')) else []
    validation_files = sorted(os.listdir(os.path.join(PROJECT, 'validations'))) if os.path.isdir(os.path.join(PROJECT, 'validations')) else []
    fp_files = sorted(os.listdir(os.path.join(PROJECT, 'fingerprints'))) if os.path.isdir(os.path.join(PROJECT, 'fingerprints')) else []

    fingerprint_names = [f for f in fp_files if f.endswith('.json') and not f.startswith('_')]
    validation_names = [f for f in validation_files if f.endswith('.md') and not f.startswith('_')]

    # ========== 2. 构建导出JSON ==========
    export = {
        'meta': {
            'name': 'Monkey Harness Agent (弼马温)',
            'version': '0.1.0',
            'description': '通用可移植AI Agent系统 - 基于猴驭马(Monkey-Horse)架构',
            'type': 'AI Agent Framework',
            'target_platform': 'PromptX / Any LLM',
            'architecture': '猴驭马(Monkey-Horse) 四角色+质检官协奏',
            'philosophy': '解析解(非数值驱动), 所有数据从多维表格(SQLite)读取, IF-THEN规则无评分',
        },
        'roles': {
            '灵猴(Monkey)': {
                'id': 'monkey',
                'responsibility': '路由与审核官',
                'core_tasks': [
                    '接收需求 → 指纹匹配 → 路由决策',
                    '领域识别(domain_tags集合匹配)',
                    '思考深度判定(IF-THEN: snapshot/standard/deep)',
                    '单链/双链决策',
                    '四级审核(step/unit/phase/whole)',
                    '猴马谈判(审核不通过时发起复审)',
                ],
                'provider': 'monkey (独立API配置,可混搭)',
                'reads': ['fingerprints表', 'subchain_weights表', 'rnd_state_def表'],
                'writes': ['rnd_tasks', 'rnd_reviews', 'cognition_chats'],
            },
            '骏马(Horse)': {
                'id': 'horse',
                'responsibility': '推理与执行者',
                'core_tasks': [
                    '接收路由指令 → 4脑全参与 → 调度子链',
                    '4步执行: 01思路→02流程→03执行方法→04结果',
                    '单链(仅通用指纹) / 双链(通用+领域垂直)',
                    '子链weight作为LLM描述性参考(不排序)',
                    '验证标准内嵌prompt(预防性约束)',
                    '重试时读取retry_context精准修复',
                ],
                'provider': 'horse (独立API配置,可混搭)',
                'brains': ['逻辑链(32子链)', '因果链(34子链)', '思维链(37子链)', '推导法(33子链)'],
                'reads': ['subchain_weights表', 'fingerprints表', '子链md文件'],
                'writes': ['rnd_steps', 'cognition_chats', 'memories'],
            },
            '司库(Keeper)': {
                'id': 'keeper',
                'responsibility': '宪法与流程守护者',
                'core_tasks': [
                    '驱动9状态状态机',
                    '版本控制与迭代',
                    '宪法8条执行',
                    '任务生命周期管理',
                ],
                'stores': ['rnd_engine.db (状态/任务/步骤/审核)', 'bimawen.db (认知/记忆/指纹)'],
                'states': ['待构思', '构思完成待执行', '待执行', '执行完成待验证', '验证中', '验证通过', '验证未通过', '待复审', '待复查'],
            },
            '书童(Scribe)': {
                'id': 'scribe',
                'responsibility': '认知与记忆管家',
                'core_tasks': [
                    '10认知库管理',
                    '指纹检索',
                    '伪注意力机制',
                    '对话历史记录',
                ],
                'libraries': [
                    'memories(长期记忆)', 'fingerprints(领域指纹)', 'sessions(会话)',
                    'task_flow(任务流)', 'output_segments(输出片段)', 'dialogue_history(对话历史)',
                    'cognition_chats(认知聊天)', 'cognition_profiles(认知画像)',
                    'subchain_weights(子链权重)', 'material_knowledge(知识库)',
                ],
            },
            '质检官(Verifier)': {
                'id': 'verifier',
                'responsibility': '验证审查者',
                'core_tasks': [
                    '使用4条验证链审查骏马产出',
                    '判定: 通过/部分通过/不通过/无法验证',
                    '提取失败项清单+修正建议',
                    '不通过时触发猴马谈判修复',
                ],
                'validation_chains': [
                    {'name': '反证逻辑链', 'target': '逻辑关系反证', 'method': 'A→B, 反查B→A'},
                    {'name': '反AI逻辑链', 'target': 'AI式逻辑错误', 'method': '机械逻辑/脱离材料/偷换概念'},
                    {'name': '反证思维链', 'target': '因果关系', 'method': '倒果为因/伪相关/伪推理'},
                    {'name': '逆AI思维链', 'target': '思维过程', 'method': '机械推理/空泛套壳/无视主客观因素'},
                ],
                'provider': '复用horse的provider配置',
                'philosophy': '验证合理性(不是正确性)',
            },
        },
        'organization': {
            'structure': '五角色协奏',
            'flow': '灵猴路由 → 骏马执行 → 质检官验证 → 司库状态 → 书童记忆',
            'decision_flow': 'Monkey.route() → Horse.execute() → Verifier.verify() → Monkey.review() → Keeper.transition() → Scribe.record()',
            'retry_flow': 'review.fail → Monkey.negotiate() → route[retry_context] → Horse.execute(带修复指引) → review again',
        },
        'fingerprints': {
            'total': len(fingerprint_names),
            'generic': 'thinker_unified_fingerprint.json (通用个人思维偏好)',
            'domains': [
                'TECH(技术)', 'ACADEMIC(学术)', 'BUSINESS(商业)', 'FINANCE(金融)',
                'PRODUCT(产品)', 'POLICY(政策)', 'AUTHOR(创作)', 'CRITIQUE(评论)',
                'CHAOS(混沌)', 'CODE(代码)',
            ],
            'storage': 'fingerprints表(domain_id, name, data=完整JSON)',
            'usage': '通用指纹必加载 + 领域垂直指纹按需加载',
        },
        'subchains': {
            'total': 136,
            'by_brain': {'逻辑链': 32, '因果链': 34, '思维链': 37, '推导法': 33},
            'tier_system': {
                'T1(快照)': '表层匹配,最常用',
                'T1+T2(标准)': '常规分析任务',
                'T1+T2+T3(深度)': '复杂任务',
                'T4/T5(潜水)': '常驻待命,按需加载',
            },
            'storage': 'subchain_weights表(chain_type=domain:brain, subchain_name, weight, tier)',
        },
        'validation_module': {
            'chains': 4,
            'template_files': validation_names,
            'judgments': ['pass(通过)', 'partial(部分通过)', 'fail(不通过)', 'cannot_verify(无法验证)'],
            'integration': 'Horse prompt含预防性标准 → 产出后Verifier验证 → review汇总',
        },
        'state_machine': {
            'states': 9,
            'state_list': [
                {'order': i+1, 'name': n} for i, n in enumerate([
                    '待构思', '构思完成待执行', '待执行', '执行完成待验证',
                    '验证中', '验证通过', '验证未通过', '待复审', '待复查',
                ])
            ],
            'transitions': {
                '待构思': ['构思完成待执行'],
                '构思完成待执行': ['待执行'],
                '待执行': ['执行完成待验证'],
                '执行完成待验证': ['验证中'],
                '验证中': ['验证通过', '验证未通过'],
                '验证通过': ['构思完成待执行', '待执行'],
                '验证未通过': ['待执行', '待复审'],
                '待复审': ['待执行', '验证通过', '待复查'],
                '待复查': ['待执行', '验证通过'],
            },
        },
        'review_system': {
            'levels': ['step(单步)', 'unit(01-04完整性)', 'phase(跨阶段)', 'whole(终审)'],
            'method': 'Verifier.verify() → 4验证链 → 汇总判定',
            'retry': '不通过 → Negotiate → 带修复指引重执行 → 终审(whole)',
        },
        'constitution': {
            'articles': 8,
            'list': [
                '解析解原则: 可能性/倾向性/合理性, 禁止二元判断和数值评分',
                '136子链原则: 所有推理基于136条子链模板(4脑)',
                '多维表格=本体: SQLite表存储一切状态,表即Agent的大脑',
                '一表一人: 每个用户绝对私有,换表即换人',
                '版本不覆盖: 旧版本永不删除,可精确回滚',
                '迭代传上下文: 每次迭代传递完整上下文',
                '对齐甲方: 以用户需求为最终标准',
                '孤证不立: 单一证据不能作为结论依据',
            ],
        },
        'config': {
            'format': 'config.yaml (YAML)',
            'providers': ['openai', 'anthropic', 'deepseek', 'ollama', 'openrouter', 'vllm'],
            'mixed_mode': 'Monkey和Horse可用不同厂商(如Monkey=OpenAI, Horse=DeepSeek)',
            'paths_auto_resolve': '空路径自动映射到项目目录',
        },
    }

    export_path = os.path.join(TARGET, 'bimawen_export.json')
    with open(export_path, 'w', encoding='utf-8') as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    print(f'[OK] Export JSON: {export_path}')
    print(f'     Size: {os.path.getsize(export_path):,} bytes')

    # ========== 3. 创建PromptX角色定义(DPML/V2格式) ==========
    roles_dpml = []
    for role_id, role_name, role_desc, role_resp in [
        ('monkey', '灵猴', '路由与审核官', '接收需求,指纹匹配,路由决策,四级审核,猴马谈判'),
        ('horse', '骏马', '推理与执行者', '4脑全参与,调度136子链,4步执行,单链/双链推理'),
        ('keeper', '司库', '宪法与流程守护者', '驱动9状态状态机,版本控制,宪法执行,任务生命周期'),
        ('scribe', '书童', '认知与记忆管家', '10认知库管理,指纹检索,伪注意力机制,对话历史'),
        ('verifier', '质检官', '验证审查者', '4条验证链审查,判定通过/不通过,提取失败项和修正建议'),
    ]:
        roles_dpml.append(f'''## Role: {role_name}

### 身份
{role_desc}

### 职责
{role_resp}

### 核心原则
- 解析解思维: 使用可能性/倾向性/合理性判断,禁止二元评分
- 证据优先: 所有主张必须有依据支撑
- 孤证不立: 单一证据不能作为结论依据

### 协作关系
- 灵猴路由 → 骏马执行 → 质检官验证 → 司库状态 → 书童记忆
- 验证不通过: 质检官→灵猴(谈判)→骏马(修复重执行)→质检官(复审)''')

    roles_path = os.path.join(TARGET, 'promptx_roles.md')
    with open(roles_path, 'w', encoding='utf-8') as f:
        f.write('# Monkey Harness Agent (弼马温) - PromptX Role Definitions\n\n')
        f.write('\n---\n'.join(roles_dpml))
    print(f'[OK] PromptX Roles: {roles_path}')

    # ========== 4. 创建部署指南 ==========
    deploy_md = '''# Monkey Harness Agent (弼马温) - PromptX 部署指南

## 一、导入方式

### 方式1: 直接激活角色
```
/monkey   - 激活灵猴角色
/horse    - 激活骏马角色
/keeper   - 激活司库角色
/scribe   - 激活书童角色
/verifier - 激活质检官角色
```

### 方式2: 使用SKILL.md作为System Prompt
将 SKILL.md 的内容作为System Prompt直接粘贴到任意AI对话中,
当前AI会自动扮演全部5个角色。

### 方式3: PromptX V2角色注册
``promptx
action("born", {{
  role: "monkey",
  name: "灵猴",
  source: "Feature: 灵猴...
}}
``

## 二、文件结构
```
monkey-harness-agent/
├── hermes_universal/          # Python源码
│   ├── core/                  # 五角色实现
│   ├── engine/                # 引擎+状态机+子链调度
│   ├── providers/             # AI厂商适配器
│   ├── messages/              # 消息内容模型
│   ├── desktop/               # Web UI
│   └── utils/                 # 工具
├── fingerprints/              # 11个指纹JSON
├── subchains/                 # 136条子链模板
├── validations/               # 4条验证链模板
├── store/                     # SQLite数据库
│   ├── rnd_engine.db          # 状态/任务/步骤/审核
│   └── bimawen.db              # 认知/记忆/指纹
├── config.yaml                # 配置文件
├── SKILL.md                   # 通用提示词技能
├── pyproject.toml             # Python包定义
└── Dockerfile                 # Docker部署
```

## 三、快速启动
```bash
# Python安装
pip install monkey-harness-agent

# 或直接运行
python -m hermes_universal

# CLI模式
monkey-harness run "你的问题"
monkey-harness chat
monkey-harness desktop
```

## 四、API配置 (config.yaml)
支持混搭模式:
- Monkey用OpenAI, Horse用Claude
- Monkey用DeepSeek, Horse用Ollama(本地)
- 全用Ollama(纯本地)
- 环境变量注入: OPENAI_API_KEY, DEEPSEEK_API_KEY等

## 五、核心验证理念
> 验证不是追求"多写分析", 而是判断合理性(不是正确性):
> - A推B, 反查B推A
> - 先看主观因素, 再看外部因素
> - 内外皆无 → 孤证失效 → 原结论不成立
> - 这是AI最常犯的错误: 想当然
'''
    deploy_path = os.path.join(TARGET, 'DEPLOY_GUIDE.md')
    with open(deploy_path, 'w', encoding='utf-8') as f:
        f.write(deploy_md)
    print(f'[OK] Deploy Guide: {deploy_path}')

    # ========== 5. 文件清单 ==========
    manifest = []
    for root, dirs, files in os.walk(TARGET):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
        rel = os.path.relpath(root, TARGET)
        if rel == '.':
            continue
        for f in files:
            if f.endswith('.pyc'):
                continue
            fpath = os.path.join(root, f)
            manifest.append({
                'path': os.path.join(rel, f),
                'size': os.path.getsize(fpath),
            })

    manifest.sort(key=lambda x: x['path'])
    manifest_path = os.path.join(TARGET, 'file_manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f'[OK] File Manifest: {manifest_path} ({len(manifest)} files)')

    total_size = sum(m['size'] for m in manifest)
    print(f'\n=== Export Complete ===')
    print(f'Target: {TARGET}')
    print(f'Files:  {len(manifest)}')
    print(f'Size:   {total_size:,} bytes ({total_size/1024:.1f} KB)')


if __name__ == '__main__':
    main()
