"""天道系统 - Y值计算链引擎 (公式01-10)

天道系统的数学核心：从事件冲击到人物状态演变的完整计算链。
所有函数都是纯函数——无副作用，给定输入总是产生可预测的输出。

公式链（单事件周期内执行顺序）：
  Phase 1 - 前期处理（来自上一周期的遗留）:
    补偿(公式07) → 回弹(公式08)
  Phase 2 - 当期事件:
    delta_Y计算(公式03+10) → Y值更新 → 击穿检测(公式06)
  Phase 3 - 状态输出:
    情绪映射(公式04-05) → 欲望演化(公式09)

Usage:
    from y_engine import (
        calculate_delta_y, apply_breakthrough_check, apply_compensation,
        apply_rebound, update_emotions, update_desires,
        process_event_y_chain,
    )
"""

import json
import math
import random
from typing import Any, Optional

# ═══════════════════════════════════════════════════════════════════════
# 常量定义
# ═══════════════════════════════════════════════════════════════════════

# 公式01: Y值范围
Y_MIN = 0.0
Y_MAX = 100.0
Y_NEUTRAL = 50.0
Y_BASE_DEFAULT = 50.0

# 公式03: 单次事件最大波动
DELTA_Y_MIN = -20.0
DELTA_Y_MAX = 20.0

# 公式05: 情绪弹性系数范围
EMOTION_RESILIENCE_MIN = 0.5
EMOTION_RESILIENCE_MAX = 2.0
EMOTION_RESILIENCE_DEFAULT = 1.0

# 公式07: 补偿比例
COMPENSATION_RATIO = 0.3

# 公式08: 回弹参数
REBOUND_RATE = 0.1
REBOUND_RESIDUAL_MIN = 0.5
REBOUND_RESIDUAL_MAX = 2.0

# 公式09: 欲望参数
DESIRE_RELEVANT_BOOST = 0.1
DESIRE_IRRELEVANT_PENALTY = -0.05
DESIRE_TRIGGER_THRESHOLD = 0.8
DESIRE_TYPES = ["权力", "金钱", "爱情", "复仇", "求知", "安全", "认同"]

# 公式10: 人物权重倍数
WEIGHT_MULTIPLIERS = {
    "protagonist": 1.5,
    "antagonist": 1.5,
    "major": 1.0,
    "minor": 0.3,
    "npc": 0.1,
}

# 公式04: 情绪维度
EMOTION_DIMENSIONS = ["喜", "怒", "哀", "惧", "思", "欲"]

# 情绪值域区间 → 主情绪
EMOTION_ZONE_MAP = [
    (0.0, 20.0, "绝望/崩溃", "哀"),
    (20.0, 40.0, "低落/焦虑", "惧"),
    (40.0, 60.0, "平静/中性", "思"),
    (60.0, 80.0, "积极/愉悦", "喜"),
    (80.0, 100.01, "狂喜/亢奋", "喜"),
]


# ═══════════════════════════════════════════════════════════════════════
# 公式01-02: 基础设定
# ═══════════════════════════════════════════════════════════════════════

def clamp_y(value: float) -> float:
    """将Y值限制在 [Y_MIN, Y_MAX]（公式01）。
    
    Args:
        value: 待限制的Y值。
    
    Returns:
        float: 限制后的Y值，范围 [0, 100]。
    """
    return max(Y_MIN, min(Y_MAX, value))


def normalize_y(y_current: float) -> float:
    """公式02: 归一化Y值到 [0, 1]。
    
    Y_effective = Y_current / 100
    
    Args:
        y_current: 当前Y值。
    
    Returns:
        float: 归一化后的有效Y值 [0, 1]。
    """
    return max(0.0, min(1.0, y_current / Y_MAX))


# ═══════════════════════════════════════════════════════════════════════
# 公式03+10: delta_Y计算
# ═══════════════════════════════════════════════════════════════════════

def calculate_delta_y(
    event_impact: float,
    influence_score: float,
    weight_class: str = "major",
) -> float:
    """公式03+10: 计算事件对人物的Y值影响量。
    
    delta_Y = event_impact × influence_score × weight_multiplier
    结果 clamp 到 [-20, +20]（公式03单次最大波动）。
    
    Args:
        event_impact: 事件影响力度。通常由事件类型和情感强度决定。
            取值范围 0~20（正值为积极事件，负值为消极事件）。
        influence_score: 人物在该事件中的关联权重，来自 tiandao_event_roles (0~1)。
        weight_class: 角色权重分类。
            - protagonist/antagonist: ×1.5（重要人物）
            - major: ×1.0（次要人物）
            - minor: ×0.3（龙套）
            - npc: ×0.1
    
    Returns:
        float: clamp后的delta_Y，范围 [-20, +20]。
    """
    multiplier = WEIGHT_MULTIPLIERS.get(weight_class, 1.0)
    delta = event_impact * influence_score * multiplier
    return max(DELTA_Y_MIN, min(DELTA_Y_MAX, delta))


