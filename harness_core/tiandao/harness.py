"""天道系统 - 马的双通道Harness （整合层）

Harness 是整合层，不是引擎。职责：
  1. 接收子链通道输入（Logic/Structure）
  2. 接收天道通道输入（Emotion/Psychology）
  3. 整合翻译为执行指令输出
  4. 每个任务生成专属临时脚本

设计原则：
  - 不内置领域知识，只做拼装和转发
  - 子链短期从markdown文件读取，长期从 tiandao_chains 表
  - 脚本按需生成，禁止复用

Usage:
    from harness import Harness
    h = Harness(subchains_dir="/path/to/subchains")
    output = h.run(
        task_id="ch-001-event-001",
        chain_type="因果链-反噬反转",
        chain_id="08_反噬反转因果链",
        novel_id="novel-001",
        event_id=1,
        char_ids=[1, 2],
    )
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Optional

from .tiandao_bridge import TiandaoDB

logger = logging.getLogger(__name__)

HARNESS_VERSION = "0.1.0"
TASKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks")


# ═══════════════════════════════════════════════════════════════════════
# 子链通道
# ═══════════════════════════════════════════════════════════════════════

class SubchainReader:
    """从子链markdown文件中读取和解析模板信息。

    短期方案：直接读取 subchains/ 目录的 .md 文件。
    长期方案：从 tiandao_chains 数据库表读取。
    """

    # 因果链分类（12大门类）
    CHAIN_CATEGORIES = {
        "01": "因果推导",
        "02": "逻辑推理",
        "03": "思维方法",
        "04": "关联分析",
        "05": "博弈策略",
        "06": "权衡决策",
        "07": "推演预判",
        "08": "反转制衡",
        "09": "反馈循环",
        "10": "层级拆解",
        "11": "多因多果",
        "12": "复合结构",
    }

    def __init__(self, subchains_dir: str):
        """初始化子链读取器。

        Args:
            subchains_dir: 子链markdown文件的目录路径。
        """
        self.subchains_dir = subchains_dir

    def get_chain_info(self, chain_id: str) -> Optional[dict]:
        """读取并解析一个子链markdown文件。

        Args:
            chain_id: 子链ID，例如 "08_反噬反转因果链"。
                传完整文件名（含或不含 .md 后缀均可）。

        Returns:
            dict: 解析后的子链信息，包含：
                - chain_id, name, type, definition, flow, prompt
            - 文件不存在时返回 None。
        """
        # 尝试多种文件名变体
        candidates = [
            os.path.join(self.subchains_dir, chain_id),
            os.path.join(self.subchains_dir, chain_id + ".md"),
        ]
        # 如果 chain_id 本身包含 _ 前缀编号，也尝试完整格式
        if "_" not in chain_id and not chain_id.endswith(".md"):
            # 在所有文件中搜索
            candidates.extend(self._search_by_name(chain_id))

        content = None
        found_path = None
        for path in candidates:
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    found_path = path
                    break
                except (IOError, OSError) as e:
                    logger.warning("读取子链文件失败 %s: %s", path, e)

        if content is None:
            logger.warning("子链文件不存在: %s (已尝试: %s)", chain_id, candidates)
            return None

        return self._parse_chain(content, found_path)

    def _parse_chain(self, content: str, file_path: str) -> dict:
        """解析子链markdown内容。

        Args:
            content: markdown文件内容。
            file_path: 文件路径（用于提取chain_id）。

        Returns:
            dict: 结构化子链信息。
        """
        # 提取标题（第一行 # 开头）
        title = ""
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()

        # 提取子类定义（## 1. 子类定义）
        definition = ""
        def_match = re.search(
            r"##\s*1\.\s*子类定义\s*\n(.+?)(?=\n##\s*\d)",
            content, re.DOTALL
        )
        if def_match:
            definition = def_match.group(1).strip()
        # 也尝试从第一行后的内容提取简短定义
        if not definition:
            lines = content.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    definition = line
                    break

        # 提取分析流程（## 6. 强制分析流程）
        flow_steps = []
        flow_match = re.search(
            r"##\s*6\.\s*强制分析流程\s*\n(.+?)(?=\n##\s*\d)",
            content, re.DOTALL
        )
        if flow_match:
            flow_text = flow_match.group(1)
            for line in flow_text.split("\n"):
                line = line.strip()
                # 匹配 "1. xxx" 或 "- xxx"
                step_match = re.match(r"^[\d\-]+[\.、]?\s*(.+)$", line)
                if step_match:
                    flow_steps.append(step_match.group(1).strip())

        # 提取分析重点（## 5. 本子类专属分析重点）
        focus = ""
        focus_match = re.search(
            r"##\s*5\.\s*本子类专属分析重点\s*\n(.+?)(?=\n##\s*\d)",
            content, re.DOTALL
        )
        if focus_match:
            focus = focus_match.group(1).strip()

        # 提取深度分析提示词（## 7 下的 ```text ... ``` 块）
        prompt = ""
        prompt_match = re.search(
            r"```text\n(.*?)```",
            content, re.DOTALL
        )
        if prompt_match:
            prompt_text = prompt_match.group(1).strip()
            # 限制提示词长度以防过大
            if len(prompt_text) > 2000:
                prompt_text = prompt_text[:2000] + "\n... [截断]"
            prompt = prompt_text

        # 提取适用/不适用
        applicable = ""
        app_match = re.search(
            r"### 适用\s*\n(.+?)(?=\n###\s*不适用)",
            content, re.DOTALL
        )
        if app_match:
            applicable = app_match.group(1).strip()

        not_applicable = ""
        napp_match = re.search(
            r"### 不适用\s*\n(.+?)(?=\n##\s*\d)",
            content, re.DOTALL
        )
        if napp_match:
            not_applicable = napp_match.group(1).strip()

        # 提取自检清单
        checklist = []
        checklist_match = re.search(
            r"##\s*9\.\s*模板自检清单\s*\n(.+?)$",
            content, re.DOTALL
        )
        if checklist_match:
            for line in checklist_match.group(1).split("\n"):
                line = line.strip()
                if line.startswith("-") or line.startswith("["):
                    checklist.append(line.lstrip("- []").strip())

        # 提取类别编号
        basename = os.path.basename(file_path) if file_path else ""
        category_code = basename[:2] if re.match(r"^\d{2}_", basename) else "00"
        category = self.CHAIN_CATEGORIES.get(category_code, "通用")

        # 确定链类型
        chain_type = "因果链"
        if "推导" in title or "思维" in title:
            chain_type = "思维链"
        elif "逻辑" in title:
            chain_type = "逻辑链"
        elif "推导" in title or "推导法" in title:
            chain_type = "推导法"

        chain_id = basename.replace(".md", "") if basename else "unknown"

        return {
            "chain_id": chain_id,
            "name": title,
            "type": chain_type,
            "category": category,
            "category_code": category_code,
            "definition": definition,
            "focus": focus,
            "flow_steps": flow_steps,
            "applicable": applicable,
            "not_applicable": not_applicable,
            "prompt_template": prompt,
            "checklist": checklist,
        }

    def _search_by_name(self, name: str) -> list:
        """按名称在所有子链文件中搜索匹配。

        Args:
            name: 要搜索的名称。

        Returns:
            list: 候选文件路径列表。
        """
        matches = []
        if not os.path.isdir(self.subchains_dir):
            return matches

        name_lower = name.lower().replace(" ", "").replace("-", "")
        try:
            for fname in os.listdir(self.subchains_dir):
                if fname.endswith(".md"):
                    fname_lower = fname.lower().replace(" ", "").replace("-", "")
                    if name_lower in fname_lower:
                        matches.append(os.path.join(self.subchains_dir, fname))
        except OSError as e:
            logger.warning("搜索子链文件失败: %s", e)

        return matches

    def list_chains(self, category_code: Optional[str] = None) -> list[dict]:
        """列出所有可用的子链。

        Args:
            category_code: 可选，按类别编号过滤（如 "01", "08"）。

        Returns:
            list[dict]: 子链基本信息列表。
        """
        if not os.path.isdir(self.subchains_dir):
            logger.warning("子链目录不存在: %s", self.subchains_dir)
            return []

        chains = []
        try:
            for fname in sorted(os.listdir(self.subchains_dir)):
                if not fname.endswith(".md"):
                    continue
                if category_code and not fname.startswith(category_code + "_"):
                    continue

                code = fname[:2] if re.match(r"^\d{2}_", fname) else "00"
                chains.append({
                    "chain_id": fname.replace(".md", ""),
                    "category": self.CHAIN_CATEGORIES.get(code, "通用"),
                    "category_code": code,
                    "file": fname,
                })
        except OSError as e:
            logger.warning("列出子链失败: %s", e)

        return chains


# ═══════════════════════════════════════════════════════════════════════
# 天道通道
# ═══════════════════════════════════════════════════════════════════════

class TiandaoChannel:
    """天道通道封装。

    通过 TiandaoDB 获取人物状态，格式化为天道通道输入。
    """

    def __init__(self, db: TiandaoDB):
        """初始化天道通道。

        Args:
            db: TiandaoDB 实例。
        """
        self.db = db

    def get_characters_for_event(
        self,
        novel_id: str,
        event_id: int,
        char_ids: Optional[list[int]] = None,
    ) -> list[dict]:
        """获取事件涉及的人物天道状态。

        优先从事件角色表获取关系信息，若无事件记录则通过 char_ids 直接查询。

        Args:
            novel_id: 小说ID。
            event_id: 事件ID（用于获取角色关系）。
            char_ids: 可选，指定人物ID列表。不指定则尝试从事件角色表读取。

        Returns:
            list[dict]: 人物状态列表，每项符合天道通道格式。
        """
        # 先尝试从事件角色表获取
        if char_ids:
            roles = self.db.get_event_roles(novel_id, event_id)
            roles = [r for r in roles if r["char_id"] in char_ids]
        else:
            roles = self.db.get_event_roles(novel_id, event_id)

        # 无事件角色记录时，直接用 char_ids 查询
        if not roles:
            if not char_ids:
                logger.info("事件 %d 无关联人物且无 char_ids 指定", event_id)
                return []
            # 直接使用 char_ids 查询，构造基本角色信息
            result = []
            for char_id in char_ids:
                state = self.db.get_character_state(novel_id, char_id)
                if not state:
                    logger.warning("人物 %d 不存在，跳过", char_id)
                    continue
                result.append({
                    "name": state.get("name", f"角色#{char_id}"),
                    "y_current": state.get("y_current", 50.0),
                    "y_effective": state.get("y_effective", 0.5),
                    "emotions": state.get("emotions", {}),
                    "desires": state.get("desires", {}),
                    "motivation": state.get("motivation", ""),
                    "event_role": "重要人物",
                    "influence_score": 1.0,
                    "breakthrough_flag": state.get("breakthrough_flag", 0),
                })
            return result

        result = []
        for role in roles:
            char_id = role["char_id"]
            state = self.db.get_character_state(novel_id, char_id)

            role_type_map = {
                "major": "重要人物",
                "supporting": "次要人物",
                "extra": "龙套",
            }
            event_role = role_type_map.get(role.get("role_type", ""), "未知")

            char_info = {
                "name": state.get("name", role.get("name", f"角色#{char_id}")),
                "y_current": state.get("y_current", 50.0),
                "y_effective": state.get("y_effective", 0.5),
                "emotions": state.get("emotions", {}),
                "desires": state.get("desires", {}),
                "motivation": state.get("motivation", ""),
                "event_role": event_role,
                "influence_score": role.get("influence_score", 1.0),
                "breakthrough_flag": state.get("breakthrough_flag", 0),
            }
            result.append(char_info)

        return result

    def build_tiandao_input(
        self,
        novel_id: str,
        event_id: int,
        char_ids: Optional[list[int]] = None,
        extra_context: Optional[dict] = None,
    ) -> dict:
        """构建天道通道的完整输入JSON。

        Args:
            novel_id: 小说ID。
            event_id: 事件ID。
            char_ids: 可选，指定人物ID列表。
            extra_context: 额外的上下文信息。

        Returns:
            dict: 天道通道输入JSON。
        """
        characters = self.get_characters_for_event(novel_id, event_id, char_ids)

        tiandao_input = {
            "novel_id": novel_id,
            "event_id": event_id,
            "characters": characters,
        }

        if extra_context:
            tiandao_input["context"] = extra_context

        return tiandao_input


# ═══════════════════════════════════════════════════════════════════════
# Harness 主控
# ═══════════════════════════════════════════════════════════════════════

class Harness:
    """马的双通道Harness主控。

    接收子链通道和天道通道的数据，整合输出为执行指令。
    每个任务生成专属临时脚本。
    """

    def __init__(
        self,
        subchains_dir: str,
        db: Optional[TiandaoDB] = None,
    ):
        """初始化Harness。

        Args:
            subchains_dir: 子链markdown目录路径。
            db: TiandaoDB实例。不传则使用默认路径创建。
        """
        self.subchain_reader = SubchainReader(subchains_dir)
        self.tiandao_channel = TiandaoChannel(db or TiandaoDB())
        self.version = HARNESS_VERSION

    # ── 主入口 ───────────────────────────────────────────────────────

    def run(
        self,
        task_id: str,
        chain_type: str,
        chain_id: str,
        novel_id: str,
        event_id: int,
        char_ids: Optional[list[int]] = None,
        params: Optional[dict] = None,
        extra_context: Optional[dict] = None,
        generate_script: bool = True,
    ) -> dict:
        """执行一次完整的Harness流程。

        步骤：
          1. 读取子链模板 → 构建子链通道输入
          2. 查询天道状态 → 构建天道通道输入
          3. 整合输出为执行指令
          4. 可选：生成临时脚本

        Args:
            task_id: 任务标识，如 "ch-001-event-001"。
            chain_type: 子链类型描述，如 "因果链-反噬反转"。
            chain_id: 子链文件ID，如 "08_反噬反转因果链"。
            novel_id: 小说ID。
            event_id: 事件ID。
            char_ids: 可选，限定人物ID列表。
            params: 可选，额外的子链参数。
            extra_context: 可选，额外上下文信息。
            generate_script: 是否生成临时脚本。默认 True。

        Returns:
            dict: 完整的Harness输出（格式参考 ticket-4/ticket-9）。
        """
        # 步骤1: 构建子链通道输入
        chain_input = self._build_chain_input(
            chain_type=chain_type,
            chain_id=chain_id,
            params=params or {},
        )

        # 步骤2: 构建天道通道输入
        tiandao_input = self.tiandao_channel.build_tiandao_input(
            novel_id=novel_id,
            event_id=event_id,
            char_ids=char_ids,
            extra_context=extra_context,
        )

        # 步骤3: 整合输出
        output = self._assemble_output(
            task_id=task_id,
            chain_input=chain_input,
            tiandao_input=tiandao_input,
        )

        # 步骤4: 生成临时脚本
        script_path = None
        if generate_script:
            script_path = self._generate_script(task_id, output)
            output["script_path"] = script_path

        return output

    # ── 子链通道 ─────────────────────────────────────────────────────

    def _build_chain_input(
        self,
        chain_type: str,
        chain_id: str,
        params: dict,
    ) -> dict:
        """构建子链通道输入JSON。

        Args:
            chain_type: 子链类型描述。
            chain_id: 子链ID。
            params: 额外参数（如关键事件、决策点等）。

        Returns:
            dict: 子链通道输入。
        """
        chain_info = self.subchain_reader.get_chain_info(chain_id)

        # 即使子链文件不存在也返回基本格式
        base = {
            "chain_type": chain_type,
            "chain_id": chain_id,
        }

        if chain_info:
            # 提取逻辑流步骤
            logic_flow = chain_info.get("flow_steps", [])

            # 从分析重点提取决策点
            decision_points = []
            focus = chain_info.get("focus", "")
            if focus:
                decision_points.append(focus)

            base["definition"] = chain_info.get("definition", "")
            base["focus"] = chain_info.get("focus", "")
            base["output_template"] = {
                "logic_flow": logic_flow,
                "decision_points": decision_points,
                "expected_outcome": chain_info.get("definition", ""),
            }
            base["prompt_template"] = chain_info.get("prompt_template", "")
        else:
            # 无文件时使用默认模板
            base["output_template"] = {
                "logic_flow": [],
                "decision_points": [],
                "expected_outcome": "",
            }

        if params:
            base["params"] = params

        return base

    # ── 整合输出 ─────────────────────────────────────────────────────

    def _assemble_output(
        self,
        task_id: str,
        chain_input: dict,
        tiandao_input: dict,
    ) -> dict:
        """整合双通道输入为执行指令。

        Args:
            task_id: 任务标识。
            chain_input: 子链通道输入。
            tiandao_input: 天道通道输入。

        Returns:
            dict: 整合后的执行指令。
        """
        # 生成叙事指令
        narrative_parts = []

        # 从子链通道生成基础指令
        chain_type = chain_input.get("chain_type", "")
        chain_id = chain_input.get("chain_id", "")
        definition = chain_input.get("definition", "")
        logic_flow = chain_input.get("output_template", {}).get("logic_flow", [])

        if definition:
            narrative_parts.append(f"【因果类型】{definition}")

        if logic_flow:
            flow_text = " → ".join(logic_flow[:4])  # 取前4步
            narrative_parts.append(f"【分析路径】{flow_text}")

        # 从天道通道生成人物状态摘要
        character_states = []
        for char in tiandao_input.get("characters", []):
            emotions = char.get("emotions", {})
            emotion_summary = "、".join(
                f"{k}{v:.1f}" for k, v in emotions.items() if v > 0
            ) if emotions else "中性"
            char_summary = (
                f"{char.get('name', '?')}"
                f"[Y={char.get('y_current', 50):.1f}]"
                f"({char.get('event_role', '?')})"
                f" 情绪:{emotion_summary}"
            )
            motivation = char.get("motivation", "")
            if motivation:
                char_summary += f" 动机:{motivation}"
            character_states.append(char_summary)

        narrative_instruction = "\n".join(narrative_parts) if narrative_parts else "无子链指令"

        return {
            "task_id": task_id,
            "harness_version": self.version,
            "inputs": {
                "chain": {
                    "chain_type": chain_type,
                    "chain_id": chain_id,
                },
                "tiandao": {
                    "novel_id": tiandao_input.get("novel_id", ""),
                    "event_id": tiandao_input.get("event_id", 0),
                    "character_count": len(tiandao_input.get("characters", [])),
                },
            },
            "output": {
                "narrative_instruction": narrative_instruction,
                "character_states_after": character_states,
                "chain_detail": chain_input.get("output_template", {}),
            },
        }

    # ── 临时脚本生成 ─────────────────────────────────────────────────

    def _generate_script(self, task_id: str, output: dict) -> str:
        """生成一个专属临时脚本并保存到磁盘。

        Args:
            task_id: 任务标识。
            output: 整合后的执行指令。

        Returns:
            str: 脚本文件的绝对路径。
        """
        # 确保任务目录存在
        task_dir = os.path.join(TASKS_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)

        # 从chain_id提取安全文件名
        chain_id = (
            output.get("inputs", {})
            .get("chain", {})
            .get("chain_id", "default")
            .replace(" ", "_")
        )
        script_path = os.path.join(task_dir, f"execute_{chain_id}.py")

        # 生成脚本内容
        narrative = output.get("output", {}).get("narrative_instruction", "")
        characters = output.get("output", {}).get("character_states_after", [])

        script_content = f'''#!/usr/bin/env python3
"""天道临时执行脚本 — 任务 {task_id}

