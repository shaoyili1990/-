"""天道系统 - Y值计算链引擎测试 (公式01-10)

测试每个公式函数的正确性，包括边界条件和公式链集成。
"""

import json
import math
import unittest

from harness_core.tiandao.y_engine import (
    # 公式01-02
    clamp_y, normalize_y,
    # 公式03+10
    calculate_delta_y,
    # 公式04-05
    get_emotion_zone, update_emotions,
    # 公式06
    calculate_breakthrough_thresholds, apply_breakthrough_check,
    # 公式07
    apply_compensation,
    # 公式08
    apply_rebound,
    # 公式09
    update_desires, get_motivation, get_triggered_desires,
    # 完整链
    process_event_y_chain,
    # 常量
    Y_MIN, Y_MAX, Y_NEUTRAL,
    DELTA_Y_MIN, DELTA_Y_MAX,
    COMPENSATION_RATIO, REBOUND_RATE,
    REBOUND_RESIDUAL_MIN, REBOUND_RESIDUAL_MAX,
    WEIGHT_MULTIPLIERS,
)


class TestFormula01YBase(unittest.TestCase):
    """公式01: Y值基础设定 — 边界与clamp"""

    def test_clamp_mid_value(self):
        """中间值不变。"""
        self.assertEqual(clamp_y(50.0), 50.0)

    def test_clamp_below_min(self):
        """低于0截断到0。"""
        self.assertEqual(clamp_y(-10.0), 0.0)

    def test_clamp_above_max(self):
        """高于100截断到100。"""
        self.assertEqual(clamp_y(120.0), 100.0)

    def test_clamp_boundary_zero(self):
        """边界0不截断。"""
        self.assertEqual(clamp_y(0.0), 0.0)

    def test_clamp_boundary_hundred(self):
        """边界100不截断。"""
        self.assertEqual(clamp_y(100.0), 100.0)


class TestFormula02Normalize(unittest.TestCase):
    """公式02: Y_effective归一化"""

    def test_normalize_neutral(self):
        """Y=50 → 0.5"""
        self.assertEqual(normalize_y(50.0), 0.5)

    def test_normalize_zero(self):
        """Y=0 → 0.0"""
        self.assertEqual(normalize_y(0.0), 0.0)

    def test_normalize_hundred(self):
        """Y=100 → 1.0"""
        self.assertEqual(normalize_y(100.0), 1.0)

    def test_normalize_overflow(self):
        """超过100仍返回1.0。"""
        self.assertEqual(normalize_y(150.0), 1.0)


class TestFormula03DeltaY(unittest.TestCase):
    """公式03+10: delta_Y计算"""

    def test_protagonist_multiplier(self):
        """主角(protagonist) ×1.5"""
        result = calculate_delta_y(10.0, 1.0, "protagonist")
        expected = 10.0 * 1.0 * 1.5
        self.assertEqual(result, expected)

    def test_antagonist_multiplier(self):
        """反派(antagonist) ×1.5"""
        result = calculate_delta_y(8.0, 0.8, "antagonist")
        expected = 8.0 * 0.8 * 1.5
        self.assertEqual(result, expected)

    def test_major_multiplier(self):
        """次要人物(major) ×1.0"""
        result = calculate_delta_y(5.0, 0.8, "major")
        expected = 5.0 * 0.8 * 1.0
        self.assertEqual(result, expected)

    def test_minor_multiplier(self):
        """龙套(minor) ×0.3"""
        result = calculate_delta_y(10.0, 0.5, "minor")
        expected = 10.0 * 0.5 * 0.3
        self.assertEqual(result, expected)

    def test_npc_multiplier(self):
        """NPC ×0.1"""
        result = calculate_delta_y(10.0, 1.0, "npc")
        expected = 10.0 * 1.0 * 0.1
        self.assertEqual(result, expected)

    def test_clamp_upper_bound(self):
        """超大冲击被clamp到+20。"""
        result = calculate_delta_y(100.0, 1.0, "protagonist")
        self.assertEqual(result, 20.0)

    def test_clamp_lower_bound(self):
        """超大负冲击被clamp到-20。"""
        result = calculate_delta_y(-100.0, 1.0, "protagonist")
        self.assertEqual(result, -20.0)

    def test_negative_impact(self):
        """消极事件产生负delta_Y。"""
        result = calculate_delta_y(-10.0, 1.0, "major")
        self.assertEqual(result, -10.0)

    def test_zero_impact(self):
        """零冲击不产生变化。"""
        result = calculate_delta_y(0.0, 1.0, "major")
        self.assertEqual(result, 0.0)


