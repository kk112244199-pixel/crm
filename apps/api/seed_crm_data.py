"""
P2 种子数据脚本 — 工业软件 / 智能制造 ToB 场景
覆盖：12 Account / 40+ Contact / 20 Opp / 80+ Activity（含真实话术纪要）
用法：docker compose exec api python /app/seed_crm_data.py
"""
import asyncio, random, uuid
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.crm import (
    Account, Contact, Opportunity, Activity,
    OppStage, HealthStatus, RoleInDeal, ActivityType,
)

# ── 真实工业软件场景话术纪要（10 份 golden 样本）─────────────────────────────

GOLDEN_MINUTES = [
    # 1. 典型推进会
    """\
【会议纪要】2026-08-01 与亿联智造 产品演示会
参会人：王总（亿联智造 VP 工程）、李明（我方 AE）

王总确认 MES 系统采购预算 380 万，Q3 决策。
王总提到现有 SAP 接口改造成本高，是主要顾虑。
竞争对手：用友 U9 在内部也做了演示。
下一步：王总要求两周内提供 POC 方案，李明承诺 8 月 15 日前发出。
技术负责人张工（VP 工程部下属）支持我方方案，表示愿意在内部推动。
""",
    # 2. 高风险 — 预算被砍
    """\
【拜访纪要】2026-07-28 华峰精密 跟进
参会：陈总（CEO）、赵晓（采购总监）、李明（AE）

陈总透露年度预算缩减 30%，MES 项目暂时搁置到 Q4。
赵晓表示如果价格能降到 250 万以内可以继续。
竞对：西门子低代码方案也在评估中，陈总认为西门子更稳定。
风险：项目可能延期超过 90 天，推进受阻。
下一步：李明需要提供阶段性交付方案，以降低客户一次性投入。
""",
    # 3. 决策链识别
    """\
【电话纪要】2026-08-05 锐捷自动化 采购决策链摸底
参会：刘强（信息化总监）、李明（AE）

刘强明确：最终拍板人是 CEO 许总，但他本人是技术评估负责人。
财务总监王芳对预算有一票否决权，尚未接触。
刘强透露内部有 "自建 vs 外购" 争议，自研团队反对采购。
建议：安排一次 CEO 级别会议，消除 "自建" 顾虑。
下一步：李明安排拜访 CEO 许总，周期 2 周内。
""",
    # 4. MEDDIC 缺口明显
    """\
【方案讲解会】2026-07-30 中科天工
参会：技术团队 5 人

客户痛点：产线数据孤岛，报工效率低，每月人工对账耗时 3 天。
尚未明确经济买家；技术团队对方案感兴趣但无采购权。
预算：不清楚，技术负责人郝工说"由集团统一审批"。
下一步：需要推动集团层面采购人员参与下一次会议。
MEDDIC 缺口：经济买家未确认、预算不明确。
""",
    # 5. 竞争激烈
    """\
【竞标推进会】2026-08-03 博远科技
参会：杨总（CTO）、李明（AE）

博远已收到 4 家供应商报价，我方最贵。
杨总明确：功能覆盖 > 价格，但董事会要求年内 ROI 正向。
我方优势：实施周期最短（3 个月），售后 7×24。
竞对：鼎捷 ERP 模块化方案最低价，但实施周期 9 个月。
下一步：准备 ROI 测算报告，李明承诺本周五发出。
""",
    # 6. 健康度良好
    """\
【POC 总结会】2026-08-10 飞越智能
参会：赵总（CEO）、技术团队

POC 结果：系统稳定，产线效率提升模拟达 18%，超出客户预期。
赵总当场拍板进入合同谈判阶段，要求本月内签约。
采购金额：480 万，年维护费 48 万。
合同责任：采购部孙经理跟进，法务审核预计 1 周。
下一步：李明本周发送合同草稿，安排法务对接。
""",
    # 7. 续费场景
    """\
【年度回顾会】2026-08-12 鑫科制造
参会：IT 总监陈伟、采购主管张梅、李明（AE）

续费情况：MES 模块使用 2 年，客户满意度良好。
新需求：陈伟提出增加 AI 质检模块，预算 150 万。
张梅提出希望打包续费 + 新模块，给予整体折扣。
竞对风险：陈伟提到有其他厂商主动接触。
下一步：制定续费 + 增购方案，7 天内发送。
""",
    # 8. 短会 — 仅跟进
    """\
【电话跟进】2026-08-14 恒安工控
与王总简短通话，确认项目仍在推进，但董事会审批延迟到 9 月。
下一步：9 月初再约正式会。
""",
    # 9. 发现新联系人
    """\
【现场拜访】2026-08-06 联创数科
参会：原联系人刘总监、新联系人 CFO 黄总、李明

黄总首次参会，表示财务对项目有审批权。
黄总关注：3 年 TCO 是否低于自建方案。
刘总监建议：先做一份自建 vs 外购 TCO 对比报告。
下一步：李明本周内完成 TCO 报告发送。
""",
    # 10. 有明确 stage 推进信号
    """\
【谈判会议】2026-08-09 宏正精机
参会：采购总监钱峰、法务李律师、李明（AE）

合同条款基本达成一致，付款方式：首付 40%，验收付 40%，质保期付 20%。
钱峰要求调整违约条款，我方法务确认可接受。
预计下周签约。
下一步：李明确认合同修订版本，本周三前发送最终版。
""",
]

