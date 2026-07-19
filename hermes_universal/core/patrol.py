"""
多门类自治巡检系统 - 每日1:00 自治联网巡逻(CURL真实搜索)

核心:
  1. 用 curl 实时联网搜索(DuckDuckGo + 垂直源)
  2. 内容质量决定评分差异
  3. 每日1:00重置 → 全部巡逻 → 分权T1-T5
  4. 多次巡逻后自然产生产分差
"""
import json
import logging
import re
import subprocess
import time
import urllib.parse
from datetime import datetime
from typing import Dict, List

from ..engine import EngineDB

# Agent Reach — 巡逻首选搜索
try:
    from ..tools.agent_reach import patrol_search as _agent_reach_search
    _HAS_AGENT_REACH = True
except ImportError:
    _HAS_AGENT_REACH = False

logger = logging.getLogger("patrol")

CURL_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
           "AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36")

# ===== 11 门类定义 =====
# (id, display_name, keywords, description, default_tier, sources)
# sources: (name, url_template, type)  type=search使用DDG, fetch直接抓
CATEGORIES = [
    ("ai", "AI领域",
     ["AI", "人工智能", "大模型", "AGI", "LLM", "GPT", "深度学习", "机器学习"],
     "AI前沿发展、大模型进展、学术突破", "T1",
     [("DDG", "https://html.duckduckgo.com/html/?q={kw}+AI+2025", "search"),
      ("HuggingFace", "https://huggingface.co/models?search={kw}", "fetch")]),

    ("current_affairs", "时事新闻",
     ["时事", "新闻", "政治", "政策", "法规", "国际", "经济", "社会"],
     "国内外重大时事、政策变化、经济走势", "T1",
     [("DDG", "https://html.duckduckgo.com/html/?q={kw}+2025+最新", "search"),
      ("HN", "https://news.ycombinator.com", "fetch")]),

    ("national_affairs", "国家大事",
     ["国家大事", "中央", "国务院", "中国", "两会", "中美", "一带一路"],
     "国家战略、重大政策、国内焦点事件", "T1",
     [("DDG", "https://html.duckduckgo.com/html/?q={kw}+2025", "search")]),

    ("tech", "科技发展",
     ["科技", "技术", "创新", "芯片", "航天", "量子", "新能源", "科研"],
     "前沿科技突破、技术创新", "T2",
     [("DDG", "https://html.duckduckgo.com/html/?q={kw}+2025+突破", "search"),
      ("36Kr", "https://www.36kr.com", "fetch")]),

    ("digital_humanities", "数字人文",
     ["数字人文", "数字化", "古籍", "文化遗产", "博物馆", "非遗"],
     "数字技术赋能人文研究", "T2",
     [("DDG", "https://html.duckduckgo.com/html/?q={kw}+2025", "search")]),

    ("entertainment", "综艺娱乐",
     ["综艺", "娱乐", "选秀", "综艺节目", "真人秀"],
     "热门综艺节目、行业动态", "T3",
     [("DDG", "https://html.duckduckgo.com/html/?q={kw}+2025", "search")]),

    ("showbiz", "演艺圈",
     ["演艺", "演员", "影视", "电影", "票房", "导演", "电视剧"],
     "影视行业动态、艺人资讯", "T3",
     [("DDG", "https://html.duckduckgo.com/html/?q={kw}+2025+最新", "search")]),

    ("gossip", "八卦新闻",
     ["八卦", "爆料", "热搜", "网红", "吃瓜", "争议"],
     "社交热点、舆论风波", "T3",
     [("DDG", "https://html.duckduckgo.com/html/?q={kw}+2025", "search")]),

    ("archaeology", "人文考古",
     ["考古", "遗址", "文物", "发掘", "化石", "古代文明"],
     "考古发现、遗迹研究", "T4",
     [("DDG", "https://html.duckduckgo.com/html/?q={kw}+最新发现", "search")]),

    ("history", "人文历史",
     ["历史", "古代", "文明", "王朝", "历史人物", "历史事件"],
     "历史研究新发现、历史解读", "T4",
     [("DDG", "https://html.duckduckgo.com/html/?q={kw}+2025", "search")]),

    ("skill_community", "技能社区",
     ["开源", "社区", "github", "插件", "工具库", "开发者"],
     "开发者社区动态、开源项目", "T5",
     [("GitHub", "https://github.com/trending", "fetch"),
      ("HF", "https://huggingface.co/models", "fetch"),
      ("DDG", "https://html.duckduckgo.com/html/?q={kw}+2025+开源", "search")]),
]

