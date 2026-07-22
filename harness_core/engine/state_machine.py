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

    def validate_transition(self, task_id: str, new_state: str) -> Tuple[dict, str]:
        """校验状态转换(解析解): 从DB读取合法转换"""
        task = self.db.get_task(task_id)
        if not task:
            return {"verdict": "任务不存在"}, "任务不存在"

        old_state = task["status"]
        allowed = self._get_allowed_transitions(old_state)
        if new_state not in allowed:
            reasons = []
            if allowed:
                reasons.append("当前状态[" + old_state + "]允许转向: " + ", ".join(allowed))
                reasons.append("请求转向: " + new_state + "，不在允许列表中")
            else:
                reasons.append("当前状态[" + old_state + "]为终态，不允许转换")
            return {"verdict": "倾向性不通过", "reasoning": "；".join(reasons), "current_state": old_state, "requested": new_state}, "；".join(reasons)
        return {"verdict": "倾向性通过", "reasoning": "从[" + old_state + "]到[" + new_state + "]为合法转换", "current_state": old_state, "requested": new_state}, ""

    def _get_allowed_transitions(self, state_name: str) -> list:
        """从DB rnd_state_def 表读取合法转换"""
        import json
        conn = self.db.engine_conn()
        try:
            row = conn.execute(
                "SELECT allowed_transitions FROM rnd_state_def WHERE state_name=?", (state_name,)
            ).fetchone()
            if row:
                return json.loads(row["allowed_transitions"])
        except:
            pass
        finally:
            conn.close()
        return TRANSITIONS.get(state_name, [])

    def transition(self, task_id: str, new_state: str) -> Tuple[dict, str]:
        """执行状态转换(解析解)"""
        verdict, msg = self.validate_transition(task_id, new_state)
        if verdict.get("verdict") != "倾向性通过":
            return verdict, msg

        task = self.db.get_task(task_id)
        old_state = task["status"]
        ok = self.db.transition_state(task_id, new_state)
        if ok:
            reason = "状态转换: {} -> {}".format(old_state, new_state)
            self.db.add_review(task_id, "step", "pass", reason)
            return {"verdict": "转换成功", "reasoning": reason}, reason
        return {"verdict": "转换失败", "reasoning": "数据库更新异常"}, "状态转换失败"

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