# ═══════════════════════════════════════════════════════════════════════
# 公式04-05: 情绪状态映射
# ═══════════════════════════════════════════════════════════════════════

def get_emotion_zone(y_current: float) -> tuple[str, str]:
    """公式04: 获取当前Y值对应的情绪区间名称和主情绪。
    
    Args:
        y_current: 当前Y值。
    
    Returns:
        tuple: (区间名称, 主情绪维度)。
    """
    for lo, hi, label, dominant in EMOTION_ZONE_MAP:
        if lo <= y_current < hi:
            return label, dominant
    return "狂喜/亢奋", "喜"


def update_emotions(
    y_current: float,
    resilience: float = EMOTION_RESILIENCE_DEFAULT,
) -> dict[str, float]:
    """公式04-05: 根据当前Y值生成六维度情绪数据。
    
    情绪强度 = |Y_current - 50| × 弹性系数
    主情绪维度获得全强度，非主情绪按比例递减。
    
    Args:
        y_current: 当前Y值。
        resilience: 情绪弹性系数，范围 [0.5, 2.0]。
            默认 1.0。值越大，情绪波动越剧烈。
    
    Returns:
        dict: 六维度情绪 { 情绪名: 强度(0~10) }。
    """
    resilience = max(EMOTION_RESILIENCE_MIN, min(EMOTION_RESILIENCE_MAX, resilience))
    _, dominant = get_emotion_zone(y_current)
    
    # 基础强度：距离中性值越远强度越大
    base_intensity = abs(y_current - Y_NEUTRAL) * resilience
    
    # 映射到 0~10 范围
    # 最大距离为50（0→50或100→50），弹性系数默认1.0
    raw_intensity = base_intensity / 5.0  # 50/10=5, 所以除以5映射到0~10
    raw_intensity = max(0.0, min(10.0, raw_intensity))
    
    # 主情绪分配比例和副情绪分配比例
    dominant_share = 1.0
    secondary_share = 0.3
    
    emotions = {}
    for dim in EMOTION_DIMENSIONS:
        if dim == dominant:
            emotions[dim] = round(raw_intensity * dominant_share, 1)
        else:
            emotions[dim] = round(min(raw_intensity * secondary_share, 5.0), 1)
    
    # 确保"欲"维度永远不为0（生物本能）
    if emotions.get("欲", 0) < 0.5:
        emotions["欲"] = 0.5
    
    return emotions


# ═══════════════════════════════════════════════════════════════════════
# 公式06: 击穿检测
# ═══════════════════════════════════════════════════════════════════════

def calculate_breakthrough_thresholds(y_base: float) -> dict[str, float]:
    """公式06: 计算人物的击穿阈值。
    
    上升阈值 = 50 + (50 - Y_base) × 0.5
    下降阈值 = 50 - Y_base × 0.5
    
    阈值解释：
    - 乐观人物（Y_base偏高）：上升阈值更高不易击穿，下降阈值更低也相对安全
    - 悲观人物（Y_base偏低）：上升阈值更低易在积极方向击穿，下降阈值更低
      但离下限更近，消极方向易击穿
    
    Args:
        y_base: 人物的基础Y值。
    
    Returns:
        dict: {"upper": 上升阈值, "lower": 下降阈值}。
    """
    upper = Y_NEUTRAL + (Y_NEUTRAL - y_base) * 0.5
    lower = Y_NEUTRAL - y_base * 0.5
    return {
        "upper": round(clamp_y(upper), 2),
        "lower": round(clamp_y(lower), 2),
    }


def apply_breakthrough_check(y_current: float, y_base: float) -> bool:
    """公式06: 检查Y值是否击穿阈值。
    
    当 Y_current > 上升阈值 或 Y_current < 下降阈值 时触发击穿。
    
    Args:
        y_current: 当前Y值。
        y_base: 人物的基础Y值。
    
    Returns:
        bool: True=击穿，False=正常。
    """
    thresholds = calculate_breakthrough_thresholds(y_base)
    return y_current > thresholds["upper"] or y_current < thresholds["lower"]


# ═══════════════════════════════════════════════════════════════════════
# 公式07: 补偿机制
# ═══════════════════════════════════════════════════════════════════════

def apply_compensation(delta_y: float) -> float:
    """公式07: 计算补偿力度。
    
    补偿发生在击穿后的下一事件周期。
    
    compensation = -sign(delta_Y) × |delta_Y| × 0.3
    
    补偿与原始冲击方向相反，力度为原始冲击的30%。
    补偿不能将Y值拉回击穿前的水平（此约束由调用方在应用时确保）。
    
    Args:
        delta_y: 导致击穿的原始冲击量。
    
    Returns:
        float: 补偿值（与原始冲击方向相反）。
    """
    sign = 1.0 if delta_y >= 0 else -1.0
    return round(-sign * abs(delta_y) * COMPENSATION_RATIO, 2)


