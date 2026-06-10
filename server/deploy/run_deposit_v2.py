"""Run deposit v2 migration with direct password."""
import asyncio
import asyncpg
import sys

async def main():
    conn = await asyncpg.connect(
        host="localhost", port=5432,
        user="postgres", password="sjmm",
        database="super_market"
    )
    sql = open("deploy/migration_deposit_v2.sql").read()
    await conn.execute(sql)
    print("Migration OK", flush=True)
    for tbl in ['deposit_addresses', 'exchange_rates']:
        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name=$1 ORDER BY ordinal_position",
            tbl)
        print(f"{tbl}: {[r['column_name'] for r in cols]}", flush=True)
    # Check deposits
    cols = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name='deposits' AND column_name IN ('chain','exchange_rate','usdt_amount')")
    print(f"deposits new cols: {[r['column_name'] for r in cols]}", flush=True)
    await conn.close()

asyncio.run(main())
