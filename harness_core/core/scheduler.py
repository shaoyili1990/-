"""
后台自治调度器 - 冷监督心跳状态机

核心: tick() 是唯一心跳入口,每次被调用时:
  1. 从本地多维表格(env_config)读取当前状态+时间戳
  2. 计算时间差,判断是否需要状态迁移
  3. 需要时执行动作(整理/巡检),更新状态
  4. 返回当前状态

四态循环:
  待整理 -(20分钟不活动)-> 整理中 -> 已整理待巡检 -(10分钟)-> 巡检中 -> 待整理(循环)
                ↑                        ↑                           ↑
             任务打断                 任务跳过巡检                任务结束

存储: 引擎DB的env_config表(多维表格),纯冷,零线程
"""
import json
import logging
import time
from datetime import datetime
from typing import Dict, Optional, List, TYPE_CHECKING

from ..engine import EngineDB

if TYPE_CHECKING:
    from .patrol import PatrolSystem

logger = logging.getLogger("scheduler")

# ── 四状态 ──
S_WAIT_MAINT = "待整理"
S_MAINTING = "整理中"
S_WAIT_INSPECT = "已整理待巡检"
S_INSPECTING = "巡检中"

# ── 时间参数(秒) ──
T_IDLE = 20 * 60      # 空闲20min→整理
T_WAIT_INSPECT = 10 * 60  # 10min→巡检

# ── env_config key ──
K_STATE = "sched_state"
K_TS = "sched_ts"       # 进入当前状态时的时间戳
K_M_CNT = "sched_maint_cnt"
K_I_CNT = "sched_inspect_cnt"
K_M_LAST = "sched_maint_last"
K_I_LAST = "sched_inspect_last"
K_EVENTS = "sched_events"


def _human_ts(t: float = None) -> str:
    return time.strftime("%m-%d %H:%M", time.localtime(t or time.time()))


