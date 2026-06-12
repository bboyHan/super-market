-- System announcements (系统公告)
CREATE TABLE IF NOT EXISTS announcements (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(256) NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    target_role VARCHAR(20) NOT NULL DEFAULT 'ALL',  -- ALL / SUPPLIER / AGENT
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',     -- ACTIVE / INACTIVE
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_announcements_status ON announcements(status);

-- Platform fee config (平台手续费率)
CREATE TABLE IF NOT EXISTS fee_config (
    id BIGSERIAL PRIMARY KEY,
    fee_name VARCHAR(64) NOT NULL UNIQUE,          -- e.g. 'order_fee', 'withdraw_fee'
    fee_rate NUMERIC(5,4) NOT NULL DEFAULT 0.0000, -- e.g. 0.0050 = 0.5%
    fee_type VARCHAR(20) NOT NULL DEFAULT 'RATE',   -- RATE / FIXED
    description VARCHAR(256) NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default fee entries
INSERT INTO fee_config (fee_name, fee_rate, fee_type, description) VALUES
    ('order_fee', 0.0050, 'RATE', '订单交易手续费(0.5%)')
ON CONFLICT (fee_name) DO NOTHING;
