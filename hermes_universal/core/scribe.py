"""
书童(Scribe) - 认知与记忆管家
职责: 管理10认知库、指纹检索匹配、伪注意力机制、记忆存取
"""

import json
from typing import List, Dict, Optional
from ..config import Config
from ..engine import EngineDB


class Scribe:
    """书童 - 认知与记忆管家"""

    def __init__(self, config: Config, db: EngineDB):
        self.config = config
        self.db = db

    # ========== 10认知库操作 ==========

    # 1. 记忆库
    def remember(self, combo_id: str, task: str, content: str) -> int:
        """存入记忆"""
        return self.db.save_memory(combo_id, task, content)

    def recall(self, combo_id: str, task: str) -> Optional[str]:
        """检索记忆"""
        return self.db.get_memory(combo_id, task)

    def search_memories(self, keyword: str) -> List[Dict]:
        """搜索相关记忆"""
        conn = self.db.cognition_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM memories WHERE content LIKE ? ORDER BY created_at DESC LIMIT 20",
                (f"%{keyword}%",)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # 2. 对话历史
    def record_chat(self, session_id: str, role: str, content: str,
                    task_id: str = "") -> int:
        return self.db.record_chat(session_id, role, content, task_id)

    def get_chat_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        conn = self.db.cognition_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM cognition_chats WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit)
            ).fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()

    # 3. 认知档案
    def update_profile(self, profile_type: str, summary: str, keywords: str = "",
                       data: Dict = None) -> int:
        conn = self.db.cognition_conn()
        try:
            existing = conn.execute(
                "SELECT id FROM cognition_profiles WHERE profile_type=?",
                (profile_type,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE cognition_profiles SET summary=?, keywords=?, data=? WHERE id=?",
                    (summary, keywords, json.dumps(data or {}, ensure_ascii=False), existing["id"])
                )
                conn.commit()
                return existing["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO cognition_profiles (profile_type, summary, keywords, data) VALUES (?, ?, ?, ?)",
                    (profile_type, summary, keywords, json.dumps(data or {}, ensure_ascii=False))
                )
                conn.commit()
                return cur.lastrowid
        finally:
            conn.close()

    def get_profile(self, profile_type: str) -> Optional[Dict]:
        conn = self.db.cognition_conn()
        try:
            row = conn.execute(
                "SELECT * FROM cognition_profiles WHERE profile_type=? ORDER BY created_at DESC LIMIT 1",
                (profile_type,)
            ).fetchone()
            if row:
                d = dict(row)
                if d.get("data"):
                    try:
                        d["data"] = json.loads(d["data"])
                    except:
                        pass
                return d
            return None
        finally:
            conn.close()

    # 4. 错误记忆 (3次拉黑)
    def record_error(self, error_type: str, error_detail: str,
                     context: str = "", fix: str = "") -> Dict:
        return self.db.record_error(error_type, error_detail, context, fix)

    def get_restrictions(self) -> List[Dict]:
        """获取已被拉黑的限制列表"""
        return self.db.get_forbidden_errors()

    # 5. 知识库
    def save_knowledge(self, keyword: str, category: str, content: str,
                       confidence: float = 0.5) -> int:
        conn = self.db.cognition_conn()
        try:
            cur = conn.execute(
                "INSERT OR REPLACE INTO material_knowledge (keyword, category, content, confidence, needs_supplement) VALUES (?, ?, ?, ?, 0)",
                (keyword, category, content, confidence)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def search_knowledge(self, query: str) -> List[Dict]:
        conn = self.db.cognition_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM material_knowledge WHERE keyword LIKE ? OR content LIKE ? ORDER BY confidence DESC LIMIT 10",
                (f"%{query}%", f"%{query}%")
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # 6. 偏好库
    def record_preference(self, pref_type: str, pref_desc: str,
                          source: str = "", strength: float = 0.5) -> int:
        conn = self.db.cognition_conn()
        try:
            cur = conn.execute(
                "INSERT INTO preferences (pref_type, pref_desc, source, strength) VALUES (?, ?, ?, ?)",
                (pref_type, pref_desc, source, strength)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_preferences(self, pref_type: Optional[str] = None) -> List[Dict]:
        conn = self.db.cognition_conn()
        try:
            if pref_type:
                rows = conn.execute(
                    "SELECT * FROM preferences WHERE pref_type=? ORDER BY strength DESC",
                    (pref_type,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM preferences ORDER BY strength DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # 7. 经验库
    def record_experience(self, exp_type: str, exp_desc: str,
                          context: str = "", analysis: str = "",
                          insight: str = "") -> int:
        conn = self.db.cognition_conn()
        try:
            cur = conn.execute(
                "INSERT INTO experience (exp_type, exp_desc, context, analysis, actionable_insight) VALUES (?, ?, ?, ?, ?)",
                (exp_type, exp_desc, context, analysis, insight)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    # 8. 行为准则
    def add_rule(self, rule: str, reason: str = "", severity: str = "medium") -> int:
        conn = self.db.cognition_conn()
        try:
            cur = conn.execute(
                "INSERT INTO conduct_rules (rule, reason, severity) VALUES (?, ?, ?)",
                (rule, reason, severity)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_rules(self) -> List[Dict]:
        conn = self.db.cognition_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM conduct_rules WHERE is_active=1 ORDER BY severity"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ========== 伪注意力机制 ==========

    def build_context(self, task_id: str, user_input: str = "") -> Dict:
        """构建理解上下文 - 聚合所有相关认知"""
        context = {
            "task": self.db.get_task(task_id),
            "memories": self.search_memories(user_input[:20]) if user_input else [],
            "knowledge": self.search_knowledge(user_input[:20]) if user_input else [],
            "preferences": self.get_preferences(),
            "restrictions": self.get_restrictions(),
            "rules": self.get_rules(),
            "chat_history": self.get_chat_history(task_id, limit=10),
        }
        return context

    def get_user_cognition(self, session_id: str) -> Dict:
        """获取用户完整认知画像"""
        return {
            "profile": self.get_profile("user"),
            "preferences": self.get_preferences(),
            "experience": self._get_recent_experiences(),
            "restrictions": self.get_restrictions(),
        }

    def _get_recent_experiences(self) -> List[Dict]:
        conn = self.db.cognition_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM experience ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
