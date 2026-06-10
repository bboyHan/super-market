# VBox B2B2B — API 对接文档（面向 API 支付商）

> 本文档参考旧系统 `PayDoc.vue` 的接口模式，结合 VBox B2B2B 新产品的业务模型重新设计。

---

## 0. 对接信息

| 项目 | 说明 |
|------|------|
| 请求地址 | 由供应商提供（Base URL） |
| 请求方式 | HTTP POST（表单/JSON） |
| 数据格式 | JSON |
| 字符编码 | UTF-8 |
| 回调 IP 白名单 | 由供应商配置 |

---

## 1. 公共签名规则

### 1.1 获取凭证

联系供应商获取以下凭证：

| 凭证 | 说明 |
|------|------|
| **API Key** | 接口调用身份标识（对应商户ID） |
| **API Secret** | 签名密钥（请妥善保管，不要泄露） |

### 1.2 签名算法（兼容旧系统模式）

```
Step 1: 将请求参数按照 ASCII 码升序排序
Step 2: 按 key=value&key=value 格式拼接
Step 3: 在末尾拼接 &key={API_Secret}
Step 4: 对完整字符串进行 MD5 运算
Step 5: 结果转为小写字母
```

**示例：**

```
原始参数：
  account = "merchant_001"
  money   = "100"
  order_id = "ORD20250101001"
  notify_url = "https://api.merchant.com/callback"
  product_id = "jd_e100"

排序后：
  account=merchant_001&money=100&notify_url=https://api.merchant.com/callback&order_id=ORD20250101001&product_id=jd_e100

拼接 Secret（假设 secret = "abc123"）：
  account=merchant_001&money=100&notify_url=https://api.merchant.com/callback&order_id=ORD20250101001&product_id=jd_e100&key=abc123

MD5 → 小写：
  6a8f2b3c4d5e6f7a8b9c0d1e2f3a4b5c
```

> **注意**：新系统建议升级为 HMAC-SHA256（更安全），但为了兼容旧对接习惯，保留 MD5 签名方式作为可选方案。供应商可在后台配置签名算法。

### 1.3 升级版签名（HMAC-SHA256，推荐）

```
Step 1: 将请求参数按 ASCII 升序排序
Step 2: 按 key=value&key=value 格式拼接
Step 3: 计算 HMAC-SHA256(payload, API_Secret)
Step 4: 结果转为十六进制字符串

Header:
  X-API-Key: {API_Key}
  X-Timestamp: {unix_timestamp}
  X-Signature: {hmac_result}
```

---

## 2. 接口列表

### 2.1 获取货品列表

查询当前可购买的货品信息。

**请求地址：** `POST /api/v1/products`

**请求参数：**

| 字段名 | 字段描述 | 类型 | 必需 | 说明 |
|--------|---------|------|------|------|
| account | 商户ID | string | 是 | 供应商分配的API Key |
| sign | 签名 | string | 是 | 按签名规则计算 |

**请求示例：**

```
POST /api/v1/products?account=merchant_001&sign=6a8f2b3c4d5e6f7a8b9c0d1e2f3a4b5c
```

**响应结果：**

```json
{
  "code": 0,
  "data": [
    {
      "product_id": "jd_e100",
      "product_name": "京东E卡 100元面额",
      "category": "电商卡券",
      "price": 100,
      "stock_status": "available"
    },
    {
      "product_id": "game_50",
      "product_name": "游戏点卡 50元面额",
      "category": "游戏点卡",
      "price": 50,
      "stock_status": "available"
    }
  ],
  "msg": "查询成功"
}
```

---

### 2.2 创建订单

下单购买指定数量的虚拟货品。

**请求地址：** `POST /api/v1/order/create`

**请求参数：**

| 字段名 | 字段描述 | 类型 | 必需 | 说明 |
|--------|---------|------|------|------|
| account | 商户ID | string | 是 | 供应商分配的API Key |
| product_id | 货品ID | string | 是 | 对应产品列表中的product_id |
| quantity | 数量 | int | 是 | 购买数量，最小为1 |
| order_id | 订单ID | string[16,32] | 是 | API支付商自定义订单号 |
| notify_url | 回调地址 | string | 是 | 用于异步通知订单状态变更，不允许携带查询参数 |
| sign | 签名 | string | 是 | 按签名规则计算 |

**请求示例：**

```
POST /api/v1/order/create
?account=merchant_001
&product_id=jd_e100
&quantity=1
&order_id=ORD20250101001
&notify_url=https://api.merchant.com/callback
&sign=6a8f2b3c4d5e6f7a8b9c0d1e2f3a4b5c
```

**响应结果：**

```json
{
  "code": 0,
  "data": {
    "platform_order_id": "PO2025010100001",
    "client_order_id": "ORD20250101001",
    "product_id": "jd_e100",
    "quantity": 1,
    "total_price": 100,
    "status": "PENDING",
    "created_at": "2025-01-01T12:00:00Z"
  },
  "msg": "创建成功"
}
```

**状态说明：**

| 状态值 | 含义 | 说明 |
|--------|------|------|
| SUBMITTED | 已提交 | 订单已提交，等待处理 |
| PENDING | 待确认 | 等待支付确认（手动模式）或系统验证（自动模式） |
| DELIVERING | 交付中 | 代理商正在交付货品 |
| SUCCESS | 已完成 | 订单已完成，货品已交付 |
| CANCELLED | 已取消 | 订单已取消 |
| EXPIRED | 已超时 | 订单超过有效期未完成 |

---

### 2.3 查询订单

根据订单号查询订单的当前状态和交付内容。

**请求地址：** `POST /api/v1/order/query`

