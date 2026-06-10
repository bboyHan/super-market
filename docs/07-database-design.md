# VBox B2B2B — 数据库设计

## 实体关系

```
suppliers ──1:N──▶ agents
suppliers ──1:N──▶ api_payers
suppliers ──1:N──▶ wallets
suppliers ──M:N──▶ products  (通过 supplier_product_auth)
agents ────M:N──▶ products  (通过 agent_product_auth)
agents ────1:N──▶ inventory_items
agents ────1:N──▶ terminal_devices
api_payers ──1:N──▶ orders
orders ────1:N──▶ order_deliveries
wallets ────1:N──▶ wallet_transactions
products ────1:N──▶ routing_rules
routing_rules ──1:N──▶ routing_rule_items
```

## 表结构

### 1. suppliers — 供应商

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| name | VARCHAR(128) | 供应商名称 |
| contact_name | VARCHAR(64) | 联系人 |
| contact_phone | VARCHAR(20) | 联系电话 |
| email | VARCHAR(128) | 邮箱 |
| status | VARCHAR(20) | ACTIVE / INACTIVE / FROZEN |
| api_key | VARCHAR(64) UNIQUE | API密钥 |
| api_secret_hash | VARCHAR(256) | 密钥哈希 |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### 2. agents — 代理商

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| supplier_id | BIGINT FK→suppliers | 所属供应商 |
| name | VARCHAR(128) | 代理商名称 |
| contact_name | VARCHAR(64) | |
| contact_phone | VARCHAR(20) | |
| status | VARCHAR(20) | ACTIVE / INACTIVE |
| balance | BIGINT DEFAULT 0 | 积分余额 |
| frozen | BIGINT DEFAULT 0 | 冻结积分 |
| total_consumed | BIGINT DEFAULT 0 | 累计消耗积分 |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### 3. api_payers — API支付商

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| supplier_id | BIGINT FK→suppliers | 所属供应商 |
| name | VARCHAR(128) | 商户名称 |
| api_key | VARCHAR(64) UNIQUE | API Key |
| api_secret | VARCHAR(256) | API Secret |
| callback_url | VARCHAR(512) | 默认回调地址 |
| ip_whitelist | JSONB | IP白名单 |
| status | VARCHAR(20) | ACTIVE / INACTIVE |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### 4. products — 货品（平台管理员创建）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| name | VARCHAR(128) | 货品名称 |
| category | VARCHAR(64) | 分类 |
| face_value | INTEGER | 面值（积分） |
| suggested_price | INTEGER | 建议售价 |
| description | TEXT | 描述 |
| delivery_mode | VARCHAR(32) | AUTO卡密/AUTO_TOKEN/MANUAL |
| confirm_mode | VARCHAR(32) | AUTO/MANUAL |
| status | BOOLEAN | 上架/下架 |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### 5. supplier_product_auth — 供应商货品授权

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| supplier_id | BIGINT FK→suppliers | |
| product_id | BIGINT FK→products | |
| settlement_price | INTEGER | 结算价 |
| status | BOOLEAN | |
| created_at | TIMESTAMPTZ | |

### 6. agent_product_auth — 代理商货品授权

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| agent_id | BIGINT FK→agents | |
| product_id | BIGINT FK→products | |
| supplier_id | BIGINT FK→suppliers | |
| agent_price | INTEGER | 代理商售价 |
| status | BOOLEAN | |
| created_at | TIMESTAMPTZ | |

