"""
质检官(Verifier) - 验证模块
职责: 使用4条验证链审查骏马产出,判定通过/不通过/无法验证

4条验证链:
  1. 反证逻辑链 - 逻辑关系反证验证 (A→B, 反查B→A)
  2. 反AI逻辑链 - 反AI式逻辑错误验证 (机械逻辑/脱离材料/偷换概念)
  3. 反证思维链 - 思维路径反证验证 (倒果为因/伪相关)
  4. 逆AI思维链 - 反AI式思维过程验证 (机械推理/空泛套壳)

哲学: 验证不追求"多写分析",而是判断:
  - 是否能通过验证标准
  - 哪里不通过
  - 为什么不通过
  - 如何修正到可通过
"""

import os
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from ..config import Config
from ..engine import EngineDB
from ..providers import get_provider


# 验证链定义
VALIDATION_CHAINS = [
    {
        "id": "counter_evid_logic",
        "short_name": "反证逻辑链",
        "file": "01_反证逻辑链.md",
        "description": "逻辑关系反证验证: A→B, 反查B→A",
        "target": "逻辑关系",
    },
    {
        "id": "anti_ai_logic",
        "short_name": "反AI逻辑链",
        "file": "02_反AI逻辑链.md",
        "description": "反AI式逻辑错误验证: 机械逻辑/脱离材料/偷换概念",
        "target": "AI式错误",
    },
    {
        "id": "counter_evid_thinking",
        "short_name": "反证思维链",
        "file": "03_反证思维链.md",
        "description": "思维路径反证验证: 倒果为因/伪相关",
        "target": "因果关系",
    },
    {
        "id": "reverse_ai_thinking",
        "short_name": "逆AI思维链",
        "file": "04_逆AI思维链.md",
        "description": "反AI式思维过程验证: 机械推理/空泛套壳",
        "target": "思维过程",
    },
    {
        "id": "no_numeric_only",
        "short_name": "禁止数值解链",
        "file": "05_禁止数值解验证链.md",
        "description": "禁止数值评分/二元判断/模板化输出,要求解析解表述",
        "target": "解析解合规",
    },
]


