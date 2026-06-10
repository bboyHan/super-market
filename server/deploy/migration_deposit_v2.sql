-- USDT充值地址管理 + 链上自动充值
BEGIN;

-- ============================================================
-- deposit_addresses — 管理员分配的充值地址
-- ============================================================
CREATE TABLE IF NOT EXISTS deposit_addresses (
    id BIGSERIAL PRIMARY KEY,
    owner_type VARCHAR(20) NOT NULL,           -- SUPPLIER / AGENT
    owner_id BIGINT NOT NULL,
    chain VARCHAR(10) NOT NULL,                -- TRC20 / ERC20 / BSC
    address VARCHAR(256) NOT NULL,             -- 链上收款地址
    label VARCHAR(64) DEFAULT '',              -- 备注标签
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE / DISABLED
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(chain, address)
);
CREATE INDEX IF NOT EXISTS idx_deposit_addr_owner ON deposit_addresses(owner_type, owner_id, status);
CREATE INDEX IF NOT EXISTS idx_deposit_addr_chain ON deposit_addresses(chain, address);

-- ============================================================
-- deposits 表增强 — 增加链信息和自动到账字段
-- ============================================================
ALTER TABLE deposits ADD COLUMN IF NOT EXISTS chain VARCHAR(10) DEFAULT '';
ALTER TABLE deposits ADD COLUMN IF NOT EXISTS confirm_blocks INTEGER DEFAULT 0;
ALTER TABLE deposits ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(12,6) DEFAULT 0;
ALTER TABLE deposits ADD COLUMN IF NOT EXISTS usdt_amount NUMERIC(20,6) DEFAULT 0;

-- ============================================================
-- 汇率配置表（管理员可设置兜底汇率）
-- ============================================================
CREATE TABLE IF NOT EXISTS exchange_rates (
    id BIGSERIAL PRIMARY KEY,
    currency_from VARCHAR(10) NOT NULL DEFAULT 'USDT',
    currency_to VARCHAR(10) NOT NULL DEFAULT 'POINT',
    rate NUMERIC(12,6) NOT NULL DEFAULT 1.0,
    source VARCHAR(20) NOT NULL DEFAULT 'FALLBACK',  -- FALLBACK / API
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO exchange_rates (currency_from, currency_to, rate, source)
VALUES ('USDT', 'POINT', 1.0, 'FALLBACK')
ON CONFLICT DO NOTHING;

COMMIT;
