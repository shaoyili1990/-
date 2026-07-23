"""
采购员(Purchaser) - 采买与仓库管理员
职责:
  1. 搜索Skill市场 - 根据需求找合适的Skill
  2. 安装Skill - 下载并注册到系统
  3. 仓库管理 - 整理/分类/巡检
  4. 采购流 - 接收猴子/马/巡检者的外部资源请求，经猴子审批后执行

采购流规则:
  - 猴子、马、巡检者需要外部信息→必须通过采购者
  - 采购需求需猴子审批(猴子自己的需求由马+巡检者协同审批)
  - Keeper把关: 非任务执行期或用户明确搜索时,采购功能默认关闭
  - 审批通过后采购者执行,完成后结果返回请求方
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

# ─── 采购请求状态 ───
PROCUREMENT_PENDING = "pending"          # 待审批
PROCUREMENT_MONKEY_REVIEW = "monkey_review"  # 猴子审批中
PROCUREMENT_HORSE_PATROL_REVIEW = "hp_review"  # 马+巡检者审批中(猴子自己的请求)
PROCUREMENT_APPROVED = "approved"        # 已通过,执行中
PROCUREMENT_COMPLETED = "completed"      # 已完成
PROCUREMENT_REJECTED = "rejected"        # 已拒绝
PROCUREMENT_CLOSED = "closed"            # 已关闭

# 采购需求类型
PROCUREMENT_TYPES = {
    "knowledge": "知识库查询",
    "skill": "Skill检索/安装",
    "web_search": "联网搜索",
    "external_api": "外部API调用",
}

# 内置市场注册表（初始种子数据）
SEED_MARKET = [
    {"id": "web-search", "name": "网页搜索", "icon": "🔍", "description": "搜索引擎查询与结果提取", "category": "信息获取", "author": "Hermes", "tags": "搜索,网页,查询"},
    {"id": "web-fetch", "name": "网页抓取", "icon": "🕸️", "description": "读取指定URL内容为Markdown", "category": "信息获取", "author": "Hermes", "tags": "网页,抓取,URL"},
    {"id": "code-review", "name": "代码审查", "icon": "👁️", "description": "代码安全与质量审查", "category": "开发", "author": "Hermes", "tags": "代码,审查,安全"},
    {"id": "image-gen", "name": "图片生成", "icon": "🎨", "description": "文本描述生成图片", "category": "创意", "author": "Hermes", "tags": "图片,生成,AI绘画"},
    {"id": "file-parse", "name": "文件解析", "icon": "📄", "description": "PDF/Word/Excel文件内容提取", "category": "工具", "author": "Hermes", "tags": "文件,解析,PDF"},
    {"id": "data-chart", "name": "数据图表", "icon": "📊", "description": "数据可视化图表生成", "category": "数据分析", "author": "Hermes", "tags": "图表,数据,可视化"},
    {"id": "translate", "name": "翻译", "icon": "🌐", "description": "多语言翻译引擎", "category": "工具", "author": "Hermes", "tags": "翻译,语言,多语言"},
    {"id": "summarize", "name": "摘要", "icon": "📝", "description": "长文本自动摘要提取", "category": "文本处理", "author": "Hermes", "tags": "摘要,总结,压缩"},
    {"id": "db-query", "name": "数据库查询", "icon": "🗄️", "description": "自然语言转SQL查询", "category": "开发", "author": "Hermes", "tags": "数据库,SQL,查询"},
    {"id": "api-tester", "name": "API测试", "icon": "🧪", "description": "REST API测试与调试", "category": "开发", "author": "Hermes", "tags": "API,测试,调试"},
]


class Purchaser:
    """采购员 - 采买与仓库管理员"""

    def __init__(self, config: Config, db: EngineDB):
        self.config = config
        self.db = db
        self._init_market()
        self._init_procurement()

    def _init_market(self):
        """初始化市场种子数据"""
        conn = self.db.cognition_conn()
        try:
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

    def _init_procurement(self):
        """初始化采购请求表"""
        conn = self.db.cognition_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS procurement_requests (
                    id TEXT PRIMARY KEY,
                    requester_role TEXT NOT NULL,
                    procurement_type TEXT NOT NULL,
                    requirement TEXT NOT NULL,
                    context TEXT,
                    status TEXT DEFAULT 'pending',
                    reviewer TEXT,
                    review_comment TEXT,
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    task_id TEXT
                )
            """)
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    # ════════════════════════════════════════════════════════════
    # 采购流核心方法
    # ════════════════════════════════════════════════════════════

    def procurement_gate_check(self, keeper=None) -> Dict:
        """
        Keeper采购闸门检查:
        检查当前是否有活跃任务,或用户是否明确发起搜索请求。
        采购功能默认关闭,仅在任务执行期或用户显式请求时开放。
        """
        # 如果keeper传入,用keeper检查任务状态
        if keeper:
            tasks = keeper.list_tasks(status=None, limit=50)
            active = [t for t in tasks if t.get("status") not in (
                "验证通过", "验证未通过", "completed", "closed", "已关闭", "已结束")]
            if active:
                return {"ok": True, "reason": f"任务执行期: {active[0].get('name', '未知')}", "task_id": active[0].get("task_id", "")}

        # 如果没有keeper或没有活跃任务
        return {"ok": False, "reason": "采购功能默认关闭。仅任务执行期或用户显式搜索请求时可开启。", "task_id": ""}

    def submit_request(self, requester_role: str, procurement_type: str,
                       requirement: str, context: str = "",
                       task_id: str = "", keeper=None) -> Dict:
        """
        提交采购请求。
        requester_role: monkey / horse / patrol
        procurement_type: knowledge / skill / web_search / external_api
        requirement: 具体需求描述
        keeper: 用于闸门检查
        """
        # 1. Keeper闸门检查
        gate = self.procurement_gate_check(keeper)
        if not gate["ok"]:
            return {"ok": False, "error": gate["reason"], "gate_closed": True}

        # 2. 验证请求者角色
        valid_roles = ["monkey", "horse", "patrol"]
        if requester_role not in valid_roles:
            return {"ok": False, "error": f"不允许的角色: {requester_role}，仅允许: {valid_roles}"}

        # 3. 验证采购类型
        if procurement_type not in PROCUREMENT_TYPES:
            return {"ok": False, "error": f"不支持的类型: {procurement_type}，允许: {list(PROCUREMENT_TYPES.keys())}"}

        # 4. 创建请求
        request_id = f"PR-{uuid.uuid4().hex[:8].upper()}"
        conn = self.db.cognition_conn()
        try:
            conn.execute(
                """INSERT INTO procurement_requests
                (id, requester_role, procurement_type, requirement, context, status, task_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (request_id, requester_role, procurement_type, requirement,
                 context, PROCUREMENT_PENDING, task_id)
            )
            conn.commit()

            # 5. 根据请求者类型决定审核路径
            if requester_role == "monkey":
                # 猴子自己的需求→马+巡检者协同审批
                new_status = PROCUREMENT_HORSE_PATROL_REVIEW
                reviewer = "horse+patrol"
                conn.execute(
                    "UPDATE procurement_requests SET status=?, reviewer=? WHERE id=?",
                    (new_status, reviewer, request_id)
                )
            else:
                # 马/巡检者的需求→猴子审批
                new_status = PROCUREMENT_MONKEY_REVIEW
                reviewer = "monkey"
                conn.execute(
                    "UPDATE procurement_requests SET status=?, reviewer=? WHERE id=?",
                    (new_status, reviewer, request_id)
                )
            conn.commit()

            logger.info("[采购员] 采购请求 %s: [%s] %s → %s",
                        request_id, requester_role, requirement[:50], new_status)

            return {
                "ok": True,
                "request_id": request_id,
                "status": new_status,
                "requester": requester_role,
                "reviewer": reviewer,
                "procurement_type": PROCUREMENT_TYPES.get(procurement_type, procurement_type),
                "requirement": requirement,
                "task_id": task_id,
                "message": f"采购请求已提交，等待{reviewer}审批",
            }
        except Exception as e:
            conn.rollback()
            return {"ok": False, "error": f"提交采购请求失败: {e}"}
        finally:
            conn.close()

    def review_request(self, request_id: str, reviewer_role: str,
                       decision: str, comment: str = "") -> Dict:
        """
        审批采购请求。
        reviewer_role: 审批者角色
        decision: approve / reject
        comment: 审批意见
        """
        conn = self.db.cognition_conn()
        try:
            row = conn.execute(
                "SELECT * FROM procurement_requests WHERE id=?", (request_id,)
            ).fetchone()
            if not row:
                return {"ok": False, "error": f"采购请求不存在: {request_id}"}

            req = dict(row)
            current = req["status"]

            # 验证审批者角色
            if current == PROCUREMENT_MONKEY_REVIEW and reviewer_role != "monkey":
                return {"ok": False, "error": f"此请求当前需要猴子审批,非{reviewer_role}"}
            if current == PROCUREMENT_HORSE_PATROL_REVIEW and reviewer_role not in ("horse", "patrol"):
                return {"ok": False, "error": f"此请求当前需要马+巡检者审批,非{reviewer_role}"}

            # 如果是马+巡检者协同审批(猴子自己的请求):需要双方都同意
            if current == PROCUREMENT_HORSE_PATROL_REVIEW:
                # 记录当前审批人意见
                existing_review = req.get("review_comment") or "{}"
                try:
                    reviews = json.loads(existing_review)
                except (json.JSONDecodeError, TypeError):
                    reviews = {}
                reviews[reviewer_role] = {"decision": decision, "comment": comment}

                if decision == "reject":
                    # 任意一人拒绝即驳回
                    new_status = PROCUREMENT_REJECTED
                    conn.execute(
                        "UPDATE procurement_requests SET status=?, review_comment=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
                        (new_status, json.dumps(reviews, ensure_ascii=False), request_id)
                    )
                elif len(reviews) >= 2 and "horse" in reviews and "patrol" in reviews:
                    # 两人都批准
                    new_status = PROCUREMENT_APPROVED
                    conn.execute(
                        "UPDATE procurement_requests SET status=?, review_comment=? WHERE id=?",
                        (new_status, json.dumps(reviews, ensure_ascii=False), request_id)
                    )
                else:
                    # 还差一人
                    conn.execute(
                        "UPDATE procurement_requests SET review_comment=? WHERE id=?",
                        (json.dumps(reviews, ensure_ascii=False), request_id)
                    )
                    conn.commit()
                    return {
                        "ok": True,
                        "request_id": request_id,
                        "status": current,
                        "message": f"{reviewer_role}已审批,等待另一方",
                        "reviews": reviews,
                    }
            else:
                # 猴子审批(马/巡检者的请求)
                if decision == "approve":
                    new_status = PROCUREMENT_APPROVED
                else:
                    new_status = PROCUREMENT_REJECTED

                conn.execute(
                    "UPDATE procurement_requests SET status=?, reviewer=?, review_comment=? WHERE id=?",
                    (new_status, reviewer_role, comment, request_id)
                )

            conn.commit()

            msg = f"采购请求{request_id}: {decision}"
            if decision == "approve":
                msg += "，采购者开始执行"
            else:
                msg += f"，原因: {comment}"

            logger.info("[采购员] %s, 状态: %s", msg, new_status)

            return {
                "ok": True,
                "request_id": request_id,
                "status": new_status,
                "reviewer": reviewer_role,
                "decision": decision,
                "comment": comment,
                "message": msg,
            }
        except Exception as e:
            conn.rollback()
            return {"ok": False, "error": f"审批失败: {e}"}
        finally:
            conn.close()

    def execute_request(self, request_id: str) -> Dict:
        """
        审批通过后,采购者执行采购请求。
        执行完成后结果返回请求方,请求关闭。
        """
        conn = self.db.cognition_conn()
        try:
            row = conn.execute(
                "SELECT * FROM procurement_requests WHERE id=?", (request_id,)
            ).fetchone()
            if not row:
                return {"ok": False, "error": f"采购请求不存在: {request_id}"}

            req = dict(row)
            if req["status"] != PROCUREMENT_APPROVED:
                return {"ok": False, "error": f"请求状态不允许执行: {req['status']}, 需为approved"}

            ptype = req["procurement_type"]
            requirement = req["requirement"]
            requester = req["requester_role"]

            # 根据采购类型执行
            result_data = {}
            if ptype == "skill":
                # 搜索Skill市场
                result_data = self._execute_skill_search(requirement)
            elif ptype == "knowledge":
                # 知识库查询
                result_data = self._execute_knowledge_query(requirement)
            elif ptype == "web_search":
                # 联网搜索
                result_data = self._execute_web_search(requirement)
            elif ptype == "external_api":
                # 外部API
                result_data = self._execute_external_api(requirement)
            else:
                result_data = {"result": f"未知类型: {ptype}"}

            # 更新结果并关闭
            result_json = json.dumps(result_data, ensure_ascii=False)
            conn.execute(
                "UPDATE procurement_requests SET status=?, result=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
                (PROCUREMENT_COMPLETED, result_json, request_id)
            )
            conn.commit()

            logger.info("[采购员] 采购请求 %s 执行完成, 结果长度: %d", request_id, len(result_json))

            return {
                "ok": True,
                "request_id": request_id,
                "status": PROCUREMENT_COMPLETED,
                "requester": requester,
                "procurement_type": ptype,
                "data": result_data,
                "message": f"采购完成,结果已返回{requester}",
            }
        except Exception as e:
            conn.rollback()
            return {"ok": False, "error": f"执行采购失败: {e}"}
        finally:
            conn.close()

    def _execute_skill_search(self, requirement: str) -> Dict:
        """执行Skill搜索"""
        skills = self.search_market(query=requirement, limit=5)
        # AI辅助匹配
        ai_matched = self.search_by_requirement(requirement)
        return {
            "found": len(skills),
            "skills": [{"id": s["id"], "name": s["name"], "desc": s.get("description", "")} for s in skills],
            "ai_recommended": [{"id": s["id"], "name": s["name"], "reason": s.get("match_reason", "")} for s in ai_matched[:3]],
            "requirement": requirement,
        }

    def _execute_knowledge_query(self, requirement: str) -> Dict:
        """执行知识库查询"""
        conn = self.db.cognition_conn()
        try:
            rows = conn.execute(
                "SELECT title, content, source FROM web_knowledge WHERE content LIKE ? LIMIT 5",
                (f"%{requirement}%",)
            ).fetchall()
            return {
                "found": len(rows),
                "results": [{"title": r["title"], "content_preview": r["content"][:200],
                             "source": r["source"]} for r in rows],
                "requirement": requirement,
            }
        except Exception:
            return {"found": 0, "results": [], "note": "知识库表不存在或无数据", "requirement": requirement}
        finally:
            conn.close()

    def _execute_web_search(self, requirement: str) -> Dict:
        """执行联网搜索"""
        import urllib.request, urllib.parse
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(requirement)}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")[:3000]
            return {"source": "web", "preview": content[:500], "requirement": requirement}
        except Exception as e:
            return {"source": "web", "error": str(e)[:200], "requirement": requirement}

    def _execute_external_api(self, requirement: str) -> Dict:
        """执行外部API调用(预留)"""
        return {"note": "外部API调用类型已预留,暂未实现", "requirement": requirement}

    def get_request_status(self, request_id: str) -> Dict:
        """查询采购请求状态"""
        conn = self.db.cognition_conn()
        try:
            row = conn.execute(
                "SELECT * FROM procurement_requests WHERE id=?", (request_id,)
            ).fetchone()
            if not row:
                return {"ok": False, "error": f"采购请求不存在: {request_id}"}
            return {"ok": True, "request": dict(row)}
        finally:
            conn.close()

    def list_my_requests(self, role: str = "", status: str = "",
                         limit: int = 20) -> Dict:
        """列出采购请求(按角色/状态过滤)"""
        conn = self.db.cognition_conn()
        try:
            sql = "SELECT * FROM procurement_requests WHERE 1=1"
            params = []
            if role:
                sql += " AND requester_role = ?"
                params.append(role)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return {"ok": True, "requests": [dict(r) for r in rows], "count": len(rows)}
        finally:
            conn.close()

    def close_request(self, request_id: str) -> Dict:
        """手动关闭采购请求"""
        conn = self.db.cognition_conn()
        try:
            conn.execute(
                "UPDATE procurement_requests SET status=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
                (PROCUREMENT_CLOSED, request_id)
            )
            conn.commit()
            return {"ok": True, "message": f"请求{request_id}已关闭"}
        except Exception as e:
            return {"ok": False, "error": f"关闭失败: {e}"}
        finally:
            conn.close()

    # ════════════════════════════════════════════════════════════
    # 原有方法 (保持向后兼容)
    # ════════════════════════════════════════════════════════════

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

    def install(self, skill_id: str) -> Dict:
        """安装Skill（从市场安装到本地）"""
        conn = self.db.cognition_conn()
        try:
            existing = conn.execute(
                "SELECT id FROM installed_skills WHERE id=?", (skill_id,)
            ).fetchone()
            if existing:
                return {"ok": False, "message": f"'{skill_id}' 已安装", "skill_id": skill_id}
            row = conn.execute(
                "SELECT * FROM skill_market WHERE id=?", (skill_id,)
            ).fetchone()
            if not row:
                return {"ok": False, "message": f"市场未找到: {skill_id}", "skill_id": skill_id}
            skill = dict(row)
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
            return {"ok": True, "message": f"✅ {skill['name']} 安装成功", "skill_id": skill_id,
                    "name": skill["name"], "icon": skill.get("icon", "📦")}
        except Exception as e:
            conn.rollback()
            return {"ok": False, "message": f"安装失败: {e}", "skill_id": skill_id}
        finally:
            conn.close()

    def uninstall(self, skill_id: str) -> Dict:
        """卸载Skill"""
        conn = self.db.cognition_conn()
        try:
            skill = conn.execute("SELECT name FROM installed_skills WHERE id=?", (skill_id,)).fetchone()
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
            rows = conn.execute("SELECT * FROM installed_skills ORDER BY installed_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def search_by_requirement(self, requirement: str, use_ai: bool = True) -> List[Dict]:
        """根据需求描述搜索合适的Skill"""
        if not use_ai:
            return self.search_market(query=requirement)
        provider_config = self.config.get_provider_config("purchaser")
        provider = get_provider(provider_config["name"], provider_config)
        all_skills = self.search_market(limit=100)
        skills_desc = "\n".join([f"- {s['id']}: {s['name']} - {s.get('description','')} [{s.get('category','')}]" for s in all_skills])
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
        return self.search_market(query=requirement, limit=5)

    def health_check(self) -> Dict:
        """采购员健康状态"""
        conn = self.db.cognition_conn()
        try:
            installed = conn.execute("SELECT COUNT(*) as c FROM installed_skills").fetchone()
            market_count = conn.execute("SELECT COUNT(*) as c FROM skill_market").fetchone()
            pending = conn.execute(
                "SELECT COUNT(*) as c FROM procurement_requests WHERE status NOT IN (?,?,?)",
                (PROCUREMENT_COMPLETED, PROCUREMENT_REJECTED, PROCUREMENT_CLOSED)
            ).fetchone()
            return {
                "status": "ok",
                "installed_count": installed["c"] if installed else 0,
                "market_count": market_count["c"] if market_count else 0,
                "pending_procurements": pending["c"] if pending else 0,
            }
        finally:
            conn.close()