class Verifier:
    """质检官 - 验证模块核心"""

    def __init__(self, config: Config, db: EngineDB,
                 validations_dir: Optional[str] = None):
        self.config = config
        self.db = db

        if validations_dir:
            self.validations_dir = validations_dir
        else:
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                base = Path(sys._MEIPASS)
            else:
                base = Path(__file__).parent.parent.parent  # project root
            self.validations_dir = str(base / "validations")

        # 使用horse的provider来执行验证(验证也需AI能力)
        self.provider_config = config.get_provider_config("horse")
        self.provider = get_provider(
            self.provider_config["name"],
            self.provider_config
        )

        # 缓存加载的验证模板
        self._templates_cache = None

    # 占位符前缀(从模板中动态匹配,避免编码问题)
    _MATERIAL_PREFIX = "{如果有原始材料"
    _OUTPUT_PLACEHOLDERS = [
        "{粘贴待验证文本、聊天内容、分析稿、结论链路、方案或提示词输出}",
        "{需要审查的回答、方案、分析稿、聊天内容或结论}",
    ]

    @staticmethod
    def _find_placeholder(text: str, candidates: List[str]) -> Optional[str]:
        """在文本中查找候选占位符,返回第一个匹配到的完整占位符"""
        for c in candidates:
            if c in text:
                return c
        # 如果精确匹配失败,尝试前缀匹配
        for c in candidates:
            prefix = c[:10]  # 取前10个字符做前缀匹配
            if prefix in text:
                idx = text.index(prefix)
                # 找到从idx到下一个换行或到行尾
                end = text.find("\n", idx)
                if end == -1:
                    end = text.find("}", idx)
                    if end != -1:
                        return text[idx:end+1]
                    return text[idx:]
                return text[idx:end]
        return None

    def _find_material_placeholder(self, text: str) -> Optional[str]:
        """查找原始材料占位符(动态匹配,避免编码问题)"""
        prefix = self._MATERIAL_PREFIX
        if prefix not in text:
            return None
        idx = text.index(prefix)
        end = text.find("}", idx)
        if end == -1:
            end = text.find("\n", idx)
        if end != -1:
            return text[idx:end+1]
        return text[idx:]

    def load_all_templates(self) -> List[Dict]:
        """加载所有验证链模板"""
        if self._templates_cache:
            return self._templates_cache

        templates = []
        for vc in VALIDATION_CHAINS:
            fpath = os.path.join(self.validations_dir, vc["file"])
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except:
                continue

            # 提取验证提示词模板(从 ```text 块中提取)
            prompt_template = self._extract_prompt_template(content)

            templates.append({
                **vc,
                "content": content,
                "prompt_template": prompt_template,
            })

        self._templates_cache = templates
        return templates

    def _extract_prompt_template(self, content: str) -> str:
        """从md文件提取通用验证提示词(```text 块)"""
        # 匹配 ```text ... ``` 块
        match = re.search(r'```text\n(.*?)\n```', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return content  # fallback: 返回全文

    def verify(self, output_text: str,
               chains: Optional[List[str]] = None,
               original_material: str = "",
               task_context: str = "") -> Dict:
        """
        执行验证 - 对输出运行指定的验证链

        Args:
            output_text: 骏马产出的结果文本
            chains: 要运行的验证链ID列表,默认运行全部4条
            original_material: 原始材料(可选)
            task_context: 任务上下文(可选)

        Returns:
            {
                "verdict": "pass" | "partial" | "fail" | "cannot_verify",
                "summary": "总体结论",
                "details": [每条验证链的结果],
                "failures": [所有失败项],
                "fix_priority": "high"/"medium"/"low",
            }
        """
        templates = self.load_all_templates()
        if not templates:
            return {
                "verdict": "cannot_verify",
                "summary": "无验证模板可用",
                "details": [],
                "failures": [],
                "fix_priority": "low",
            }

        # 筛选要运行的验证链
        if chains:
            target = [t for t in templates if t["id"] in chains]
        else:
            target = templates

        details = []
        all_failures = []

        for template in target:
            result = self._run_single_validation(
                template, output_text, original_material, task_context
            )
            details.append(result)
            all_failures.extend(result.get("failures", []))

        # 汇总判定
        verdicts = [d["judgment"] for d in details]
        if "fail" in verdicts:
            overall = "fail"
        elif "partial" in verdicts:
            overall = "partial"
        elif "cannot_verify" in verdicts:
            overall = "cannot_verify"
        else:
            overall = "pass"

        # 汇总优先级
        priorities = [d.get("priority", "low") for d in details]
        if "high" in priorities:
            fix_priority = "high"
        elif "medium" in priorities:
            fix_priority = "medium"
        else:
            fix_priority = "low"

        summary_parts = []
        for d in details:
            status = d["judgment"]
            summary_parts.append(f"{d['short_name']}: {status}")
        summary = " | ".join(summary_parts)

        return {
            "verdict": overall,
            "summary": summary,
            "details": details,
            "failures": all_failures,
            "fix_priority": fix_priority,
        }

    def _run_single_validation(self, template: Dict,
                                output_text: str,
                                original_material: str,
                                task_context: str) -> Dict:
        """运行单条验证链"""
        prompt = template["prompt_template"]

        # 填充待验证对象 - 从模板里找到正确的占位符
        placeholder_output = self._find_placeholder(prompt, self._OUTPUT_PLACEHOLDERS)
        if placeholder_output:
            filled_prompt = prompt.replace(placeholder_output, output_text)
        else:
            filled_prompt = prompt  # fallback: 无法匹配就追加

        # 填充原始材料 - 使用前缀动态匹配(避免编码问题)
        placeholder_material = self._find_material_placeholder(filled_prompt)
        if placeholder_material:
            if original_material:
                filled_prompt = filled_prompt.replace(placeholder_material, original_material)
            else:
                filled_prompt = filled_prompt.replace(placeholder_material, "无原始材料，仅做内部自洽验证")
        elif original_material:
            # 无占位符但有原始材料，追加
            filled_prompt += f"\n\n【原始材料】\n{original_material}"
        else:
            filled_prompt += "\n\n【原始材料】无原始材料，仅做内部自洽验证"

        # 如果有任务上下文，附加到输入
        if task_context:
            filled_prompt += f"\n\n【任务上下文】\n{task_context}"

        # 调用AI执行验证
        messages = [
            {"role": "system", "content": f"你是质检官(Verifier) - Hermes Agent的验证审查者。\n你被调度了验证链: {template['short_name']}\n任务: 审查待验证对象是否通过验证标准，不是继续分析材料。"},
            {"role": "user", "content": filled_prompt},
        ]

        try:
            response = self.provider.generate(messages)
            result_text = response.content
        except Exception as e:
            return {
                "chain_id": template["id"],
                "short_name": template["short_name"],
                "judgment": "cannot_verify",
                "summary": f"验证执行失败: {str(e)}",
                "failures": [],
                "priority": "low",
                "detail": "",
            }

        # 解析判定结果
        judgment = self._parse_judgment(result_text)
        failures = self._parse_failures(result_text)
        priority = self._parse_priority(result_text)

        return {
            "chain_id": template["id"],
            "short_name": template["short_name"],
            "judgment": judgment,
            "summary": self._extract_summary(result_text),
            "failures": failures,
            "priority": priority,
            "detail": result_text,
        }

    def _parse_judgment(self, text: str) -> str:
        """从验证报告解析总体判定"""
        text_lower = text.lower()
        # 查找通过/不通过/无法验证等判定
        if "总体判定" in text:
            # 提取"总体判定"后面的内容
            idx = text.index("总体判定")
            line = text[idx:idx+60]
            if "不通过" in line:
                return "fail"
            elif "无法验证" in line:
                return "cannot_verify"
            elif "部分通过" in line:
                return "partial"
            elif "通过" in line:
                return "pass"

        # fallback: 关键词匹配
        if "不通过" in text:
            return "fail"
        if "无法验证" in text:
            return "cannot_verify"
        if "部分通过" in text:
            return "partial"
        if "通过" in text:
            return "pass"
        return "cannot_verify"

    def _parse_failures(self, text: str) -> List[Dict]:
        """从验证报告解析失败项清单"""
        failures = []
        # 查找失败项表格区域
        if "失败项清单" in text or "失败项" in text:
            # 提取表格行
            lines = text.split("\n")
            in_table = False
            for line in lines:
                if "失败项" in line and ("|" in line or "清单" in line):
                    in_table = True
                    continue
                if in_table and "|" in line:
                    cells = [c.strip() for c in line.split("|")]
                    cells = [c for c in cells if c]  # 去掉空cell
                    if len(cells) >= 3:
                        failures.append({
                            "item": cells[0],
                            "type": cells[1] if len(cells) > 1 else "",
                            "reason": cells[2] if len(cells) > 2 else "",
                            "severity": cells[3] if len(cells) > 3 else "",
                            "fix": cells[4] if len(cells) > 4 else "",
                        })
        return failures

    def _parse_priority(self, text: str) -> str:
        """从验证报告解析修正优先级"""
        if "修正优先级" in text:
            idx = text.index("修正优先级")
            line = text[idx:idx+30]
            if "高" in line:
                return "high"
            elif "中" in line:
                return "medium"
            elif "低" in line:
                return "low"
        return "medium"

    def _extract_summary(self, text: str) -> str:
        """提取验证摘要(主要问题部分)"""
        if "主要问题" in text:
            idx = text.index("主要问题")
            return text[idx:idx+100].split("\n")[0].strip()
        return text[:100]

    def get_chain_info(self) -> List[Dict]:
        """获取验证链信息(供系统状态查询)"""
        templates = self.load_all_templates()
        return [
            {
                "id": t["id"],
                "name": t["short_name"],
                "description": t["description"],
                "target": t["target"],
                "has_template": bool(t["prompt_template"]),
            }
            for t in templates
        ]
