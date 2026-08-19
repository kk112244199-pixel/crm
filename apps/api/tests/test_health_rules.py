"""
H001–H008 规则引擎单元测试（100% 覆盖）
纯内存测试，不需要 DB。
"""
import pytest
from datetime import date, timedelta
from uuid import uuid4

from app.services.health.rules import HealthContext, evaluate_health, _h001_stagnation, _h002_no_economic_buyer, _h003_competitor_no_plan, _h004_budget_cut, _h005_close_date_overdue, _h006_high_level_dormant, _h007_meddic_critical_gap, _h008_budget_unknown_late_stage


def ctx(**kwargs) -> HealthContext:
    """Build a HealthContext with safe defaults."""
    defaults = dict(
        opp_id=uuid4(),
        opp_name="测试商机",
        stage="PROPOSAL",
        amount=1_000_000,
        expected_close_date=date.today() + timedelta(days=30),
        competitor=None,
        budget_status="confirmed",
        meddic_gaps={},
        last_activity_date=date.today() - timedelta(days=5),
        last_high_level_contact_date=date.today() - timedelta(days=5),
        has_economic_buyer_confirmed=True,
        total_activities=5,
        today=date.today(),
    )
    defaults.update(kwargs)
    return HealthContext(**defaults)


# ── H001 ──────────────────────────────────────────────────────────────────────

class TestH001:
    def test_not_triggered_recent(self):
        result = _h001_stagnation(ctx(last_activity_date=date.today() - timedelta(days=10)))
        assert result is None

    def test_triggered_30_days(self):
        result = _h001_stagnation(ctx(last_activity_date=date.today() - timedelta(days=30)))
        assert result is not None
        assert result.rule_id == "H001"
        assert result.severity == "MEDIUM"

    def test_triggered_60_days_high(self):
        result = _h001_stagnation(ctx(last_activity_date=date.today() - timedelta(days=61)))
        assert result is not None
        assert result.severity == "HIGH"
        assert result.deduction == 25

    def test_never_activity(self):
        result = _h001_stagnation(ctx(last_activity_date=None))
        assert result is not None
        assert result.deduction >= 15


# ── H002 ──────────────────────────────────────────────────────────────────────

class TestH002:
    def test_small_deal_no_trigger(self):
        result = _h002_no_economic_buyer(ctx(amount=500_000, has_economic_buyer_confirmed=False))
        assert result is None

    def test_large_deal_no_buyer_triggers(self):
        result = _h002_no_economic_buyer(ctx(amount=2_000_000, has_economic_buyer_confirmed=False))
        assert result is not None
        assert result.rule_id == "H002"
        assert result.deduction == 20

    def test_large_deal_with_buyer_ok(self):
        result = _h002_no_economic_buyer(ctx(amount=2_000_000, has_economic_buyer_confirmed=True))
        assert result is None


# ── H003 ──────────────────────────────────────────────────────────────────────

class TestH003:
    def test_no_competitor_no_trigger(self):
        result = _h003_competitor_no_plan(ctx(competitor=None))
        assert result is None

    def test_competitor_with_gap_triggers(self):
        result = _h003_competitor_no_plan(ctx(
            competitor="西门子",
            meddic_gaps={"decision_criteria": "客户决策标准未明确"},
        ))
        assert result is not None
        assert result.rule_id == "H003"

    def test_competitor_no_gap_ok(self):
        result = _h003_competitor_no_plan(ctx(
            competitor="西门子",
            meddic_gaps={"decision_criteria": None},
        ))
        assert result is None


# ── H004 ──────────────────────────────────────────────────────────────────────

class TestH004:
    def test_budget_cut_triggers(self):
        result = _h004_budget_cut(ctx(budget_status="cut"))
        assert result is not None
        assert result.rule_id == "H004"
        assert result.deduction == 30

    def test_budget_confirmed_ok(self):
        result = _h004_budget_cut(ctx(budget_status="confirmed"))
        assert result is None


# ── H005 ──────────────────────────────────────────────────────────────────────

class TestH005:
    def test_not_overdue(self):
        result = _h005_close_date_overdue(ctx(
            expected_close_date=date.today() + timedelta(days=5)
        ))
        assert result is None

    def test_overdue_1_day(self):
        result = _h005_close_date_overdue(ctx(
            expected_close_date=date.today() - timedelta(days=1),
            stage="PROPOSAL",
        ))
        assert result is not None
        assert result.rule_id == "H005"

    def test_closed_won_ok(self):
        result = _h005_close_date_overdue(ctx(
            expected_close_date=date.today() - timedelta(days=10),
            stage="CLOSED_WON",
        ))
        assert result is None


# ── H006 ──────────────────────────────────────────────────────────────────────

