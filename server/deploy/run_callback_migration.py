"""Run callback migration."""
import asyncio
import asyncpg

DSN = "postgresql://postgres:***@localhost:5432/super_market"

async def main():
    conn = await asyncpg.connect(DSN)
    sql = open("deploy/migration_callback.sql").read()
    await conn.execute(sql)
    rows = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name='orders' AND column_name='next_retry_at'")
    if rows:
        print("OK: next_retry_at column exists")
    else:
        print("FAIL: column not found")
    await conn.close()

asyncio.run(main())
