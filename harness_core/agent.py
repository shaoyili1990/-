"""
Monkey Harness Agent - 主编排器
整合四角色: 灵猴 + 骏马 + 司库 + 书童
固定流程: 猴子管马，司库状态驱动，书童记忆存取
"""

import os
import json
import uuid
from typing import List, Dict, Optional, Generator, Union
from .config import Config, load_config
from .engine import EngineDB, seed_engine_db, seed_fingerprints
from .engine.state_machine import StateMachine
from .engine.subchain import SubchainScheduler
from .core import Monkey, Horse, Purchaser, Keeper, Scribe, Verifier
from .core.scheduler import IdleScheduler
from .core.patrol import PatrolSystem
from .providers import get_provider, ProviderRegistry


class HarnessAgent:
    """Monkey Harness Agent 主编排器"""

    def __init__(self, config_path: Optional[str] = None, **config_overrides):
        self.config = load_config(config_path, **config_overrides)
        self.db = EngineDB(
            engine_path=self.config.get("keeper", "db_path"),
            cognition_path=self.config.get("scribe", "db_path"),
        )
        self.state_machine = StateMachine(self.db)
        self.subchain = SubchainScheduler(
            subchains_dir=self.config.get("system", "subchains_dir"),
            db=self.db,
        )

        # ===== 填充多维表格 =====
        seed_engine_db(self.db)

        fingerprints_dir = self.config.get("system", "fingerprints_dir")
        seed_fingerprints(self.db, fingerprints_dir)

        # ===== 初始化五角色 + 质检官 =====
        self.verifier = Verifier(self.config, self.db)
        self.monkey = Monkey(self.config, self.db, self.state_machine, verifier=self.verifier)
        self.horse = Horse(self.config, self.db, self.state_machine, self.subchain)
        self.purchaser = Purchaser(self.config, self.db)
        self.keeper = Keeper(self.config, self.db)
        self.scribe = Scribe(self.config, self.db)

        # ===== 多门类巡检系统(每日1:00自治巡逻) =====
        self.patrol = PatrolSystem(
            db=self.db,
            agent=self,
            monkey=self.monkey,
            purchaser=self.purchaser,
        )

        # ===== 后台空闲调度器(自治循环) =====
        self.scheduler = IdleScheduler(
            db=self.db,
            purchaser=self.purchaser,
            monkey=self.monkey,
            patrol=self.patrol,
        )

    # ========== 主流程 ==========

    def _is_aileran_mode(self) -> bool:
        """冷监督模式: 开启则允许自治后台循环(scheduler/patrol)，关闭则冻结"""
        return self.db.get_aileran_mode()

    def run(self, user_input: str, images: Optional[List[str]] = None,
            stream: bool = False, task_id: Optional[str] = None):
        """
        完整执行流程:
        灵猴路由 -> 采购员补充Skill -> 骏马执行 -> 司库状态 -> 书童记忆
        """
        # 通知调度器: 任务进来了
        self.scheduler.task_incoming()

        # 1. 书童构建上下文
        context = self.scribe.build_context(task_id or "new", user_input)

        # 2. 灵猴路由决策
        route = self.monkey.route(user_input, multimodal=bool(images))

        # 3. 三方协奏：猴子路由后检查是否需要Skill
        skill_support = {}
        matched_skills = self.monkey.suggest_skills_for_route(route) if route.get("domain_tags") else {}
        if matched_skills and matched_skills.get("auto_install_candidates"):
            for skill in matched_skills["auto_install_candidates"]:
                try:
                    self.purchaser.install(skill["id"])
                    skill_support.setdefault("installed", []).append(skill["name"])
                except Exception:
                    pass

        route["skill_support"] = {
            "matched": matched_skills.get("total_matched", 0),
            "installed_during_route": skill_support.get("installed", []),
        }

        # 4. 司库状态转换
        self.keeper.transition(route["task_id"], "待执行")

        # 5. 骏马执行
        if stream:
            return self._stream_execute(route, user_input, images)
        else:
            return self._sync_execute(route, user_input, images)

    def _sync_execute(self, route: Dict, user_input: str,
                      images: Optional[List[str]] = None) -> Dict:
        """同步执行 — 含双路径收敛(多路径推理)"""
        # ────────── 第一次执行 ──────────
        result = self.horse.execute(route, user_input, images)

        # 提取结果文本
        if isinstance(result, dict):
            result_text = json.dumps(result, ensure_ascii=False)
            final_output = result.get("04-结果", result_text)
        else:
            result_text = str(result)
            final_output = result_text

        # ────────── 灵猴审核 ──────────
        review = self.monkey.review(route["task_id"], final_output, "unit")

        # ────────── 通过→直接返回 ──────────
        if review["pass"]:
            self.keeper.transition(route["task_id"], "验证通过")
            self.scribe.record_chat(route["task_id"], "user", user_input)
            self.scribe.record_chat(route["task_id"], "assistant", final_output)
            self.scheduler.task_done()
            return {
                "task_id": route["task_id"],
                "route": route,
                "result": result,
                "final_output": final_output,
                "review": review,
                "status": "complete",
                "path": "single",
            }

        # ────────── 不通过→双路径收敛 ──────────
        failures = review.get("failures", review.get("issues", []))
        fix_msgs = []
        for f in failures:
            if isinstance(f, dict):
                item = f.get("item", f.get("reason", str(f)))
                fix = f.get("fix", "")
                fix_msgs.append(f"{item}" + (f" → {fix}" if fix else ""))
            else:
                fix_msgs.append(str(f))
        instruction = "修复以下问题后重新提交: " + "; ".join(fix_msgs) if fix_msgs else "修复后重新提交"

        negotiate = self.monkey.negotiate(route["task_id"], review)

        # ── 路径A: 基于修复指令重试(当前行为) ──
        route_a = dict(route)
        retry_ctx_a = {
            "previous_review": review.get("verdict", "fail"),
            "fix_instruction": instruction,
            "failures": failures,
        }
        route_a["retry_context"] = retry_ctx_a
        result_a = self.horse.execute(route_a, user_input, images)
        output_a = result_a.get("04-结果", json.dumps(result_a, ensure_ascii=False)) if isinstance(result_a, dict) else str(result_a)
        review_a = self.monkey.review(route["task_id"], output_a, "whole")

        # ── 路径B: 从零重新推理(新鲜路径) ──
        route_b = dict(route)
        # 不加 retry_context,让horse完全重新推理
        # 但传审核失败作为附加上下文让推理方向更有针对性
        route_b["retry_context"] = {
            "previous_review": review.get("verdict", "fail"),
            "fix_instruction": f"上一次审核未通过。请从零开始重新推理,避免上述问题:\n{instruction}",
            "failures": failures,
            "fresh_start": True,  # horse 识别这个标记走新鲜路径
        }
        result_b = self.horse.execute(route_b, user_input, images)
        output_b = result_b.get("04-结果", json.dumps(result_b, ensure_ascii=False)) if isinstance(result_b, dict) else str(result_b)
        review_b = self.monkey.review(route["task_id"], output_b, "whole")

        # ── 双路径收敛: 选择更好的结果 ──
        if review_a["pass"] and not review_b["pass"]:
            chosen = "path_a"
            final_output = output_a
            review = review_a
        elif review_b["pass"] and not review_a["pass"]:
            chosen = "path_b"
            final_output = output_b
            review = review_b
        elif review_a["pass"] and review_b["pass"]:
            # 都通过 → 选验证更好的(失败项更少)
            chosen = "path_a"
            final_output = output_a
            review = review_a
            if len(review_b.get("failures", [])) < len(review_a.get("failures", [])):
                chosen = "path_b"
                final_output = output_b
                review = review_b
        else:
            # 都未通过 → 选失败更少的
            chosen = "path_a"
            final_output = output_a
            review = review_a
            if len(review_b.get("failures", [])) < len(review_a.get("failures", [])):
                chosen = "path_b"
                final_output = output_b
                review = review_b

        # 司库最终状态
        if review["pass"]:
            self.keeper.transition(route["task_id"], "验证通过")
        else:
            self.keeper.transition(route["task_id"], "验证未通过")

        # 书童记录
        self.scribe.record_chat(route["task_id"], "user", user_input)
        self.scribe.record_chat(route["task_id"], "assistant", final_output)

        # 任务结束
        self.scheduler.task_done()

        return {
            "task_id": route["task_id"],
            "route": route,
            "result": result,
            "final_output": final_output,
            "review": review,
            "status": "complete",
            "path": chosen,
            "path_a_passed": review_a["pass"],
            "path_b_passed": review_b["pass"],
        }

    def _stream_execute(self, route: Dict, user_input: str,
                        images: Optional[List[str]] = None):
        """流式执行"""
        yield from self.horse.execute(route, user_input, images, stream=True)

    # ========== 快捷方法 ==========

    def chat(self, message: str) -> str:
        """简单对话"""
        result = self.run(message)
        if isinstance(result, dict):
            return result.get("final_output", str(result))
        return str(result)

    def ask(self, message: str, images: Optional[List[str]] = None) -> Dict:
        """完整问答(返回结构化结果)"""
        return self.run(message, images)

    def develop(self, concept: str, iterations: int = 5) -> List[Dict]:
        """开发模式: 构思 + 迭代优化"""
        results = []

        # 创建主任务
        task = self.keeper.create_task(concept[:50], level="whole")
        task_id = task["task_id"]

        # 初始构思
        r1 = self.run(f"提供构思大纲: {concept}", task_id=task_id)
        results.append(r1)

        # 迭代优化
        for i in range(iterations):
            self.keeper.iterate(task_id)
            r = self.run(
                f"第{i+1}次迭代优化，基于前序结果改进: {concept}",
                task_id=task_id
            )
            results.append(r)

        return results

    # ========== 系统信息 ==========

    def get_status(self) -> Dict:
        """获取系统状态(触发一次心跳)"""
        tasks = self.db.list_tasks(limit=10)
        has_active = any(t.get("status") in ("待执行", "执行完成待验证", "验证中") for t in tasks)
        sched_state = self.scheduler.tick(has_active_task=has_active)
        
        # 巡逻系统tick驱动(检查是否到1:00)
        patrol_state = self.patrol.tick()
        
        stats = self.subchain.get_statistics()
        validation_chains = self.verifier.get_chain_info()
        return {
            "version": "0.1.0",
            "tasks_total": len(tasks),
            "chain_stats": stats,
            "validation_chains": validation_chains,
            "monkey_provider": self.config.get("monkey", "provider"),
            "horse_provider": self.config.get("horse", "provider"),
            "scheduler": sched_state,
            "scheduler_detail": self.scheduler.get_status(),
            "patrol": patrol_state,
            "patrol_status": self.patrol.get_status(),
        }

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        return self.keeper.get_status(task_id)
