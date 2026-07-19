"""
多门类自治巡检系统 - 每日1:00 自治联网巡逻

核心机制:
  1. 定义多门类方向: 综艺、演艺圈、八卦、时事、科技、AI、国家大事、考古、历史等
  2. AI领域为T1最高优先级
  3. 每次巡检: 联网搜索 → 摘要 → 更新关注度评分
  4. 评分满分150分, 根据: 巡检次数(≥10次基数)、指纹解读反馈、猴子评估
  5. 全部打分完毕 → 分权 T1-T5 五档
  6. 每日1:00 从头开始巡检

存储: 引擎DB + 认知DB的env_config表
"""
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ..engine import EngineDB
from ..providers import get_provider

logger = logging.getLogger("patrol")

# ===== 多门类定义 =====
# (id, display_name, keywords, description, tier)
CATEGORIES = [
    # T1 - AI领域最高优先级
    ("ai", "AI领域", ["AI", "人工智能", "大模型", "AGI", "LLM", "GPT", "深度学习",
                       "机器学习", "神经网络", "自然语言处理", "计算机视觉"],
     "AI前沿发展、大模型进展、学术突破、应用落地", "T1"),

    # T1 - 时事/国家大事
    ("current_affairs", "时事新闻", ["时事", "新闻", "政治", "政策", "法规", "国际",
                                     "外交", "经济", "财经", "社会"],
     "国内外重大时事、政策变化、经济走势", "T1"),

    ("national_affairs", "国家大事", ["国家大事", "中央", "国务院", "两会", "十四五",
                                       "二十大", "中国", "中美", "一带一路"],
     "国家战略、重大政策、国内焦点事件", "T1"),

    # T2 - 科技/人文
    ("tech", "科技发展", ["科技", "技术", "创新", "科研", "芯片", "航天", "量子",
                          "新能源", "生物技术", "脑机"],
     "前沿科技突破、技术创新、科研进展", "T2"),

    ("digital_humanities", "数字人文", ["数字人文", "数字化", "古籍", "文化遗产",
                                         "博物馆", "非遗", "文物保护"],
     "数字技术赋能人文研究的交叉领域", "T2"),

    # T3 - 文化/历史
    ("entertainment", "综艺娱乐", ["综艺", "真人秀", "选秀", "综艺节目", "娱乐"],
     "热门综艺节目、行业动态、文化现象", "T3"),

    ("showbiz", "演艺圈", ["演艺", "演员", "歌手", "影视", "电影", "电视剧",
                            "票房", "导演"],
     "影视行业动态、艺人资讯、作品评价", "T3"),

    ("gossip", "八卦新闻", ["八卦", "爆料", "热搜", "网红", "吃瓜", "争议"],
     "社交热点、舆论风波、公众话题", "T3"),

    # T4 - 人文考古/历史
    ("archaeology", "人文考古", ["考古", "遗址", "文物", "发掘", "化石", "古代文明"],
     "考古发现、遗迹研究、文物考据", "T4"),

    ("history", "人文历史", ["历史", "古代", "近代", "文明", "王朝", "历史人物",
                              "历史事件", "史书"],
     "历史研究新发现、历史解读、文化传承", "T4"),

    # T5 - 其他生态
    ("skill_community", "技能社区", ["开源", "社区", "github", "插件", "工具库",
                                       "开发者生态"],
     "开发者社区动态、开源项目、Skill生态", "T5"),
]

# env_config keys
KEY_PATROL = "patrol_state"         # patrol_状态 (idle/patrolling/reporting)
KEY_PATROL_TS = "patrol_ts"         # 当前巡逻时间戳
KEY_PATROL_INDEX = "patrol_idx"     # 当前巡逻到的分类索引
KEY_PATROL_DATE = "patrol_date"     # 最后巡逻日期(YYYY-MM-DD)
KEY_PATROL_SCORES = "patrol_scores" # 所有分类评分JSON
KEY_PATROL_TIERS = "patrol_tiers"   # 分权结果JSON
KEY_PATROL_SUMMARY = "patrol_summary"  # 最近一次巡逻摘要
KEY_PATROL_COUNTS = "patrol_counts"    # 每个分类巡逻次数JSON


