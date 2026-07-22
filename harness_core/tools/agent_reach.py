"""
Agent Reach 集成 v2 — 巡逻系统首选检索工具

确认可用的搜索源:
  1. HN Algolia API    → 科技/AI内容 (188万+结果, 免费)
  2. V2EX API          → 技术社区 (公开API, 无需Token)
  3. GitHub API        → 开源仓库趋势 (公共API)
  4. Jina Reader       → 任意网页转Markdown (免费)

架构:
  patrol_search() → 并行调用4源 → 汇总内容 → 直接喂入巡逻results列表
  patrol.py 中, AR 结果与 curl 结果合并评分
"""
import json
import logging
import re
import urllib.request
import urllib.parse
from typing import Dict, List, Optional

logger = logging.getLogger("agent_reach")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"


def _fetch(url: str, timeout: int = 10) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _html_to_text(html: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', text).strip()


# ── 搜索源 ──

def search_hn_algolia(query: str, max_hits: int = 5) -> List[Dict]:
    """HN Algolia: AI/科技类内容"""
    raw = _fetch(
        f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(query)}"
        f"&hitsPerPage={max_hits}&tags=story",
        timeout=8
    )
    if not raw:
        return []
    data = json.loads(raw)
    return [
        {"title": h.get("title", ""), "url": h.get("url") or "",
         "points": h.get("points", 0), "author": h.get("author", "")}
        for h in data.get("hits", [])
    ]


def search_v2ex(max_topics: int = 5) -> List[Dict]:
    """V2EX 热门话题（技术社区内容）"""
    raw = _fetch("https://www.v2ex.com/api/topics/hot.json", timeout=8)
    if not raw:
        return []
    data = json.loads(raw)
    return [
        {"title": t.get("title", ""), "url": f"https://www.v2ex.com/t/{t.get('id','')}",
         "node": t.get("node", {}).get("title", "") if isinstance(t.get("node"), dict) else ""}
        for t in data[:max_topics]
    ]


def search_github(query: str, max_repos: int = 5) -> List[Dict]:
    """GitHub 仓库搜索"""
    raw = _fetch(
        f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}"
        f"&sort=stars&order=desc&per_page={max_repos}",
        timeout=8
    )
    if not raw:
        return []
    data = json.loads(raw)
    return [
        {"name": r["full_name"], "stars": r.get("stargazers_count", 0),
         "desc": (r.get("description") or "")[:80]}
        for r in data.get("items", [])
    ]


def read_via_jina(url: str, max_chars: int = 2000) -> Optional[str]:
    """Jina Reader: 任意网页转Markdown"""
    jina_url = f"https://r.jina.ai/{url}"
    req = urllib.request.Request(jina_url, headers={"User-Agent": UA,
        "X-With-Generated-Alt": "false", "X-Return-Format": "text"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.read().decode("utf-8", errors="replace")[:max_chars]
    except Exception:
        return None


def search_jina(query: str) -> List[Dict]:
    """Jina Reader 搜索：先 DDG 出链接 → Jina 读关键页"""
    # 跳过需要bot检测的DDG, 直接用Jina读已知信息页
    try:
        hn_text = read_via_jina("https://hn.algolia.com/?query=" + urllib.parse.quote(query), 2000)
        if hn_text and len(hn_text) > 100:
            return [{"source": "Jina+Algolia", "text": hn_text[:1500]}]
    except Exception:
        pass
    # fallback: 读 HN 首页
    try:
        front = read_via_jina("https://news.ycombinator.com/", 2000)
        if front:
            return [{"source": "HN首页", "text": front[:1500]}]
    except Exception:
        pass
    return []


# ── 主搜索 ──

def multi_search(query: str) -> Dict:
    """并行搜索所有源，汇总结果"""
    sources = {}

    # 1. HN Algolia
    hn = search_hn_algolia(query)
    if hn:
        texts = [f"• {h['title']} ({h['points']}pts)" for h in hn]
        sources["hn_algolia"] = {
            "text": "\n".join(texts),
            "count": len(hn),
            "length": sum(len(t) for t in texts),
        }

    # 2. V2EX
    v2 = search_v2ex()
    if v2:
        texts = [f"• {t['title']}" for t in v2]
        sources["v2ex"] = {
            "text": "\n".join(texts),
            "count": len(v2),
            "length": sum(len(t) for t in texts),
        }

    # 3. GitHub
    gh = search_github(query)
    if gh:
        texts = [f"• {g['name']} ⭐{g['stars']} {g['desc']}" for g in gh]
        sources["github"] = {
            "text": "\n".join(texts),
            "count": len(gh),
            "length": sum(len(t) for t in texts),
        }

    # 4. Jina Reader (深度内容)
    jina = search_jina(query)
    if jina:
        for j in jina:
            sources[j["source"]] = {
                "text": j["text"],
                "count": 1,
                "length": len(j["text"]),
            }

    total_bytes = sum(s.get("length", 0) for s in sources.values())

    # 聚合文本
    aggregated = "\n\n---\n\n".join(
        f"【{name}】\n{data['text']}"
        for name, data in sources.items()
    )[:8000]

    return {
        "ok": len(sources) > 0,
        "sources": sources,
        "source_count": len(sources),
        "total_bytes": total_bytes,
        "content_found": total_bytes > 300,
        "content_rich": total_bytes > 3000,
        "aggregated_text": aggregated,
        "summary": f"ARv2:{len(sources)}源·{total_bytes//1024}KB",
    }


# 全局单例
_client = None


def get_client():
    global _client
    if _client is None:
        class _Client:
            available = True
            def search(self, query):
                return multi_search(query)
        _client = _Client()
    return _client


def patrol_search(category_name: str, keywords: List[str]) -> Dict:
    """巡逻系统专用搜索 — 多源并行"""
    kw = keywords[0] if keywords else category_name
    result = multi_search(kw)
    if not result.get("ok"):
        return {"ok": False, "fallback": True, "summary": "AR无结果,准备fallback"}
    return result


if __name__ == "__main__":
    r = multi_search("AI latest news")
    print(f"源数: {r['source_count']}")
    print(f"内容: {r['total_bytes']} bytes")
    print(f"聚合:\n{r.get('aggregated_text','')[:600]}")
