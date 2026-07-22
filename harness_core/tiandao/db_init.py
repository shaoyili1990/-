"""天道系统 - 数据库初始化模块

创建 rnd_tiandao.db 及其所有P0表。
遵循天道设计原则：改表不改代码，所有DDL集中管理。

Usage:
    python db_init.py [--db-path PATH]
"""

import sqlite3
import logging
import argparse
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# 当前目录默认为脚本所在目录
DEFAULT_DB_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "rnd_tiandao.db")

# ─── DDL 定义 ────────────────────────────────────────────────────────────────

DDL_STATEMENTS = [
    # 1. tiandao_novels - 小说注册表
    """CREATE TABLE IF NOT EXISTS tiandao_novels (
        novel_id    TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        status      TEXT DEFAULT 'planning',
        style       TEXT,
        main_story_goal TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",

    # 2. tiandao_characters - 人物表
    """CREATE TABLE IF NOT EXISTS tiandao_characters (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        novel_id    TEXT NOT NULL REFERENCES tiandao_novels(novel_id),
        name        TEXT NOT NULL,
        mbti        TEXT,
        y_base      REAL DEFAULT 50.0,
        weight_class TEXT DEFAULT 'major'
                    CHECK(weight_class IN ('protagonist', 'antagonist', 'major', 'minor', 'npc')),
        description TEXT,
        persona_json TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",

    # 3. tiandao_states - 人物状态快照
    """CREATE TABLE IF NOT EXISTS tiandao_states (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        novel_id        TEXT NOT NULL,
        char_id         INTEGER NOT NULL REFERENCES tiandao_characters(id),
        chapter         TEXT,
        event_seq       INTEGER DEFAULT 0,
        y_current       REAL DEFAULT 50.0,
        y_effective     REAL DEFAULT 0.5,
        emotions_json   TEXT DEFAULT '{}',
        desires_json    TEXT DEFAULT '{}',
        motivation      TEXT,
        breakthrough_flag INTEGER DEFAULT 0,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",

    # 4. tiandao_events - 事件记录
    """CREATE TABLE IF NOT EXISTS tiandao_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        novel_id    TEXT NOT NULL REFERENCES tiandao_novels(novel_id),
        chapter     TEXT,
        title       TEXT,
        description TEXT,
        causal_chain TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",

    # 5. tiandao_event_roles - 事件-人物分配（核心权重表）
    """CREATE TABLE IF NOT EXISTS tiandao_event_roles (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id        INTEGER NOT NULL REFERENCES tiandao_events(id),
        char_id         INTEGER NOT NULL REFERENCES tiandao_characters(id),
        role_type       TEXT NOT NULL DEFAULT 'supporting'
                        CHECK(role_type IN ('major', 'supporting', 'extra')),
        influence_score REAL DEFAULT 1.0
                        CHECK(influence_score >= 0 AND influence_score <= 1),
        notes           TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",
]


def create_database(db_path: str) -> sqlite3.Connection:
    """创建数据库文件并建立所有表。

    Args:
        db_path: 数据库文件路径。

    Returns:
        sqlite3.Connection: 数据库连接对象。
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    logger.info("数据库已连接: %s", db_path)
    return conn


def execute_ddl(conn: sqlite3.Connection) -> int:
    """执行所有DDL语句创建表。

    Args:
        conn: 数据库连接对象。

    Returns:
        int: 创建的表数量。
    """
    count = 0
    for ddl in DDL_STATEMENTS:
        table_name = ddl.split("TABLE IF NOT EXISTS ")[1].split(" ")[0].strip()
        try:
            conn.execute(ddl)
            logger.info("表已就绪: %s", table_name)
            count += 1
        except sqlite3.Error as e:
            logger.error("创建表 %s 失败: %s", table_name, e)
            raise
    conn.commit()
    return count


def verify_tables(conn: sqlite3.Connection) -> list:
    """验证所有预期的表已创建。

    Args:
        conn: 数据库连接对象。

    Returns:
        list: 已创建的表名列表。
    """
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    )
    tables = [row[0] for row in cursor.fetchall()]
    logger.info("数据库中的表 (%d): %s", len(tables), tables)
    return tables


def insert_seed_data(conn: sqlite3.Connection) -> None:
    """插入种子数据以便开发和测试。

    创建示例小说和初始人物，方便bridge接口调试。
    """
    # 示例小说
    conn.execute(
        """INSERT OR IGNORE INTO tiandao_novels (novel_id, name, status, style, main_story_goal)
           VALUES (?, ?, ?, ?, ?)""",
        ("novel-001", "天道试炼", "active", "玄幻", "主角从凡人走向天道掌控者的历程"),
    )

    # 示例人物
    sample_characters = [
        ("novel-001", "张平凡", "ENFP", 50.0, "protagonist", "天性乐观的普通少年",
         '{"traits": ["乐观", "坚韧", "好奇心强"]}'),
        ("novel-001", "冷月", "INTJ", 45.0, "antagonist", "冷静睿智的宿敌",
         '{"traits": ["冷静", "算计", "高傲"]}'),
        ("novel-001", "老李头", "ESFJ", 60.0, "major", "主角的 mentor",
         '{"traits": ["慈祥", "智慧", "神秘"]}'),
    ]
    for char in sample_characters:
        conn.execute(
            """INSERT OR IGNORE INTO tiandao_characters
               (novel_id, name, mbti, y_base, weight_class, description, persona_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            char,
        )
    conn.commit()
    logger.info("种子数据已插入 (1 部小说, %d 个人物)", len(sample_characters))


def main():
    """主入口：创建数据库、执行DDL、验证并插入种子数据。"""
    parser = argparse.ArgumentParser(description="天道系统数据库初始化")
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help=f"数据库文件路径 (默认: {DEFAULT_DB_PATH})",
    )
    args = parser.parse_args()

    db_path = args.db_path
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info("创建目录: %s", db_dir)

    conn = create_database(db_path)
    try:
        table_count = execute_ddl(conn)
        tables = verify_tables(conn)

        if table_count == len(DDL_STATEMENTS):
            logger.info("✅ 所有 %d 张表创建成功", table_count)
        else:
            logger.warning(
                "预期 %d 张表，实际创建 %d 张",
                len(DDL_STATEMENTS),
                table_count,
            )

        insert_seed_data(conn)
    finally:
        conn.close()

    logger.info("✅ 数据库初始化完成: %s", db_path)


if __name__ == "__main__":
    main()
