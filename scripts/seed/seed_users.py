"""
种子用户脚本 — P1 启动后运行一次
用法：cd apps/api && python ../../scripts/seed/seed_users.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.db.session import Base


SEED_USERS = [
    {"email": "admin@montocrm.local", "password": "Admin@123!", "full_name": "系统管理员", "role": UserRole.ADMIN},
    {"email": "manager@montocrm.local", "password": "Manager@123!", "full_name": "销售主管", "role": UserRole.MANAGER},
    {"email": "ae@montocrm.local", "password": "AE@123!", "full_name": "客户经理 A", "role": UserRole.AE},
]


async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        for u in SEED_USERS:
            user = User(
                email=u["email"],
                hashed_password=hash_password(u["password"]),
                full_name=u["full_name"],
                role=u["role"],
            )
            session.add(user)
        await session.commit()
    await engine.dispose()
    print("✅ Seed users created")


if __name__ == "__main__":
    asyncio.run(main())
