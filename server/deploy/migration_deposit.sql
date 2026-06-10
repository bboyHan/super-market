-- USDT充值迁移
BEGIN;

-- ============================================================
-- deposits — USDT充值申请
-- ============================================================
CREATE TABLE IF NOT EXISTS deposits (
    id BIGSERIAL PRIMARY KEY,
    owner_type VARCHAR(20) NOT NULL,           -- SUPPLIER / AGENT
    owner_id BIGINT NOT NULL,
    wallet_id BIGINT NOT NULL REFERENCES wallets(id),
    amount BIGINT NOT NULL,                    -- 积分数量（1:1 USDT）
    currency VARCHAR(10) NOT NULL DEFAULT 'USDT',
    tx_hash VARCHAR(256) NOT NULL DEFAULT '',  -- 链上交易哈希
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',  -- PENDING / CONFIRMED / REJECTED
    admin_id BIGINT DEFAULT 0,                 -- 审核的管理员ID
    admin_note TEXT DEFAULT '',                -- 审核备注
    remark TEXT DEFAULT '',
    confirmed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_deposits_owner ON deposits(owner_type, owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deposits_status ON deposits(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deposits_tx_hash ON deposits(tx_hash);

-- wallet_transactions 增加关联充值ID
ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS deposit_id BIGINT DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_wallet_tx_deposit ON wallet_transactions(deposit_id);

COMMIT;
