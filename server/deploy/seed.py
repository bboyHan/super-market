"""Seed test data: supplier + agent + api_payer + wallet + inventory."""
import asyncio
import asyncpg

DB = dict(user="postgres", password="sjmm", host="localhost", port=5432, database="super_market")


async def seed():
    conn = await asyncpg.connect(**DB)

    # 1. Supplier
    sid = await conn.fetchval(
        """INSERT INTO suppliers (name, contact_name, api_key, api_secret_hash)
           VALUES ('测试供应商', '张三', 'sk_test_supplier_001', 'hash_abc123')
           ON CONFLICT (api_key) DO UPDATE SET name=EXCLUDED.name
           RETURNING id"""
    )
    print(f"Supplier ID: {sid}")

    # 2. Agent
    aid = await conn.fetchval(
        """INSERT INTO agents (supplier_id, name, contact_name, balance, frozen)
           VALUES ($1, '优质代理商', '李四', 50000, 0)
           RETURNING id""",
        sid,
    )
    print(f"Agent ID: {aid}")

    # 3. API Payer
    pid = await conn.fetchval(
        """INSERT INTO api_payers (supplier_id, name, api_key, api_secret, callback_url, ip_whitelist)
           VALUES ($1, '商户A', 'sk_api_merchant_a', 'sec_merchant_a_key', 'https://merchant-a.com/callback', '["127.0.0.1"]')
           ON CONFLICT (api_key) DO UPDATE SET name=EXCLUDED.name
           RETURNING id""",
        sid,
    )
    print(f"API Payer ID: {pid}")

    # 4. Authorize product for supplier
    await conn.execute(
        """INSERT INTO supplier_product_auth (supplier_id, product_id, settlement_price)
           SELECT $1, id, 95 FROM products WHERE name LIKE '京东E卡%' LIMIT 1
           ON CONFLICT DO NOTHING""",
        sid,
    )
    print("Supplier product auth done")

    # 5. Authorize product for agent
    prod_id = await conn.fetchval("SELECT id FROM products WHERE name LIKE '京东E卡%' LIMIT 1")
    await conn.execute(
        """INSERT INTO agent_product_auth (agent_id, product_id, supplier_id, agent_price)
           VALUES ($1, $2, $3, 100) ON CONFLICT DO NOTHING""",
        aid,
        prod_id,
        sid,
    )
    print(f"Agent product auth done (product_id={prod_id})")

    # 6. Wallet for supplier
    ws = await conn.fetchval(
        """INSERT INTO wallets (owner_type, owner_id, balance) VALUES ('SUPPLIER', $1, 100000)
           ON CONFLICT (owner_type, owner_id) DO UPDATE SET balance=EXCLUDED.balance
           RETURNING id""",
        sid,
    )
    print(f"Supplier wallet ID: {ws}")

    # 7. Wallet for agent
    wa = await conn.fetchval(
        """INSERT INTO wallets (owner_type, owner_id, balance) VALUES ('AGENT', $1, 50000)
           ON CONFLICT (owner_type, owner_id) DO UPDATE SET balance=EXCLUDED.balance
           RETURNING id""",
        aid,
    )
    print(f"Agent wallet ID: {wa}")

    # 8. Inventory
    inv = await conn.fetchval(
        """INSERT INTO inventory_items (agent_id, product_id, content)
           VALUES ($1, $2, 'JD-TEST-CARD-001')
           RETURNING id""",
        aid,
        prod_id,
    )
    print(f"Inventory item ID: {inv}")

    # 9. Verify
    rows = await conn.fetch("SELECT owner_type, owner_id, balance FROM wallets")
    for r in rows:
        print(f"  Wallet: {r['owner_type']} #{r['owner_id']} = {r['balance']} pts")

    await conn.close()
    print("\n✅ Seed complete")


asyncio.run(seed())