class IdleScheduler:
    """冷监督心跳状态机"""

    DEFAULTS = {
        K_STATE: S_WAIT_MAINT,
        K_TS: str(time.time()),
        K_M_CNT: "0", K_I_CNT: "0",
        K_M_LAST: "从未", K_I_LAST: "从未",
        K_EVENTS: "[]",
    }

    def __init__(self, db: EngineDB, purchaser=None, monkey=None, patrol: 'PatrolSystem' = None):
        self.db = db
        self.purchaser = purchaser
        self.monkey = monkey
        self.patrol = patrol
        self._ensure()

    def _conn(self):
        return self.db.engine_conn()

    def _ensure(self):
        conn = self._conn()
        try:
            for k, v in self.DEFAULTS.items():
                conn.execute(
                    "INSERT OR IGNORE INTO env_config (key, value) VALUES (?, ?)", (k, v)
                )
            conn.commit()
        finally:
            conn.close()

    def _g(self, k: str) -> str:
        conn = self._conn()
        try:
            r = conn.execute("SELECT value FROM env_config WHERE key=?", (k,)).fetchone()
            return r[0] if r else self.DEFAULTS.get(k, "")
        finally:
            conn.close()

    def _s(self, k: str, v: str):
        conn = self._conn()
        try:
            conn.execute("INSERT OR REPLACE INTO env_config (key, value) VALUES (?, ?)", (k, v))
            conn.commit()
        finally:
            conn.close()

    def _add_event(self, text: str):
        raw = self._g(K_EVENTS) or "[]"
        try:
            events = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            events = []
        events.insert(0, {"t": _human_ts(), "text": text})
        self._s(K_EVENTS, json.dumps(events[:5], ensure_ascii=False))

    # ================================================================
    #  心跳入口 — tick()
    #  这是唯一的推进方法。每次前端/用户操作都会触发。
    # ================================================================

    def tick(self, has_active_task: bool = False, task_done: bool = False) -> Dict:
        """
        has_active_task: 当前有用户任务在执行
        task_done:       用户任务刚结束
        返回: {state, state_seconds, action, action_detail, ...}
        """
        now = time.time()
        state = self._g(K_STATE)
        ts = float(self._g(K_TS) or now)
        elapsed = now - ts

        r = {"state": state, "state_seconds": int(elapsed),
             "action": None, "action_detail": ""}

        # ── 冷监督关闭: 冻结所有后台自治循环 ──
        if not self.db.get_aileran_mode():
            # 有任务完成也可能需要重置,但其他自动推进全部冻结
            if task_done:
                self._s(K_STATE, S_WAIT_MAINT)
                self._s(K_TS, str(now))
                r["state"] = S_WAIT_MAINT
                r["action"] = "task_done"
                r["action_detail"] = f"任务结束→待整理(冷监督关闭,冻结)"
            else:
                r["action_detail"] = "冷监督关闭,自治循环冻结"
            # 无论是否冻结,都不主动调用 patrol.tick()
            return r
        if task_done:
            self._s(K_STATE, S_WAIT_MAINT)
            self._s(K_TS, str(now))
            r["state"] = S_WAIT_MAINT
            r["action"] = "task_done"
            r["action_detail"] = f"任务结束→待整理"
            return r

        # ── 有活跃任务 → 仅重置计时,不推进状态 ──
        if has_active_task:
            self._s(K_TS, str(now))
            return r

        # ── 无任务: 标准状态机推进 ──

        if state == S_WAIT_MAINT and elapsed >= T_IDLE:
            return self._do_maint(now)

        if state == S_MAINTING:
            return self._maint_done(now)

        if state == S_WAIT_INSPECT and elapsed >= T_WAIT_INSPECT:
            return self._do_inspect(now)

        if state == S_INSPECTING:
            return self._inspect_done(now)

        # ── 每次tick驱动巡逻系统(检查是否到1:00、执行巡逻) ──
        if self.patrol:
            try:
                self.patrol.tick()
            except Exception as e:
                logger.warning(f"[Scheduler] 巡逻异常: {e}")

        return r

    def task_incoming(self):
        """任务进来时调用。如果正在整理/巡检,让它们走完再切"""
        now = time.time()
        state = self._g(K_STATE)
        if state in (S_WAIT_MAINT, S_WAIT_INSPECT):
            # 空闲/等待态: 直接重置空闲计时
            self._s(K_TS, str(now))
        # 整理中/巡检中: 什么也不做,等它们自然完成

    def task_done(self):
        """任务结束 → 回到待整理"""
        return self.tick(task_done=True)

    # ── 内部: 状态转换 ──

    def _do_maint(self, now: float) -> Dict:
        state = self._g(K_STATE)
        self._s(K_STATE, S_MAINTING)
        self._s(K_TS, str(now))
        cnt = int(self._g(K_M_CNT) or "0") + 1
        self._s(K_M_CNT, str(cnt))
        self._s(K_M_LAST, _human_ts(now))

        acts = []
        if self.purchaser:
            try:
                r = self.purchaser.organize()
                if r.get("ok"):
                    acts.extend(r.get("actions", []))
            except Exception as e:
                logger.warning(f"[Sched] 整理异常: {e}")
        if self.monkey:
            try:
                ck = self.monkey.evaluate_idle_skills()
                if ck:
                    acts.append(ck)
            except Exception:
                pass

        msg = f"整理完成({len(acts)}项)" if acts else "整理完成(无操作)"
        self._add_event(msg)
        return {"state": S_MAINTING, "state_seconds": 0,
                "action": "maintenance", "action_detail": msg}

    def _maint_done(self, now: float) -> Dict:
        self._s(K_STATE, S_WAIT_INSPECT)
        self._s(K_TS, str(now))
        self._add_event("→已整理待巡检")
        return {"state": S_WAIT_INSPECT, "state_seconds": 0,
                "action": "maint_done", "action_detail": "整理完成,等待10分钟后巡检"}

    def _do_inspect(self, now: float) -> Dict:
        self._s(K_STATE, S_INSPECTING)
        self._s(K_TS, str(now))
        cnt = int(self._g(K_I_CNT) or "0") + 1
        self._s(K_I_CNT, str(cnt))
        self._s(K_I_LAST, _human_ts(now))

        updates = []
        if self.purchaser:
            try:
                updates = self.purchaser.inspect_updates()
            except Exception as e:
                logger.warning(f"[Sched] 巡检异常: {e}")
            try:
                self.purchaser.suggest_new_skills(self.monkey)
            except Exception:
                pass

        msg = f"巡检完成({len(updates)}项更新)" if updates else "巡检完成(无更新)"
        self._add_event(msg)
        return {"state": S_INSPECTING, "state_seconds": 0,
                "action": "inspect", "action_detail": msg}

    def _inspect_done(self, now: float) -> Dict:
        self._s(K_STATE, S_WAIT_MAINT)
        self._s(K_TS, str(now))
        cnt = self._g(K_M_CNT) or "0"
        self._add_event(f"→待整理(第{cnt}轮)")
        return {"state": S_WAIT_MAINT, "state_seconds": 0,
                "action": "cycle", "action_detail": f"巡检完成→待整理(第{cnt}轮)"}

    # ================================================================
    #  查询
    # ================================================================

    def get_status(self) -> Dict:
        now = time.time()
        state = self._g(K_STATE)
        ts = float(self._g(K_TS) or now)
        elapsed = now - ts

        remain = 0
        if state == S_WAIT_MAINT:
            remain = max(0, T_IDLE - elapsed)
        elif state == S_WAIT_INSPECT:
            remain = max(0, T_WAIT_INSPECT - elapsed)
        elif state == S_MAINTING:
            remain = 0  # 正在整理
        elif state == S_INSPECTING:
            remain = 0  # 正在巡检

        try:
            events = json.loads(self._g(K_EVENTS) or "[]")
        except (json.JSONDecodeError, TypeError):
            events = []

        return {
            "state": state,
            "elapsed_seconds": int(elapsed),
            "remaining_seconds": int(remain),
            "idle_display": f"{int(elapsed//60)}m{int(elapsed%60)}s",
            "last_maintenance": self._g(K_M_LAST),
            "last_inspect": self._g(K_I_LAST),
            "maintenance_count": int(self._g(K_M_CNT) or "0"),
            "inspect_count": int(self._g(K_I_CNT) or "0"),
            "events": events,
        }

    def coordinate_skill(self, user_input: str, route: Dict) -> Optional[Dict]:
        """
        猴购协奏: 用户输入进入后,采购员搜索匹配Skill,
        猴子评估是否值得安装,自动判断
        """
        if not self.purchaser or not self.monkey:
            return None

        # 用猴子的路由信息判断是否需要Skill
        domain = route.get("domain")
        depth = route.get("depth", "snapshot")

        # snapshot不需要额外Skill
        if depth == "snapshot":
            return None

        try:
            candidates = self.purchaser.search_by_requirement(user_input, use_ai=False)
            if not candidates:
                return None

            approved = []
            for c in candidates[:3]:
                eval_result = self.monkey.evaluate_skill(user_input, c)
                if eval_result.get("approve"):
                    # 自动安装
                    r = self.purchaser.install(c["id"])
                    if r.get("ok"):
                        approved.append({"id": c["id"], "name": c["name"],
                                         "icon": c.get("icon", "📦")})
            if approved:
                self._add_event(f"猴购协奏: 自动安装{','.join(a['name'] for a in approved)}")
                return {"installed": approved}
        except Exception as e:
            logger.warning(f"[Sched] coordinate_skill: {e}")

        return None

    def mark_idle_now(self):
        """标记立刻空闲(用于测试)"""
        self._s(K_STATE, S_WAIT_MAINT)
        self._s(K_TS, str(time.time()))