由 Harness v{HARNESS_VERSION} 自动生成。
生成时间: {datetime.now().isoformat()}

任务类型: {chain_id}
"""

import json


def main():
    """执行剧本分析。"""
    narrative_instruction = {json.dumps(narrative, ensure_ascii=False, indent=2)}

    characters = {json.dumps(characters, ensure_ascii=False, indent=2)}

    print("=" * 50)
    print("任务: {task_id}")
    print("=" * 50)
    print()
    print("【叙事指令】")
    print(narrative_instruction)
    print()
    print("【人物状态】")
    for c in characters:
        print("  -", c)
    print()
    print("【完成】请根据以上信息进行创作。")


if __name__ == "__main__":
    main()
'''

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        os.chmod(script_path, 0o755)
        logger.info("临时脚本已生成: %s", script_path)
        return script_path


# ═══════════════════════════════════════════════════════════════════════
# 快捷函数
# ═══════════════════════════════════════════════════════════════════════

def build_chain_input(
    subchains_dir: str,
    chain_type: str,
    chain_id: str,
    params: Optional[dict] = None,
) -> dict:
    """快捷函数：构建子链通道输入。"""
    reader = SubchainReader(subchains_dir)
    harness = Harness(subchains_dir)
    return harness._build_chain_input(chain_type, chain_id, params or {})


def build_tiandao_input(
    db_path: str,
    novel_id: str,
    event_id: int,
    char_ids: Optional[list[int]] = None,
) -> dict:
    """快捷函数：构建天道通道输入。"""
    db = TiandaoDB(db_path)
    channel = TiandaoChannel(db)
    return channel.build_tiandao_input(novel_id, event_id, char_ids)


def assemble_output(
    task_id: str,
    chain_input: dict,
    tiandao_input: dict,
) -> dict:
    """快捷函数：整合双通道输出。"""
    harness = Harness("")  # subchains_dir 不需要，我们直接传 chain_input
    return harness._assemble_output(task_id, chain_input, tiandao_input)
