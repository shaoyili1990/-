"""天道系统 - 状态机与天道联动接口 (Bridge)

提供四大接口连接状态机(rnd_engine.db)与天道(rnd_tiandao.db)：
  1. trigger_event()     - 状态机通知天道事件发生
  2. get_character_state() - 读取人物当前状态
  3. get_event_roles()   - 读取事件的人物分配及权重
  4. update_after_god_intervention() - 老天爷手动介入

设计原则：
  - 事件驱动，非实时同步，批量或按章节触发
  - 人和天分离：天道自动计算，老天爷通过独立接口介入
  - 数据持久化：所有状态快照写入tiandao_states，支持断点恢复
  - 公式计算链(A3)通过 TODO 钩子接入，当前版本完成DDL读写

Usage:
    from tiandao_bridge import TiandaoDB
    db = TiandaoDB()
    result = db.trigger_event("novel-001", {...})
"""

import json
import logging
import os
import sqlite3
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 默认数据库路径：与脚本同级的 rnd_tiandao.db
_DEFAULT_DB_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(_DEFAULT_DB_DIR, "rnd_tiandao.db")


# ═══════════════════════════════════════════════════════════════════════
# Dao 层
# ═══════════════════════════════════════════════════════════════════════

class TiandaoDB:
    """天道系统数据库操作封装。

    管理 rnd_tiandao.db 的连接，提供四大业务接口。
    所有写操作使用参数化查询，禁止拼接SQL。

    Attributes:
        db_path: 数据库文件路径。
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """初始化TiandaoDB。

        Args:
            db_path: rnd_tiandao.db 的路径。默认与脚本同级。
        """
        self.db_path = db_path

    # ── 连接管理 ─────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        """创建数据库连接并启用外键约束。

        Returns:
            sqlite3.Connection: 数据库连接对象。
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """将 sqlite3.Row 转换为字典。

        Args:
            row: 查询结果的单行。

        Returns:
            dict: 行数据的字典表示。
        """
        if row is None:
            return {}
        return dict(row)

    # ── 接口一: trigger_event ────────────────────────────────────────

    def trigger_event(
        self,
        novel_id: str,
        event_data: dict,
    ) -> list[dict]:
        """状态机通知天道：一个事件发生了。

        天道自动执行：记录事件 → 查人物角色权重 → 计算Y值波动(A3) →
        更新状态快照 → 返回所有受影响人物的更新后状态。

        Args:
            novel_id: 小说ID，对应 tiandao_novels.novel_id。
            event_data: 事件数据字典，包含：
                - chapter (str): 章节标识
                - title (str): 事件标题
                - description (str): 事件描述
                - causal_chain (str, optional): 关联因果链
                - characters (list[dict], optional): 涉及人物的预指定信息。
                  每项包含 char_id 和可选的 role_type/influence_score 覆盖。
                  不传则从 tiandao_event_roles 读取。

        Returns:
            list[dict]: 每个受影响人物的更新后状态列表，
            每项包含 char_id, y_current, y_effective, emotions_json,
            desires_json, motivation, breakthrough_flag。

        Raises:
            ValueError: novel_id 不存在或 event_data 缺少必要字段。
            sqlite3.Error: 数据库操作失败。
        """
        # 校验小说存在
        if not self._novel_exists(novel_id):
            raise ValueError(f"小说不存在: novel_id={novel_id}")

        # 校验必要字段
        chapter = event_data.get("chapter")
        title = event_data.get("title")
        description = event_data.get("description")
        if not all([chapter, title, description]):
            raise ValueError(
                "event_data 缺少必要字段: chapter, title, description"
            )

        conn = self._connect()
        try:
            # 步骤1: 记录事件
            event_id = self._insert_event(
                conn, novel_id, chapter, title, description,
                event_data.get("causal_chain"),
            )

            # 步骤2: 获取涉及人物及权重
            characters_raw = event_data.get("characters")
            if characters_raw:
                # 调用方已经指定了人物列表和权重
                roles = self._resolve_explicit_roles(conn, novel_id, characters_raw)
            else:
                # 从 tiandao_event_roles 读取
                roles = self._get_event_roles_internal(conn, event_id)
                if not roles:
                    logger.warning(
                        "事件 %s 无关联人物，返回空状态", event_id
                    )
                    return []

            # 步骤3: 获取人物的 Y_base 和 weight_class
            char_ids = [r["char_id"] for r in roles]
            char_bases = self._get_character_bases(conn, novel_id, char_ids)

            # 步骤4: 计算并写入新状态快照
            # TODO(A3): 接入 Y值计算公式链 (公式03-08)
            #   当前实现：先生成占位状态快照，A3 替换计算逻辑
            updated_states = []
            for role in roles:
                char_id = role["char_id"]
                base_info = char_bases.get(char_id, {})
                y_base = base_info.get("y_base", 50.0)
                weight_class = base_info.get("weight_class", "major")

                # ── 此处为 A3 计算链的接入点 ──
                # 当前只做：读取最新状态或使用基线，不做复杂计算
                latest_state = self._get_latest_state(conn, novel_id, char_id)
                y_current_before = latest_state.get("y_current", y_base)

                # 简易 delta（A3将替换为完整公式03-08）
                influence = role.get("influence_score", 1.0)
                weight_multiplier = self._weight_multiplier(weight_class)
                delta_y = round(event_data.get("impact", 5.0) * influence * weight_multiplier, 2)
                delta_y = max(-20.0, min(20.0, delta_y))  # 公式03: 单次最大±20

                y_current = round(y_current_before + delta_y, 2)
                y_current = max(0.0, min(100.0, y_current))
                y_effective = round(y_current / 100.0, 4)  # 公式02

                # 简易情绪映射（A3将替换为公式04-05）
                emotions = self._simple_emotion_map(y_current)

                # 状态快照写入
                conn.execute(
                    """INSERT INTO tiandao_states
                       (novel_id, char_id, chapter, event_seq, y_current,
                        y_effective, emotions_json, desires_json,
                        motivation, breakthrough_flag)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        novel_id, char_id, chapter, event_id, y_current,
                        y_effective, json.dumps(emotions, ensure_ascii=False),
                        "{}", latest_state.get("motivation", ""), 0,
                    ),
                )
                conn.commit()

                updated_states.append({
                    "char_id": char_id,
                    "name": base_info.get("name", ""),
                    "y_current": y_current,
                    "y_effective": y_effective,
                    "emotions": emotions,
                    "motivation": latest_state.get("motivation", ""),
                    "breakthrough_flag": 0,
                })

            logger.info(
                "事件 %d (【%s】%s) 已处理，%d 个人物状态更新",
                event_id, chapter, title, len(updated_states),
            )
            return updated_states

        except sqlite3.Error as e:
            conn.rollback()
            logger.error("trigger_event 数据库错误: %s", e)
            raise
        finally:
            conn.close()

    # ── 接口二: get_character_state ──────────────────────────────────

    def get_character_state(
        self,
        novel_id: str,
        char_id: int,
        chapter: Optional[str] = None,
    ) -> dict:
        """读取指定人物在当前章节的最新状态。

        Args:
            novel_id: 小说ID。
            char_id: 人物ID (tiandao_characters.id)。
            chapter: 可选，指定章节。不传则返回所有章节中最新的一条。

        Returns:
            dict: 人物状态信息，包含:
                - char_id, name, y_current, y_effective, emotions (dict),
                  desires (dict), motivation, breakthrough_flag, chapter,
                  event_seq, created_at
            - 如果人物不存在或无状态记录，返回空字典。

        Raises:
            sqlite3.Error: 数据库操作失败。
        """
        conn = self._connect()
        try:
            # 获取人物基本信息
            char_info = conn.execute(
                "SELECT id, name, y_base, weight_class FROM tiandao_characters "
                "WHERE id = ? AND novel_id = ?",
                (char_id, novel_id),
            ).fetchone()

            if char_info is None:
                logger.warning(
                    "人物不存在: novel_id=%s, char_id=%d", novel_id, char_id
                )
                return {}

            char_info = dict(char_info)

            # 获取最新状态快照
            if chapter:
                state = conn.execute(
                    """SELECT * FROM tiandao_states
                       WHERE novel_id = ? AND char_id = ? AND chapter = ?
                       ORDER BY event_seq DESC LIMIT 1""",
                    (novel_id, char_id, chapter),
                ).fetchone()
            else:
                state = conn.execute(
                    """SELECT * FROM tiandao_states
                       WHERE novel_id = ? AND char_id = ?
                       ORDER BY event_seq DESC, created_at DESC LIMIT 1""",
                    (novel_id, char_id),
                ).fetchone()

            if state is None:
                # 无状态快照时返回基线信息
                return {
                    "char_id": char_info["id"],
                    "name": char_info["name"],
                    "y_current": char_info["y_base"],
                    "y_effective": round(char_info["y_base"] / 100.0, 4),
                    "emotions": self._simple_emotion_map(char_info["y_base"]),
                    "desires": {},
                    "motivation": "",
                    "breakthrough_flag": 0,
                    "chapter": chapter or "",
                    "event_seq": 0,
                }

            state = dict(state)
            return {
                "char_id": state["char_id"],
                "name": char_info["name"],
                "y_current": state["y_current"],
                "y_effective": state["y_effective"],
                "emotions": self._safe_json_load(state["emotions_json"]),
                "desires": self._safe_json_load(state["desires_json"]),
                "motivation": state["motivation"] or "",
                "breakthrough_flag": state["breakthrough_flag"],
                "chapter": state["chapter"] or "",
                "event_seq": state["event_seq"],
                "created_at": state["created_at"],
            }

        except sqlite3.Error as e:
            logger.error("get_character_state 数据库错误: %s", e)
            raise
        finally:
            conn.close()

    # ── 接口三: get_event_roles ─────────────────────────────────────

    def get_event_roles(
        self,
        novel_id: str,
        event_id: int,
    ) -> list[dict]:
        """读取指定事件的人物分配及权重。

        Args:
            novel_id: 小说ID。
            event_id: 事件ID (tiandao_events.id)。

        Returns:
            list[dict]: 事件涉及人物列表，每项包含:
                - char_id, name, role_type, influence_score, notes。
            - 如果事件不存在或无关联人物，返回空列表。

        Raises:
            sqlite3.Error: 数据库操作失败。
        """
        conn = self._connect()
        try:
            # 确认事件存在且属于该小说
            event = conn.execute(
                "SELECT id FROM tiandao_events WHERE id = ? AND novel_id = ?",
                (event_id, novel_id),
            ).fetchone()
            if event is None:
                logger.warning(
                    "事件不存在: novel_id=%s, event_id=%d", novel_id, event_id
                )
                return []

            roles = conn.execute(
                """SELECT r.char_id, c.name, r.role_type, r.influence_score, r.notes
                   FROM tiandao_event_roles r
                   JOIN tiandao_characters c ON c.id = r.char_id
                   WHERE r.event_id = ?
                   ORDER BY
                       CASE r.role_type
                           WHEN 'major' THEN 1
                           WHEN 'supporting' THEN 2
                           WHEN 'extra' THEN 3
                       END""",
                (event_id,),
            ).fetchall()

            return [dict(r) for r in roles]

        except sqlite3.Error as e:
            logger.error("get_event_roles 数据库错误: %s", e)
            raise
        finally:
            conn.close()

    # ── 接口四: update_after_god_intervention ────────────────────────

    def update_after_god_intervention(
        self,
        novel_id: str,
        char_id: int,
        delta_y: float,
        reason: str,
    ) -> dict:
        """老天爷手动介入，直接调整人物的Y值并记录状态快照。

        人和天分离原则：此接口绕过自动Y值计算链，
        由老天爷（人类创作者/姜子牙）直接指定Y值变化量。

        Args:
            novel_id: 小说ID。
            char_id: 人物ID。
            delta_y: Y值变化量，正值上升，负值下降。
                此值不受公式03的±20限制——老天爷的意志高于规则。
            reason: 介入原因描述，用于审计追踪。

        Returns:
            dict: 更新后的人物状态，包含 char_id, name, y_current,
            y_effective, emotions, motivation, breakthrough_flag。

        Raises:
            ValueError: 人物不存在。
            sqlite3.Error: 数据库操作失败。
        """
        conn = self._connect()
        try:
            # 获取人物基本信息
            char_info = conn.execute(
                "SELECT id, name, y_base FROM tiandao_characters "
                "WHERE id = ? AND novel_id = ?",
                (char_id, novel_id),
            ).fetchone()

            if char_info is None:
                raise ValueError(
                    f"人物不存在: novel_id={novel_id}, char_id={char_id}"
                )

            char_info = dict(char_info)

            # 获取最新Y值作为基线，若无记录则从Y_base开始
            latest = self._get_latest_state(conn, novel_id, char_id)
            y_previous = latest.get("y_current", char_info["y_base"])

            # 计算新Y值（老天爷的修改不受±20限制，但仍保持在[0,100]）
            y_new = round(y_previous + delta_y, 2)
            y_new = max(0.0, min(100.0, y_new))
            y_effective = round(y_new / 100.0, 4)

            emotions = self._simple_emotion_map(y_new)

            # 获取当前事件序列号（自增）
            max_seq = conn.execute(
                "SELECT COALESCE(MAX(event_seq), 0) FROM tiandao_states "
                "WHERE novel_id = ? AND char_id = ?",
                (novel_id, char_id),
            ).fetchone()[0]

            # 写入新状态快照，reason 写入 emotions_json 做审计
            audit_emotions = emotions.copy()
            audit_emotions["_god_intervention"] = reason

            conn.execute(
                """INSERT INTO tiandao_states
                   (novel_id, char_id, chapter, event_seq, y_current,
                    y_effective, emotions_json, motivation, breakthrough_flag)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    novel_id, char_id, "_god_intervention",
                    max_seq + 1, y_new, y_effective,
                    json.dumps(audit_emotions, ensure_ascii=False),
                    latest.get("motivation", ""), 0,
                ),
            )
            conn.commit()

            logger.info(
                "老天爷介入: 人物 %s (id=%d) Y值 %.2f → %.2f，原因: %s",
                char_info["name"], char_id, y_previous, y_new, reason,
            )

            return {
                "char_id": char_id,
                "name": char_info["name"],
                "y_current": y_new,
                "y_effective": y_effective,
                "emotions": emotions,
                "motivation": latest.get("motivation", ""),
                "breakthrough_flag": 0,
                "god_reason": reason,
            }

        except sqlite3.Error as e:
            conn.rollback()
            logger.error("update_after_god_intervention 数据库错误: %s", e)
            raise
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════════════════════════════════

    def _novel_exists(self, novel_id: str) -> bool:
        """检查小说是否存在。

        Args:
            novel_id: 小说ID。

        Returns:
            bool: 是否存在。
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM tiandao_novels WHERE novel_id = ?",
                (novel_id,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def _insert_event(
        self,
        conn: sqlite3.Connection,
        novel_id: str,
        chapter: str,
        title: str,
        description: str,
        causal_chain: Optional[str] = None,
    ) -> int:
        """插入一条事件记录并返回自增ID。

        Args:
            conn: 数据库连接。
            novel_id: 小说ID。
            chapter: 章节。
            title: 事件标题。
            description: 事件描述。
            causal_chain: 关联因果链（可选）。

        Returns:
            int: 新插入事件的ID。
        """
        cursor = conn.execute(
            """INSERT INTO tiandao_events
               (novel_id, chapter, title, description, causal_chain)
               VALUES (?, ?, ?, ?, ?)""",
            (novel_id, chapter, title, description, causal_chain),
        )
        conn.commit()
        return cursor.lastrowid

    def _resolve_explicit_roles(
        self,
        conn: sqlite3.Connection,
        novel_id: str,
        characters: list[dict],
    ) -> list[dict]:
        """解析调用方显式指定的人物角色关系。

        如果没有提供 role_type/influence_score，从 tiandao_characters 的
        weight_class 推导默认值。

        Args:
            conn: 数据库连接。
            novel_id: 小说ID。
            characters: 人物列表，每项应包含 char_id。

        Returns:
            list[dict]: 解析后的人物角色列表。
        """
        roles = []
        for char in characters:
            char_id = char["char_id"]
            role_type = char.get("role_type")
            influence_score = char.get("influence_score")

            if not role_type or influence_score is None:
                # 从 weight_class 推导
                row = conn.execute(
                    "SELECT weight_class FROM tiandao_characters "
                    "WHERE id = ? AND novel_id = ?",
                    (char_id, novel_id),
                ).fetchone()
                if row is None:
                    logger.warning("人物 %d 不存在，跳过", char_id)
                    continue
                inferred = self._infer_role_from_weight(row["weight_class"])
                if not role_type:
                    role_type = inferred["role_type"]
                if influence_score is None:
                    influence_score = inferred["influence_score"]

            roles.append({
                "char_id": char_id,
                "role_type": role_type,
                "influence_score": influence_score,
            })
        return roles

    def _get_event_roles_internal(
        self,
        conn: sqlite3.Connection,
        event_id: int,
    ) -> list[dict]:
        """从 tiandao_event_roles 表读取事件人物关系。

        Args:
            conn: 数据库连接。
            event_id: 事件ID。

        Returns:
            list[dict]: 人物角色列表。
        """
        rows = conn.execute(
            "SELECT char_id, role_type, influence_score FROM tiandao_event_roles "
            "WHERE event_id = ?",
            (event_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _get_character_bases(
        self,
        conn: sqlite3.Connection,
        novel_id: str,
        char_ids: list[int],
    ) -> dict[int, dict]:
        """批量获取人物的基础信息。

        Args:
            conn: 数据库连接。
            novel_id: 小说ID。
            char_ids: 人物ID列表。

        Returns:
            dict[int, dict]: char_id → { name, y_base, weight_class }。
        """
        if not char_ids:
            return {}

        placeholders = ",".join("?" for _ in char_ids)
        rows = conn.execute(
            f"SELECT id, name, y_base, weight_class FROM tiandao_characters "
            f"WHERE id IN ({placeholders}) AND novel_id = ?",
            (*char_ids, novel_id),
        ).fetchall()
        return {row["id"]: dict(row) for row in rows}

    def _get_latest_state(
        self,
        conn: sqlite3.Connection,
        novel_id: str,
        char_id: int,
    ) -> dict:
        """获取人物的最新状态快照。

        Args:
            conn: 数据库连接。
            novel_id: 小说ID。
            char_id: 人物ID。

        Returns:
            dict: 最新状态，无记录则返回空字典。
        """
        row = conn.execute(
            """SELECT * FROM tiandao_states
               WHERE novel_id = ? AND char_id = ?
               ORDER BY event_seq DESC, created_at DESC LIMIT 1""",
            (novel_id, char_id),
        ).fetchone()
        return dict(row) if row else {}

    def _weight_multiplier(self, weight_class: str) -> float:
        """根据角色权重类型返回Y值波动倍数（公式10）。

        Args:
            weight_class: 角色权重类型。

        Returns:
            float: 波动倍数。
        """
        multipliers = {
            "protagonist": 1.5,
            "antagonist": 1.5,
            "major": 1.0,
            "minor": 0.3,
            "npc": 0.3,
        }
        return multipliers.get(weight_class, 1.0)

    def _infer_role_from_weight(self, weight_class: str) -> dict:
        """从 weight_class 推导默认的 role_type 和 influence_score。

        Args:
            weight_class: 角色权重类型。

        Returns:
            dict: 包含 role_type 和 influence_score。
        """
        mapping = {
            "protagonist": {"role_type": "major", "influence_score": 1.0},
            "antagonist": {"role_type": "major", "influence_score": 1.0},
            "major": {"role_type": "major", "influence_score": 0.8},
            "minor": {"role_type": "extra", "influence_score": 0.3},
            "npc": {"role_type": "extra", "influence_score": 0.1},
        }
        return mapping.get(weight_class, {"role_type": "supporting", "influence_score": 0.5})

    def _simple_emotion_map(self, y_current: float) -> dict:
        """简易情绪映射（公式04）。

        A3将替换为完整的情绪计算链，当前版本仅做值域映射。

        Args:
            y_current: 当前Y值。

        Returns:
            dict: 情绪维度 → 强度(1-10)。
        """
        # 情绪主基调
        if y_current >= 80:
            primary = "喜"
            intensity = int((y_current - 80) / 20 * 5 + 5)  # 5-10
        elif y_current >= 60:
            primary = "喜"
            intensity = int((y_current - 60) / 20 * 4 + 1)  # 1-5
        elif y_current >= 40:
            primary = "思"
            intensity = int(abs(y_current - 50) / 10 * 3 + 1)  # 1-3
        elif y_current >= 20:
            primary = "哀"
            intensity = int((40 - y_current) / 20 * 4 + 1)  # 1-5
        else:
            primary = "惧"
            intensity = int((20 - y_current) / 20 * 5 + 5)  # 5-10

        return {
            "喜": intensity if primary == "喜" else max(0, intensity - 2),
            "怒": 0,
            "哀": intensity if primary == "哀" else max(0, intensity - 2),
            "惧": intensity if primary == "惧" else max(0, intensity - 3),
            "思": intensity if primary == "思" else max(1, intensity - 1),
            "欲": max(1, min(5, int(abs(y_current - 50) / 10))),
        }

    def _safe_json_load(self, text: str) -> dict:
        """安全地解析JSON字符串。

        Args:
            text: 待解析的JSON字符串。

        Returns:
            dict: 解析后的字典，解析失败则返回空字典。
        """
        if not text:
            return {}
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            logger.warning("JSON解析失败: %s", text[:50])
            return {}
