"""
Workspace 输出引擎 — 任务输出的文件系统 + 多维表格双写

当Agent完成任务后,自动:
1. 确定输出模板(根据任务类型从 output_templates 表获取)
2. 创建 workspace/output/T<任务号>/v<版本>/ 目录
3. 写入 .md 文件
4. 同步写入多维表格 task_outputs 表

迭代机制:
  v1: 初版输出
  v2: 基于新问题反馈 + 旧推理结果 → 修订版
  v3...: 持续迭代

用户可见: workspace/output/ 下的 markdown 文件
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Optional


def init_workspace(workspace_root: str = None) -> str:
    """初始化 workspace/output 目录结构"""
    if workspace_root is None:
        workspace_root = os.path.expanduser("~/workspace")
    output_dir = Path(workspace_root) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    # 生成结构说明文件
    readme = output_dir / "_README.md"
    if not readme.exists():
        readme.write_text(
            "# 🐒 弼马温 Agent — 任务输出目录\n\n"
            "## 目录结构\n\n"
            "```\n"
            "output/\n"
            "  T001/              ← 任务编号\n"
            "    v1/              ← 版本号(初版)\n"
            "      01_问题.md     ← 问题/需求/构思\n"
            "      02_推理过程.md  ← 推理/推导步骤\n"
            "      03_输出结果.md  ← 最终输出\n"
            "    v2/              ← 迭代版\n"
            "      01_问题.md     ← 新问题(含反馈)\n"
            "      02_推理过程.md  ← 基于新问题重新推理\n"
            "      03_输出结果.md  ← 修订版输出\n"
            "  T002/\n"
            "    ...\n"
            "```\n\n"
            "## 怎么看\n\n"
            "每个任务文件夹的 `03_输出结果.md` 就是你要看的东西。\n"
            "想看思考过程就看 `02_推理过程.md`。\n"
            "每次迭代都是独立版本，方便对比。\n\n"
            "> 提示: 在 Obsidian 里打开这个目录，可以直接当知识库用\n",
            encoding="utf-8"
        )
    return str(output_dir)


def get_task_dir(output_root: str, task_id: str) -> Path:
    """获取任务目录: output/T001/"""
    return Path(output_root) / task_id


def get_version_dir(output_root: str, task_id: str, version: str = "v1") -> Path:
    """获取版本目录: output/T001/v1/"""
    return get_task_dir(output_root, task_id) / version


def ensure_version_dir(output_root: str, task_id: str, version: str = "v1") -> Path:
    """确保版本目录存在并返回"""
    vdir = get_version_dir(output_root, task_id, version)
    vdir.mkdir(parents=True, exist_ok=True)
    return vdir


def save_output_to_files(
    output_root: str,
    task_id: str,
    version: str,
    files: Dict[str, str],
    iteration_note: str = "",
) -> List[str]:
    """保存输出到文件系统
    
    Args:
        output_root: workspace/output 路径
        task_id: 任务ID (如 T001)
        version: 版本号 (如 v1, v2)
        files: {文件名: 内容} 如 {"01_问题": "xxx", "02_推理过程": "yyy", ...}
        iteration_note: 迭代说明(可选)
    
    Returns:
        创建的文件路径列表
    """
    vdir = ensure_version_dir(output_root, task_id, version)
    created = []
    
    for fname, content in files.items():
        # 确保文件名有 .md 后缀
        if not fname.endswith(".md"):
            fname = fname + ".md"
        fpath = vdir / fname
        fpath.write_text(content.strip(), encoding="utf-8")
        created.append(str(fpath))
    
    # 如果有迭代说明,写一个 _迭代说明.md
    if iteration_note:
        note_path = vdir / "_迭代说明.md"
        note_path.write_text(iteration_note.strip() + "\n", encoding="utf-8")
        created.append(str(note_path))
    
    return created


def build_iteration_input(prev_files: Dict[str, str], feedback: str,
                          template: str = "创作") -> Dict[str, str]:
    """构建迭代输入: 将反馈+旧内容作为新问题的上下文
    
    支持任意模板(三文件制、四文件制等)。
    关键是"上一版的全部内容 + 反馈 → 新问题"。
    
    Args:
        prev_files: 上一版本的输出文件 {文件名: 内容}
        feedback: 用户/甲方修改意见
        template: 输出模板类型名(用于描述)
    
    Returns:
        新版本的 01_问题 或 01_思路 内容(含完整上下文)
    """
    # 找到 "第一个文件" 的 key: 01_问题 或 01_思路 或 01_需求 等
    first_key = None
    ordered = sorted(prev_files.keys())
    if ordered:
        first_key = ordered[0]  # 一般是 01_xx
    
    # 构建完整的上下文,按文件顺序排列
    context_parts = []
    for fname in ordered:
        content = prev_files[fname]
        label = fname.replace("_", "」").replace("01", "❶").replace("02", "❷")\
                     .replace("03", "❸").replace("04", "❹")
        context_parts.append(f"━━━ {label} ━━━\n{content}")
    
    prev_context = "\n\n".join(context_parts)
    next_key = first_key or "01_问题"
    
    new_problem = (
        f"【迭代输入 — 基于上一版修订 (模板: {template})】\n\n"
        f"━━━ 用户/甲方反馈 ━━━\n{feedback}\n\n"
        f"━━━ 上一版所有文件(参考) ━━━\n{prev_context}\n\n"
        f"━━━ 修订要求 ━━━\n"
        f"基于以上反馈,对上一版输出进行修订。\n"
        f"保持合理的部分,修改被指出的问题,形成新的版本。\n"
        f"输出新的完整结果,不要只说修改了什么。"
    )
    return {next_key: new_problem}


def read_version_files(output_root: str, task_id: str, version: str) -> Dict[str, str]:
    """读取某版本的所有输出文件"""
    vdir = get_version_dir(output_root, task_id, version)
    if not vdir.exists():
        return {}
    files = {}
    for fpath in sorted(vdir.iterdir()):
        if fpath.is_file() and not fpath.name.startswith("_"):
            name = fpath.stem  # 去掉 .md 后缀
            files[name] = fpath.read_text(encoding="utf-8", errors="replace")
    return files


def list_task_versions(output_root: str, task_id: str) -> List[str]:
    """列出任务的所有版本"""
    task_dir = get_task_dir(output_root, task_id)
    if not task_dir.exists():
        return []
    return sorted([d.name for d in task_dir.iterdir() if d.is_dir() and d.name.startswith("v")])


def list_all_tasks(output_root: str) -> List[Dict]:
    """列出所有任务及其版本"""
    output_dir = Path(output_root)
    if not output_dir.exists():
        return []
    tasks = []
    for d in sorted(output_dir.iterdir()):
        if d.is_dir() and d.name.startswith("T"):
            versions = list_task_versions(output_root, d.name)
            tasks.append({"task_id": d.name, "versions": versions})
    return tasks