class TestFormula04EmotionZone(unittest.TestCase):
    """公式04: 情绪状态映射"""

    def test_despair_zone(self):
        """Y∈[0,20) → 绝望/崩溃 + 哀"""
        label, dominant = get_emotion_zone(10.0)
        self.assertEqual(label, "绝望/崩溃")
        self.assertEqual(dominant, "哀")

    def test_anxiety_zone(self):
        """Y∈[20,40) → 低落/焦虑 + 惧"""
        label, dominant = get_emotion_zone(30.0)
        self.assertEqual(label, "低落/焦虑")
        self.assertEqual(dominant, "惧")

    def test_calm_zone(self):
        """Y∈[40,60) → 平静/中性 + 思"""
        label, dominant = get_emotion_zone(50.0)
        self.assertEqual(label, "平静/中性")
        self.assertEqual(dominant, "思")

    def test_positive_zone(self):
        """Y∈[60,80) → 积极/愉悦 + 喜"""
        label, dominant = get_emotion_zone(70.0)
        self.assertEqual(label, "积极/愉悦")
        self.assertEqual(dominant, "喜")

    def test_euphoria_zone(self):
        """Y∈[80,100] → 狂喜/亢奋 + 喜"""
        label, dominant = get_emotion_zone(90.0)
        self.assertEqual(label, "狂喜/亢奋")
        self.assertEqual(dominant, "喜")

    def test_boundary_20(self):
        """Y=20 → 低落/焦虑（包含下限）"""
        label, _ = get_emotion_zone(20.0)
        self.assertEqual(label, "低落/焦虑")

    def test_boundary_40(self):
        """Y=40 → 平静/中性"""
        label, _ = get_emotion_zone(40.0)
        self.assertEqual(label, "平静/中性")

    def test_boundary_60(self):
        """Y=60 → 积极/愉悦"""
        label, _ = get_emotion_zone(60.0)
        self.assertEqual(label, "积极/愉悦")

    def test_boundary_80(self):
        """Y=80 → 狂喜/亢奋"""
        label, _ = get_emotion_zone(80.0)
        self.assertEqual(label, "狂喜/亢奋")


class TestFormula05Emotions(unittest.TestCase):
    """公式05: 情绪强度计算"""

    def test_neutral_emotions(self):
        """Y=50 → 所有情绪低强度，主情绪为思。"""
        emotions = update_emotions(50.0)
        self.assertGreaterEqual(emotions["思"], emotions["喜"])
        self.assertGreaterEqual(emotions["欲"], 0.5)

    def test_high_joy(self):
        """Y=100 → 喜最高。"""
        emotions = update_emotions(100.0)
        self.assertGreater(emotions["喜"], emotions["哀"])
        self.assertGreater(emotions["喜"], emotions["惧"])

    def test_deep_despair(self):
        """Y=0 → 哀最高。"""
        emotions = update_emotions(0.0)
        # Y=0时主情绪是哀(绝望/崩溃)
        self.assertGreater(emotions["哀"], emotions["喜"])

    def test_resilience_amplifies(self):
        """弹性系数2.0使情绪强度翻倍。"""
        emotions_default = update_emotions(80.0, resilience=1.0)
        emotions_high = update_emotions(80.0, resilience=2.0)
        self.assertGreater(emotions_high["喜"], emotions_default["喜"])

    def test_resilience_dampens(self):
        """弹性系数0.5使情绪强度减半。"""
        emotions_default = update_emotions(80.0, resilience=1.0)
        emotions_low = update_emotions(80.0, resilience=0.5)
        self.assertGreater(emotions_default["喜"], emotions_low["喜"])

    def test_desire_never_zero(self):
        """欲维度永远不低于0.5。"""
        for y in [0, 25, 50, 75, 100]:
            emotions = update_emotions(float(y))
            self.assertGreaterEqual(emotions["欲"], 0.5,
                                    f"Y={y}时欲={emotions['欲']}应≥0.5")


