-- ══════════════════════════════════════════════════════════
-- VBox Super Market — 数据清理脚本
-- 保留唯一管理员 admin/admin，清空所有 mock 测试数据
-- ══════════════════════════════════════════════════════════

BEGIN;

-- 1. 清理业务数据（按外键顺序）
DELETE FROM point_freeze_records;
DELETE FROM order_deliveries;
DELETE FROM orders;
DELETE FROM inventory_items;
DELETE FROM wallet_transactions;
DELETE FROM deposits;
DELETE FROM daily_stats_merchant;
DELETE FROM daily_stats_category;
DELETE FROM routing_rule_items;
DELETE FROM routing_rules;
DELETE FROM blockchain_txns;
DELETE FROM blockchain_monitor_state;
DELETE FROM auth_tokens;
DELETE FROM terminal_devices;
DELETE FROM login_logs;

-- 2. 清理钱包（除管理员外）
DELETE FROM wallets WHERE owner_type != 'SUPPLIER' OR (owner_type = 'SUPPLIER' AND owner_id NOT IN (SELECT id FROM suppliers));

-- 3. 清理关系表
DELETE FROM supplier_product_auth;
DELETE FROM agent_product_auth;

-- 4. 清理业务角色
DELETE FROM agents;
DELETE FROM api_payers;
DELETE FROM suppliers;

-- 5. 清理用户（保留一个）
DELETE FROM users WHERE role != 'ADMIN';

-- 6. 清理商品
DELETE FROM products;

-- 7. 重置所有 admin 账号为 admin/admin
DELETE FROM users WHERE role = 'ADMIN';
INSERT INTO users (username, password_hash, role, status)
VALUES ('admin', crypt('admin', gen_salt('bf')), 'ADMIN', 'ACTIVE');

-- 8. 创建默认供应商
INSERT INTO suppliers (name, status) VALUES ('默认供应商', 'ACTIVE');

-- 9. 创建默认商品（3个品类各一个）
INSERT INTO products (name, category, face_value, suggested_price, collection_config, status)
VALUES
  ('京东E卡 100元', '电商卡券', 100, 95, '{"platform":"京东","methods":["browser","manual"],"default_method":"manual","implementation":{"capture":"network","product_url":"https://item.jd.com/100082765615.html"}}'::jsonb, TRUE),
  ('游戏点卡 50元', '游戏点卡', 50, 48, '{"platform":"通用","methods":["manual"],"default_method":"manual"}'::jsonb, TRUE),
  ('视频会员月卡', '会员权益', 30, 28, '{"platform":"通用","methods":["manual"],"default_method":"manual"}'::jsonb, TRUE);

-- 10. 创建默认代理商（关联默认供应商）
WITH sup AS (SELECT id FROM suppliers ORDER BY id LIMIT 1)
INSERT INTO agents (supplier_id, name, status, balance, frozen)
SELECT sup.id, '默认代理商', 'ACTIVE', 10000, 0 FROM sup;

-- 11. 创建代理商钱包
WITH ag AS (SELECT id FROM agents ORDER BY id LIMIT 1)
INSERT INTO wallets (owner_type, owner_id, balance, frozen)
SELECT 'AGENT', ag.id, 10000, 0 FROM ag
WHERE NOT EXISTS (SELECT 1 FROM wallets w WHERE w.owner_type='AGENT' AND w.owner_id=(SELECT id FROM agents ORDER BY id LIMIT 1));

-- 12. 创建供应商钱包
WITH sup AS (SELECT id FROM suppliers ORDER BY id LIMIT 1)
INSERT INTO wallets (owner_type, owner_id, balance, frozen)
SELECT 'SUPPLIER', sup.id, 50000, 0 FROM sup
WHERE NOT EXISTS (SELECT 1 FROM wallets w WHERE w.owner_type='SUPPLIER' AND w.owner_id=(SELECT id FROM suppliers ORDER BY id LIMIT 1));

-- 13. 创建代理商登录账号
WITH ag AS (SELECT id FROM agents ORDER BY id LIMIT 1)
INSERT INTO users (username, password_hash, role, reference_id, status)
SELECT 'agent', crypt('agent123', gen_salt('bf')), 'AGENT', ag.id, 'ACTIVE' FROM ag
WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.reference_id=(SELECT id FROM agents ORDER BY id LIMIT 1) AND u.role='AGENT');

-- 14. 授权供应商可销售默认商品
WITH sup AS (SELECT id FROM suppliers ORDER BY id LIMIT 1)
INSERT INTO supplier_product_auth (supplier_id, product_id, status)
SELECT sup.id, p.id, TRUE FROM sup, products p;

-- 15. 创建默认 API 支付商
WITH sup AS (SELECT id FROM suppliers ORDER BY id LIMIT 1)
INSERT INTO api_payers (supplier_id, name, api_key, api_secret, callback_url, status)
SELECT sup.id, '测试商户', 'sk_demo_key_001', 'ss_demo_secret_001', 'http://localhost:8080/callback', 'ACTIVE' FROM sup;

-- 16. 添加 USDT 充值地址
INSERT INTO deposit_addresses (owner_type, owner_id, chain, address, status)
SELECT 'SYSTEM', 0, 'TRC20', 'TEvK7pDTCkB3U6STFd65TWgbiYDa8kH5tf', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM deposit_addresses WHERE chain='TRC20');
INSERT INTO deposit_addresses (owner_type, owner_id, chain, address, status)
SELECT 'SYSTEM', 0, 'ERC20', '0x28C6c06298d514Db089934071355E5743bf21d60', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM deposit_addresses WHERE chain='ERC20');
INSERT INTO deposit_addresses (owner_type, owner_id, chain, address, status)
SELECT 'SYSTEM', 0, 'BSC', '0x8894E0a0c962CB723c1976a4421c95949bE2D4E3', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM deposit_addresses WHERE chain='BSC');

-- 17. 添加汇率
INSERT INTO exchange_rates (currency_from, currency_to, rate, source)
SELECT 'USDT', 'POINT', 1.0, 'FALLBACK'
WHERE NOT EXISTS (SELECT 1 FROM exchange_rates);

COMMIT;
