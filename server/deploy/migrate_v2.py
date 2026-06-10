"""Migration v2 — user system + wallet enhancements."""
import asyncio
import asyncpg


async def run():
    conn = await asyncpg.connect(
        user="postgres", password="sjmm", host="localhost",
        port=5432, database="super_market",
    )
    with open("deploy/migration_v2.sql") as f:
        sql = f.read()
    await conn.execute(sql)

    # Verify
    tables = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    )
    print("Tables:", [r["tablename"] for r in tables])

    # Verify admin user
    admin = await conn.fetchrow("SELECT id, username, role FROM users WHERE username='admin'")
    print(f"Admin user: id={admin['id']} username={admin['username']} role={admin['role']}")

    await conn.close()
    print("✅ Migration v2 complete")


asyncio.run(run())
