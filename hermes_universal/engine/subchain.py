"""
子链调度器 - 136条推理链调度
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from ..engine import EngineDB


# 4脑分类
CHAIN_CATEGORIES = {
    "逻辑链": "结构性关系分析",
    "因果链": "因果关系推理",
    "思维链": "思维步骤序列",
    "推导法": "形式化推理方法",
}


class SubchainScheduler:
    """子链调度器 - 骏马核心"""

    def __init__(self, subchains_dir: Optional[str] = None, db: Optional[EngineDB] = None):
        if subchains_dir:
            self.subchains_dir = subchains_dir
        else:
            base = Path(__file__).parent.parent.parent
            self.subchains_dir = str(base / "subchains")
        self.db = db
        self._chains_cache = None

    def load_all(self) -> List[Dict]:
        """加载所有子链"""
        if self._chains_cache:
            return self._chains_cache

        chains = []
        if not os.path.isdir(self.subchains_dir):
            self._chains_cache = chains
            return chains

        for fname in sorted(os.listdir(self.subchains_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(self.subchains_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                except:
                    continue
                # 从内容中提取名称和类型
                name = self._extract_name(content, fname)
                chain_type = self._classify_chain(fname, content)
                chains.append({
                    "id": fname.replace(".md", ""),
                    "name": name,
                    "file": fname,
                    "type": chain_type,
                    "content": content,
                    "path": fpath,
                    "length": len(content),
                })

        self._chains_cache = chains
        return chains

    def _extract_name(self, content: str, fname: str) -> str:
        """从md内容提取子链名称"""
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                name = line[2:].strip()
                # 去掉"深度定制化提示词模板"后缀
                name = name.replace("深度定制化提示词模板", "").replace("定制化提示词模板", "").strip()
                return name
        return fname.replace(".md", "").replace("_", " ")

    def _classify_chain(self, fname: str, content: str) -> str:
        """分类子链到4脑"""
        for ctype, keywords in CHAIN_CATEGORIES.items():
            if ctype in content[:500]:
                return ctype
        # 基于文件名判断
        fname_lower = fname.lower()
        if "逻辑" in fname_lower:
            return "逻辑链"
        if "因果" in fname_lower:
            return "因果链"
        if "思维" in fname_lower:
            return "思维链"
        if "推导" in fname_lower or "演绎" in fname_lower or "归谬" in fname_lower:
            return "推导法"
        if "比较" in fname_lower or "分类" in fname_lower:
            return "逻辑链"
        if "矛盾" in fname_lower or "反证" in fname_lower:
            return "推导法"
        return "思维链"

    def get_by_type(self, chain_type: str) -> List[Dict]:
        """按类型获取子链"""
        chains = self.load_all()
        return [c for c in chains if c["type"] == chain_type]

    def get_by_id(self, chain_id: str) -> Optional[Dict]:
        """按ID获取子链"""
        chains = self.load_all()
        for c in chains:
            if c["id"] == chain_id:
                return c
        return None

    def schedule(self, task: str, top_n: int = 5) -> List[Dict]:
        """根据任务调度合适的子链"""
        chains = self.load_all()
        if not chains:
            return []

        # 从DB加载权重
        weights = {}
        if self.db:
            db_weights = self.db.get_subchain_weights()
            for w in db_weights:
                weights[w["subchain_name"]] = w.get("weight", 0.5)

        # 任务关键词匹配得分
        task_lower = task.lower()
        scored = []
        for c in chains:
            score = 0.0
            name_lower = c["name"].lower()
            # 标题匹配
            for keyword in task_lower.split():
                if keyword in name_lower and len(keyword) > 1:
                    score += 0.3
            # 内容匹配
            content_lower = c["content"].lower()
            for keyword in task_lower.split():
                if keyword in content_lower and len(keyword) > 1:
                    score += 0.1
            # DB权重加成
            weight = weights.get(c["name"], 0.5)
            score += weight * 0.2
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for score, c in scored[:top_n]]

    def build_chain_context(self, chain_ids: List[str]) -> str:
        """构建子链上下文供大模型使用"""
        context_parts = []
        for cid in chain_ids:
            chain = self.get_by_id(cid)
            if chain:
                content = chain["content"]
                # 提取关键部分
                sections = self._extract_sections(content)
                context_parts.append(f"## {chain['name']} ({chain['type']})\n")
                context_parts.append(f"定义: {sections.get('定义', 'N/A')}\n")
                if "分析重点" in sections:
                    context_parts.append(f"分析重点: {sections['分析重点']}\n")
                context_parts.append("\n")
        return "\n".join(context_parts)

    def _extract_sections(self, content: str) -> Dict[str, str]:
        """提取子链的关键章节"""
        sections = {}
        current_section = "其他"
        current_text = []

        for line in content.split("\n"):
            if line.startswith("## "):
                if current_text:
                    sections[current_section] = "\n".join(current_text).strip()
                current_section = line[3:].strip()
                current_text = []
            else:
                current_text.append(line)

        if current_text:
            sections[current_section] = "\n".join(current_text).strip()

        # 提取简版定义
        result = {}
        for section_name in sections:
            text = sections[section_name]
            if "定义" in section_name:
                result["定义"] = text[:300] if len(text) > 300 else text
            elif "分析重点" in section_name or "分析流程" in section_name:
                result["分析重点"] = text[:500] if len(text) > 500 else text

        return result

    def get_statistics(self) -> Dict:
        """获取子链统计信息"""
        chains = self.load_all()
        by_type = {}
        for c in chains:
            by_type.setdefault(c["type"], []).append(c)

        return {
            "total": len(chains),
            "by_type": {k: len(v) for k, v in by_type.items()},
            "categories": list(CHAIN_CATEGORIES.keys()),
        }

    def build_name_map(self) -> Dict[str, Dict]:
        """
        建立子链简称→全名的映射
        fingerprint中的简称如'互斥' → 完整的子链文件数据
        """
        chains = self.load_all()
        mapping = {}
        brain_suffixes = ["逻辑链", "因果链", "思维链", "推导法", "推导链",
                          "优先级思维链", "因果链式思维链", "链式因果链"]

        for c in chains:
            name = c["name"]
            # 去掉后缀提取简称
            short = name
            for suffix in brain_suffixes:
                if suffix in short:
                    short = short.replace(suffix, "").strip()
                    break
            # 去掉其他常见后缀
            short = short.replace("深度定制化提示词模板", "").replace("定制化提示词模板", "").strip()
            if short:
                mapping[short] = c
            # 也按完整名称索引
            mapping[name] = c

        return mapping
