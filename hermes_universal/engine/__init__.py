"""
引擎数据库 - 本地多维表格系统
核心: SQLite表即本体, 存储一切状态
"""
import sqlite3
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

SCHEMA_SQL = """
-- ========== 引擎数据库 (rnd_engine.db) ==========

-- 宪法定义
CREATE TABLE IF NOT EXISTS rnd_constitution (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '研发宪法',
    content TEXT NOT NULL DEFAULT '',
    category TEXT DEFAULT 'flow',
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 状态定义 (9状态)
CREATE TABLE IF NOT EXISTS rnd_state_def (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state_name TEXT NOT NULL UNIQUE,
    state_order INTEGER NOT NULL,
    description TEXT DEFAULT '',
    allowed_transitions TEXT DEFAULT '[]',
    trigger TEXT DEFAULT '',
    context_requirement TEXT DEFAULT '',
    rules TEXT DEFAULT '{}'
);

-- 步骤定义 (4步)
CREATE TABLE IF NOT EXISTS rnd_step_def (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_name TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    doc_name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    supervisor_required INTEGER DEFAULT 0,
    initially_empty INTEGER DEFAULT 0,
    context TEXT DEFAULT ''
);

-- 审核级别定义
CREATE TABLE IF NOT EXISTS rnd_review_def (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level_name TEXT NOT NULL,
    description TEXT DEFAULT '',
    check_item TEXT DEFAULT '',
    precondition TEXT DEFAULT ''
);

-- 任务表
CREATE TABLE IF NOT EXISTS rnd_tasks (
    task_id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    level TEXT NOT NULL DEFAULT 'unit',
    parent_id TEXT DEFAULT '',
    status TEXT DEFAULT '待构思',
    prd_ref TEXT DEFAULT '',
    goal_ref TEXT DEFAULT '',
    iteration_count INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 步骤记录表
CREATE TABLE IF NOT EXISTS rnd_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    doc_path TEXT DEFAULT '',
    status TEXT DEFAULT '待执行',
    supervisor_approved INTEGER DEFAULT 0,
    supervisor_comment TEXT DEFAULT '',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES rnd_tasks(task_id)
);

-- 审核记录表
CREATE TABLE IF NOT EXISTS rnd_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_type TEXT NOT NULL CHECK(review_type IN ('step','unit','phase','whole')),
    target_id TEXT NOT NULL,
    result TEXT DEFAULT '待审核',
    conclusion TEXT DEFAULT '',
    negotiation_log TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 初始流程定义
CREATE TABLE IF NOT EXISTS rnd_init_flow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_order INTEGER NOT NULL,
    action TEXT NOT NULL,
    condition_notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 依赖追踪
CREATE TABLE IF NOT EXISTS rnd_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT DEFAULT '',
    version TEXT DEFAULT '',
    url TEXT DEFAULT '',
    md5 TEXT DEFAULT '',
    target_path TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    deploy_cmd TEXT DEFAULT ''
);

-- ========== 认知数据库 (hermes.db) ==========

-- API凭证存储
CREATE TABLE IF NOT EXISTS api_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    vendor TEXT DEFAULT '',
    base_url TEXT DEFAULT '',
    model TEXT DEFAULT '',
    key_value TEXT DEFAULT '',
    is_test INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 环境配置
CREATE TABLE IF NOT EXISTS env_config (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT '',
    platform TEXT DEFAULT ''
);

-- 会话记录
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    combo_id TEXT NOT NULL,
    fingerprint_name TEXT DEFAULT '',
    subchains TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 指纹数据
CREATE TABLE IF NOT EXISTS fingerprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    domain_id TEXT DEFAULT '',
    source TEXT DEFAULT '',
    stats TEXT DEFAULT '{}',
    data TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, domain_id)
);

-- 子链权重
CREATE TABLE IF NOT EXISTS subchain_weights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_type TEXT NOT NULL,
    subchain_name TEXT NOT NULL,
    weight REAL DEFAULT 0.0,
    tier INTEGER DEFAULT 5,
    usage_count INTEGER DEFAULT 0,
    UNIQUE(chain_type, subchain_name)
);

-- 记忆库
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    combo_id TEXT NOT NULL,
    task TEXT NOT NULL,
    content TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 认知聊天记录
CREATE TABLE IF NOT EXISTS cognition_chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT DEFAULT '',
    task_id TEXT DEFAULT '',
    metadata TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 认知档案
CREATE TABLE IF NOT EXISTS cognition_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_type TEXT NOT NULL,
    summary TEXT DEFAULT '',
    keywords TEXT DEFAULT '',
    data TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 错误记忆
CREATE TABLE IF NOT EXISTS error_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    error_type TEXT NOT NULL,
    error_detail TEXT DEFAULT '',
    context TEXT DEFAULT '',
    fix TEXT DEFAULT '',
    repeat_count INTEGER DEFAULT 0,
    is_forbidden INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 知识库
CREATE TABLE IF NOT EXISTS material_knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    category TEXT DEFAULT '',
    content TEXT DEFAULT '',
    confidence REAL DEFAULT 0.5,
    needs_supplement INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 偏好库
CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pref_type TEXT NOT NULL,
    pref_desc TEXT DEFAULT '',
    source TEXT DEFAULT '',
    strength REAL DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 经验库
CREATE TABLE IF NOT EXISTS experience (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exp_type TEXT NOT NULL,
    exp_desc TEXT DEFAULT '',
    context TEXT DEFAULT '',
    analysis TEXT DEFAULT '',
    actionable_insight TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 行为准则
CREATE TABLE IF NOT EXISTS conduct_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule TEXT NOT NULL,
    reason TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 核心清单
CREATE TABLE IF NOT EXISTS core_manifest (
    doc_id TEXT PRIMARY KEY,
    category TEXT DEFAULT '',
    file_path TEXT DEFAULT '',
    content_hash TEXT DEFAULT '',
    status TEXT DEFAULT 'normal',
    platform TEXT DEFAULT ''
);

-- 提供者配置
CREATE TABLE IF NOT EXISTS api_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT DEFAULT '',
    base_url TEXT DEFAULT '',
    model TEXT DEFAULT '',
    params_json TEXT DEFAULT '{}'
);
"""


