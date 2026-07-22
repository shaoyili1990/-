"""
采购员(Purchaser) - 采买与仓库管理员
职责:
  1. 搜索Skill市场 - 根据需求找合适的Skill
  2. 安装Skill - 下载并注册到系统
  3. 仓库管理 - 整理/分类/巡检
  4. 与灵猴协作 - 接收需求，反馈结果
"""

import json
import uuid
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from ..config import Config
from ..engine import EngineDB
from ..providers import get_provider

logger = logging.getLogger("purchaser")


# 内置市场注册表（初始种子数据）
SEED_MARKET = [
    {
        "id": "web-search", "name": "网页搜索",
        "icon": "🔍", "description": "搜索引擎查询与结果提取",
        "category": "信息获取", "author": "Hermes",
        "tags": "搜索,网页,查询",
    },
    {
        "id": "web-fetch", "name": "网页抓取",
        "icon": "🕸️", "description": "读取指定URL内容为Markdown",
        "category": "信息获取", "author": "Hermes",
        "tags": "网页,抓取,URL",
    },
    {
        "id": "code-review", "name": "代码审查",
        "icon": "👁️", "description": "代码安全与质量审查",
        "category": "开发", "author": "Hermes",
        "tags": "代码,审查,安全",
    },
    {
        "id": "image-gen", "name": "图片生成",
        "icon": "🎨", "description": "文本描述生成图片",
        "category": "创意", "author": "Hermes",
        "tags": "图片,生成,AI绘画",
    },
    {
        "id": "file-parse", "name": "文件解析",
        "icon": "📄", "description": "PDF/Word/Excel文件内容提取",
        "category": "工具", "author": "Hermes",
        "tags": "文件,解析,PDF",
    },
    {
        "id": "data-chart", "name": "数据图表",
        "icon": "📊", "description": "数据可视化图表生成",
        "category": "数据分析", "author": "Hermes",
        "tags": "图表,数据,可视化",
    },
    {
        "id": "translate", "name": "翻译",
        "icon": "🌐", "description": "多语言翻译引擎",
        "category": "工具", "author": "Hermes",
        "tags": "翻译,语言,多语言",
    },
    {
        "id": "summarize", "name": "摘要",
        "icon": "📝", "description": "长文本自动摘要提取",
        "category": "文本处理", "author": "Hermes",
        "tags": "摘要,总结,压缩",
    },
    {
        "id": "voice-io", "name": "语音输入",
        "icon": "🎤", "description": "语音识别与语音合成",
        "category": "多媒体", "author": "Hermes",
        "tags": "语音,识别,合成",
    },
    {
        "id": "schedule", "name": "日程管理",
        "icon": "📅", "description": "日程安排与提醒管理",
        "category": "效率", "author": "Hermes",
        "tags": "日程,提醒,时间管理",
    },
    {
        "id": "email-helper", "name": "邮件助手",
        "icon": "✉️", "description": "邮件撰写与回复建议",
        "category": "效率", "author": "Hermes",
        "tags": "邮件,撰写,回复",
    },
    {
        "id": "db-query", "name": "数据库查询",
        "icon": "🗄️", "description": "自然语言转SQL查询",
        "category": "开发", "author": "Hermes",
        "tags": "数据库,SQL,查询",
    },
    {
        "id": "api-tester", "name": "API测试",
        "icon": "🧪", "description": "REST API测试与调试",
        "category": "开发", "author": "Hermes",
        "tags": "API,测试,调试",
    },
    {
        "id": "note-taking", "name": "笔记",
        "icon": "📓", "description": "智能笔记与知识整理",
        "category": "效率", "author": "Hermes",
        "tags": "笔记,知识,整理",
    },
    {
        "id": "mind-map", "name": "思维导图",
        "icon": "🧠", "description": "自动生成思维导图",
        "category": "创意", "author": "Hermes",
        "tags": "思维导图,脑图,可视化",
    },
]