**请求参数：**

| 字段名 | 字段描述 | 类型 | 必需 | 说明 |
|--------|---------|------|------|------|
| account | 商户ID | string | 是 | 供应商分配的API Key |
| order_id | 订单ID | string | 是 | 创建订单时使用的自定义订单号 |
| sign | 签名 | string | 是 | 按签名规则计算 |

**请求示例：**

```
POST /api/v1/order/query
?account=merchant_001
&order_id=ORD20250101001
&sign=6a8f2b3c4d5e6f7a8b9c0d1e2f3a4b5c
```

**响应结果：**

```json
{
  "code": 0,
  "data": {
    "platform_order_id": "PO2025010100001",
    "client_order_id": "ORD20250101001",
    "product_id": "jd_e100",
    "quantity": 1,
    "total_price": 100,
    "status": "SUCCESS",
    "deliveries": [
      {
        "type": "card_key",
        "content": "JD-XXXX-YYYY-ZZZZ",
        "delivered_at": "2025-01-01T12:00:05Z"
      }
    ],
    "created_at": "2025-01-01T12:00:00Z",
    "updated_at": "2025-01-01T12:00:05Z"
  },
  "msg": "查询成功"
}
```

---

## 3. 回调通知

### 3.1 回调触发时机

当订单状态发生以下变更时，系统会向 `notify_url` 发送回调通知：

| 触发条件 | 说明 |
|---------|------|
| 订单支付确认完成 | 自动模式验证通过 / 手动模式供应商确认后 |
| 货品交付成功 | 代理商完成货品交付后 |
| 订单异常 | 交付失败、超时取消等 |

### 3.2 回调通知内容

系统以 **HTTP POST** 方式向 `notify_url` 发送 JSON 数据：

```json
{
  "platform_order_id": "PO2025010100001",
  "client_order_id": "ORD20250101001",
  "status": "SUCCESS",
  "deliveries": [
    {
      "type": "card_key",
      "content": "JD-XXXX-YYYY-ZZZZ",
      "delivered_at": "2025-01-01T12:00:05Z"
    }
  ],
  "sign": "6a8f2b3c4d5e6f7a8b9c0d1e2f3a4b5c"
}
```

**交付内容类型说明：**

| type | 含义 | content 格式 |
|------|------|-------------|
| card_key | 卡密 | 字符串形式的卡密/激活码 |
| token | Token | 字符串形式的访问令牌 |
| account_info | 账号信息 | JSON字符串，包含账号密码等 |
| url | 链接 | 可访问的URL |

### 3.3 回调确认

收到回调通知后，**必须返回 HTTP 状态码 200**，否则系统将按以下频率重复通知：

| 次数 | 间隔 |
|------|------|
| 第1次重试 | 30秒后 |
| 第2次重试 | 5分钟后 |
| 第3次重试 | 30分钟后 |
| 第4次重试 | 2小时后 |
| 第5次重试 | 6小时后 |
| 第6次重试 | 24小时后 |

> 建议：收到回调后，先验证 sign 签名合法性，再处理业务逻辑，最后返回200。重试超过6次仍未收到200响应，请人工联系供应商处理。

---

## 4. 回调验证签名

API 支付商收到回调后，应验证 `sign` 字段的合法性：

```
Step 1: 从回调 JSON 中取出 sign 以外的所有字段
Step 2: 按 ASCII 升序排序
Step 3: 按 key=value&key=value 拼接
Step 4: 末尾追加 &key={API_Secret}
Step 5: MD5 运算并转为小写
Step 6: 与回调中的 sign 字段比对

若一致 → 签名合法，处理回调内容
若不一致 → 签名非法，可能被篡改，丢弃该回调
```

---

## 5. 错误码对照表

| Code | 含义 | 说明 |
|------|------|------|
| 0 | 成功 | 请求处理成功 |
| 40001 | 签名错误 | sign 校验失败，请检查签名算法 |
| 40002 | 参数缺失 | 必填参数未提供 |
| 40003 | IP 被限制 | 请求 IP 不在供应商白名单中 |
| 40004 | 账户不存在 | account 参数无效 |
| 40005 | 订单号重复 | 同一 account 下 order_id 已存在 |
| 40301 | 无权限 | 无权访问该货品 |
| 40401 | 货品不存在 | product_id 无效 |
| 40402 | 订单不存在 | 查询的 order_id 不存在 |
| 42901 | 频率超限 | 请求频率超过限制，请稍后重试 |
| 50001 | 库存不足 | 该货品暂无可用库存 |
| 50002 | 交付超时 | 订单已超时取消 |
| 50003 | 系统错误 | 服务器内部异常，请联系供应商 |

---

## 6. 与旧系统 `PayDoc.vue` 的关键差异

| 维度 | 旧系统（支付通道） | 新系统（VBox B2B2B） |
|------|-----------------|---------------------|
| 核心业务 | 支付通道下单（金额） | 虚拟货品购买（积分） |
| 金额字段 | `money`（人民币元） | `total_price`（积分） |
| 产品标识 | `channel_code`（通道编码） | `product_id`（货品ID） |
| 下单结果 | `pay_url`（支付链接） | `deliveries`（货品内容） |
| 订单状态 | `status: 0/1/2`（失败/成功/未支付） | `status: SUBMITTED/PENDING/DELIVERING/SUCCESS` |
| 数量支持 | 仅单次下单 | 支持 `quantity` 批量购买 |
| 签名算法 | MD5（前后追加key） | MD5（兼容旧模式）+ HMAC-SHA256（推荐） |
| API 调用方 | 商户（付方） | API 支付商（供应商的客户） |