class TestFormula06Breakthrough(unittest.TestCase):
    """公式06: 击穿阈值检测"""

    def test_neutral_yield_symmetric(self):
        """Y_base=50 → 上阈50, 下阈25。"""
        t = calculate_breakthrough_thresholds(50.0)
        self.assertEqual(t["upper"], 50.0)
        self.assertEqual(t["lower"], 25.0)

    def test_optimistic_upper_narrow_lower_wide(self):
        """Y_base=70（乐观）→ 上阈40, 下阈15。"""
        t = calculate_breakthrough_thresholds(70.0)
        self.assertEqual(t["upper"], 40.0)
        self.assertEqual(t["lower"], 15.0)

    def test_pessimistic_upper_wide_lower_narrow(self):
        """Y_base=30（悲观）→ 上阈60, 下阈35。"""
        t = calculate_breakthrough_thresholds(30.0)
        self.assertEqual(t["upper"], 60.0)
        self.assertEqual(t["lower"], 35.0)

    def test_no_breakthrough_at_neutral(self):
        """Y=50 ≤ 上阈50, Y_base=50 → 未击穿。"""
        self.assertFalse(apply_breakthrough_check(50.0, 50.0))

    def test_breakthrough_above_upper(self):
        """Y=55 > 上阈50, Y_base=50 → 击穿。"""
        self.assertTrue(apply_breakthrough_check(55.0, 50.0))

    def test_breakthrough_below_lower(self):
        """Y=20 < 下阈25, Y_base=50 → 击穿。"""
        self.assertTrue(apply_breakthrough_check(20.0, 50.0))

    def test_at_upper_threshold_no_breakthrough(self):
        """Y=50 = 上阈50 → 不大于阈值，未击穿。"""
        self.assertFalse(apply_breakthrough_check(50.0, 50.0))

    def test_just_below_lower_threshold_is_breakthrough(self):
        """Y=24.9 < 下阈25 → 击穿。"""
        self.assertTrue(apply_breakthrough_check(24.9, 50.0))


class TestFormula07Compensation(unittest.TestCase):
    """公式07: 补偿机制"""

    def test_positive_impact_negative_compensation(self):
        """正向冲击 → 负向补偿。"""
        comp = apply_compensation(10.0)
        expected = -10.0 * 0.3
        self.assertEqual(comp, expected)

    def test_negative_impact_positive_compensation(self):
        """负向冲击 → 正向补偿。"""
        comp = apply_compensation(-10.0)
        expected = -(-1.0) * 10.0 * 0.3  # = 3.0
        # Wait: sign(-10.0) = -1, -sign = -(-1) = 1
        # compensation = 1 * 10 * 0.3 = 3.0
        self.assertEqual(comp, expected)

    def test_compensation_ratio(self):
        """补偿力度为原始冲击的30%。"""
        comp = apply_compensation(20.0)
        self.assertAlmostEqual(comp, -6.0)

    def test_zero_impact_zero_compensation(self):
        """零冲击 → 零补偿。"""
        comp = apply_compensation(0.0)
        self.assertEqual(comp, 0.0)

    def test_max_impact_compensation(self):
        """最大冲击20 → 补偿-6。"""
        comp = apply_compensation(20.0)
        self.assertEqual(comp, -6.0)


class TestFormula08Rebound(unittest.TestCase):
    """公式08: 回弹效应"""

    def test_rebound_toward_base(self):
        """Y=80, Y_base=50 → 向下回弹。"""
        result = apply_rebound(80.0, 50.0)
        # speed = |80-50| * 0.1 = 3.0
        # new_y = 80 - 3.0 = 77.0
        # 77 > 50, 未跨越，差值27 > residual → 77.0
        self.assertAlmostEqual(result, 77.0)

    def test_rebound_upward(self):
        """Y=30, Y_base=50 → 向上回弹。"""
        result = apply_rebound(30.0, 50.0)
        # speed = |30-50| * 0.1 = 2.0
        # new_y = 30 + 2.0 = 32.0
        self.assertAlmostEqual(result, 32.0)

    def test_rebound_residual_offset(self):
        """Y=50.5, Y_base=50 → 太接近，保持残余偏移。"""
        result = apply_rebound(50.5, 50.0)
        # direction = -1, speed = 0.05, new_y = 50.45
        # |50.45-50| = 0.45 < 0.5 → 推到残余偏移
        diff = abs(result - 50.0)
        self.assertGreaterEqual(diff, REBOUND_RESIDUAL_MIN)
        self.assertLessEqual(diff, REBOUND_RESIDUAL_MAX)

    def test_rebound_at_base(self):
        """Y=Y_base → 加残余偏移。"""
        result = apply_rebound(50.0, 50.0)
        diff = abs(result - 50.0)
        self.assertGreaterEqual(diff, REBOUND_RESIDUAL_MIN)
        self.assertLessEqual(diff, REBOUND_RESIDUAL_MAX)

    def test_rebound_never_exceeds_range(self):
        """回弹后Y值始终在[0, 100]。"""
        for y in [0, 10, 50, 90, 100]:
            for base in [30, 50, 70]:
                result = apply_rebound(float(y), float(base))
                self.assertGreaterEqual(result, 0.0)
                self.assertLessEqual(result, 100.0)


