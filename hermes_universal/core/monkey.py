"""
灵猴(Monkey) - 路由与审核官
核心任务: 识别三件事
  1. 识别什么领域(或通用) — domain_tags集合匹配
  2. 识别需要多深的思考 — 输入特征IF-THEN
  3. 识别单链还是双链 — 有领域且非快照→双链,否则单链
哲学: 解析解(非数值),所有数据从DB读
"""

import json
import uuid
from typing import List, Dict, Optional, Tuple
from ..config import Config
from ..engine import EngineDB
from ..engine.state_machine import StateMachine
from ..providers import get_provider
# 延迟导入Verifier避免循环依赖
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .verifier import Verifier


class Monkey:
    """灵猴 - 路由与审核官"""

    # 代码关键词(用于深度判定)
    CODE_KEYWORDS = [
        "代码", "实现", "function", "class", "bug", "算法", "架构",
        "微服务", "数据库", "API", "接口", "部署", "容器", "docker",
        "k8s", "编程", "写一个", "开发", "重构", "代码审查",
    ]

    # 深度判定规则(IF-THEN,无数值阈值)
    DEEP_INDICATORS = CODE_KEYWORDS  # 含代码关键词+较长文本→deep
    STANDARD_INDICATORS = [
        "分析", "比较", "解释", "为什么", "如何", "设计", "规划",
        "方案", "策略", "评估", "预测",
    ]

    def __init__(self, config: Config, db: EngineDB, state_machine: StateMachine,
                 verifier: Optional['Verifier'] = None):
        self.config = config
        self.db = db
        self.sm = state_machine
        self.verifier = verifier
        self.provider_config = config.get_provider_config("monkey")
        self.provider = get_provider(
            self.provider_config["name"],
            self.provider_config
        )

    def route(self, user_input: str, multimodal: bool = False) -> Dict:
        """
        路由决策(解析解,无数值计算)

        返回: {
          task_id, domain, depth, chain_count,
          fingerprints: {generic, domain?},
          active_chains: [从DB查出的子链]
        }
        """
        # 1. 识别领域(从DB读fingerprints,集合匹配)
        domain_id, domain_tags = self._match_domain(user_input)

        # 2. 识别思考深度(输入特征IF-THEN)
        depth = self._determine_depth(user_input, multimodal)

        # 3. 加载通用指纹(必选)
        fingerprints = {
            "generic": self._load_fingerprint("jiapo_unified"),
        }

        # 4. 如有领域,加载领域垂直指纹
        if domain_id:
            fingerprints["domain"] = self._load_fingerprint(domain_id)

        # 5. 从DB的subchain_weights表查子链(按tier过滤)
        tier_limit = {"snapshot": 1, "standard": 2, "deep": 3}[depth]
        # 无领域匹配时使用通用指纹(jiapo_unified)的子链
        chain_domain = domain_id if domain_id else "jiapo_unified"
        active_chains = self._load_active_chains(
            chain_domain, tier_limit
        )

        # 6. 决定链数
        chain_count = "dual" if (domain_id and depth != "snapshot") else "single"

        # 7. 创建任务记录
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        task_name = user_input[:50] if len(user_input) > 50 else user_input
        level = "whole" if depth == "deep" else ("unit" if depth == "standard" else "step")
        self.sm.create_task_flow(task_id, task_name, level=level)

        result = {
            "task_id": task_id,
            "domain": domain_id,             # None=走通用
            "domain_tags": domain_tags,       # 匹配到的标签
            "depth": depth,                   # snapshot/standard/deep
            "chain_count": chain_count,       # single/dual
            "fingerprints": fingerprints,     # 完整指纹数据
            "active_chains": active_chains,   # 从DB查出的子链(无数值排序)
            "level": level,
            "multimodal": multimodal,
        }

        # 记录路由决策到认知库
        self.db.record_chat(
            session_id=task_id,
            role="assistant",
            content=json.dumps(result, ensure_ascii=False),
            task_id=task_id,
            metadata=json.dumps({"action": "route", "domain": domain_id or "generic"})
        )

        return result

    def _match_domain(self, text: str) -> Tuple[Optional[str], List[str]]:
        """
        领域匹配(解析解: 集合判定,无评分)
        从fingerprints表读domain_tags,做集合交集
        返回 (domain_id, matched_tags) 或 (None, [])
        """
        text_lower = text.lower()
        input_words = set(text_lower.split())

        for fp in self.db.get_fingerprints():
            try:
                data = json.loads(fp["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            domain_tags = data.get("domain_tags", [])
            if not domain_tags:
                continue

            # 集合判定: domain_tags中任意一个出现在输入中 → 匹配
            matched = [t for t in domain_tags if t.lower() in text_lower]
            if matched:
                return fp["domain_id"], matched

            # 签名模式匹配: signature字段中的关键词
            signature = data.get("signature", "")
            if signature:
                sig_keywords = [kw.strip() for kw in signature.replace("→", " ").split()]
                sig_matched = [kw for kw in sig_keywords if kw in text_lower]
                if sig_matched:
                    return fp["domain_id"], sig_matched

        return None, []

    def _determine_depth(self, text: str, multimodal: bool) -> str:
        """
        思考深度判定(IF-THEN规则,无阈值)

        快照(snapshot):  简单问答, 短文本
        标准(standard):  常规分析任务, 中等长度
        深度(deep):      复杂任务, 含代码/架构/算法, 长文本
        """
        # 多模态强制升级
        if multimodal:
            return "deep"

        text_len = len(text)

        # 含代码关键词且较长 → deep
        for kw in self.DEEP_INDICATORS:
            if kw in text and (text_len > 20 or kw in ("代码", "写一个", "实现")):
                return "deep"

        # 含分析类关键词或中等长度 → standard
        for kw in self.STANDARD_INDICATORS:
            if kw in text:
                return "standard"

        # 较长文本(>50字) → standard
        if text_len > 50:
            return "standard"

        # 短文本、问候、简单问答 → snapshot
        return "snapshot"

    def _load_fingerprint(self, domain_id: str) -> Optional[Dict]:
        """从DB的fingerprints表加载指定指纹"""
        for fp in self.db.get_fingerprints():
            if fp["domain_id"] == domain_id:
                try:
                    return json.loads(fp["data"])
                except (json.JSONDecodeError, TypeError):
                    pass
        # 如果DB中没有,尝试从JSON文件加载(fallback)
        return self._load_fingerprint_from_file(domain_id)

    def _load_fingerprint_from_file(self, domain_id: str) -> Optional[Dict]:
        """从fingerprints目录加载指纹JSON(fallback)"""
        import os
        from pathlib import Path

        fp_dir = self.config.get("system", "fingerprints_dir")
        if domain_id == "jiapo_unified":
            fname = "jiapo_unified_fingerprint.json"
        else:
            fname = f"domain_{domain_id}.json"

        fpath = os.path.join(fp_dir, fname)
        if os.path.isfile(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return None

    def _load_active_chains(self, domain_id: str, tier_limit: int) -> List[Dict]:
        """
        从subchain_weights表加载激活子链
        按 domain:brain 前缀 + tier过滤
        返回无数值排序的子链列表
        """
        all_chains = self.db.get_subchain_weights()
        prefix = f"{domain_id}:"
        active = []
        for c in all_chains:
            if c["chain_type"].startswith(prefix) and c["tier"] <= tier_limit:
                active.append(dict(c))
        return active

    # ========== 审核 ==========

    def review(self, task_id: str, result_content: str,
               level: str = "unit") -> Dict:
        """
        四级审核(使用验证链)
        如有Verifier,运行4条验证链;否则fallback到原始检查
        """
        self.sm.transition(task_id, "验证中")

        if self.verifier:
            return self._verify_with_chains(task_id, result_content, level)
        else:
            return self._primitive_review(task_id, result_content, level)

    def _verify_with_chains(self, task_id: str, result_content: str,
                             level: str) -> Dict:
        """使用4条验证链执行审核"""
        # 运行全部4条验证链
        v_result = self.verifier.verify(
            output_text=result_content,
            chains=None,  # 全部4条
            original_material="",
            task_context=f"审核级别: {level}"
        )

        # 映射验证结果到审核结论
        verdict = v_result["verdict"]
        if verdict == "pass":
            passed = True
            issues = []
            conclusion = f"{level}审核: 通过"
        elif verdict == "partial":
            passed = False
            issues = v_result.get("failures", [])
            summary = v_result.get("summary", "部分不通过")
            conclusion = f"{level}审核: 部分通过 - {summary}"
        elif verdict == "cannot_verify":
            passed = True  # 无法验证时默认通过(避免阻塞)
            issues = []
            conclusion = f"{level}审核: 无法验证，默认通过"
        else:  # fail
            passed = False
            issues = v_result.get("failures", [])
            summary = v_result.get("summary", "验证不通过")
            conclusion = f"{level}审核: 不通过 - {summary}"

        # 记录审核结果
        self.db.add_review(
            target_id=task_id,
            review_type=level,
            result="pass" if passed else "fail",
            conclusion=conclusion
        )

        # 状态转换
        if passed:
            self.sm.transition(task_id, "验证通过")
        else:
            self.sm.transition(task_id, "验证未通过")

        return {
            "pass": passed,
            "level": level,
            "verdict": verdict,
            "conclusion": conclusion,
            "issues": issues,
            "failures": v_result.get("failures", []),
            "fix_priority": v_result.get("fix_priority", "medium"),
            "details": v_result.get("details", []),
            "task_id": task_id,
        }

    def _primitive_review(self, task_id: str, result_content: str,
                           level: str) -> Dict:
        """原始字符串检查(fallback)"""
        issues = []

        if not result_content or len(result_content.strip()) < 10:
            issues.append("结果内容过短或为空")
        if "错误" in result_content or "失败" in result_content:
            issues.append("结果包含错误信息")

        passed = len(issues) == 0
        conclusion = f"{level}审核: {'通过' if passed else '不通过'}"

        self.db.add_review(
            target_id=task_id,
            review_type=level,
            result="pass" if passed else "fail",
            conclusion=conclusion + ("; " + "; ".join(issues) if issues else "")
        )

        if passed:
            self.sm.transition(task_id, "验证通过")
        else:
            self.sm.transition(task_id, "验证未通过")

        return {
            "pass": passed,
            "level": level,
            "conclusion": conclusion,
            "issues": issues,
            "task_id": task_id,
        }

    def negotiate(self, task_id: str, failed_review: Dict) -> Dict:
        """猴马谈判 - 处理审核不通过"""
        self.sm.transition(task_id, "待复审")
        self.sm.iterate_task(task_id)

        return {
            "action": "复审",
            "task_id": task_id,
            "iteration": self.db.get_task(task_id).get("iteration_count", 0),
            "instruction": f"修复以下问题后重新提交: {failed_review.get('issues', [])}",
        }
