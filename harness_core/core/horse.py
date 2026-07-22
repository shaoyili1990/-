"""
骏马(Horse) - 推理与执行者
职责: 接收路由指令 → 4脑全参与 → 调度子链 → 调用AI执行 → 产出4步结果

核心改变:
  1. 4脑(逻辑链/因果链/思维链/推导法)每次推理全部参与
  2. 支持单链(仅通用指纹)和双链(通用+领域)执行
  3. weight作为LLM的描述性参考,不在代码中做排序
  4. 子链从route["active_chains"]获取(非硬编码chain_type过滤)
"""

import json
import uuid
from typing import List, Dict, Optional, Generator, Set
from ..config import Config
from ..engine import EngineDB
from ..engine.state_machine import StateMachine
from ..engine.subchain import SubchainScheduler
from ..providers import get_provider
from ..messages.content import Message


# 脑名称统一映射
NORMALIZE_BRAIN = {
    "推导链": "推导法",
}


class Horse:
    """骏马 - 推理与执行者"""

    # 4脑定义(固定跑道)
    BRAINS = ["逻辑链", "因果链", "思维链", "推导法"]

    def __init__(self, config: Config, db: EngineDB,
                 state_machine: StateMachine, subchain: SubchainScheduler):
        self.config = config
        self.db = db
        self.sm = state_machine
        self.subchain = subchain
        self.provider_config = config.get_provider_config("horse")
        self.provider = get_provider(
            self.provider_config["name"],
            self.provider_config
        )

        # 子链简称→全名映射(建立一次,重复使用)
        self._name_map = None

    @property
    def name_map(self) -> Dict[str, dict]:
        """子链简称→全名映射(惰性加载)"""
        if self._name_map is None:
            self._name_map = self.subchain.build_name_map()
        return self._name_map

    def execute(self, route_result: Dict, user_input: str,
                images: Optional[List[str]] = None, stream: bool = False):
        """
        执行任务 - 4脑全参与

        单链(single): 仅通用指纹 → 1次4步推理
        双链(dual):   通用指纹→结果, 领域指纹→深化结果
        """
        task_id = route_result["task_id"]
        chain_count = route_result["chain_count"]

        # 状态转换: 待执行
        self.sm.transition(task_id, "待执行")

        if chain_count == "single":
            # 单链: 仅通用指纹
            if stream:
                return self._stream_reasoning(route_result, user_input, images)
            return self._execute_single(route_result, user_input, images)
        else:
            # 双链: 通用→领域
            if stream:
                return self._stream_dual(route_result, user_input, images)
            return self._execute_dual(route_result, user_input, images)

    # ========== 验证标准(从route提取) ==========

    @staticmethod
    def _extract_validation_standards(route: Dict) -> str:
        """从route提取验证标准(正常执行+重试修复指引)"""
        retry = route.get("retry_context")
        if retry and retry.get("fresh_start"):
            # 路径B: 新鲜路径 — 从零推理但带上审核失败作为参考
            parts = ["本次是新鲜路径重推理。之前的审核未通过,请从零开始重新思考。"]
            failures = retry.get("failures", [])
            for f in failures:
                if isinstance(f, dict):
                    item = f.get("item", "")
                    reason = f.get("reason", "")
                    parts.append(f"- 需避免: {item}")
                    if reason:
                        parts.append(f"  原因: {reason}")
            return "\n".join(parts)
        if retry:
            # 重试: 带上验证失败详情
            parts = ["本次是修复重试。请确保修复以下问题:"]
            failures = retry.get("failures", [])
            for f in failures:
                if isinstance(f, dict):
                    item = f.get("item", "")
                    reason = f.get("reason", "")
                    fix = f.get("fix", "")
                    parts.append(f"- {item}")
                    if reason:
                        parts.append(f"  原因: {reason}")
                    if fix:
                        parts.append(f"  修复方向: {fix}")
                else:
                    parts.append(f"- {f}")
            return "\n".join(parts)

        # 正常执行: 给出验证标准预防
        return """1. 反证逻辑链: 每个A→B断言,反查B→A是否合理(主观意愿or客观因素)
2. 反AI逻辑链: 不机械套模板,不脱离材料,不偷换概念
3. 反证思维链: 不把B的存在作为A必然成立的证明
4. 逆AI思维链: 推理从材料和问题出发,不是从模板出发"""

    # ========== 单链执行 ==========

    def _execute_single(self, route: Dict, user_input: str,
                        images: Optional[List[str]] = None) -> Dict:
        """单链: 仅通用指纹,1次4步推理"""
        context = self._build_chain_context(route, "generic")
        vc = self._extract_validation_standards(route)
        result = self._four_step_reasoning(
            user_input, context, images,
            fingerprint_type="generic",
            validation_standards=vc
        )
        self._record_result(route["task_id"], result)
        return result

    # ========== 双链执行 ==========

    def _execute_dual(self, route: Dict, user_input: str,
                      images: Optional[List[str]] = None) -> Dict:
        """双链: 通用先出结果 → 领域垂直深化"""
        vc = self._extract_validation_standards(route)

        # Pass 1: 通用指纹
        generic_context = self._build_chain_context(route, "generic")
        generic_result = self._four_step_reasoning(
            user_input, generic_context, images,
            fingerprint_type="generic",
            validation_standards=vc
        )

        # Pass 2: 领域指纹 + 前序结果
        domain_context = self._build_chain_context(route, "domain")
        domain_result = self._four_step_reasoning(
            user_input, domain_context, images,
            fingerprint_type="domain",
            prev_result=generic_result,
            validation_standards=vc
        )

        self._record_result(route["task_id"], domain_result)
        return domain_result

    # ========== 4步推理 ==========

    def _four_step_reasoning(self, user_input: str, chain_context: str,
                             images: Optional[List[str]] = None,
                             fingerprint_type: str = "generic",
                             prev_result: Optional[Dict] = None,
                             validation_standards: str = "") -> Dict:
        """4步推理: 01思路→02流程→03执行方法→04结果"""
        steps = {}

        # Step 01 - 思路
        steps["01-思路"] = self._execute_step(
            "01-思路", user_input, chain_context, images,
            "分析任务的核心问题，明确目标和约束。输出清晰的问题定义。",
            validation_standards=validation_standards
        )

        # Step 02 - 流程
        steps["02-流程"] = self._execute_step(
            "02-流程", user_input, chain_context, images,
            "规划完整的解决步骤和方法论。输出详细的执行路径。",
            validation_standards=validation_standards
        )

        # Step 03 - 执行方法
        steps["03-执行方法"] = self._execute_step(
            "03-执行方法", user_input, chain_context, images,
            "给出具体的技术方案或操作步骤。如果有代码需求，输出完整代码。",
            validation_standards=validation_standards
        )

        # Step 04 - 结果(综合前序)
        prev_context = ""
        if prev_result:
            prev_context = (
                f"前序通用分析:\n"
                f"思路: {prev_result.get('01-思路', '')[:500]}\n"
                f"流程: {prev_result.get('02-流程', '')[:500]}\n"
            )
        elif steps.get("01-思路") or steps.get("02-流程"):
            prev_context = (
                f"前序分析:\n"
                f"思路: {steps.get('01-思路', '')[:500]}\n"
                f"流程: {steps.get('02-流程', '')[:500]}\n"
            )

        steps["04-结果"] = self._execute_step(
            "04-结果", user_input, chain_context, images,
            "综合前面分析，输出最终结果。确保完整、准确、可直接使用。",
            extra_context=prev_context,
            validation_standards=validation_standards
        )

        return {
            "task_id": "",
            "fingerprint_type": fingerprint_type,
            "01-思路": steps.get("01-思路", ""),
            "02-流程": steps.get("02-流程", ""),
            "03-执行方法": steps.get("03-执行方法", ""),
            "04-结果": steps.get("04-结果", ""),
        }

    def _execute_step(self, step_name: str, user_input: str,
                      chain_context: str, images: Optional[List[str]],
                      instruction: str,
                      extra_context: str = "",
                      validation_standards: str = "") -> str:
        """执行单个步骤"""
        vc_section = ""
        if validation_standards:
            vc_section = f"""
【重要】你的产出将通过以下4条验证链审查合理性(不是正确性):
{validation_standards}
请确保每一步推理都有依据支撑，避免想当然的断言。"""

        system_prompt = f"""你是骏马(Horse) - Hermes Agent的推理执行者。
你被调度了以下4脑子链来辅助推理：

{chain_context}
{extra_context}
{vc_section}

当前步骤: {step_name}
任务: {instruction}

请以{step_name}的格式输出。"""

        messages = [{"role": "system", "content": system_prompt}]
        msg = Message.from_text("user", user_input)
        if images:
            for img_data in images:
                msg.add_image(data=img_data)
        messages.extend(msg.to_list())

        result = self.provider.generate(messages)
        return result.content

    # ========== 构建子链上下文 ==========

    def _build_chain_context(self, route: Dict, fp_type: str) -> str:
        """
        从active_chains按4脑分组,构建LLM可读的上下文
        weight作为描述性参考放入prompt
        """
        active_chains = route.get("active_chains", [])
        fingerprints = route.get("fingerprints", {})

        # 按4脑分组(不排序)
        chains_by_brain: Dict[str, List[str]] = {b: [] for b in self.BRAINS}
        chain_weights: Dict[str, float] = {}  # 简称→weight(用于prompt参考)

        for c in active_chains:
            # chain_type 格式: "TECH:逻辑链" 或 "generic:推导链"
            try:
                _, brain_raw = c["chain_type"].split(":", 1)
            except ValueError:
                continue
            brain = NORMALIZE_BRAIN.get(brain_raw, brain_raw)
            if brain in chains_by_brain:
                short_name = c["subchain_name"]
                chains_by_brain[brain].append(short_name)
                chain_weights[short_name] = c.get("weight", 0.0)

        # 构建LLM上下文
        parts = ["## 当前激活的4脑子链", ""]

        for brain in self.BRAINS:
            chains = chains_by_brain.get(brain, [])
            if not chains:
                parts.append(f"### {brain}")
                parts.append("(无特定激活子链，使用通用推理能力)")
                parts.append("")
                continue

            parts.append(f"### {brain}")
            for short_name in chains:
                # 从子链文件获取完整内容(仅提取关键部分)
                content = self._get_chain_content(short_name)
                weight = chain_weights.get(short_name, 0)
                if content:
                    parts.append(f"- {short_name} (参考权重: {weight})")
                    parts.append(f"  {content[:300]}")
                else:
                    parts.append(f"- {short_name} (参考权重: {weight})")
            parts.append("")

        # 添加指纹签名/核心画像(如果有)
        fp_data = fingerprints.get(fp_type, {})
        if isinstance(fp_data, dict):
            core_portrait = fp_data.get("core_portrait", "")
            if core_portrait:
                parts.append(f"### 领域核心画像\n{core_portrait}\n")

        # 注明T4/T5潜水机制
        parts.append("### 待命子链(T4/T5)")
        parts.append("更深层的子链(T4层级、T5层级)处于待命状态，如需按需加载请明确要求。")
        parts.append("")

        return "\n".join(parts)

    def _get_chain_content(self, short_name: str) -> str:
        """
        从子链文件获取内容(提取关键定义部分)
        通过build_name_map匹配简称→全名
        """
        chain_file = self.name_map.get(short_name)
        if not chain_file:
            return ""
        # 提取定义部分
        content = chain_file.get("content", "")
        sections = self._extract_key_sections(content)
        return sections.get("定义", content[:300])

    def _extract_key_sections(self, content: str) -> Dict[str, str]:
        """提取子链的关键章节"""
        sections = {}
        current_section = "其他"
        current_text = []

        for line in content.split("\n"):
            if line.startswith("## "):
                if current_text:
                    sections[current_section] = "\n".join(current_text).strip()
                current_section = line[3:].strip()
                current_text = []
            else:
                current_text.append(line)

        if current_text:
            sections[current_section] = "\n".join(current_text).strip()

        result = {}
        for section_name, text in sections.items():
            if "定义" in section_name:
                result["定义"] = text[:500] if len(text) > 500 else text
            elif "分析重点" in section_name:
                result["分析重点"] = text[:500] if len(text) > 500 else text
        if "定义" not in result:
            result["定义"] = content[:300]
        return result

    # ========== 流式执行 ==========

    def _stream_reasoning(self, route: Dict, user_input: str,
                          images: Optional[List[str]] = None):
        """单链流式推理"""
        context = self._build_chain_context(route, "generic")
        vc = self._extract_validation_standards(route)
        system_prompt = f"""你是骏马(Horse)，Hermes Agent的执行者。
当前使用通用指纹。

{context}

【验证标准——产出将接受以下审查】
{vc}

请按照以下4步结构输出:
## 01-思路
## 02-流程
## 03-执行方法
## 04-结果"""

        messages = [{"role": "system", "content": system_prompt}]
        msg = Message.from_text("user", user_input)
        if images:
            for img_data in images:
                msg.add_image(data=img_data)
        messages.extend(msg.to_list())

        full = []
        for chunk in self.provider.stream(messages):
            full.append(chunk)
            yield chunk

        self._record_result(route["task_id"], "".join(full))

    def _stream_dual(self, route: Dict, user_input: str,
                     images: Optional[List[str]] = None):
        """双链流式推理(简化:仅流式输出最终结果)"""
        # 非流式执行双链
        result = self._execute_dual(route, user_input, images)
        result_text = json.dumps(result, ensure_ascii=False, indent=2)
        yield result_text

    # ========== 记录结果 ==========

    def _record_result(self, task_id: str, result):
        """记录执行结果到DB"""
        result_text = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
        self.db.create_step(task_id, "04-结果", 4,
                            f"results/{task_id}/result.md", "已完成")
        self.db.save_memory(f"session-{task_id}", "result", result_text[:2000])
        self.db.record_chat(task_id, "assistant", result_text[:1000], task_id)
        self.sm.transition(task_id, "执行完成待验证")

    def get_chain_recommendations(self, task: str) -> List[Dict]:
        """获取子链推荐(供灵猴参考)"""
        return self.subchain.schedule(task, top_n=5)
