"""
Agent Reach 集成模块 — 巡逻系统首选检索工具

功能:
  1. ExaSearch — AI语义搜索(if API key available)
  2. Jina Web Reader — 任意URL转Markdown
  3. GitHub — 仓库/issue/trending
  4. YouTube — 视频搜索/字幕
  5. Reddit/Twitter/V2EX — 社交平台
  6. 自动fallback: ExaSearch → DDG(curl) → 内置Web

架构:
  巡逻时 优先调用 Agent Reach 搜索，
  不可用时 fallback 到 curl 直连搜索。
"""
import json
import logging
import time
from typing import Dict, List, Optional, Any

logger = logging.getLogger("agent_reach")


class AgentReachClient:
    """Agent Reach 封装器 — 为巡逻系统提供统一的搜索接口"""

    def __init__(self):
        self._ar = None
        self._channels = []
        self._init_ok = False
        self._doctor_report = ""
        self._init()

    def _init(self):
        """初始化 Agent Reach"""
        try:
            from agent_reach import AgentReach
            self._ar = AgentReach()
            report = self._ar.doctor_report()
            self._doctor_report = report
            self._init_ok = True
            logger.info(f"[AgentReach] 初始化成功\n{report[:200]}")
        except ImportError:
            logger.warning("[AgentReach] 未安装,请运行: pip install agent-reach")
        except Exception as e:
            logger.warning(f"[AgentReach] 初始化失败: {e}")

    @property
    def available(self) -> bool:
        return self._init_ok and self._ar is not None

    def doctor(self) -> str:
        """健康检查报告"""
        if self._ar:
            try:
                return self._ar.doctor_report()
            except Exception as e:
                return f"AgentReach 检查失败: {e}"
        return "AgentReach 未安装"

    def _read_url(self, url: str, timeout: int = 15) -> Optional[str]:
        """用 Jina Reader 读网页 (AgentReach 核心能力)"""
        import urllib.request
        jina_url = f"https://r.jina.ai/http://{url.removeprefix('http://').removeprefix('https://')}"
        try:
            req = urllib.request.Request(
                jina_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; HermesAgent/0.1)"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")[:5000]
        except Exception:
            return None

    def search(self, query: str, max_results: int = 5) -> Dict:
        """
        首要搜索方法 — 多级 fallback
        1. ExaSearch (if configured)
        2. Jina Reader (通用web)
        3. DDG via curl (兜底)
        """
        results = []

        # Level 1: Jina Reader 搜索
        try:
            web_text = self._read_url(f"www.google.com/search?q={query.replace(' ', '+')}")
            if web_text and len(web_text) > 200:
                results.append({
                    "source": "JinaWeb",
                    "ok": True,
                    "length": len(web_text),
                    "preview": web_text[:300],
                })
        except Exception:
            pass

        # Level 2: Exa Search (if key available)
        try:
            from agent_reach.channels.exa_search import ExaSearchChannel
            exa = ExaSearchChannel()
            exa_results = exa.search(query, num_results=max_results)
            if exa_results:
                results.append({
                    "source": "ExaSearch",
                    "ok": True,
                    "length": len(str(exa_results)),
                    "preview": str(exa_results)[:300],
                })
        except Exception:
            pass

        # Level 3: 尽量用多个渠道
        for channel_name in ["web", "v2ex", "github"]:
            try:
                text = self._read_url(f"https://{channel_name}.com/search?q={query.replace(' ', '+')}")
                if text and len(text) > 500:
                    results.append({
                        "source": channel_name,
                        "ok": True,
                        "length": len(text),
                        "preview": text[:200],
                    })
            except Exception:
                pass

        # 汇总
        ok_count = sum(1 for r in results if r.get("ok"))
        total_bytes = sum(r.get("length", 0) for r in results)

        return {
            "ok": ok_count > 0,
            "results": results,
            "success_count": ok_count,
            "total_sources": len(results) if results else 1,
            "total_bytes": total_bytes,
            "content_found": total_bytes > 500,
            "content_rich": total_bytes > 5000,
            "summary": f"AgentReach:{ok_count}源·{total_bytes // 1024}KB",
        }

    def search_multi_category(self, categories: List[tuple]) -> List[Dict]:
        """
        批量搜索多个门类 — 每个门类用不同关键词和渠道
        返回每个门类的搜索结果
        """
        all_results = []
        for cid, name, keywords, desc, tier, sources in categories:
            kw = keywords[0] if keywords else name
            r = self.search(kw)
            all_results.append({
                "cid": cid,
                "name": name,
                "agent_reach_result": r,
                "tier": tier,
            })
        return all_results


# 全局单例
_client = None


def get_client() -> AgentReachClient:
    global _client
    if _client is None:
        _client = AgentReachClient()
    return _client


def patrol_search(category_name: str, keywords: List[str]) -> Dict:
    """
    巡逻系统专用搜索 — 首选 Agent Reach，fallback 到 curl
    被 patrol.py 调用
    """
    client = get_client()
    kw = keywords[0] if keywords else category_name
    result = client.search(kw)

    # 如果 AgentReach 搜不到，返回空结果让 patrol 走 curl fallback
    if not result.get("ok"):
        return {"ok": False, "fallback": True, "summary": f"AgentReach不可用,准备fallback"}

    return result


if __name__ == "__main__":
    # 测试
    client = get_client()
    print(f"AgentReach 可用: {client.available}")
    print(f"\n健康检查:\n{client.doctor()}")
    r = client.search("AI 最新进展 2025")
    print(f"\n搜索结果: {r.get('summary', 'none')}")
