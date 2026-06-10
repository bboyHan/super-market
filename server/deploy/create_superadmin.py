"""Create superadmin user."""
import asyncio
import asyncpg


async def run():
    conn = await asyncpg.connect(
        user="postgres", password="sjmm", host="localhost",
        port=5432, database="super_market",
    )
    exists = await conn.fetchval("SELECT id FROM users WHERE username='superadmin'")
    if not exists:
        await conn.execute(
            "INSERT INTO users (username, password_hash, role, status) "
            "VALUES ('superadmin', crypt('superadmin', gen_salt('bf')), 'ADMIN', 'ACTIVE')"
        )
        print("✅ superadmin created")
    else:
        print("superadmin already exists")
    await conn.close()


asyncio.run(run())
