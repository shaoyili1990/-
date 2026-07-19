"""
后台空闲调度器 - 自治状态机
空闲20分钟 → 整理 → 等10分钟 → 巡检 → 循环

原理: 非线程,基于poll检查。每次被调用时检查时间戳,
判断当前空闲状态,需要执行的动作立即同步执行。
"""
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from ..engine import EngineDB

logger = logging.getLogger("scheduler")

# 空闲调度状态
STATE_IDLE = "idle"
STATE_MAINTENANCE = "maintenance"
STATE_WAIT_INSPECT = "wait_inspect"
STATE_INSPECT = "inspect"
STATE_ACTIVE = "active"  # 有用户任务时

# 时间参数(秒)
IDLE_TRIGGER = 20 * 60      # 20分钟空闲触发整理
WAIT_INSPECT_TIME = 10 * 60 # 整理后等10分钟再巡检
POLL_INTERVAL = 10           # 轮询间隔(秒, 与前端对齐)

# DB表名
SCHED_TABLE = "scheduler_state"
SCHED_SQL = f"""
CREATE TABLE IF NOT EXISTS {SCHED_TABLE} (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class IdleScheduler:
    """
    空闲调度器 - 自治循环:
    IDLE(20min) → MAINTENANCE → WAIT_INSPECT(10min) → INSPECT → IDLE(loop)
    """

    def __init__(self, db: EngineDB, purchaser=None, monkey=None, keeper=None):
        self.db = db
        self.purchaser = purchaser
        self.monkey = monkey
        self.keeper = keeper
        self._init_db()

    def _init_db(self):
        """初始化调度器本身到认知DB"""
        conn = self.db.cognition_conn()
        try:
            conn.executescript(SCHED_SQL)
            # 初始化状态
            defaults = {
                "state": STATE_IDLE,
                "last_active_time": "0",
                "last_maintenance_time": "0",
                "last_inspect_time": "0",
                "idle_start_time": str(time.time()),
                "wait_start_time": "0",
                "cycle_count": "0",
                "total_maintenance": "0",
                "total_inspects": "0",
            }
            for k, v in defaults.items():
                conn.execute(
                    f"INSERT OR IGNORE INTO {SCHED_TABLE} (key, value) VALUES (?, ?)",
                    (k, v)
                )
            conn.commit()
        except Exception as e:
            logger.warning(f"Scheduler init: {e}")
            conn.rollback()
        finally:
            conn.close()

    # ========== 读写状态 ==========

    def _get(self, key: str) -> str:
        conn = self.db.cognition_conn()
        try:
            r = conn.execute(f"SELECT value FROM {SCHED_TABLE} WHERE key=?", (key,)).fetchone()
            return r[0] if r else ""
        finally:
            conn.close()

    def _set(self, key: str, value: str):
        conn = self.db.cognition_conn()
        try:
            conn.execute(
                f"INSERT OR REPLACE INTO {SCHED_TABLE} (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (key, value)
            )
            conn.commit()
        finally:
            conn.close()

    def state(self) -> str:
        return self._get("state") or STATE_IDLE

    def _set_state(self, s: str):
        self._set("state", s)

    # ========== 核心：每次poll时调用 ==========

    def tick(self, has_active_task: bool = False) -> Dict:
        """
        每次poll检查,返回当前状态和最近动作记录
        has_active_task: 当前是否有用户任务在处理
        """
        now = time.time()
        state = self.state()
        result = {
            "state": state,
            "action": None,
            "action_detail": "",
            "idle_seconds": 0,
        }

        # 有活动任务 → 重置空闲计时
        if has_active_task:
            self._ping_active()
            if state != STATE_ACTIVE:
                self._set_state(STATE_ACTIVE)
                self._set("last_active_time", str(now))
            return {**result, "state": STATE_ACTIVE}

        # 刚从活动转为空闲 → 记录空闲开始时间
        if state == STATE_ACTIVE:
            self._set_state(STATE_IDLE)
            self._set("idle_start_time", str(now))
            self._set("last_active_time", str(now))
            return {**result, "state": STATE_IDLE}

        # === 正常空闲状态机 ===
        idle_start = float(self._get("idle_start_time") or "0")
        idle_secs = now - idle_start
        result["idle_seconds"] = int(idle_secs)

        if state == STATE_IDLE:
            # 空闲累计 ≥ 20分钟 → 执行整理
            if idle_secs >= IDLE_TRIGGER:
                return self._do_maintenance(now)
            return result

        elif state == STATE_MAINTENANCE:
            # 整理完成 → 进入等待巡检
            self._set_state(STATE_WAIT_INSPECT)
            self._set("wait_start_time", str(now))
            return {**result, "state": STATE_WAIT_INSPECT}

        elif state == STATE_WAIT_INSPECT:
            # 等待 ≥ 10分钟 → 执行巡检
            wait_start = float(self._get("wait_start_time") or "0")
            if now - wait_start >= WAIT_INSPECT_TIME:
                return self._do_inspect(now)
            return {**result, "state": STATE_WAIT_INSPECT,
                    "wait_remaining": int(WAIT_INSPECT_TIME - (now - wait_start))}

        elif state == STATE_INSPECT:
            # 巡检完成 → 重置空闲计时器,回到IDLE
            self._set_state(STATE_IDLE)
            self._set("idle_start_time", str(now))
            cycle = int(self._get("cycle_count") or "0") + 1
            self._set("cycle_count", str(cycle))
            return {**result, "state": STATE_IDLE, "cycle": cycle}

        return result

    def _ping_active(self):
        """标记活动状态"""
        self._set("last_active_time", str(time.time()))

    def _do_maintenance(self, now: float) -> Dict:
        """执行整理"""
        self._set_state(STATE_MAINTENANCE)

        maint_count = int(self._get("total_maintenance") or "0") + 1
        self._set("total_maintenance", str(maint_count))
        self._set("last_maintenance_time", str(now))

        actions = []
        # 调用采购员整理
        if self.purchaser:
            try:
                r = self.purchaser.organize()
                if r.get("ok"):
                    actions = r.get("actions", [])
            except Exception as e:
                logger.warning(f"Maintenance error: {e}")

        # 猴子评估空转skill
        if self.monkey and self.keeper:
            try:
                skill_check = self.monkey.evaluate_idle_skills()
                if skill_check:
                    actions.append(skill_check)
            except Exception:
                pass

        logger.info(f"[Scheduler] 整理完成, 动作: {len(actions)}")
        return {
            "state": STATE_MAINTENANCE,
            "action": "maintenance",
            "action_detail": f"整理完成, {len(actions)}项操作",
            "maintenance_count": maint_count,
            "actions": actions,
        }

    def _do_inspect(self, now: float) -> Dict:
        """执行巡检"""
        self._set_state(STATE_INSPECT)

        inspect_count = int(self._get("total_inspects") or "0") + 1
        self._set("total_inspects", str(inspect_count))
        self._set("last_inspect_time", str(now))

        updates = []
        suggestions = []

        # 采购员巡检市场
        if self.purchaser:
            try:
                updates = self.purchaser.inspect_updates()
            except Exception as e:
                logger.warning(f"Inspect error: {e}")

            # 猴子+采购员联合评估新Skill
            try:
                suggestions = self.purchaser.suggest_new_skills(self.monkey)
            except Exception:
                pass

        logger.info(f"[Scheduler] 巡检完成, 更新: {len(updates)}, 推荐: {len(suggestions)}")
        return {
            "state": STATE_INSPECT,
            "action": "inspect",
            "action_detail": f"巡检完成, {len(updates)}项更新, {len(suggestions)}项推荐",
            "inspect_count": inspect_count,
            "updates": updates,
            "suggestions": suggestions,
        }

    # ========== 三方协作入口 ==========

    def coordinate_skill(self, requirement: str, route_context: Dict) -> Dict:
        """
        猴子路由后,检查是否需要Skill支持,
        采购员搜索→猴子评估→安装→骏马使用
        返回安装结果和补充信息
        """
        if not self.purchaser or not self.monkey:
            return {"ok": False, "message": "采购员或猴子不可用"}

        # 1. 采购员搜索匹配Skill
        candidates = self.purchaser.search_by_requirement(requirement, use_ai=True)
        if not candidates:
            return {"ok": True, "found": False, "message": "无匹配Skill,使用默认能力"}

        # 2. 猴子评估是否应该安装
        best = candidates[0]
        skill_id = best["id"]

        # 检查是否已安装
        installed = self.purchaser.list_installed()
        if any(s["id"] == skill_id for s in installed):
            return {"ok": True, "found": True, "skill": best, "installed": True}

        # 猴子决策: 匹配度>阈值则自动安装
        monkey_verdict = self.monkey.evaluate_skill(requirement, best)
        if monkey_verdict.get("approve", False):
            result = self.purchaser.install(skill_id)
            if result.get("ok"):
                return {
                    "ok": True,
                    "found": True,
                    "installed": True,
                    "skill": best,
                    "message": f"✅ {best['name']} 已自动安装",
                    "reason": monkey_verdict.get("reason", ""),
                }

        return {
            "ok": True,
            "found": True,
            "installed": False,
            "skill": best,
            "message": f"发现 {best['name']}, 未被猴子批准",
        }

    def get_status(self) -> Dict:
        """调度器完整状态"""
        now = time.time()
        state = self.state()
        idle_start = float(self._get("idle_start_time") or "0")
        last_active = float(self._get("last_active_time") or "0")
        last_maint = float(self._get("last_maintenance_time") or "0")
        last_inspect = float(self._get("last_inspect_time") or "0")

        return {
            "state": state,
            "idle_seconds": int(now - idle_start) if state in (STATE_IDLE, STATE_WAIT_INSPECT) else 0,
            "idle_display": self._fmt_duration(now - idle_start),
            "last_active": self._fmt_ago(now - last_active) if last_active > 0 else "从未",
            "last_maintenance": self._fmt_ago(now - last_maint) if last_maint > 0 else "从未",
            "last_inspect": self._fmt_ago(now - last_inspect) if last_inspect > 0 else "从未",
            "cycle_count": int(self._get("cycle_count") or "0"),
            "total_maintenance": int(self._get("total_maintenance") or "0"),
            "total_inspects": int(self._get("total_inspects") or "0"),
            "next_action": self._next_action(state, idle_start, now),
        }

    def _next_action(self, state: str, idle_start: float, now: float) -> str:
        if state == STATE_IDLE:
            remaining = IDLE_TRIGGER - (now - idle_start)
            if remaining > 0:
                return f"空闲后 {self._fmt_duration(remaining)} 开始整理"
            return "即将整理"
        if state == STATE_WAIT_INSPECT:
            wait_start = float(self._get("wait_start_time") or "0")
            remaining = WAIT_INSPECT_TIME - (now - wait_start)
            return f"等待 {self._fmt_duration(max(0, remaining))} 后巡检"
        return "—"

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        if seconds < 0:
            seconds = 0
        m = int(seconds // 60)
        s = int(seconds % 60)
        if m >= 60:
            h = m // 60
            return f"{h}h{m%60}m"
        return f"{m}m{s}s" if m > 0 else f"{s}s"

    @staticmethod
    def _fmt_ago(seconds: float) -> str:
        if seconds < 60:
            return "刚刚"
        m = int(seconds // 60)
        if m < 60:
            return f"{m}分钟前"
        h = m // 60
        return f"{h}小时前"