class Purchaser:
    """采购员 - 采买与仓库管理员"""

    def __init__(self, config: Config, db: EngineDB):
        self.config = config
        self.db = db
        self._init_market()

    def _init_market(self):
        """初始化市场种子数据"""
        conn = self.db.cognition_conn()
        try:
            # 检查是否已有数据
            count = conn.execute("SELECT COUNT(*) as c FROM skill_market").fetchone()
            if count and count["c"] == 0:
                for skill in SEED_MARKET:
                    conn.execute(
                        """INSERT OR IGNORE INTO skill_market
                        (id, name, icon, description, category, author, tags)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (skill["id"], skill["name"], skill["icon"],
                         skill["description"], skill["category"],
                         skill["author"], skill["tags"])
                    )
                conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    # ========== 市场搜索 ==========

    def search_market(self, query: str = "", category: str = "",
                      limit: int = 30) -> List[Dict]:
        """搜索Skill市场"""
        conn = self.db.cognition_conn()
        try:
            sql = "SELECT * FROM skill_market WHERE 1=1"
            params = []

            if query:
                sql += " AND (name LIKE ? OR description LIKE ? OR tags LIKE ?)"
                like = f"%{query}%"
                params.extend([like, like, like])

            if category:
                sql += " AND category = ?"
                params.append(category)

            sql += " ORDER BY downloads DESC, rating DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_market_categories(self) -> List[Dict]:
        """获取市场分类"""
        conn = self.db.cognition_conn()
        try:
            rows = conn.execute(
                "SELECT category, COUNT(*) as count FROM skill_market GROUP BY category ORDER BY count DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ========== 安装管理 ==========

    def install(self, skill_id: str) -> Dict:
        """安装Skill（从市场安装到本地）"""
        conn = self.db.cognition_conn()
        try:
            # 检查是否已安装
            existing = conn.execute(
                "SELECT id FROM installed_skills WHERE id=?", (skill_id,)
            ).fetchone()
            if existing:
                return {"ok": False, "message": f"'{skill_id}' 已安装", "skill_id": skill_id}

            # 从市场读取
            row = conn.execute(
                "SELECT * FROM skill_market WHERE id=?", (skill_id,)
            ).fetchone()
            if not row:
                return {"ok": False, "message": f"市场未找到: {skill_id}", "skill_id": skill_id}
            skill = dict(row)

            # 安装到本地
            conn.execute(
                """INSERT INTO installed_skills
                (id, name, icon, description, version, color, source_url, category, author)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (skill["id"], skill["name"], skill.get("icon", "📦"),
                 skill.get("description", ""), skill.get("version", "1.0.0"),
                 skill.get("color", "#7c6ff0"), skill.get("source_url", ""),
                 skill.get("category", "通用"), skill.get("author", ""))
            )
            conn.commit()

            return {
                "ok": True,
                "message": f"✅ {skill['name']} 安装成功",
                "skill_id": skill_id,
                "name": skill["name"],
                "icon": skill.get("icon", "📦"),
            }
        except Exception as e:
            conn.rollback()
            return {"ok": False, "message": f"安装失败: {e}", "skill_id": skill_id}
        finally:
            conn.close()

    def uninstall(self, skill_id: str) -> Dict:
        """卸载Skill"""
        conn = self.db.cognition_conn()
        try:
            skill = conn.execute(
                "SELECT name FROM installed_skills WHERE id=?", (skill_id,)
            ).fetchone()
            if not skill:
                return {"ok": False, "message": f"未安装: {skill_id}"}

            conn.execute("DELETE FROM installed_skills WHERE id=?", (skill_id,))
            conn.commit()
            return {"ok": True, "message": f"🗑️ {skill['name']} 已卸载", "skill_id": skill_id}
        except Exception as e:
            conn.rollback()
            return {"ok": False, "message": f"卸载失败: {e}"}
        finally:
            conn.close()

    def list_installed(self) -> List[Dict]:
        """列出已安装Skill"""
        conn = self.db.cognition_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM installed_skills ORDER BY installed_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ========== 巡检（检查市场更新） ==========

    def inspect_updates(self) -> List[Dict]:
        """巡检市场，检查已安装的Skill是否有更新"""
        conn = self.db.cognition_conn()
        try:
            installed = conn.execute(
                "SELECT id, name, version FROM installed_skills"
            ).fetchall()

            updates = []
            for skill in installed:
                market = conn.execute(
                    "SELECT version, name FROM skill_market WHERE id=?",
                    (skill["id"],)
                ).fetchone()
                if market and market["version"] != skill["version"]:
                    updates.append({
                        "skill_id": skill["id"],
                        "name": skill["name"],
                        "current": skill["version"],
                        "latest": market["version"],
                    })

            return updates
        finally:
            conn.close()

    # ========== 精灵协调（接收猴子需求） ==========

    def search_by_requirement(self, requirement: str,
                              use_ai: bool = True) -> List[Dict]:
        """根据需求描述（来自猴子）搜索合适的Skill"""
        if not use_ai:
            # 简单关键词匹配
            return self.search_market(query=requirement)

        # AI辅助匹配：用采购员的Key调用LLM
        provider_config = self.config.get_provider_config("purchaser")
        provider = get_provider(provider_config["name"], provider_config)

        # 获取所有可用Skill
        all_skills = self.search_market(limit=100)

        # 构建Prompt让LLM匹配
        skills_desc = "\n".join([
            f"- {s['id']}: {s['name']} - {s.get('description','')} [{s.get('category','')}]"
            for s in all_skills
        ])

        prompt = f"""你是一个Skill采购员。用户需求: {requirement}

可选Skill列表:
{skills_desc}

请从列表中选择最匹配的3-5个Skill，按匹配度排序。
只返回JSON数组，格式: [{{"id":"...", "reason":"匹配原因"}}]
不返回其他文字。"""

        resp = provider.generate([{"role": "user", "content": prompt}])

        try:
            matched = json.loads(resp.content)
            if isinstance(matched, list):
                # 富化返回
                skill_map = {s["id"]: s for s in all_skills}
                result = []
                for m in matched:
                    sid = m.get("id", "")
                    if sid in skill_map:
                        s = dict(skill_map[sid])
                        s["match_reason"] = m.get("reason", "")
                        result.append(s)
                return result
        except (json.JSONDecodeError, TypeError):
            pass

        # 兜底：关键词匹配
        return self.search_market(query=requirement, limit=5)

    # ========== 整理（空闲时自动执行） ==========

    def organize(self) -> Dict:
        """整理 - 清理无用skill、合并重复、标记过期、整理仓库
        由IdleScheduler在空闲20分钟后自动触发
        """
        conn = self.db.cognition_conn()
        result = {"ok": True, "actions": [], "message": ""}
        try:
            actions = []

            # 1. 检查orphan skill（市场已下架但本地记录还在）
            for skill in conn.execute(
                "SELECT id, name FROM installed_skills WHERE enabled=1"
            ).fetchall():
                market = conn.execute(
                    "SELECT id FROM skill_market WHERE id=?", (skill["id"],)
                ).fetchone()
                if not market:
                    actions.append(f"发现已下架Skill: {skill['name']}, 标记为禁用")
                    conn.execute(
                        "UPDATE installed_skills SET enabled=0 WHERE id=?",
                        (skill["id"],)
                    )

            # 2. 检查重复安装（同名不同id）
            names = {}
            for skill in conn.execute(
                "SELECT id, name FROM installed_skills WHERE enabled=1"
            ).fetchall():
                if skill["name"] in names:
                    actions.append(f"发现重复Skill: {skill['name']}, 移除重复")
                    conn.execute("DELETE FROM installed_skills WHERE id=?", (skill["id"],))
                else:
                    names[skill["name"]] = skill["id"]

            result["actions"] = actions
            result["count"] = len(actions)
            result["message"] = f"整理完成: {'; '.join(actions[:5])}" + (
                f" 等{len(actions)}项" if len(actions) > 5 else ""
            ) if actions else "整理完成，无需操作"

            conn.commit()
            logger.info("[采购员] 整理: %s", result["message"])
        except Exception as e:
            conn.rollback()
            result["ok"] = False
            result["message"] = f"整理失败: {e}"
            logger.error("[采购员] 整理异常: %s", e)
        finally:
            conn.close()
        return result

    # ========== 猴子+采购员协同评估Skill更新 ==========

    def evaluate_with_monkey(self, monkey_evaluator, updates: List[Dict]) -> Dict:
        """猴子和采购员一起评估候选更新，决定是否安装"""
        if not updates:
            return {"ok": True, "message": "无待评估项", "installed": [], "skipped": []}

        conn = self.db.cognition_conn()
        installed = []
        skipped = []
        try:
            for upd in updates:
                skill_id = upd["skill_id"]
                skill = dict(conn.execute(
                    "SELECT * FROM skill_market WHERE id=?", (skill_id,)
                ).fetchone() or {})

                if not skill:
                    skipped.append({"id": skill_id, "reason": "市场已无此Skill"})
                    continue

                # 调用猴子做智能评估
                if monkey_evaluator:
                    try:
                        decision = monkey_evaluator(skill)
                    except Exception:
                        decision = {"install": True, "reason": "评估异常，默认采纳"}
                else:
                    decision = {"install": True, "reason": "猴子无反馈，默认采纳"}

                if decision.get("install", True):
                    conn.execute(
                        "UPDATE installed_skills SET version=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (skill.get("version", "1.0.0"), skill_id)
                    )
                    installed.append({
                        "id": skill_id, "name": skill["name"],
                        "version": skill.get("version", "1.0.0"),
                        "reason": decision.get("reason", ""),
                    })
                else:
                    skipped.append({
                        "id": skill_id, "name": skill["name"],
                        "reason": decision.get("reason", "猴子评估跳过"),
                    })

            conn.commit()
        except Exception as e:
            conn.rollback()
            return {"ok": False, "message": f"评估失败: {e}"}
        finally:
            conn.close()

        return {
            "ok": True,
            "message": f"评估完成: 安装{len(installed)}个, 跳过{len(skipped)}个",
            "installed": installed,
            "skipped": skipped,
        }

    # ========== 健康检查 ==========

    def health_check(self) -> Dict:
        """采购员健康状态"""
        conn = self.db.cognition_conn()
        try:
            installed = conn.execute(
                "SELECT COUNT(*) as c FROM installed_skills"
            ).fetchone()
            market_count = conn.execute(
                "SELECT COUNT(*) as c FROM skill_market"
            ).fetchone()
            updates = self.inspect_updates()

            return {
                "status": "ok",
                "installed_count": installed["c"] if installed else 0,
                "market_count": market_count["c"] if market_count else 0,
                "updates_available": len(updates),
                "updates": updates,
            }
        finally:
            conn.close()

    def suggest_new_skills(self, monkey=None) -> List[Dict]:
        """
        巡检时自动发现市场新Skill并评估是否值得安装
        猴子+采购员联合决策
        """
        conn = self.db.cognition_conn()
        try:
            installed_ids = [r[0] for r in conn.execute(
                "SELECT id FROM installed_skills"
            ).fetchall()]
            candidates = conn.execute(
                "SELECT * FROM skill_market ORDER BY downloads DESC, rating DESC LIMIT 10"
            ).fetchall()
            suggestions = []
            for c in candidates:
                if c["id"] in installed_ids:
                    continue
                skill = dict(c)
                suggestions.append({
                    "id": skill["id"], "name": skill["name"],
                    "icon": skill["icon"], "description": skill["description"],
                    "category": skill["category"], "reason": "热门推荐",
                })
            return suggestions[:5]
        finally:
            conn.close()

    # ========== 社区Skill市场匹配 ==========

    def community_search(self, query: str, source: str = "zhichai.net") -> List[Dict]:
        """
        搜索AI社区(如智柴网)的可用Skill
        返回当前搜到的社区Skill列表
        """
        import urllib.request
        import urllib.parse

        # 智柴网等AI社区搜索
        sources = {
            "zhichai.net": f"https://zhichai.net/search?q={urllib.parse.quote(query)}",
            "github.com": f"https://github.com/search?q={urllib.parse.quote(query)}+ai+skill&type=repositories",
            "huggingface.co": f"https://huggingface.co/models?search={urllib.parse.quote(query)}",
        }

        url = sources.get(source, sources["zhichai.net"])
        results = []

        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")[:500]
                results.append({
                    "source": source,
                    "url": url,
                    "status": resp.status,
                    "preview": content[:200],
                })
        except Exception as e:
            results.append({"source": source, "url": url, "error": str(e)[:100]})

        # 注册到市场
        conn = self.db.cognition_conn()
        try:
            for r in results:
                if r.get("status") == 200:
                    conn.execute(
                        "INSERT OR IGNORE INTO skill_market (id, name, icon, description, category, tags, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (f"community_{source.replace('.','_')}_{urllib.parse.quote(query)[:20]}",
                         f"社区搜索: {query}", "🌐",
                         f"来自{source}的社区搜索结果: {r.get('preview','')[:100]}",
                         "社区", f"{source},{query}", "1.0.0")
                    )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

        return results
