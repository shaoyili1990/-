"""
司库(Keeper) - 宪法与流程守护者
职责: 驱动状态机、管理任务生命周期、版本控制、宪法执行
"""

import json
from typing import List, Dict, Optional
from ..config import Config
from ..engine import EngineDB
from ..engine.state_machine import StateMachine


# 绝对宪法8条
CONSTITUTION = [
    "解析解原则: 所有决策使用可能性/倾向性/合理性，禁止二元判",
    "136子链原则: 所有推理必须基于136条子链模板",
    "多维表格=本体: SQLite表存储一切，表即Agent的大脑",
    "一表一人: 每个用户绝对私有，换表即换人",
    "版本不覆盖: 旧版本永不删除，可精确回滚到任意版本",
    "迭代传上下文: 每次迭代传递完整上下文，不丢失信息",
    "对齐甲方: 以甲方需求为最终标准，不全员对齐",
    "孤证不立: 单一证据不能作为结论依据，需要交叉验证",
]


class Keeper:
    """司库 - 宪法与流程守护者"""

    def __init__(self, config: Config, db: EngineDB):
        self.config = config
        self.db = db
        self.state_machine = StateMachine(db)
        self._ensure_constitution()

    def _ensure_constitution(self):
        """确保宪法已写入数据库"""
        conn = self.db.engine_conn()
        try:
            existing = conn.execute("SELECT COUNT(*) FROM rnd_constitution").fetchone()[0]
            if existing == 0:
                for i, article in enumerate(CONSTITUTION):
                    conn.execute(
                        "INSERT INTO rnd_constitution (name, content, version) VALUES (?, ?, 1)",
                        (f"宪法第{i+1}条", article)
                    )
                conn.commit()
        finally:
            conn.close()

    def get_constitution(self) -> List[Dict]:
        """获取宪法"""
        conn = self.db.engine_conn()
        try:
            rows = conn.execute("SELECT * FROM rnd_constitution ORDER BY id").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def enforce_constitution(self, action: str, context: Dict) -> Dict:
        """宪法执行检查"""
        violations = []
        for article in CONSTITUTION:
            if "解析解" in article and action in ("judge_binary", "numeric_score"):
                violations.append(f"违反宪法: {article}")
            if "版本不覆盖" in article and context.get("delete_old_version"):
                violations.append(f"违反宪法: {article}")
            if "孤证不立" in article and context.get("single_evidence"):
                violations.append(f"违反宪法: {article}")

        return {
            "pass": len(violations) == 0,
            "violations": violations,
            "action": action,
        }

    def create_task(self, name: str, level: str = "unit",
                    parent_id: str = "") -> Dict:
        """创建任务 - 司库管理任务生命周期"""
        import uuid
        task_id = f"t-{uuid.uuid4().hex[:12]}"
        ok = self.state_machine.create_task_flow(task_id, name, level, parent_id)
        if ok:
            self.db.record_chat(task_id, "system", f"任务创建: {name}", task_id)
        return {
            "task_id": task_id,
            "name": name,
            "level": level,
            "status": "待构思",
            "created": ok,
        }

    def transition(self, task_id: str, to_state: str) -> Dict:
        """驱动状态转换"""
        valid, msg = self.state_machine.validate_transition(task_id, to_state)
        if not valid:
            return {"success": False, "error": msg}

        ok = self.state_machine.transition(task_id, to_state)
        if ok:
            self.db.record_chat(task_id, "system",
                                f"状态转换: -> {to_state}", task_id)
        return {"success": ok, "task_id": task_id, "to_state": to_state}

    def get_status(self, task_id: str) -> Optional[Dict]:
        """获取任务完整状态"""
        return self.state_machine.get_task_status_summary(task_id)

    def list_tasks(self, status: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """列出任务"""
        return self.db.list_tasks(status=status, limit=limit)

    def iterate(self, task_id: str) -> bool:
        """递增迭代"""
        return self.state_machine.iterate_task(task_id)

    def save_version(self, task_id: str, version_data: Dict) -> Dict:
        """保存版本记录"""
        self.iterate(task_id)
        version_info = {
            "task_id": task_id,
            "iteration": self.db.get_task(task_id).get("iteration_count", 0),
            "data": version_data,
            "timestamp": "now",
        }
        self.db.save_memory(f"version-{task_id}",
                            f"v{version_info['iteration']}",
                            json.dumps(version_data, ensure_ascii=False))
        return version_info