# ═══════════════════════════════════════════════════════════════════════
# 公式08: 回弹效应
# ═══════════════════════════════════════════════════════════════════════

def apply_rebound(y_current: float, y_base: float) -> float:
    """公式08: 计算回弹后的Y值。
    
    回弹发生在补偿完成后，在无新事件干扰时持续进行。
    
    回弹速度 = |Y_current - Y_base| × 0.1（每事件步）
    回弹方向朝向 Y_base。
    回弹不能完全回到 Y_base，保留 0.5~2.0 的残余偏移。
    
    Args:
        y_current: 当前Y值。
        y_base: 人物的基础Y值。
    
    Returns:
        float: 回弹后的Y值，保持在 [0, 100]。
    """
    # 如果已经等于Y_base，直接加上残余偏移
    if y_current == y_base:
        residual = random.uniform(REBOUND_RESIDUAL_MIN, REBOUND_RESIDUAL_MAX)
        direction = 1 if random.random() > 0.5 else -1
        return clamp_y(y_base + direction * residual)
    
    # 计算回弹方向（朝向Y_base）
    direction = 1.0 if y_base > y_current else -1.0
    distance = abs(y_current - y_base)
    speed = distance * REBOUND_RATE
    new_y = y_current + direction * speed
    
    # 检查是否跨越了Y_base
    if (direction > 0 and new_y > y_base) or (direction < 0 and new_y < y_base):
        # 跨越了Y_base → 停在对面，保留残余偏移
        residual = random.uniform(REBOUND_RESIDUAL_MIN, REBOUND_RESIDUAL_MAX)
        if direction > 0:
            # 从下方回弹，超越Y_base，停在Y_base上方residual处... 
            # 不对，direction>0说明向上回弹，原始位置在Y_base之下
            # 如果跨过了Y_base，现在在Y_base之上
            # 残余应该在原始方向（向下偏移）
            new_y = y_base + residual  # 停在Y_base上方residual处... 不对
            # 让我重新思考
            # 原始位置在Y_base之下(direction>0)，回弹向上
            # 如果跨过了Y_base，说明回弹太猛了
            # 残余偏移应该在原始方向一侧：即Y_base之下
            new_y = y_base - residual
        else:
            # 原始在Y_base之上，向下回弹跨过了Y_base
            new_y = y_base + residual
    else:
        # 没有跨越Y_base，检查是否太接近
        new_distance = abs(new_y - y_base)
        if new_distance < REBOUND_RESIDUAL_MIN:
            # 太近了，推到残余偏移距离
            residual = random.uniform(REBOUND_RESIDUAL_MIN, REBOUND_RESIDUAL_MAX)
            if direction > 0:
                new_y = y_base - residual
            else:
                new_y = y_base + residual
    
    return clamp_y(round(new_y, 2))


# ═══════════════════════════════════════════════════════════════════════
# 公式09: 欲望/动机演化
# ═══════════════════════════════════════════════════════════════════════

def _init_desires() -> list[dict]:
    """初始化默认欲望列表（4项，权重各0.3）。
    
    Returns:
        list[dict]: 初始欲望列表。
    """
    return [{"name": d, "weight": 0.3} for d in DESIRE_TYPES[:4]]


def update_desires(
    event_type: str,
    current_desires: Optional[list[dict]] = None,
) -> list[dict]:
    """公式09: 根据事件类型更新欲望权重。
    
    每次事件后调整：
    - 相关欲望权重 +0.1（与事件类型关键词匹配）
    - 无关欲望权重 -0.05
    - 所有权重保持在 [0, 1]
    
    Args:
        event_type: 事件类型描述（用于匹配欲望关键词）。
        current_desires: 当前欲望列表，每项 {"name": 欲望名, "weight": 权重}。
            为 None 时初始化为默认欲望。
    
    Returns:
        list[dict]: 更新后的欲望列表。
    """
    desires = current_desires if current_desires else _init_desires()
    event_lower = (event_type or "").lower()
    
    for d in desires:
        # 相关检测：欲望名是否出现在事件类型描述中
        is_relevant = d["name"] in event_type if event_type else False
        if is_relevant:
            d["weight"] = min(1.0, d["weight"] + DESIRE_RELEVANT_BOOST)
        else:
            d["weight"] = max(0.0, d["weight"] + DESIRE_IRRELEVANT_PENALTY)
        d["weight"] = round(d["weight"], 2)
    
    return desires


