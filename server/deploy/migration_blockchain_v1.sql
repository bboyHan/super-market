-- 链上交易监控 + 自动匹配系统 v1
-- 记录所有检测到的链上交易，支持自动匹配和手动认领
BEGIN;

-- ============================================================
-- blockchain_txns — 已检测到的链上交易记录
-- ============================================================
CREATE TABLE IF NOT EXISTS blockchain_txns (
    id              BIGSERIAL PRIMARY KEY,
    chain           VARCHAR(10) NOT NULL,            -- TRC20 / ERC20 / BSC
    tx_hash         VARCHAR(128) NOT NULL,           -- 链上交易哈希
    from_address    VARCHAR(64) NOT NULL,            -- 发送方地址
    to_address      VARCHAR(64) NOT NULL,            -- 接收方地址（即平台地址）
    amount          DECIMAL(20,6) NOT NULL,          -- USDT 金额
    block_number    BIGINT NOT NULL DEFAULT 0,       -- 区块高度
    block_ts        TIMESTAMPTZ,                     -- 区块时间戳
    status          VARCHAR(20) NOT NULL DEFAULT 'UNMATCHED', -- UNMATCHED / MATCHED / CLAIMED_MANUAL / IGNORED
    deposit_id      BIGINT,                          -- 匹配到的 deposits.id
    remark          VARCHAR(256) DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(chain, tx_hash)
);
CREATE INDEX IF NOT EXISTS idx_bc_txns_status ON blockchain_txns(status);
CREATE INDEX IF NOT EXISTS idx_bc_txns_to_addr ON blockchain_txns(to_address);
CREATE INDEX IF NOT EXISTS idx_bc_txns_block ON blockchain_txns(block_number);
CREATE INDEX IF NOT EXISTS idx_bc_txns_tx_hash ON blockchain_txns(tx_hash);

-- ============================================================
-- blockchain_monitor_state — 监控进度记录
-- ============================================================
CREATE TABLE IF NOT EXISTS blockchain_monitor_state (
    id              BIGSERIAL PRIMARY KEY,
    chain           VARCHAR(10) NOT NULL,
    address         VARCHAR(64) NOT NULL,            -- 平台钱包地址
    last_block      BIGINT NOT NULL DEFAULT 0,       -- 已扫描到的最大区块
    last_tx_at      TIMESTAMPTZ,                     -- 最后交易时间
    poll_count      BIGINT NOT NULL DEFAULT 0,       -- 轮询次数
    last_error      TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(chain, address)
);

-- ============================================================
-- 给 deposit_addresses 加 qr_code / last_balance 字段
-- ============================================================
ALTER TABLE deposit_addresses ADD COLUMN IF NOT EXISTS last_balance DECIMAL(20,6) DEFAULT 0;
ALTER TABLE deposit_addresses ADD COLUMN IF NOT EXISTS balance_updated_at TIMESTAMPTZ;

COMMIT;