# env_config keys
KEY_PATROL = "patrol_state"
KEY_PATROL_TS = "patrol_ts"
KEY_PATROL_IDX = "patrol_idx"
KEY_PATROL_DATE = "patrol_date"
KEY_PATROL_SCORES = "patrol_scores"
KEY_PATROL_TIERS = "patrol_tiers"
KEY_PATROL_SUMMARY = "patrol_summary"


class PatrolSystem:
    """多门类自治巡检系统 - 真实联网搜索"""

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
                KEY_PATROL_IDX: "0",
                KEY_PATROL_DATE: "",
                KEY_PATROL_SCORES: json.dumps({
                    c[0]: {"score": 0, "count": 0, "last": "", "tier": c[4]}
                    for c in CATEGORIES
                }, ensure_ascii=False),
                KEY_PATROL_TIERS: json.dumps({}, ensure_ascii=False),
                KEY_PATROL_SUMMARY: json.dumps([], ensure_ascii=False),
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

    # ── 状态查询 ──

    def get_categories(self) -> List[Dict]:
        try:
            scores = json.loads(self._get(KEY_PATROL_SCORES) or "{}")
        except Exception:
            scores = {}
        try:
            tiers = json.loads(self._get(KEY_PATROL_TIERS) or "{}")
        except Exception:
            tiers = {}
        result = []
        for cid, name, keywords, desc, default_tier, sources in CATEGORIES:
            s = scores.get(cid, {"score": 0, "count": 0, "last": ""})
            result.append({
                "id": cid, "name": name, "description": desc, "keywords": keywords,
                "score": s.get("score", 0), "count": s.get("count", 0),
                "last_patrol": s.get("last", ""),
                "current_tier": tiers.get(cid, default_tier), "default_tier": default_tier,
            })
        return result

    def get_status(self) -> Dict:
        cats = self.get_categories()
        idx_raw = self._get(KEY_PATROL_IDX)
        idx = int(idx_raw) if idx_raw.isdigit() else 0
        current = cats[idx] if idx < len(cats) else (cats[-1] if cats else {"name": "无"})
        scored = [c for c in cats if c["score"] > 0]
        tier_dist = {}
        for c in cats:
            t = c["current_tier"]
            tier_dist[t] = tier_dist.get(t, 0) + 1
        try:
            summary = json.loads(self._get(KEY_PATROL_SUMMARY) or "[]")
        except Exception:
            summary = []
        return {
            "state": self._get(KEY_PATROL) or "idle",
            "last_date": self._get(KEY_PATROL_DATE),
            "current_index": idx,
            "total_categories": len(cats),
            "scored_categories": len(scored),
            "tier_distribution": tier_dist,
            "current_category": current,
            "categories": cats,
            "recent_summary": summary[:5],
        }

    # ── 心跳入口 ──

    def tick(self, force_patrol: bool = False) -> Dict:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        last_date = self._get(KEY_PATROL_DATE)
        state = self._get(KEY_PATROL)

        # 每日1:00自动重置
        if now.hour == 1 and now.minute < 5 and last_date != today:
            self._daily_reset(today)
            return {"action": "daily_reset", "date": today}

        if force_patrol:
            self._daily_reset(today)
            return {"action": "force_reset", "date": today}

        if state == "patrolling":
            return self._do_patrol_one()
        if state == "scoring":
            return self._do_scoring()
        return {"action": "idle"}

    def _daily_reset(self, today: str):
        self._set(KEY_PATROL_DATE, today)
        self._set(KEY_PATROL_IDX, "0")
        self._set(KEY_PATROL, "patrolling")
        self._set(KEY_PATROL_TS, str(time.time()))

    # ── 核心: curl联网搜索 ──

    def _curl_fetch(self, url: str, timeout: int = 8) -> Dict:
        """curl获取URL内容(Popen+communicate避免pipe满阻塞)"""
        try:
            proc = subprocess.Popen(
                ["curl", "-s", "-L", "--max-time", str(timeout),
                 "-A", CURL_UA, url],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = proc.communicate(timeout=timeout + 2)
            body = stdout.decode("utf-8", errors="replace")
            cleaned = re.sub(r'<[^>]+>', ' ', body)
            text = re.sub(r'\s+', ' ', cleaned).strip()
            return {"ok": True, "text": text, "length": len(body)}
        except subprocess.TimeoutExpired:
            proc.kill()
            return {"ok": False, "error": "timeout"}
        except FileNotFoundError:
            return {"ok": False, "error": "curl not found"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:80]}

    def _do_patrol_one(self) -> Dict:
        idx = int(self._get(KEY_PATROL_IDX) or "0")
        if idx >= len(CATEGORIES):
            self._set(KEY_PATROL, "scoring")
            return self._do_scoring()

        cid, name, keywords, desc, tier, sources = CATEGORIES[idx]
        kw = urllib.parse.quote(keywords[0] if keywords else name)
        raw_kw = keywords[0] if keywords else name

        results = []
        ar_content = None  # AR 聚合文本

        # ── P0: Agent Reach 优先搜索（多源并行） ──
        if _HAS_AGENT_REACH:
            try:
                from ..tools.agent_reach import patrol_search as ar_search
                ar_result = ar_search(name, keywords)
                if ar_result.get("ok"):
                    ar_content = ar_result.get("aggregated_text", "")
                    ar_bytes = ar_result.get("total_bytes", 0)
                    ar_sources = ar_result.get("source_count", 0)
                    logger.info(f"[Patrol] AgentReach {name}: {ar_sources}源 {ar_bytes//1024}KB")
                    # AR 内容直接加入 results
                    if ar_bytes > 0:
                        results.append({
                            "source": f"AR_{ar_sources}源",
                            "length": ar_bytes,
                            "text": ar_content[:500],
                        })
                else:
                    logger.info(f"[Patrol] AgentReach {name}: 无结果,走curl")
            except Exception as e:
                logger.warning(f"[Patrol] AgentReach {name} 异常: {e}")

        # ── P1: curl 直连搜索（现有方式） ──
        for src_name, src_url, src_type in sources:
            url = src_url.replace("{kw}", kw)
            fetched = self._curl_fetch(url)
            if fetched["ok"]:
                results.append({"source": src_name, "length": fetched["length"]})
            else:
                results.append({"source": src_name, "error": fetched.get("error", "?")})

        ok_count = sum(1 for r in results if "length" in r)
        total_bytes = sum(r.get("length", 0) for r in results)
        summary = f"{ok_count}/{len(sources)}源·{total_bytes // 1024}KB"
        logger.info(f"[Patrol] {name}: {summary}")

        # 更新评分（含 AgentReach 加分）
        self._update_score(cid, {
            "ok": ok_count > 0,
            "success_count": ok_count,
            "total_sources": len(sources),
            "total_bytes": total_bytes,
            "content_found": total_bytes > 500,
            "content_rich": total_bytes > 5000,
        })

        self._set(KEY_PATROL_IDX, str(idx + 1))

        info = f"{ok_count}/{len(sources)}源"
        if total_bytes > 0:
            info += f"·{total_bytes//1024}KB"
        if ar_content:
            info += "·AR✨"

        return {"action": "patrol", "category": name, "index": idx,
                "total": len(CATEGORIES), "progress": f"{idx+1}/{len(CATEGORIES)}",
                "search_result": info, "ar_content": (ar_content or "")[:200]}

    # ── 评分 ──

    def _content_volume_score(self, total_bytes: int) -> int:
        """内容量分级评分(0-20),使不同体量内容产生参差"""
        if total_bytes > 500000: return 20    # >500KB
        if total_bytes > 200000: return 18    # >200KB
        if total_bytes > 100000: return 15    # >100KB
        if total_bytes > 50000:  return 12    # >50KB
        if total_bytes > 20000:  return 10    # >20KB
        if total_bytes > 10000:  return 8     # >10KB
        if total_bytes > 5000:   return 5     # >5KB
        if total_bytes > 1000:   return 3     # >1KB
        return 0

    def _update_score(self, cid: str, sr: Dict):
        try:
            scores = json.loads(self._get(KEY_PATROL_SCORES) or "{}")
        except Exception:
            scores = {}
        now = datetime.now().strftime("%m-%d %H:%M")
        entry = scores.get(cid, {"score": 0, "count": 0, "last": ""})

        entry["count"] = entry.get("count", 0) + 1

        # 基础分: 每次+5, 上限50
        base = min(50, entry["count"] * 5)

        # 内容质量: 0-70
        content = 0
        ok = sr.get("ok", False)
        success = sr.get("success_count", 0)
        total_src = sr.get("total_sources", 0)
        total_bytes = sr.get("total_bytes", 0)

        if ok:
            content += 15                          # 搜索成功
            if total_src > 0:
                content += int((success / total_src) * 15)  # 源覆盖率(0-15)
        content += self._content_volume_score(total_bytes)  # 内容体积(0-20)
        if ok and success > 0:
            content += 10                          # 有结果额外奖励
        if total_bytes > 1000:
            content += 10                          # 有实质内容

        content = min(70, content)

        # 连续分: ≥10次+25
        continuity = 25 if entry["count"] >= 10 else 0

        # 猴子反馈分: 后续可通过调用猴子上浮
        monkey = 5 if ok else 2

        total = min(150, base + content + continuity + monkey)
        entry["score"] = total
        entry["last"] = now
        scores[cid] = entry
        self._set(KEY_PATROL_SCORES, json.dumps(scores, ensure_ascii=False))
        logger.info(f"[Patrol] {cid} score={total}/150 (cnt={entry['count']})")

    def _apply_ar_bonus(self, cid: str, ar_result: Dict):
        """AgentReach 搜索成功奖励分 (5-10分, 不重复累计)"""
        try:
            scores = json.loads(self._get(KEY_PATROL_SCORES) or "{}")
        except Exception:
            return
        entry = scores.get(cid)
        if not entry:
            return
        # 只在 Ar 有新内容时加分（不重复累加）
        bonus_key = f"ar_bonus_{cid}"
        if self._get(bonus_key) == "1":
            return  # 已加过不分
        bonus = 10 if ar_result.get("content_rich") else 5
        entry["score"] = min(150, entry.get("score", 0) + bonus)
        scores[cid] = entry
        self._set(KEY_PATROL_SCORES, json.dumps(scores, ensure_ascii=False))
        self._set(bonus_key, "1")
        logger.info(f"[Patrol] {cid} AgentReach加分+{bonus} → {entry['score']}")

    # ── 分权 T1-T5 ──

    def _do_scoring(self) -> Dict:
        try:
            scores = json.loads(self._get(KEY_PATROL_SCORES) or "{}")
        except Exception:
            scores = {}
        sorted_cats = sorted(scores.items(), key=lambda x: x[1].get("score", 0), reverse=True)
        n = len(sorted_cats)
        tiers = {}

        for i, (cid, entry) in enumerate(sorted_cats):
            pct = (i + 1) / n if n > 0 else 1
            if pct <= 0.15:
                t = "T1"
            elif pct <= 0.35:
                t = "T2"
            elif pct <= 0.55:
                t = "T3"
            elif pct <= 0.75:
                t = "T4"
            else:
                t = "T5"
            for cid_orig, _, _, _, dt, _ in CATEGORIES:
                if cid_orig == cid and dt == "T1" and t not in ("T1", "T2"):
                    t = "T2"
                    break
            tiers[cid] = t

        self._set(KEY_PATROL_TIERS, json.dumps(tiers, ensure_ascii=False))
        self._set(KEY_PATROL, "idle")

        summary = []
        for cid, t in sorted(tiers.items(), key=lambda x: x[1]):
            e = scores.get(cid, {})
            summary.append({"cid": cid, "tier": t, "score": e.get("score", 0), "count": e.get("count", 0)})
        self._set(KEY_PATROL_SUMMARY, json.dumps(summary[:10], ensure_ascii=False))

        logger.info(f"[Patrol] 分权完成: {tiers}")
        return {"action": "scoring_complete", "tiers": tiers, "summary": summary}