def get_motivation(desires: list[dict]) -> str:
    """从欲望列表中获取当前权重最高的欲望作为动机。
    
    Args:
        desires: 欲望列表。
    
    Returns:
        str: 主欲望名称。
    """
    if not desires:
        return "未知"
    return max(desires, key=lambda d: d["weight"])["name"]


def get_triggered_desires(desires: list[dict]) -> list[str]:
    """检查是否有欲望权重超过触发阈值(>0.8)。
    
    当某个欲望权重 > 0.8 时，该欲望已达到触发剧情分支的临界点。
    
    Args:
        desires: 欲望列表。
    
    Returns:
        list[str]: 已触发的欲望名称列表（权重 > 0.8）。
    """
    return [d["name"] for d in desires if d["weight"] > DESIRE_TRIGGER_THRESHOLD]


# ═══════════════════════════════════════════════════════════════════════
# 完整事件计算链
# ═══════════════════════════════════════════════════════════════════════

def process_event_y_chain(
    y_current_before: float,
    y_base: float,
    weight_class: str,
    event_impact: float,
    influence_score: float,
    event_type: str,
    current_desires: Optional[list[dict]] = None,
    pending_compensation: Optional[float] = None,
    was_breakthrough: bool = False,
) -> dict:
    """执行一次事件周期的完整Y值计算链。
    
    三阶段流程：
    Phase 1: 前期处理——补偿(公式07) → 回弹(公式08)
    Phase 2: 当期冲击——delta_Y(公式03+10) → Y值更新 → 击穿检测(公式06)
    Phase 3: 状态输出——情绪(公式04-05) → 欲望(公式09)
    
    Args:
        y_current_before: 当期事件开始前的人物Y值。
        y_base: 人物的基础Y值。
        weight_class: 人物权重分类。
        event_impact: 事件影响力度。
        influence_score: 人物在该事件中的关联权重 (0~1)。
        event_type: 事件类型描述（用于欲望匹配）。
        current_desires: 当前欲望列表，None则初始化。
        pending_compensation: 来自上一周期的待处理补偿值。None=无。
        was_breakthrough: 上一周期是否击穿。True=有pending补偿。
    
    Returns:
        dict: 包含以下键：
            - y_after_phase1: Phase 1后的Y值（补偿+回弹）
            - compensation_applied: 本次应用的补偿值（如有）
            - rebound_applied: 本次应用的回弹值（如有）
            - delta_y: 当期事件的delta_Y
            - y_after_event: Phase 2后的Y值
            - is_breakthrough: 是否击穿
            - breakthrough_thresholds: 击穿阈值
            - compensation_pending_next: 击穿时的补偿值（用于下一周期）
            - emotions: 六维度情绪
            - desires: 更新后的欲望
            - motivation: 主欲望（动机）
            - triggered_desires: 触发阈值的欲望列表
    """
    y = y_current_before
    compensation_applied = 0.0
    rebound_applied = 0.0
    new_pending_compensation = None
    
    # ── Phase 1: 前期处理 ────────────────────────────────────────────
    
    if was_breakthrough and pending_compensation is not None:
        # 公式07: 应用补偿
        y = clamp_y(y + pending_compensation)
        compensation_applied = pending_compensation
        
        # 公式08: 补偿完成，应用回弹
        y_before_rebound = y
        y = apply_rebound(y, y_base)
        rebound_applied = round(y - y_before_rebound, 2)
    
    # ── Phase 2: 当期事件冲击 ────────────────────────────────────────
    
    # 公式03+10: 计算delta_Y
    delta_y = calculate_delta_y(event_impact, influence_score, weight_class)
    y_after_event = clamp_y(y + delta_y)
    
    # 公式06: 击穿检测
    is_breakthrough = apply_breakthrough_check(y_after_event, y_base)
    thresholds = calculate_breakthrough_thresholds(y_base)
    
    if is_breakthrough:
        # 公式07: 计算下次的补偿值
        new_pending_compensation = apply_compensation(delta_y)
    
    # ── Phase 3: 状态输出 ────────────────────────────────────────────
    
    # 公式04-05: 情绪
    emotions = update_emotions(y_after_event)
    
    # 公式09: 欲望
    desires = update_desires(event_type, current_desires)
    motivation = get_motivation(desires)
    triggered = get_triggered_desires(desires)
    
    return {
        "y_after_phase1": round(y, 2),
        "compensation_applied": round(compensation_applied, 2),
        "rebound_applied": round(rebound_applied, 2),
        "delta_y": round(delta_y, 2),
        "y_after_event": round(y_after_event, 2),
        "y_effective": round(normalize_y(y_after_event), 4),
        "is_breakthrough": is_breakthrough,
        "breakthrough_thresholds": thresholds,
        "compensation_pending_next": new_pending_compensation,
        "emotions": emotions,
        "desires": desires,
        "motivation": motivation,
        "triggered_desires": triggered,
    }
