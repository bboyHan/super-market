"""Run deposit migration SQL."""
import asyncio
import asyncpg

DSN = "postgresql://postgres:sjmm@localhost:5432/super_market"

async def main():
    conn = await asyncpg.connect(DSN)
    sql = open("deploy/migration_deposit.sql").read()
    await conn.execute(sql)
    # verify
    rows = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name='deposits' ORDER BY ordinal_position")
    print("deposits columns:", [r['column_name'] for r in rows])
    await conn.close()
    print("Migration OK")

asyncio.run(main())
