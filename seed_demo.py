import asyncio
import os
import secrets
import uuid
from app.auth import hash_password
from app.database import AsyncSessionLocal
from app.models import Tenant, User, UserRole

async def seed():
    password = os.environ.get("SEED_ADMIN_PASSWORD") or secrets.token_urlsafe(16)
    async with AsyncSessionLocal() as session:
        t_id = uuid.uuid4()
        new_tenant = Tenant(
            id=t_id, 
            name="TPA Member - Nashville Pharmacy", 
            is_active=True
        )
        session.add(new_tenant)

        admin_user = User(
            tenant_id=t_id,
            email="admin@example.com",
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
        )
        session.add(admin_user)

        await session.commit()
        print(f"✅ SUCCESS: Seeded Tenant ID: {t_id}")
        if not os.environ.get("SEED_ADMIN_PASSWORD"):
            print(f"✅ SUCCESS: Seeded admin user: admin@example.com — generated password printed once; store it securely: {password}")
        else:
            print("✅ SUCCESS: Seeded admin user: admin@example.com (password set from SEED_ADMIN_PASSWORD env var)")

if __name__ == "__main__":
    asyncio.run(seed())