### 7. orders — 订单（按月分区）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL | |
| order_no | VARCHAR(64) UNIQUE | 平台订单号 |
| client_order_id | VARCHAR(64) | API支付商自定义订单号 |
| api_payer_id | BIGINT FK→api_payers | |
| supplier_id | BIGINT FK→suppliers | |
| agent_id | BIGINT FK→agents | |
| product_id | BIGINT FK→products | |
| quantity | INTEGER DEFAULT 1 | |
| amount | INTEGER | 总金额（积分） |
| status | VARCHAR(20) | SUBMITTED/PENDING/DELIVERING/SUCCESS/CANCELLED/EXPIRED/FAILED |
| confirm_mode | VARCHAR(20) | AUTO/MANUAL |
| callback_url | VARCHAR(512) | |
| callback_status | VARCHAR(20) | PENDING/SUCCESS/FAILED |
| callback_cnt | INTEGER DEFAULT 0 | |
| callback_at | TIMESTAMPTZ | |
| expired_at | TIMESTAMPTZ | |
| paid_at | TIMESTAMPTZ | |
| remark | TEXT | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |
| PRIMARY KEY (id, created_at) | | 分区键 |

### 8. order_deliveries — 交付内容

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| order_id | BIGINT FK→orders | |
| type | VARCHAR(32) | card_key/token/account_info/url |
| content | TEXT | 交付内容（加密） |
| delivered_at | TIMESTAMPTZ | |

### 9. wallets — 钱包

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| owner_type | VARCHAR(20) | SUPPLIER/AGENT |
| owner_id | BIGINT | 对应供应商或代理商ID |
| balance | BIGINT DEFAULT 0 | |
| frozen | BIGINT DEFAULT 0 | |
| currency | VARCHAR(10) DEFAULT 'POINT' | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |
| UNIQUE (owner_type, owner_id) | | |

### 10. wallet_transactions — 交易流水

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| wallet_id | BIGINT FK→wallets | |
| type | VARCHAR(20) | RECHARGE/CONSUME/TRANSFER_IN/TRANSFER_OUT/REFUND/FEE |
| amount | BIGINT | |
| balance_before | BIGINT | |
| balance_after | BIGINT | |
| related_order_no | VARCHAR(64) | 关联订单号 |
| remark | VARCHAR(256) | |
| created_at | TIMESTAMPTZ | |

### 11. inventory_items — 库存

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| agent_id | BIGINT FK→agents | |
| product_id | BIGINT FK→products | |
| content | TEXT | 卡密/Token（加密） |
| status | VARCHAR(20) | AVAILABLE/USED/EXPIRED |
| order_id | BIGINT | 绑定订单（已售时） |
| expires_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |

### 12. routing_rules — 路由规则

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| supplier_id | BIGINT FK→suppliers | |
| product_id | BIGINT FK→products | |
| strategy | VARCHAR(20) | ROUND_ROBIN/PRIORITY/WEIGHTED |
| created_at | TIMESTAMPTZ | |
| UNIQUE (supplier_id, product_id) | | |

### 13. routing_rule_items — 路由规则明细

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| rule_id | BIGINT FK→routing_rules | |
| agent_id | BIGINT FK→agents | |
| priority | INTEGER DEFAULT 0 | 优先级/权重值 |
| enabled | BOOLEAN DEFAULT TRUE | 是否启用 |

### 14. daily_stats_merchant — API支付商日结

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| supplier_id | BIGINT | |
| api_payer_id | BIGINT | |
| stat_date | DATE | |
| total_orders | INTEGER | |
| success_orders | INTEGER | |
| total_amount | BIGINT | |
| success_amount | BIGINT | |
| created_at | TIMESTAMPTZ | |
| UNIQUE (supplier_id, api_payer_id, stat_date) | | |

### 15. daily_stats_category — 品类日结

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| supplier_id | BIGINT | |
| product_id | BIGINT | |
| stat_date | DATE | |
| total_orders | INTEGER | |
| total_amount | BIGINT | |
| created_at | TIMESTAMPTZ | |
| UNIQUE (supplier_id, product_id, stat_date) | | |

### 16. terminal_devices — 终端设备

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| agent_id | BIGINT FK→agents | |
| terminal_id | VARCHAR(64) UNIQUE | |
| machine_code | VARCHAR(128) | |
| token | VARCHAR(256) | 认证令牌 |
| version | VARCHAR(32) | |
| status | VARCHAR(20) | ONLINE/OFFLINE/BUSY |
| last_heartbeat | TIMESTAMPTZ | |
| bound_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |
