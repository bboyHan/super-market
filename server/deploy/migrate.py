"""Run schema migration."""
import asyncio
import asyncpg


async def run():
    conn = await asyncpg.connect(
        user="postgres",
        password="sjmm",
        host="localhost",
        port=5432,
        database="super_market",
    )
    with open("deploy/schema.sql") as f:
        sql = f.read()
    await conn.execute(sql)
    rows = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    )
    print("Tables created:")
    for r in rows:
        print(f"  - {r['tablename']}")
    # Count seed products
    cnt = await conn.fetchval("SELECT count(*) FROM products")
    print(f"Seed products: {cnt}")
    await conn.close()


asyncio.run(run())
