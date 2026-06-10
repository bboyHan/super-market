"""Add 2026 order partitions."""
import asyncio
import asyncpg


async def run():
    conn = await asyncpg.connect(
        user="postgres", password="sjmm", host="localhost",
        port=5432, database="super_market",
    )
    for m in range(1, 13):
        ym = f"2026{m:02d}"
        start = f"2026-{m:02d}-01"
        end = f"2026-{m+1:02d}-01" if m < 12 else "2027-01-01"
        await conn.execute(
            f"CREATE TABLE IF NOT EXISTS orders_{ym} PARTITION OF orders "
            f"FOR VALUES FROM ('{start}') TO ('{end}')"
        )
        print(f"  orders_{ym}  ({start} → {end})")
    await conn.close()
    print("✅ Done")


asyncio.run(run())