class TestH006:
    def test_recent_hl_contact_ok(self):
        result = _h006_high_level_dormant(ctx(
            last_high_level_contact_date=date.today() - timedelta(days=10)
        ))
        assert result is None

    def test_21_days_triggers(self):
        result = _h006_high_level_dormant(ctx(
            last_high_level_contact_date=date.today() - timedelta(days=22),
            amount=600_000,
        ))
        assert result is not None
        assert result.rule_id == "H006"

    def test_small_deal_no_hl_no_trigger(self):
        result = _h006_high_level_dormant(ctx(
            last_high_level_contact_date=None,
            amount=100_000,
        ))
        assert result is None


# ── H007 ──────────────────────────────────────────────────────────────────────

class TestH007:
    def test_small_deal_no_trigger(self):
        result = _h007_meddic_critical_gap(ctx(amount=200_000))
        assert result is None

    def test_large_deal_missing_eb_triggers(self):
        result = _h007_meddic_critical_gap(ctx(
            amount=1_500_000,
            meddic_gaps={"economic_buyer": "经济买家未确认"},
        ))
        assert result is not None
        assert result.rule_id == "H007"

    def test_large_deal_no_gaps_ok(self):
        result = _h007_meddic_critical_gap(ctx(
            amount=1_500_000,
            meddic_gaps={"economic_buyer": None, "metrics": None},
        ))
        assert result is None


# ── H008 ──────────────────────────────────────────────────────────────────────

class TestH008:
    def test_early_stage_no_trigger(self):
        result = _h008_budget_unknown_late_stage(ctx(stage="PROSPECTING", budget_status=None))
        assert result is None

    def test_late_stage_budget_unknown_triggers(self):
        result = _h008_budget_unknown_late_stage(ctx(stage="PROPOSAL", budget_status=None))
        assert result is not None
        assert result.rule_id == "H008"

    def test_late_stage_confirmed_ok(self):
        result = _h008_budget_unknown_late_stage(ctx(stage="NEGOTIATION", budget_status="confirmed"))
        assert result is None


# ── Engine Integration ────────────────────────────────────────────────────────

class TestEngineIntegration:
    def test_healthy_opp_green(self):
        score, status, rules = evaluate_health(ctx())
        assert status == "GREEN"
        assert score >= 70
        assert rules == []

    def test_red_opp_multiple_rules(self):
        score, status, rules = evaluate_health(ctx(
            last_activity_date=date.today() - timedelta(days=65),
            budget_status="cut",
            has_economic_buyer_confirmed=False,
            amount=2_000_000,
        ))
        assert status == "RED"
        assert score < 40
        assert len(rules) >= 3

    def test_score_capped_at_zero(self):
        score, status, rules = evaluate_health(ctx(
            last_activity_date=date.today() - timedelta(days=100),
            budget_status="cut",
            competitor="西门子",
            meddic_gaps={"decision_criteria": "gap", "economic_buyer": "gap", "metrics": "gap"},
            has_economic_buyer_confirmed=False,
            amount=3_000_000,
            expected_close_date=date.today() - timedelta(days=30),
            stage="PROPOSAL",
            last_high_level_contact_date=None,
        ))
        assert score >= 0
        assert status == "RED"

    def test_seed_data_has_5_red(self):
        """Verify at least 5 seed-like opps would be RED (budget_cut + stagnation combos)."""
        red_count = 0
        test_cases = [
            # H004(30) + H001(25) = -55 → score=45 → YELLOW, add H002 to push RED
            ctx(last_activity_date=date.today() - timedelta(days=65), budget_status="cut",
                has_economic_buyer_confirmed=False, amount=2_000_000),
            # H004(30) + H002(20) + H007(10) = -60 → score=40 → YELLOW; add H005
            ctx(budget_status="cut", has_economic_buyer_confirmed=False, amount=2_000_000,
                expected_close_date=date.today() - timedelta(days=20), stage="PROPOSAL",
                meddic_gaps={"economic_buyer": "gap"}),
            # H001(25) + H004(30) + H006(10) = -65 → RED
            ctx(last_activity_date=date.today() - timedelta(days=65), budget_status="cut",
                last_high_level_contact_date=date.today() - timedelta(days=30), amount=600_000),
            # H004 + H002 + H005 + H008 → lots of deduction
            ctx(budget_status="cut", has_economic_buyer_confirmed=False, amount=2_000_000,
                expected_close_date=date.today() - timedelta(days=10), stage="NEGOTIATION"),
            # H001(25) + H002(20) + H007(10) + H006(10) = -65 → RED
            ctx(last_activity_date=date.today() - timedelta(days=65),
                has_economic_buyer_confirmed=False, amount=2_000_000,
                last_high_level_contact_date=date.today() - timedelta(days=30),
                meddic_gaps={"economic_buyer": "gap"}),
        ]
        for c in test_cases:
            _, status, _ = evaluate_health(c)
            if status == "RED":
                red_count += 1
        assert red_count >= 5