class EngineDB:
    """多维表格引擎 - 统一数据库访问层"""

    def __init__(self, engine_path: Optional[str] = None, cognition_path: Optional[str] = None):
        """多维表格引擎 - 路径由上层Config驱动，不从__file__硬编码"""
        if engine_path and cognition_path:
            # 路径已由上层Config.resolve_paths提供
            self.engine_path = engine_path
            self.cognition_path = cognition_path
        else:
            # 兜底：走与Config一致的逻辑
            from ..config import load_config
            cfg = load_config()
            self.engine_path = engine_path or cfg.get("keeper", "db_path", default="")
            self.cognition_path = cognition_path or cfg.get("scribe", "db_path", default="")
            # 如果Config也返回空，才用硬编码兜底（仅测试场景）
            if not self.engine_path:
                self.engine_path = str(Path(__file__).parent.parent.parent / "store" / "rnd_engine.db")
            if not self.cognition_path:
                self.cognition_path = str(Path(__file__).parent.parent.parent / "store" / "hermes.db")
        self._ensure_store()
        self._init_engine()
        self._init_cognition()

    def _ensure_store(self):
        os.makedirs(os.path.dirname(self.engine_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.cognition_path), exist_ok=True)

    def _init_engine(self):
        conn = sqlite3.connect(self.engine_path)
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()

    def _init_cognition(self):
        conn = sqlite3.connect(self.cognition_path)
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()

    # === 引擎数据库操作 ===

    def engine_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.engine_path)
        conn.row_factory = sqlite3.Row
        return conn

    def cognition_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.cognition_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- 任务操作 --
    def create_task(self, task_id: str, name: str, level: str = "unit",
                    parent_id: str = "", status: str = "待构思",
                    notes: str = "", prd_ref: str = "", goal_ref: str = "") -> bool:
        conn = self.engine_conn()
        try:
            conn.execute(
                """INSERT OR IGNORE INTO rnd_tasks
                   (task_id, name, level, parent_id, status, notes, prd_ref, goal_ref,
                    iteration_count, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now','localtime'), datetime('now','localtime'))""",
                (task_id, name, level, parent_id, status, notes, prd_ref, goal_ref)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def update_task(self, task_id: str, **kwargs) -> bool:
        conn = self.engine_conn()
        try:
            fields = []
            values = []
            for k, v in kwargs.items():
                fields.append(f"{k}=?")
                values.append(v)
            values.append(task_id)
            fields.append("updated_at=datetime('now','localtime')")
            conn.execute(f"UPDATE rnd_tasks SET {', '.join(fields)} WHERE task_id=?", values)
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def get_task(self, task_id: str) -> Optional[Dict]:
        conn = self.engine_conn()
        try:
            row = conn.execute("SELECT * FROM rnd_tasks WHERE task_id=?", (task_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_tasks(self, status: Optional[str] = None, level: Optional[str] = None,
                   limit: int = 50) -> List[Dict]:
        conn = self.engine_conn()
        try:
            where = []
            params = []
            if status:
                where.append("status=?")
                params.append(status)
            if level:
                where.append("level=?")
                params.append(level)
            sql = "SELECT * FROM rnd_tasks"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    # -- 步骤操作 --
    def create_step(self, task_id: str, step_name: str, step_order: int,
                    doc_path: str = "", status: str = "待执行") -> int:
        conn = self.engine_conn()
        try:
            cur = conn.execute(
                """INSERT INTO rnd_steps (task_id, step_name, step_order, doc_path, status, started_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))""",
                (task_id, step_name, step_order, doc_path, status)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def complete_step(self, step_id: int, comment: str = "") -> bool:
        conn = self.engine_conn()
        try:
            conn.execute(
                "UPDATE rnd_steps SET status='已完成', supervisor_approved=1, supervisor_comment=?, completed_at=datetime('now','localtime') WHERE id=?",
                (comment, step_id)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    # -- 审核操作 --
    def add_review(self, target_id: str, review_type: str, result: str,
                   conclusion: str = "") -> bool:
        conn = self.engine_conn()
        try:
            conn.execute(
                "INSERT INTO rnd_reviews (review_type, target_id, result, conclusion) VALUES (?, ?, ?, ?)",
                (review_type, target_id, result, conclusion)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    # -- 状态机操作 --
    def transition_state(self, task_id: str, new_state: str) -> bool:
        conn = self.engine_conn()
        try:
            task = conn.execute("SELECT status FROM rnd_tasks WHERE task_id=?", (task_id,)).fetchone()
            if not task:
                return False
            old_state = task["status"]
            # 校验转换是否合法
            state_def = conn.execute(
                "SELECT allowed_transitions FROM rnd_state_def WHERE state_name=?",
                (old_state,)
            ).fetchone()
            if state_def:
                allowed = json.loads(state_def["allowed_transitions"])
                if new_state not in allowed:
                    return False
            conn.execute(
                "UPDATE rnd_tasks SET status=?, updated_at=datetime('now','localtime') WHERE task_id=?",
                (new_state, task_id)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    # -- 认知库操作 --
    def save_memory(self, combo_id: str, task: str, content: str) -> int:
        conn = self.cognition_conn()
        try:
            cur = conn.execute(
                "INSERT INTO memories (combo_id, task, content) VALUES (?, ?, ?)",
                (combo_id, task, content)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_memory(self, combo_id: str, task: str) -> Optional[str]:
        conn = self.cognition_conn()
        try:
            row = conn.execute(
                "SELECT content FROM memories WHERE combo_id=? AND task=? ORDER BY created_at DESC LIMIT 1",
                (combo_id, task)
            ).fetchone()
            return row["content"] if row else None
        finally:
            conn.close()

    def record_chat(self, session_id: str, role: str, content: str,
                    task_id: str = "", metadata: str = "{}") -> int:
        conn = self.cognition_conn()
        try:
            cur = conn.execute(
                "INSERT INTO cognition_chats (session_id, role, content, task_id, metadata) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, task_id, metadata)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_fingerprints(self) -> List[Dict]:
        conn = self.cognition_conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM fingerprints ORDER BY name"
            ).fetchall()]
        finally:
            conn.close()

    def get_subchain_weights(self, chain_type: Optional[str] = None) -> List[Dict]:
        conn = self.cognition_conn()
        try:
            if chain_type:
                return [dict(r) for r in conn.execute(
                    "SELECT * FROM subchain_weights WHERE chain_type=? ORDER BY weight DESC",
                    (chain_type,)
                ).fetchall()]
            return [dict(r) for r in conn.execute(
                "SELECT * FROM subchain_weights ORDER BY chain_type, weight DESC"
            ).fetchall()]
        finally:
            conn.close()

    def record_error(self, error_type: str, error_detail: str,
                     context: str = "", fix: str = "") -> Dict:
        conn = self.cognition_conn()
        try:
            # 检查是否已有相同错误
            existing = conn.execute(
                "SELECT * FROM error_memories WHERE error_type=? AND error_detail=?",
                (error_type, error_detail)
            ).fetchone()
            if existing:
                cnt = existing["repeat_count"] + 1
                forbidden = 1 if cnt >= 3 else existing["is_forbidden"]
                conn.execute(
                    "UPDATE error_memories SET repeat_count=?, is_forbidden=?, fix=? WHERE id=?",
                    (cnt, forbidden, fix, existing["id"])
                )
                conn.commit()
                return {"repeat_count": cnt, "is_forbidden": bool(forbidden)}
            else:
                conn.execute(
                    "INSERT INTO error_memories (error_type, error_detail, context, fix) VALUES (?, ?, ?, ?)",
                    (error_type, error_detail, context, fix)
                )
                conn.commit()
                return {"repeat_count": 1, "is_forbidden": False}
        finally:
            conn.close()

    def get_forbidden_errors(self) -> List[Dict]:
        conn = self.cognition_conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM error_memories WHERE is_forbidden=1"
            ).fetchall()]
        finally:
            conn.close()


# ========== Seed 函数: 填充多维表格 ==========

def seed_engine_db(db: EngineDB):
    """填充引擎多维表格: 步骤定义 + 审核定义 + 宪法"""
    conn = db.engine_conn()
    try:
        # rnd_step_def: 4步定义
        steps = [
            ("01-思路", 1, "分析核心问题、目标和约束条件"),
            ("02-流程", 2, "规划解决步骤和方法论"),
            ("03-执行方法", 3, "具体技术方案或操作步骤"),
            ("04-结果", 4, "最终输出结果"),
        ]
        for name, order, desc in steps:
            conn.execute(
                "INSERT OR IGNORE INTO rnd_step_def (step_name, step_order, description) VALUES (?, ?, ?)",
                (name, order, desc)
            )

        # rnd_review_def: 4级审核定义
        reviews = [
            ("step", "单步方向是否正确"),
            ("unit", "01-04完整性和一致性"),
            ("phase", "跨阶段对齐"),
            ("whole", "终审质量"),
        ]
        for level, desc in reviews:
            conn.execute(
                "INSERT OR IGNORE INTO rnd_review_def (level_name, description) VALUES (?, ?)",
                (level, desc)
            )

        # rnd_constitution: 8条宪法
        constitutions = [
            ("宪法1: 目标导向", "所有推理必须以目标为起点，以结果为终点", "flow"),
            ("宪法2: 逻辑闭环", "推理过程必须形成完整闭环，不能跳跃或断裂", "flow"),
            ("宪法3: 因果可溯", "每个结论必须有可追溯的因果依据", "flow"),
            ("宪法4: 多维思考", "必须从4脑(逻辑链/因果链/思维链/推导法)多角度分析", "flow"),
            ("宪法5: 深度适配", "思考深度适配任务复杂度: 快照T1/标准T1+T2/深度T1+T2+T3", "quality"),
            ("宪法6: 指纹驱动", "通用指纹(jiapo)必须加载,领域垂直指纹按需加载", "flow"),
            ("宪法7: 证据优先", "主张必须有证据支持,无证据的主张须标明'推测'", "quality"),
            ("宪法8: 迭代改进", "每次输出都要自检,发现问题主动迭代", "quality"),
        ]
        for name, content, category in constitutions:
            conn.execute(
                "INSERT OR IGNORE INTO rnd_constitution (name, content, category) VALUES (?, ?, ?)",
                (name, content, category)
            )

        conn.commit()
    finally:
        conn.close()


def seed_fingerprints(db: EngineDB, fingerprints_dir: str):
    """从指纹JSON填充fingerprints表 + subchain_weights表"""
    import os
    fdir = fingerprints_dir
    if not os.path.isdir(fdir):
        return

    conn = db.cognition_conn()
    try:
        for fname in sorted(os.listdir(fdir)):
            if not fname.endswith(".json"):
                continue
            # 跳过辅助文件(无usage_by_chain)
            if fname.startswith("_"):
                continue
            fpath = os.path.join(fdir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                continue

            # 解析domain_id: JSON中的domain_id优先,否则从文件名推导
            base_name = fname.replace(".json", "")
            if base_name.endswith("_fingerprint"):
                base_name = base_name[:-len("_fingerprint")]
            domain_id = data.get("domain_id") or base_name
            fp_name = data.get("name", fname)

            # 写入fingerprints表
            conn.execute(
                "INSERT OR REPLACE INTO fingerprints (name, domain_id, source, data) VALUES (?, ?, ?, ?)",
                (fp_name, domain_id, data.get("source", ""), json.dumps(data, ensure_ascii=False))
            )

            # 从usage_by_chain提取子链权重 → subchain_weights表
            usage = data.get("usage_by_chain", {})
            for chain_short_name, chain_data in usage.items():
                weight = chain_data.get("weight", 0.0)
                tier = chain_data.get("tier", 5)
                brains = chain_data.get("brains", ["思维链"])
                for brain in brains:
                    # 统一脑名称: "推导链" → "推导法"
                    brain_norm = brain.replace("推导链", "推导法")
                    chain_type = f"{domain_id}:{brain_norm}"
                    conn.execute(
                        "INSERT OR REPLACE INTO subchain_weights (chain_type, subchain_name, weight, tier) VALUES (?, ?, ?, ?)",
                        (chain_type, chain_short_name, weight, tier)
                    )

        conn.commit()
    finally:
        conn.close()
