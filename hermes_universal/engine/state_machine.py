"""
9状态状态机 - 任务生命周期管理
固定流程: 猴子管马, 司库驱动状态
"""

import json
from typing import List, Dict, Optional, Tuple
from . import EngineDB


# 9状态定义 (与rnd_engine.db同步)
STATES = [
    ("待构思", 1, "任务初始状态，等待构思"),
    ("构思完成待执行", 2, "构思完成，等待马执行"),
    ("待执行", 3, "马正在执行任务"),
    ("执行完成待验证", 4, "执行完成，等待猴子验证"),
    ("验证中", 5, "猴子正在进行四级审核"),
    ("验证通过", 6, "审核通过，可继续下一步"),
    ("验证未通过", 7, "审核未通过，需要修改"),
    ("待复审", 8, "需要猴和马谈判复审"),
    ("待复查", 9, "最终复查"),
]

# 合法转换表
TRANSITIONS = {
    "待构思": ["构思完成待执行"],
    "构思完成待执行": ["待执行"],
    "待执行": ["执行完成待验证"],
    "执行完成待验证": ["验证中"],
    "验证中": ["验证通过", "验证未通过"],
    "验证通过": ["构思完成待执行", "待执行", "已验证"],
    "验证未通过": ["待执行", "待复审"],
    "待复审": ["待执行", "验证通过", "待复查"],
    "待复查": ["待执行", "验证通过"],
}


class StateMachine:
    """9状态状态机 - 司库核心"""

    def __init__(self, db: EngineDB):
        self.db = db
        self._ensure_states()

    def _ensure_states(self):
        """确保状态定义已初始化"""
        conn = self.db.engine_conn()
        try:
            existing = conn.execute("SELECT COUNT(*) FROM rnd_state_def").fetchone()[0]
            if existing == 0:
                for name, order, desc in STATES:
                    allowed = json.dumps(TRANSITIONS.get(name, []), ensure_ascii=False)
                    conn.execute(
                        "INSERT INTO rnd_state_def (state_name, state_order, description, allowed_transitions) VALUES (?, ?, ?, ?)",
                        (name, order, desc, allowed)
                    )
                conn.commit()
        finally:
            conn.close()

    def get_all_states(self) -> List[Dict]:
        """获取所有状态定义"""
        conn = self.db.engine_conn()
        try:
            rows = conn.execute("SELECT * FROM rnd_state_def ORDER BY state_order").fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["allowed_transitions"] = json.loads(d.get("allowed_transitions", "[]"))
                result.append(d)
            return result
        finally:
            conn.close()

    def validate_transition(self, task_id: str, new_state: str) -> Tuple[bool, str]:
        """校验状态转换是否合法"""
        task = self.db.get_task(task_id)
        if not task:
            return False, "任务不存在"

        old_state = task["status"]
        allowed = TRANSITIONS.get(old_state, [])
        if new_state not in allowed:
            return False, f"非法转换: {old_state} -> {new_state} (允许: {allowed})"
        return True, ""

    def transition(self, task_id: str, new_state: str) -> Tuple[bool, str]:
        """执行状态转换"""
        valid, msg = self.validate_transition(task_id, new_state)
        if not valid:
            return False, msg

        task = self.db.get_task(task_id)
        old_state = task["status"]
        ok = self.db.transition_state(task_id, new_state)
        if ok:
            self.db.add_review(task_id, "step", "pass",
                               f"状态转换: {old_state} -> {new_state}")
            return True, f"{old_state} -> {new_state}"
        return False, "状态转换失败"

    def get_task_status_summary(self, task_id: str) -> Optional[Dict]:
        """获取任务完整状态摘要"""
        task = self.db.get_task(task_id)
        if not task:
            return None

        conn = self.db.engine_conn()
        try:
            steps = [dict(r) for r in conn.execute(
                "SELECT * FROM rnd_steps WHERE task_id=? ORDER BY step_order", (task_id,)
            ).fetchall()]
            reviews = [dict(r) for r in conn.execute(
                "SELECT * FROM rnd_reviews WHERE target_id=? ORDER BY created_at", (task_id,)
            ).fetchall()]
        finally:
            conn.close()

        return {
            "task": task,
            "steps": steps,
            "reviews": reviews,
            "current_state": task["status"],
            "allowed_transitions": TRANSITIONS.get(task["status"], []),
            "step_count": len(steps),
            "review_count": len(reviews),
        }

    def create_task_flow(self, task_id: str, name: str, level: str = "unit",
                         parent_id: str = "") -> bool:
        """创建新任务并初始化状态"""
        return self.db.create_task(task_id, name, level, parent_id, "待构思")

    def iterate_task(self, task_id: str) -> bool:
        """递增迭代版本号"""
        task = self.db.get_task(task_id)
        if not task:
            return False
        new_count = (task.get("iteration_count", 0) or 0) + 1
        return self.db.update_task(task_id, iteration_count=new_count)
