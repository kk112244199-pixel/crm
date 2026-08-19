"""
健康度规则引擎 H001–H008
每条规则：check(opp, context) → RuleResult | None
None 表示规则未触发
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


@dataclass
class RuleResult:
    rule_id: str           # e.g. "H001"
    title: str
    description: str
    severity: str          # HIGH / MEDIUM / LOW
    deduction: int         # 0-100，正数（最终取负）
    evidence: str = ""


# ── Context object ─────────────────────────────────────────────────────────────

@dataclass
class HealthContext:
    """Inputs for health rule evaluation — populated from DB queries."""
    opp_id: uuid.UUID
    opp_name: str
    stage: str
    amount: float | None
    expected_close_date: date | None
    competitor: str | None
    budget_status: str | None
    meddic_gaps: dict | None

    # Derived from activities
    last_activity_date: date | None
    last_high_level_contact_date: date | None  # CEO/CFO/CTO
    has_economic_buyer_confirmed: bool
    total_activities: int

    # Today for deterministic tests
    today: date = field(default_factory=date.today)


# ── Rules ─────────────────────────────────────────────────────────────────────

def _h001_stagnation(ctx: HealthContext) -> RuleResult | None:
    """H001: 商机停滞超 30 天（无任何 Activity）"""
    if ctx.last_activity_date is None:
        days = 999
    else:
        days = (ctx.today - ctx.last_activity_date).days

    if days >= 30:
        severity = "HIGH" if days >= 60 else "MEDIUM"
        deduction = 25 if days >= 60 else 15
        return RuleResult(
            rule_id="H001",
            title="商机停滞",
            description=f"距上次活动已 {days} 天，商机缺乏推进",
            severity=severity,
            deduction=deduction,
            evidence=f"last_activity_date={ctx.last_activity_date}",
        )
    return None


def _h002_no_economic_buyer(ctx: HealthContext) -> RuleResult | None:
    """H002: 大单（≥100万）无经济买家确认"""
    if not ctx.amount or ctx.amount < 1_000_000:
        return None
    if ctx.has_economic_buyer_confirmed:
        return None
    return RuleResult(
        rule_id="H002",
        title="大单无经济买家",
        description=f"金额 {ctx.amount/10000:.0f} 万，经济买家未确认",
        severity="HIGH",
        deduction=20,
        evidence="has_economic_buyer_confirmed=False",
    )


def _h003_competitor_no_plan(ctx: HealthContext) -> RuleResult | None:
    """H003: 竞对进入且无应对方案（meddic_gaps.decision_criteria 为空）"""
    if not ctx.competitor:
        return None
    gaps = ctx.meddic_gaps or {}
    criteria_gap = gaps.get("decision_criteria")
    if criteria_gap:  # Gap exists = no plan
        return RuleResult(
            rule_id="H003",
            title="竞对进入未应对",
            description=f"竞对 [{ctx.competitor}] 进入，决策标准 MEDDIC 缺口未填补",
            severity="MEDIUM",
            deduction=15,
            evidence=f"competitor={ctx.competitor}, decision_criteria={criteria_gap}",
        )
    return None


def _h004_budget_cut(ctx: HealthContext) -> RuleResult | None:
    """H004: 预算明确被砍"""
    if ctx.budget_status == "cut":
        return RuleResult(
            rule_id="H004",
            title="预算被砍",
            description="客户预算已明确削减",
            severity="HIGH",
            deduction=30,
            evidence=f"budget_status={ctx.budget_status}",
        )
    return None


def _h005_close_date_overdue(ctx: HealthContext) -> RuleResult | None:
    """H005: 超过预计成交日未结案"""
    if not ctx.expected_close_date:
        return None
    days_overdue = (ctx.today - ctx.expected_close_date).days
    if days_overdue > 0:
        stage_ok = ctx.stage in ("CLOSED_WON", "CLOSED_LOST")
        if not stage_ok:
            deduction = min(30, 10 + days_overdue // 7 * 5)
            return RuleResult(
                rule_id="H005",
                title="逾期未结案",
                description=f"已逾期 {days_overdue} 天，阶段仍为 {ctx.stage}",
                severity="HIGH" if days_overdue > 14 else "MEDIUM",
                deduction=deduction,
                evidence=f"expected_close_date={ctx.expected_close_date}, stage={ctx.stage}",
            )
    return None


def _h006_high_level_dormant(ctx: HealthContext) -> RuleResult | None:
    """H006: 高层联系人（CEO/CFO/CTO）超过 21 天未互动"""
    if ctx.last_high_level_contact_date is None:
        # Never contacted high level on large deal
        if ctx.amount and ctx.amount >= 500_000:
            return RuleResult(
                rule_id="H006",
                title="高层未互动",
                description="大单未记录任何高层互动",
                severity="MEDIUM",
                deduction=10,
                evidence="last_high_level_contact_date=None",
            )
        return None
    days = (ctx.today - ctx.last_high_level_contact_date).days
    if days > 21:
        return RuleResult(
            rule_id="H006",
            title="高层互动停滞",
            description=f"高层联系人 {days} 天未互动",
            severity="MEDIUM" if days <= 45 else "HIGH",
            deduction=10,
            evidence=f"last_high_level_contact_date={ctx.last_high_level_contact_date}",
        )
    return None


def _h007_meddic_critical_gap(ctx: HealthContext) -> RuleResult | None:
    """H007: MEDDIC 经济买家或指标缺失（大单）"""
    if not ctx.amount or ctx.amount < 500_000:
        return None
    gaps = ctx.meddic_gaps or {}
    critical_missing = []
    if gaps.get("economic_buyer"):
        critical_missing.append("经济买家")
    if gaps.get("metrics"):
        critical_missing.append("可量化指标")
    if not critical_missing:
        return None
    return RuleResult(
        rule_id="H007",
        title="MEDDIC 关键缺口",
        description=f"缺失: {', '.join(critical_missing)}",
        severity="MEDIUM",
        deduction=10,
        evidence=f"meddic_gaps={critical_missing}",
    )


def _h008_budget_unknown_late_stage(ctx: HealthContext) -> RuleResult | None:
    """H008: 晚期阶段预算未确认"""
    late_stages = {"PROPOSAL", "NEGOTIATION", "VALUE_PROPOSITION"}
    if ctx.stage not in late_stages:
        return None
    if ctx.budget_status in ("confirmed",):
        return None
    return RuleResult(
        rule_id="H008",
        title="晚期阶段预算不明",
        description=f"阶段 {ctx.stage}，预算状态 {ctx.budget_status or '未知'}",
        severity="MEDIUM",
        deduction=10,
        evidence=f"stage={ctx.stage}, budget_status={ctx.budget_status}",
    )


# ── Engine ────────────────────────────────────────────────────────────────────

_RULES = [
    _h001_stagnation,
    _h002_no_economic_buyer,
    _h003_competitor_no_plan,
    _h004_budget_cut,
    _h005_close_date_overdue,
    _h006_high_level_dormant,
    _h007_meddic_critical_gap,
    _h008_budget_unknown_late_stage,
]

MAX_SCORE = 100


def evaluate_health(ctx: HealthContext) -> tuple[int, str, list[RuleResult]]:
    """
    Run all rules.
    Returns (score 0-100, status GREEN/YELLOW/RED, triggered_rules).
    """
    triggered: list[RuleResult] = []
    for rule_fn in _RULES:
        result = rule_fn(ctx)
        if result:
            triggered.append(result)

    total_deduction = sum(r.deduction for r in triggered)
    score = max(0, MAX_SCORE - total_deduction)

    if score >= 70:
        status = "GREEN"
    elif score >= 40:
        status = "YELLOW"
    else:
        status = "RED"

    return score, status, triggered
