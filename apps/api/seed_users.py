"""临时种子脚本 — 在容器内运行一次后可删除"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole

SEED = [
    {"email": "admin@montocrm.local", "password": "Admin@123!", "full_name": "系统管理员", "role": UserRole.ADMIN},
    {"email": "manager@montocrm.local", "password": "Manager@123!", "full_name": "销售主管", "role": UserRole.MANAGER},
    {"email": "ae@montocrm.local", "password": "AE@123!", "full_name": "客户经理 A", "role": UserRole.AE},
]

async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        for u in SEED:
            exists = await session.execute(select(User).where(User.email == u["email"]))
            if exists.scalar_one_or_none():
                print(f"  skip (exists): {u['email']}")
                continue
            user = User(
                email=u["email"],
                hashed_password=hash_password(u["password"]),
                full_name=u["full_name"],
                role=u["role"],
            )
            session.add(user)
            print(f"  created: {u['email']}")
        await session.commit()
    await engine.dispose()
    print("done")

asyncio.run(main())
