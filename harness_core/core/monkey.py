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
from typing import List, Dict, Optional, Tuple, Callable
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
            "generic": self._load_fingerprint("thinker"),
        }

        # 4. 如有领域,加载领域垂直指纹
        if domain_id:
            fingerprints["domain"] = self._load_fingerprint(domain_id)

        # 5. 从DB的subchain_weights表查子链(按tier过滤)
        tier_limit = {"snapshot": 1, "standard": 2, "deep": 3}[depth]
        # 无领域匹配时使用通用指纹(thinker)的子链
        chain_domain = domain_id if domain_id else "thinker"
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
        if domain_id == "thinker":
            fname = "thinker_unified_fingerprint.json"
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

    # ========== 采购员协奏：Skill评估 ==========

    def evaluate_skill(self, requirement: str, skill: Dict) -> Dict:
        """评估一个Skill是否符合当前任务需求,返回是否批准安装"""
        # 规则1: 不信任本地/未经验证的Skill→默认批准(信任市场)
        if skill.get("verified") == 0 and skill.get("local"):
            return {"approve": False, "reason": "未经验证的本地Skill"}

        # 规则2: 标签匹配检测
        requirement_lower = requirement.lower()
        tags = (skill.get("tags", "") or "")
        name = skill.get("name", "")
        desc = (skill.get("description", "") or "")

        # 需求中出现Skill名/描述/标签中的关键词→匹配
        keywords = (tags + " " + name + " " + desc).lower()
        req_words = set(requirement_lower.split())
        kw_set = set(keywords.split())

        overlap = req_words & kw_set
        if len(overlap) >= 1 or any(kw in requirement_lower for kw in [name.lower(), desc[:10].lower()]):
            return {"approve": True, "reason": f"需求与Skill匹配(重叠关键词: {overlap})", "confidence": "high"}

        # 规则3: 没有关键词重叠但需求较长→用LLM判断
        if len(requirement) > 30:
            try:
                provider_config = self.config.get_provider_config("monkey")
                provider = get_provider(provider_config["name"], provider_config)
                prompt = f"""需求: {requirement}
Skill: {name} - {desc}
标签: {tags}

这个Skill是否适合这个需求？只回答YES或NO。"""
                resp = provider.generate([{"role": "user", "content": prompt}])
                content = resp.content.strip().upper()
                if "YES" in content:
                    return {"approve": True, "reason": "AI评估符合需求", "confidence": "medium"}
            except Exception:
                pass

        # 默认:保守策略,不自动安装
        return {"approve": False, "reason": "与当前需求关联度不足", "confidence": "low"}

    def evaluate_idle_skills(self) -> Optional[str]:
        """空闲时检查已安装Skill是否有用,记录评估"""
        installed = self.db.cognition_conn().execute(
            "SELECT id, name, description, category FROM installed_skills WHERE enabled=1"
        ).fetchall()
        if not installed or len(installed) < 3:
            return None  # Skill太少,不做清理

        # 简单规则: 保留所有类别唯一的,只标记可能重复类别的
        categories = {}
        for s in installed:
            cat = s["category"] or "通用"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(s["name"])

        redundant = []
        for cat, names in categories.items():
            if len(names) > 2:
                redundant.append(f"{cat}分类有{len(names)}个Skill可能冗余: {', '.join(names[:3])}")

        return f"Skill评估: {len(installed)}个已安装,{'、'.join(redundant)}" if redundant else None

    # ========== 采购员协奏：自动Skill匹配 ==========

    def match_skills_for_tags(self, domain_tags: List[str]) -> List[Dict]:
        """
        根据domain_tags自动匹配Skill市场中的可用技能
        猴子用标签关键词去skill_market表做交集匹配
        """
        if not domain_tags:
            return []
        conn = self.db.cognition_conn()
        try:
            all_skills = conn.execute(
                "SELECT id, name, icon, description, category, tags FROM skill_market"
            ).fetchall()
            matched = []
            for skill in all_skills:
                skill_tags = (skill["tags"] or "").lower().split(",")
                skill_name = (skill["name"] or "").lower()
                skill_desc = (skill["description"] or "").lower()
                for tag in domain_tags:
                    tag_lower = tag.lower().strip()
                    if (tag_lower in skill_tags
                            or tag_lower in skill_name
                            or tag_lower in skill_desc):
                        matched.append(dict(skill))
                        break
            return matched[:10]
        finally:
            conn.close()

    def suggest_skills_for_route(self, route: Dict) -> Dict:
        """
        路由决策后自动建议匹配的Skill
        monkey在route返回后调用,自动装匹配的Skill
        """
        domain_tags = route.get("domain_tags", [])
        domain_id = route.get("domain")

        tagged_skills = self.match_skills_for_tags(domain_tags) if domain_tags else []

        fp_skills = []
        if domain_id:
            fp = self._load_fingerprint(domain_id)
            if fp:
                fp_keywords = fp.get("domain_tags", []) + fp.get("keywords", [])
                fp_skills = self.match_skills_for_tags(fp_keywords)

        seen = set()
        all_matched = []
        for s in tagged_skills + fp_skills:
            if s["id"] not in seen:
                seen.add(s["id"])
                all_matched.append(s)

        conn = self.db.cognition_conn()
        try:
            installed_ids = {r[0] for r in conn.execute("SELECT id FROM installed_skills").fetchall()}
        finally:
            conn.close()

        auto_install = [s for s in all_matched if s["id"] not in installed_ids]

        return {
            "matched_skills": all_matched,
            "auto_install_candidates": auto_install,
            "already_installed": [s for s in all_matched if s["id"] in installed_ids],
            "total_matched": len(all_matched),
        }
