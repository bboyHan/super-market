-- VBox B2B2B — 用户体系 + 积分体系增强迁移
BEGIN;

-- ============================================================
-- 密码加密扩展
-- ============================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- users — 统一用户认证表
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(20) NOT NULL,           -- SUPPLIER / AGENT / ADMIN
    reference_id BIGINT,                 -- 关联 supplier.id 或 agent.id
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_reference ON users(role, reference_id);

-- ============================================================
-- login_log — 登录日志（安全审计）
-- ============================================================
CREATE TABLE IF NOT EXISTS login_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    username VARCHAR(64) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    fail_reason VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_login_logs_user ON login_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_login_logs_time ON login_logs(created_at DESC);

-- ============================================================
-- 钱包增强 — 增加累计字段和版本号（乐观锁防并发）
-- ============================================================
ALTER TABLE wallets ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE wallets ADD COLUMN IF NOT EXISTS total_recharge BIGINT NOT NULL DEFAULT 0;
ALTER TABLE wallets ADD COLUMN IF NOT EXISTS total_consumed BIGINT NOT NULL DEFAULT 0;
ALTER TABLE wallets ADD COLUMN IF NOT EXISTS total_transferred_in BIGINT NOT NULL DEFAULT 0;
ALTER TABLE wallets ADD COLUMN IF NOT EXISTS total_transferred_out BIGINT NOT NULL DEFAULT 0;

-- ============================================================
-- wallet_transactions 增加索引和状态
-- ============================================================
ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'COMPLETED';
ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS operator_id BIGINT DEFAULT 0;
ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS operator_type VARCHAR(20) DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_wallet_tx_type ON wallet_transactions(wallet_id, type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wallet_tx_order ON wallet_transactions(related_order_no);

-- ============================================================
-- 积分冻结记录表（订单预抵扣明细）
-- ============================================================
CREATE TABLE IF NOT EXISTS point_freeze_records (
    id BIGSERIAL PRIMARY KEY,
    wallet_id BIGINT NOT NULL REFERENCES wallets(id),
    order_no VARCHAR(64) NOT NULL,
    agent_id BIGINT NOT NULL REFERENCES agents(id),
    amount INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'FROZEN',  -- FROZEN / DEDUCTED / UNFROZEN
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unfrozen_at TIMESTAMPTZ,
    deducted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_freeze_wallet ON point_freeze_records(wallet_id, status);
CREATE INDEX IF NOT EXISTS idx_freeze_order ON point_freeze_records(order_no);

-- ============================================================
-- 创建默认管理员（密码: admin123）
-- ============================================================
INSERT INTO users (username, password_hash, role, status)
VALUES (
    'admin',
    crypt('admin123', gen_salt('bf')),
    'ADMIN',
    'ACTIVE'
) ON CONFLICT (username) DO NOTHING;

COMMIT;