class TestFormula09Desires(unittest.TestCase):
    """公式09: 欲望/动机演化"""

    def test_init_desires(self):
        """初始欲望有4项，结构完整。"""
        desires = update_desires("", None)
        self.assertEqual(len(desires), 4)
        for d in desires:
            self.assertIn("name", d)
            self.assertIn("weight", d)
            self.assertGreaterEqual(d["weight"], 0.0)
            self.assertLessEqual(d["weight"], 1.0)

    def test_relevant_desire_boost(self):
        """相关欲望权重+0.1。"""
        desires = [
            {"name": "权力", "weight": 0.3},
            {"name": "金钱", "weight": 0.3},
        ]
        result = update_desires("权力斗争事件", desires)
        for d in result:
            if d["name"] == "权力":
                self.assertAlmostEqual(d["weight"], 0.4)
            else:
                self.assertAlmostEqual(d["weight"], 0.25)

    def test_desire_stays_in_range(self):
        """欲望权重保持在[0,1]。"""
        desires = [{"name": "复仇", "weight": 1.0}]
        for _ in range(20):
            desires = update_desires("无关事件", desires)
        for d in desires:
            self.assertGreaterEqual(d["weight"], 0.0)
            self.assertLessEqual(d["weight"], 1.0)

    def test_get_motivation(self):
        """get_motivation返回权重最高的欲望。"""
        desires = [
            {"name": "金钱", "weight": 0.9},
            {"name": "复仇", "weight": 0.2},
        ]
        self.assertEqual(get_motivation(desires), "金钱")

    def test_get_motivation_empty(self):
        """空欲望列表返回"未知"。 """
        self.assertEqual(get_motivation([]), "未知")

    def test_triggered_desires(self):
        """权重>0.8的欲望被标记触发。"""
        desires = [
            {"name": "权力", "weight": 0.9},
            {"name": "金钱", "weight": 0.7},
            {"name": "复仇", "weight": 0.85},
        ]
        triggered = get_triggered_desires(desires)
        self.assertIn("权力", triggered)
        self.assertIn("复仇", triggered)
        self.assertNotIn("金钱", triggered)


# ═══════════════════════════════════════════════════════════════════════
# 完整公式链集成测试
# ═══════════════════════════════════════════════════════════════════════