ACCOUNT_DATA = [
    ("亿联智造", "智能制造", "华东", 2000),
    ("华峰精密", "精密制造", "华南", 800),
    ("锐捷自动化", "工业自动化", "华北", 1200),
    ("中科天工", "航天制造", "西部", 5000),
    ("博远科技", "工业软件", "华东", 600),
    ("飞越智能", "机器人制造", "华东", 1500),
    ("鑫科制造", "电子制造", "华南", 3000),
    ("恒安工控", "工控系统", "华中", 400),
    ("联创数科", "数字化转型", "华北", 700),
    ("宏正精机", "精密加工", "华东", 900),
    ("天誉智控", "智慧工厂", "华南", 1100),
    ("兴盛工业", "重工制造", "东北", 4000),
]

CONTACT_TEMPLATES = [
    ("CEO", RoleInDeal.ECONOMIC_BUYER, 5),
    ("CFO", RoleInDeal.ECONOMIC_BUYER, 4),
    ("CTO", RoleInDeal.TECHNICAL_BUYER, 4),
    ("VP 工程", RoleInDeal.TECHNICAL_BUYER, 4),
    ("信息化总监", RoleInDeal.CHAMPION, 3),
    ("采购总监", RoleInDeal.INFLUENCER, 3),
    ("IT 总监", RoleInDeal.CHAMPION, 3),
    ("技术负责人", RoleInDeal.TECHNICAL_BUYER, 2),
    ("财务总监", RoleInDeal.INFLUENCER, 2),
    ("法务", RoleInDeal.INFLUENCER, 1),
]

OPP_TEMPLATES = [
    ("MES 系统采购", OppStage.PROPOSAL, 3800000, 45, HealthStatus.YELLOW),
    ("MES 项目搁置", OppStage.QUALIFICATION, 2500000, 90, HealthStatus.RED),
    ("工业软件采购", OppStage.NEEDS_ANALYSIS, 1800000, 60, HealthStatus.YELLOW),
    ("数字化转型项目", OppStage.NEEDS_ANALYSIS, 5000000, 90, HealthStatus.GREEN),
    ("ERP 替换", OppStage.PROPOSAL, 2200000, 30, HealthStatus.GREEN),
    ("POC → 正式采购", OppStage.NEGOTIATION, 4800000, 15, HealthStatus.GREEN),
    ("MES 续费 + 增购", OppStage.VALUE_PROPOSITION, 1500000, 30, HealthStatus.GREEN),
    ("董事会延迟审批", OppStage.QUALIFICATION, 900000, 120, HealthStatus.RED),
    ("TCO 评估中", OppStage.NEEDS_ANALYSIS, 1200000, 60, HealthStatus.YELLOW),
    ("合同谈判收尾", OppStage.NEGOTIATION, 3200000, 7, HealthStatus.GREEN),
    ("预算压缩商机", OppStage.QUALIFICATION, 800000, 90, HealthStatus.RED),
    ("AI 质检模块", OppStage.VALUE_PROPOSITION, 1500000, 45, HealthStatus.GREEN),
    ("智慧工厂项目", OppStage.PROSPECTING, 6000000, 120, HealthStatus.YELLOW),
    ("产线数字化", OppStage.NEEDS_ANALYSIS, 2800000, 60, HealthStatus.GREEN),
    ("MES 二期扩容", OppStage.PROPOSAL, 1200000, 30, HealthStatus.GREEN),
    ("重工 ERP 项目", OppStage.QUALIFICATION, 4500000, 90, HealthStatus.RED),
    ("工控升级改造", OppStage.NEEDS_ANALYSIS, 700000, 60, HealthStatus.YELLOW),
    ("质量管理系统", OppStage.VALUE_PROPOSITION, 1100000, 45, HealthStatus.GREEN),
    ("供应链协同", OppStage.PROPOSAL, 2400000, 30, HealthStatus.GREEN),
    ("自动化改造", OppStage.NEGOTIATION, 1800000, 14, HealthStatus.GREEN),
]

LAST_NAMES = ["王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴"]
FIRST_NAMES = ["总", "明", "华", "伟", "强", "芳", "莉", "峰", "敏", "军"]


async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    sf = async_sessionmaker(engine, expire_on_commit=False)

    async with sf() as session:
        # Get AE user
        res = await session.execute(select(User).where(User.role == UserRole.AE))
        ae = res.scalar_one_or_none()
        if not ae:
            print("❌ AE user not found — run seed_users.py first")
            return

        accounts = []
        contacts_all = []
        opps = []

        # ── Accounts ───────────────────────────────────────────────────────
        for i, (name, industry, region, emp) in enumerate(ACCOUNT_DATA):
            acc = Account(
                name=name, industry=industry, region=region,
                employee_count=emp, owner_id=ae.id,
                website=f"https://www.{name.lower().replace(' ','')}.com",
            )
            session.add(acc)
            accounts.append(acc)

        await session.flush()

        # ── Contacts (3-4 per account) ─────────────────────────────────────
        surnames = LAST_NAMES * 10
        for acc_idx, acc in enumerate(accounts):
            n_contacts = random.randint(3, 4)
            for j in range(n_contacts):
                tmpl = CONTACT_TEMPLATES[j % len(CONTACT_TEMPLATES)]
                title, role, influence = tmpl
                surname = surnames[(acc_idx * 4 + j) % len(surnames)]
                firstname = FIRST_NAMES[(acc_idx + j * 3) % len(FIRST_NAMES)]
                c = Contact(
                    account_id=acc.id,
                    full_name=f"{surname}{firstname}",
                    title=title,
                    email=f"{surname.lower()}{acc_idx}{j}@{acc.name[:2]}.com",
                    phone=f"138{acc_idx:02d}{j:03d}0000",
                    role_in_deal=role,
                    influence_level=influence,
                )
                session.add(c)
                contacts_all.append((acc.id, c))

        await session.flush()

        # ── Opportunities (20) ─────────────────────────────────────────────
        for i, (name, stage, amount, days_to_close, health_status) in enumerate(OPP_TEMPLATES):
            acc = accounts[i % len(accounts)]
            close_date = date.today() + timedelta(days=days_to_close)
            health_score = {
                HealthStatus.GREEN: random.randint(75, 95),
                HealthStatus.YELLOW: random.randint(45, 65),
                HealthStatus.RED: random.randint(15, 40),
            }[health_status]
            opp = Opportunity(
                account_id=acc.id, owner_id=ae.id,
                name=name, stage=stage,
                amount=amount,
                expected_close_date=close_date,
                health_score=health_score,
                health_status=health_status,
                pain_points="数据孤岛严重，人工报工效率低，缺乏实时产线监控" if i % 3 == 0 else None,
                competitor=["用友 U9", "西门子", "鼎捷 ERP", None, "SAP"][i % 5],
                budget_status=["confirmed", "under_review", "cut", "tbd"][i % 4],
            )
            session.add(opp)
            opps.append(opp)

        await session.flush()

        # ── Activities (4-5 per opp, including golden minutes) ─────────────
        activity_count = 0
        for opp_idx, opp in enumerate(opps):
            n = random.randint(3, 5)
            for j in range(n):
                if opp_idx < len(GOLDEN_MINUTES) and j == 0:
                    # First activity of first N opps uses golden minutes
                    body = GOLDEN_MINUTES[opp_idx]
                    canonical = body
                    atype = ActivityType.MEETING
                    subject = f"会议纪要 — {opp.name}"
                else:
                    atype = random.choice([ActivityType.CALL, ActivityType.EMAIL, ActivityType.NOTE])
                    subject = random.choice([
                        "电话跟进", "发送方案", "价格谈判", "技术评估反馈",
                        "演示跟进", "合同审核", "项目推进沟通",
                    ])
                    body = None
                    canonical = None

                activity = Activity(
                    opportunity_id=opp.id,
                    owner_id=ae.id,
                    activity_type=atype,
                    subject=f"{subject} — {opp.name}",
                    body=body,
                    canonical_text=canonical,
                )
                session.add(activity)
                activity_count += 1

        await session.commit()

    await engine.dispose()
    print(f"✅ Seed done:")
    print(f"   Accounts:    {len(ACCOUNT_DATA)}")
    print(f"   Contacts:    {len(contacts_all)}")
    print(f"   Opps:        {len(opps)}")
    print(f"   Activities:  {activity_count}")


if __name__ == "__main__":
    asyncio.run(main())
