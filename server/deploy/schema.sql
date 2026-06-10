-- VBox B2B2B 初始建表脚本
-- PostgreSQL 18.4

BEGIN;

-- ============================================================
-- 1. 供应商
-- ============================================================
CREATE TABLE IF NOT EXISTS suppliers (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    contact_name VARCHAR(64) DEFAULT '',
    contact_phone VARCHAR(20) DEFAULT '',
    email VARCHAR(128) DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    api_key VARCHAR(64) UNIQUE,
    api_secret_hash VARCHAR(256),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 2. 代理商
-- ============================================================
CREATE TABLE IF NOT EXISTS agents (
    id BIGSERIAL PRIMARY KEY,
    supplier_id BIGINT NOT NULL REFERENCES suppliers(id),
    name VARCHAR(128) NOT NULL,
    contact_name VARCHAR(64) DEFAULT '',
    contact_phone VARCHAR(20) DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    balance BIGINT NOT NULL DEFAULT 0,
    frozen BIGINT NOT NULL DEFAULT 0,
    total_consumed BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agents_supplier ON agents(supplier_id);

-- ============================================================
-- 3. API支付商
-- ============================================================
CREATE TABLE IF NOT EXISTS api_payers (
    id BIGSERIAL PRIMARY KEY,
    supplier_id BIGINT NOT NULL REFERENCES suppliers(id),
    name VARCHAR(128) NOT NULL,
    api_key VARCHAR(64) UNIQUE NOT NULL,
    api_secret VARCHAR(256) NOT NULL,
    callback_url VARCHAR(512) DEFAULT '',
    ip_whitelist JSONB DEFAULT '[]',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_api_payers_supplier ON api_payers(supplier_id);

-- ============================================================
-- 4. 货品品类（平台管理员创建）
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT '',
    face_value INTEGER NOT NULL DEFAULT 0,
    suggested_price INTEGER NOT NULL DEFAULT 0,
    description TEXT DEFAULT '',
    delivery_mode VARCHAR(32) NOT NULL DEFAULT 'AUTO_CARD_KEY',
    confirm_mode VARCHAR(32) NOT NULL DEFAULT 'MANUAL',
    status BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 5. 供应商货品授权
-- ============================================================
CREATE TABLE IF NOT EXISTS supplier_product_auth (
    id BIGSERIAL PRIMARY KEY,
    supplier_id BIGINT NOT NULL REFERENCES suppliers(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    settlement_price INTEGER NOT NULL DEFAULT 0,
    status BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(supplier_id, product_id)
);

-- ============================================================
-- 6. 代理商货品授权
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_product_auth (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL REFERENCES agents(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    supplier_id BIGINT NOT NULL REFERENCES suppliers(id),
    agent_price INTEGER NOT NULL DEFAULT 0,
    status BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_prod_auth_agent ON agent_product_auth(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_prod_auth_product ON agent_product_auth(product_id);

-- ============================================================
-- 7. 订单（按月分区）
-- ============================================================
CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL,
    order_no VARCHAR(64) NOT NULL,
    client_order_id VARCHAR(64) DEFAULT '',
    api_payer_id BIGINT NOT NULL,
    supplier_id BIGINT NOT NULL,
    agent_id BIGINT,
    product_id BIGINT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    amount INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'SUBMITTED',
    confirm_mode VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    callback_url VARCHAR(512) DEFAULT '',
    callback_status VARCHAR(20) DEFAULT 'PENDING',
    callback_cnt INTEGER DEFAULT 0,
    callback_at TIMESTAMPTZ,
    expired_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    remark TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- 创建初始分区
DO $$
DECLARE
    m INTEGER;
    ym TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    FOR m IN 6..12 LOOP
        ym := '2025' || LPAD(m::TEXT, 2, '0');
        start_date := '2025-' || LPAD(m::TEXT, 2, '0') || '-01';
        IF m = 12 THEN
            end_date := '2026-01-01';
        ELSE
            end_date := '2025-' || LPAD((m+1)::TEXT, 2, '0') || '-01';
        END IF;
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS orders_%s PARTITION OF orders FOR VALUES FROM (%L) TO (%L)',
            ym, start_date, end_date
        );
    END LOOP;
END $$;

-- 分区表上唯一索引必须包含分区键
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_order_no ON orders(order_no, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_api_payer ON orders(api_payer_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_supplier ON orders(supplier_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_agent ON orders(agent_id, status);

-- ============================================================
-- 8. 订单交付内容
-- ============================================================
CREATE TABLE IF NOT EXISTS order_deliveries (
    id BIGSERIAL PRIMARY KEY,
    order_no VARCHAR(64) NOT NULL,
    type VARCHAR(32) NOT NULL DEFAULT 'card_key',
    content TEXT NOT NULL,
    delivered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_order_deliveries_order ON order_deliveries(order_no);

-- ============================================================
-- 9. 钱包
-- ============================================================
CREATE TABLE IF NOT EXISTS wallets (
    id BIGSERIAL PRIMARY KEY,
    owner_type VARCHAR(20) NOT NULL,
    owner_id BIGINT NOT NULL,
    balance BIGINT NOT NULL DEFAULT 0,
    frozen BIGINT NOT NULL DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'POINT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(owner_type, owner_id)
);

-- ============================================================
-- 10. 交易流水
-- ============================================================
CREATE TABLE IF NOT EXISTS wallet_transactions (
    id BIGSERIAL PRIMARY KEY,
    wallet_id BIGINT NOT NULL REFERENCES wallets(id),
    type VARCHAR(20) NOT NULL,
    amount BIGINT NOT NULL,
    balance_before BIGINT NOT NULL,
    balance_after BIGINT NOT NULL,
    related_order_no VARCHAR(64) DEFAULT '',
    remark VARCHAR(256) DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wallet_tx_wallet ON wallet_transactions(wallet_id, created_at DESC);

-- ============================================================
-- 11. 库存单元
-- ============================================================
CREATE TABLE IF NOT EXISTS inventory_items (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL REFERENCES agents(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    content TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
    order_no VARCHAR(64) DEFAULT '',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_inventory_agent ON inventory_items(agent_id, product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_status ON inventory_items(agent_id, status);

-- ============================================================
-- 12. 路由规则
-- ============================================================
CREATE TABLE IF NOT EXISTS routing_rules (
    id BIGSERIAL PRIMARY KEY,
    supplier_id BIGINT NOT NULL REFERENCES suppliers(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    strategy VARCHAR(20) NOT NULL DEFAULT 'ROUND_ROBIN',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(supplier_id, product_id)
);

-- ============================================================
-- 13. 路由规则明细
-- ============================================================
CREATE TABLE IF NOT EXISTS routing_rule_items (
    id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT NOT NULL REFERENCES routing_rules(id),
    agent_id BIGINT NOT NULL REFERENCES agents(id),
    priority INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 14. 日结 — 按API支付商
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_stats_merchant (
    id BIGSERIAL PRIMARY KEY,
    supplier_id BIGINT NOT NULL,
    api_payer_id BIGINT NOT NULL,
    stat_date DATE NOT NULL,
    total_orders INTEGER NOT NULL DEFAULT 0,
    success_orders INTEGER NOT NULL DEFAULT 0,
    total_amount BIGINT NOT NULL DEFAULT 0,
    success_amount BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(supplier_id, api_payer_id, stat_date)
);

-- ============================================================
-- 15. 日结 — 按品类
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_stats_category (
    id BIGSERIAL PRIMARY KEY,
    supplier_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    stat_date DATE NOT NULL,
    total_orders INTEGER NOT NULL DEFAULT 0,
    total_amount BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(supplier_id, product_id, stat_date)
);

-- ============================================================
-- 16. 终端设备
-- ============================================================
CREATE TABLE IF NOT EXISTS terminal_devices (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT NOT NULL REFERENCES agents(id),
    terminal_id VARCHAR(64) UNIQUE NOT NULL,
    machine_code VARCHAR(128) DEFAULT '',
    token VARCHAR(256) DEFAULT '',
    version VARCHAR(32) DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'OFFLINE',
    last_heartbeat TIMESTAMPTZ,
    bound_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 种子数据：默认货品
-- ============================================================
INSERT INTO products (name, category, face_value, suggested_price, delivery_mode, confirm_mode, status)
VALUES
    ('京东E卡 100元面额', '电商卡券', 100, 100, 'AUTO_CARD_KEY', 'MANUAL', TRUE),
    ('京东E卡 50元面额',  '电商卡券', 50,  50,  'AUTO_CARD_KEY', 'MANUAL', TRUE),
    ('游戏点卡 50元面额', '游戏点卡', 50,  50,  'AUTO_CARD_KEY', 'MANUAL', TRUE),
    ('游戏点卡 100元面额','游戏点卡', 100, 100, 'AUTO_CARD_KEY', 'MANUAL', TRUE),
    ('视频会员月卡',      '会员权益', 30,  30,  'AUTO_CARD_KEY', 'MANUAL', TRUE)
ON CONFLICT DO NOTHING;

COMMIT;