class TestFullChainProcess(unittest.TestCase):
    """完整Y值计算链集成测试"""

    def test_basic_event_flow_no_breakthrough(self):
        """基本事件流：小冲击不触发击穿。"""
        result = process_event_y_chain(
            y_current_before=45.0,
            y_base=50.0,
            weight_class="major",
            event_impact=3.0,
            influence_score=0.5,
            event_type="日常散步",
            current_desires=None,
        )
        # delta_y = 3.0 * 0.5 * 1.0 = 1.5
        self.assertEqual(result["delta_y"], 1.5)
        # y_after_event = 45.0 + 1.5 = 46.5
        self.assertEqual(result["y_after_event"], 46.5)
        # 46.5 ≤ 50(上阈)，未击穿
        self.assertFalse(result["is_breakthrough"])
        # 主情绪应是平静(40-60区间)，思为主
        self.assertGreaterEqual(result["emotions"]["思"], result["emotions"]["喜"])
        # 无补偿
        self.assertEqual(result["compensation_pending_next"], None)

    def test_breakthrough_trigger(self):
        """强烈冲击触发击穿。"""
        result = process_event_y_chain(
            y_current_before=80.0,  # 已经很高
            y_base=50.0,
            weight_class="protagonist",
            event_impact=15.0,
            influence_score=1.0,
            event_type="权力巅峰",
        )
        # delta_y = 15.0 * 1.0 * 1.5 = 22.5 → clamped to 20.0
        self.assertEqual(result["delta_y"], 20.0)
        # y_after_event = 80 + 20 = 100
        self.assertEqual(result["y_after_event"], 100.0)
        # 100 > 75(上阈)，击穿
        self.assertTrue(result["is_breakthrough"])
        # 应有pending补偿
        self.assertIsNotNone(result["compensation_pending_next"])
        # 补偿 = -1 * 20 * 0.3 = -6.0
        self.assertEqual(result["compensation_pending_next"], -6.0)

    def test_compensation_and_rebound_chain(self):
        """两周期链：周期1击穿 → 周期2补偿+回弹。"""
        # 周期1：击穿
        phase1 = process_event_y_chain(
            y_current_before=70.0,
            y_base=50.0,
            weight_class="protagonist",
            event_impact=15.0,
            influence_score=1.0,
            event_type="权力巅峰",
        )
        self.assertTrue(phase1["is_breakthrough"])
        
        # 周期2：应用补偿+回弹，再处理新事件
        pending = phase1["compensation_pending_next"]
        phase2 = process_event_y_chain(
            y_current_before=phase1["y_after_event"],
            y_base=50.0,
            weight_class="protagonist",
            event_impact=3.0,  # 小事件
            influence_score=0.5,
            event_type="日常",
            pending_compensation=pending,
            was_breakthrough=True,
        )
        # Phase1中应用了补偿
        self.assertNotEqual(phase2["compensation_applied"], 0.0)
        # 事件后的Y值应低于周期的起始值（补偿+回弹向下拉回）
        self.assertLess(phase2["y_after_event"], phase1["y_after_event"])

    def test_negative_event(self):
        """负面事件：人物Y值下降。"""
        result = process_event_y_chain(
            y_current_before=50.0,
            y_base=50.0,
            weight_class="protagonist",
            event_impact=-10.0,
            influence_score=1.0,
            event_type="背叛",
        )
        # delta_y = -10 * 1.0 * 1.5 = -15.0
        self.assertEqual(result["delta_y"], -15.0)
        self.assertEqual(result["y_after_event"], 35.0)
        # 35在[20,40)区间 → 低落/焦虑，主情绪为惧
        self.assertGreater(result["emotions"]["惧"], result["emotions"]["喜"])

    def test_negative_breakthrough_and_positive_compensation(self):
        """负面击穿 → 正向补偿（下一周期）。"""
        # 周期1：负面击穿
        phase1 = process_event_y_chain(
            y_current_before=30.0,
            y_base=50.0,
            weight_class="protagonist",
            event_impact=-15.0,
            influence_score=1.0,
            event_type="背叛",
        )
        # delta_y = -15 * 1.5 = -22.5 → clamped -20
        # y_after = 30 - 20 = 10
        # 10 < 25(下阈) → 击穿
        self.assertTrue(phase1["is_breakthrough"])
        # 补偿方向为正（因为冲击为负）
        self.assertGreater(phase1["compensation_pending_next"], 0)

    def test_minor_character_small_impact(self):
        """龙套人物受冲击微乎其微。"""
        result = process_event_y_chain(
            y_current_before=50.0,
            y_base=50.0,
            weight_class="minor",
            event_impact=10.0,
            influence_score=1.0,
            event_type="大战",
        )
        # delta_y = 10 * 1.0 * 0.3 = 3.0
        self.assertEqual(result["delta_y"], 3.0)
        self.assertEqual(result["y_after_event"], 53.0)

    def test_desire_evolution_across_events(self):
        """多次事件推动欲望演化。"""
        desires = None
        for event_type in ["权力斗争", "权力斗争", "金钱交易"]:
            result = process_event_y_chain(
                y_current_before=50.0,
                y_base=50.0,
                weight_class="major",
                event_impact=3.0,
                influence_score=0.5,
                event_type=event_type,
                current_desires=desires,
            )
            desires = result["desires"]
        
        # 经过多次权力事件，权力的权重应该高于其他
        power = [d for d in desires if d["name"] == "权力"][0]
        money = [d for d in desires if d["name"] == "金钱"][0]
        self.assertGreaterEqual(power["weight"], money["weight"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
