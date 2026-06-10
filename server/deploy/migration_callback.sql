-- 回调重试迁移: orders 表增加 next_retry_at
BEGIN;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_orders_callback_pending ON orders(callback_url, callback_status, next_retry_at)
    WHERE callback_url != '' AND callback_status != 'SUCCESS';
COMMIT;
