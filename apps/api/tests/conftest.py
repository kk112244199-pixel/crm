"""共享测试 fixtures。"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.main import app
from app.db.session import Base, get_db
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.crm import Account, Opportunity, OppStage, HealthStatus

TEST_DATABASE_URL = "postgresql+asyncpg://montocrm:changeme@localhost:5432/montocrm_test"
_schema_ready = False


@pytest.fixture
async def test_engine():
    global _schema_ready
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    if not _schema_ready:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            await conn.run_sync(Base.metadata.create_all)
        _schema_ready = True
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def seed_users(db_session: AsyncSession):
    specs = [
        ("ae@test.com", "ae123", "AE User", UserRole.AE),
        ("manager@test.com", "mgr123", "Manager", UserRole.MANAGER),
        ("admin@test.com", "adm123", "Admin", UserRole.ADMIN),
    ]
    out: dict[str, User] = {}
    for email, password, name, role in specs:
        row = (await db_session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not row:
            row = User(email=email, hashed_password=hash_password(password), full_name=name, role=role)
            db_session.add(row)
            await db_session.flush()
        out[role.value] = row
    await db_session.commit()
    return out


@pytest.fixture
async def ae_token(client: AsyncClient, seed_users):
    resp = await client.post(
        "/auth/token",
        data={"username": "ae@test.com", "password": "ae123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return resp.json()["access_token"]


@pytest.fixture
async def test_opportunity_id(db_session: AsyncSession, seed_users):
    from datetime import date, timedelta
    ae = seed_users[UserRole.AE.value]

    account = Account(
        name="测试客户",
        industry="工业软件",
        region="华东",
        owner_id=ae.id,
    )
    db_session.add(account)
    await db_session.flush()

    opp = Opportunity(
        account_id=account.id,
        owner_id=ae.id,
        name="MES 采购项目（测试）",
        stage=OppStage.PROPOSAL,
        amount=3800000,
        expected_close_date=date.today() + timedelta(days=45),
        health_status=HealthStatus.YELLOW,
        health_score=60,
    )
    db_session.add(opp)
    await db_session.commit()
    return opp.id
