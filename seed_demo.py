import asyncio
import uuid
from app.database import AsyncSessionLocal
from app.models import Tenant

async def seed():
    async with AsyncSessionLocal() as session:
        t_id = uuid.uuid4()
        new_tenant = Tenant(
            id=t_id, 
            name="TPA Member - Nashville Pharmacy", 
            is_active=True
        )
        session.add(new_tenant)
        await session.commit()
        print(f"✅ SUCCESS: Seeded Tenant ID: {t_id}")

if __name__ == "__main__":
    asyncio.run(seed())