class PatrolSystem:
    """多门类自治巡检系统"""

    def __init__(self, db: EngineDB, agent=None, monkey=None, purchaser=None):
        self.db = db
        self.agent = agent
        self.monkey = monkey
        self.purchaser = purchaser
        self._ensure()

    def _conn(self):
        return self.db.engine_conn()

    def _ensure(self):
        conn = self._conn()
        try:
            defaults = {
                KEY_PATROL: "idle",
                KEY_PATROL_TS: str(time.time()),
                KEY_PATROL_INDEX: "0",
                KEY_PATROL_DATE: "",
                KEY_PATROL_SCORES: json.dumps({
                    c[0]: {"id": c[0], "name": c[1], "score": 0, "tier": c[4],
                           "count": 0, "last": ""} for c in CATEGORIES
                }, ensure_ascii=False),
                KEY_PATROL_TIERS: json.dumps({}, ensure_ascii=False),
                KEY_PATROL_SUMMARY: json.dumps([], ensure_ascii=False),
                KEY_PATROL_COUNTS: json.dumps({}, ensure_ascii=False),
            }
            for k, v in defaults.items():
                conn.execute("INSERT OR IGNORE INTO env_config (key, value) VALUES (?, ?)", (k, v))
            conn.commit()
        finally:
            conn.close()

    def _get(self, key: str) -> str:
        conn = self._conn()
        try:
            r = conn.execute("SELECT value FROM env_config WHERE key=?", (key,)).fetchone()
            return r[0] if r else ""
        finally:
            conn.close()

    def _set(self, key: str, value: str):
        conn = self._conn()
        try:
            conn.execute("INSERT OR REPLACE INTO env_config (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
        finally:
            conn.close()

    def get_categories(self) -> List[Dict]:
        """获取所有门类及其当前评分"""
        scores_raw = self._get(KEY_PATROL_SCORES)
        try:
            scores = json.loads(scores_raw)
        except (json.JSONDecodeError, TypeError):
            scores = {}
        tiers_raw = self._get(KEY_PATROL_TIERS)
        try:
            tiers = json.loads(tiers_raw)
        except (json.JSONDecodeError, TypeError):
            tiers = {}

        result = []
        for cid, name, keywords, desc, default_tier in CATEGORIES:
            s = scores.get(cid, {"score": 0, "count": 0, "last": ""})
            result.append({
                "id": cid, "name": name, "description": desc,
                "keywords": keywords, "score": s.get("score", 0),
                "count": s.get("count", 0),
                "last_patrol": s.get("last", ""),
                "current_tier": tiers.get(cid, default_tier),
                "default_tier": default_tier,
            })
        return result

    def get_status(self) -> Dict:
        """获取巡检系统完整状态"""
        state = self._get(KEY_PATROL)
        idx_raw = self._get(KEY_PATROL_INDEX)
        idx = int(idx_raw) if idx_raw.isdigit() else 0
        last_date = self._get(KEY_PATROL_DATE)
        cats = self.get_categories()

        # 统计
        scored = [c for c in cats if c["score"] > 0]
        tier_dist = {}
        for c in cats:
            t = c["current_tier"]
            tier_dist[t] = tier_dist.get(t, 0) + 1

        # 当前正在巡逻的分类
        current = cats[idx] if idx < len(cats) else cats[0]

        summary_raw = self._get(KEY_PATROL_SUMMARY)
        try:
            summary = json.loads(summary_raw)
        except (json.JSONDecodeError, TypeError):
            summary = []

        return {
            "state": state,
            "current_index": idx,
            "total_categories": len(cats),
            "last_patrol_date": last_date,
            "scored_categories": len(scored),
            "tier_distribution": tier_dist,
            "current_category": current,
            "categories": cats,
            "recent_summary": summary[:5],
            "tier_dist": tier_dist,
        }

    def tick(self, force_patrol: bool = False) -> Dict:
        """
        调度器 tick 时调用 (通常在 空闲→巡检阶段)
        检查是否已到 1:00 每日重置时间
        force_patrol=True: 手动强制开启一轮巡逻
        """
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        last_date = self._get(KEY_PATROL_DATE)
        state = self._get(KEY_PATROL)

        # 每日 1:00 重置所有分类评分
        if now.hour == 1 and now.minute == 0 and last_date != today:
            self._daily_reset(today)
            return {"action": "daily_reset", "date": today}

        # 强制巡逻: 重置状态开始巡逻
        if force_patrol and state != "patrolling":
            self._set(KEY_PATROL_DATE, today)
            self._set(KEY_PATROL_INDEX, "0")
            self._set(KEY_PATROL, "patrolling")
            self._set(KEY_PATROL_TS, str(time.time()))
            return {"action": "force_start", "date": today}

        # 如果处于巡逻中状态
        if state == "patrolling":
            return self._do_patrol_one()

        return {"action": "idle", "state": state}

    def _daily_reset(self, today: str):
        """每日1:00重置: 把所有分类标记为待巡逻"""
        self._set(KEY_PATROL_DATE, today)
        self._set(KEY_PATROL_INDEX, "0")
        self._set(KEY_PATROL, "patrolling")
        self._set(KEY_PATROL_TS, str(time.time()))
        logger.info(f"[Patrol] 每日重置: {today} 开始巡逻")

    def _do_patrol_one(self) -> Dict:
        """巡逻一个分类"""
        idx_raw = self._get(KEY_PATROL_INDEX)
        idx = int(idx_raw) if idx_raw.isdigit() else 0

        if idx >= len(CATEGORIES):
            # 全部巡逻完毕 → 进入评分分权
            self._set(KEY_PATROL, "scoring")
            return self._do_scoring()

        cat = CATEGORIES[idx]
        cid, name, keywords, desc, tier = cat

        logger.info(f"[Patrol] 巡逻第{idx+1}/{len(CATEGORIES)}: {name}")

        # 执行联网搜索
        try:
            search_result = self._web_search(name, keywords)
        except Exception as e:
            search_result = {"ok": False, "error": str(e)[:100]}
            logger.warning(f"[Patrol] {name} 搜索失败: {e}")

        # 更新评分
        self._update_score(cid, search_result)

        # 更新Next index
        self._set(KEY_PATROL_INDEX, str(idx + 1))

        return {
            "action": "patrol",
            "category": name,
            "index": idx,
            "total": len(CATEGORIES),
            "progress": f"{idx+1}/{len(CATEGORIES)}",
            "search_result": search_result.get("summary") if isinstance(search_result, dict) else "",
        }

    def _web_search(self, category_name: str, keywords: List[str]) -> Dict:
        """联网搜索分类最新内容"""
        try:
            from ..agent import HermesAgent
            if self.agent:
                result = self.agent.chat(f"搜索 {category_name} 最新动态: {', '.join(keywords[:3])}")
                return {"ok": True, "summary": str(result)[:300]}
            return {"ok": False, "summary": "agent不可用"}
        except ImportError:
            pass

        # 用Python简单web请求
        import urllib.request
        import urllib.parse

        query_words = keywords[:3]
        query = f"{category_name} {' '.join(query_words)} 最新进展"
        try:
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                summary = f"已搜索 {category_name} 方向，共获取{len(resp.read())}字节内容"
                return {"ok": True, "summary": summary}
        except Exception as e:
            return {"ok": False, "error": str(e)[:100], "summary": f"搜索{category_name}失败"}

    def _update_score(self, cid: str, search_result: Dict):
        """更新关注度评分 (满分150)"""
        scores_raw = self._get(KEY_PATROL_SCORES)
        try:
            scores = json.loads(scores_raw)
        except (json.JSONDecodeError, TypeError):
            scores = {}

        now = datetime.now().strftime("%m-%d %H:%M")
        entry = scores.get(cid, {"score": 0, "count": 0, "last": ""})

        # 基础分: 每次巡检+5
        entry["count"] = entry.get("count", 0) + 1
        base_score = min(50, entry["count"] * 5)

        # 内容分: 搜索成功+15
        content_score = 15 if isinstance(search_result, dict) and search_result.get("ok") else 0

        # 连贯分: 连续巡检≥10次+25
        continuity = 25 if entry["count"] >= 10 else 0

        # 猴子反馈分: 调用猴子评估 (模拟+5)
        monkey_score = 5

        total = min(150, base_score + content_score + continuity + monkey_score)

        entry["score"] = total
        entry["last"] = now
        scores[cid] = entry

        self._set(KEY_PATROL_SCORES, json.dumps(scores, ensure_ascii=False))
        logger.info(f"[Patrol] {cid} 评分更新: {total}/150 (巡检{entry['count']}次)")

    def _do_scoring(self) -> Dict:
        """全部打分完毕后进行 T1-T5 分权"""
        scores_raw = self._get(KEY_PATROL_SCORES)
        try:
            scores = json.loads(scores_raw)
        except (json.JSONDecodeError, TypeError):
            scores = {}

        # 按评分排序
        sorted_cats = sorted(scores.items(), key=lambda x: x[1].get("score", 0), reverse=True)
        n = len(sorted_cats)

        tiers = {}
        for i, (cid, entry) in enumerate(sorted_cats):
            # 按排名分T1-T5
            if i < max(1, n * 0.15):  # top 15%
                t = "T1"
            elif i < max(2, n * 0.35):  # 15-35%
                t = "T2"
            elif i < max(3, n * 0.55):  # 35-55%
                t = "T3"
            elif i < max(4, n * 0.75):  # 55-75%
                t = "T4"
            else:
                t = "T5"

            # 保底: 原默认T1的不低于T2
            for cid_orig, _, _, _, default_tier in CATEGORIES:
                if cid_orig == cid and default_tier == "T1":
                    if t not in ("T1", "T2"):
                        t = "T2"
                    break

            tiers[cid] = t

        self._set(KEY_PATROL_TIERS, json.dumps(tiers, ensure_ascii=False))
        self._set(KEY_PATROL, "idle")

        logger.info(f"[Patrol] 分权完成: {tiers}")

        # 记录摘要
        summary = []
        for cid, t in sorted(tiers.items(), key=lambda x: x[1]):
            entry = scores.get(cid, {})
            summary.append({
                "cid": cid, "tier": t,
                "score": entry.get("score", 0),
                "count": entry.get("count", 0),
            })
        self._set(KEY_PATROL_SUMMARY, json.dumps(summary[:10], ensure_ascii=False))

        return {
            "action": "scoring_complete",
            "tiers": tiers,
            "scored_count": n,
        }
