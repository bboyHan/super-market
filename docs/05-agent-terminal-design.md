# VBox Agent Terminal — 代理商本地终端工具（初步设计）

> 本文档定义代理商本地终端工具与 VBox 平台的连接交互与通讯机制。详细功能（抓包、识图验证、模拟通过等）留待后续细化。

---

## 一、产品定位

### 1.1 解决什么问题

代理商需要在第三方平台（京东、淘宝、抖音、拼多多等）生成支付二维码或支付链接，然后将这些支付资源上传到 VBox 平台。当前流程依赖人工操作，效率低且易出错。

**本地终端工具**作为代理商侧的桌面应用，实现：

```
第三方平台 (JD/TB/DY/PDD...)     VBox Agent Terminal         VBox 平台
      │                                │                        │
      │  登录凭证/Cookie                │                        │
      │───────────────────────────────▶│                        │
      │                                │                        │
      │  生成支付二维码                 │                        │
      │◀───────────────────────────────│                        │
      │                                │  上传支付资源            │
      │                                │───────────────────────▶│
      │                                │                        │
      │                                │  下发交付指令           │
      │                                │◀───────────────────────│
      │  查询/确认订单                  │                        │
      │───────────────────────────────▶│                        │
```

### 1.2 核心能力

| 能力 | 当前阶段 | 说明 |
|------|---------|------|
| 平台通讯 | ✅ 初步设计 | 与 VBox 平台的 API 交互、心跳、状态同步 |
| 支付资源上传 | ✅ 初步设计 | 上传支付二维码/链接到平台 |
| 抓包能力 | ⏸ 预留 | 捕获第三方平台的支付请求/响应 |
| 验证码识别 | ⏸ 预留 | 图形验证码、文字点选、滑块验证等 |
| 自动登录 | ⏸ 预留 | Cookie/Token 持久化、会话保持 |
| 本地 GUI | ⏸ 后续 | 桌面界面（PyQt/Electron/Tauri） |

---

## 二、通讯架构

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    VBox 平台（服务端）                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Agent API 网关                                         │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │ 身份认证  │ │ 资源管理  │ │ 指令下发  │ │ 状态同步  │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │ HTTPS / WebSocket                         │
└─────────────────────┼───────────────────────────────────────────┘
                      │
┌─────────────────────┼───────────────────────────────────────────┐
│                     │        代理商本地网络                      │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │              VBox Agent Terminal                          │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │  │
│  │  │ 通讯模块  │ │ 资源生成  │ │ 自动化   │ │ 本地存储  │   │  │
│  │  │ (HTTP+WS)│ │ (支付码)  │ │ (预留)   │ │ (SQLite)  │   │  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘   │  │
│  │       │             │           │             │         │  │
│  │  ┌────▼─────────────▼───────────▼─────────────▼─────┐   │  │
│  │  │              第三方平台适配层                      │   │  │
│  │  │    JD Adapter  ·  TB Adapter  ·  DY Adapter      │   │  │
│  │  └──────────────────────┬───────────────────────────┘   │  │
│  └─────────────────────────┼───────────────────────────────┘  │
│                            │                                   │
│  ┌─────────────────────────▼───────────────────────────────┐  │
│  │              第三方平台（JD/TB/DY/PDD...）               │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 通讯方式

采用 **双通道通讯** 策略：

| 通道 | 协议 | 用途 | 方向 |
|------|------|------|------|
| **控制通道** | HTTPS REST API | 身份认证、资源上传、状态上报 | 终端 → 平台 |
| **指令通道** | WebSocket | 实时指令下发（交付指令、心跳、配置更新） | 平台 → 终端 |

**选择 WebSocket 的理由：**
- 平台需要实时向终端下发交付指令（API支付商下单后，需要立即通知代理商）
- 长连接减少握手开销，适合高频交互
- 支持双向推送，无需轮询

---

## 三、API 设计（终端 ↔ 平台）

### 3.1 身份认证

终端需要注册并绑定到对应的代理商账户。

**终端注册 / 绑定：**

```
POST /api/v1/terminal/bind

Request:
{
  "agent_id": "agent_001",          // 代理商ID（从平台后台获取）
  "terminal_id": "TERM-XXXX-001",   // 终端唯一标识（硬件/软件生成）
  "machine_code": "ABC123...",      // 机器码
  "version": "1.0.0"                // 终端版本
}

Headers:
  Authorization: Bearer {agent_api_token}

Response:
{
  "code": 0,
  "data": {
    "terminal_token": "tkn_xxxx...",  // 终端专属令牌（后续通讯使用）
    "expires_at": "2025-06-08T12:00:00Z",
    "ws_endpoint": "wss://api.vbox.com/ws/terminal"
  },
  "msg": "绑定成功"
}
```

**心跳保活：**

```
POST /api/v1/terminal/heartbeat

Request:
{
  "terminal_id": "TERM-XXXX-001",
  "status": "online",           // online / busy / offline
  "load": 0.3,                  // 当前负载（0~1）
  "timestamp": 1704067200
}

Response:
{
  "code": 0,
  "data": {
    "server_time": 1704067205,
    "pending_commands": 0        // 待处理指令数
  }
}
```

### 3.2 支付资源上传

代理商在本地生成支付二维码/链接后，上传到平台。

**上传支付资源：**

```
POST /api/v1/terminal/resources/upload

Request:
{
  "terminal_id": "TERM-XXXX-001",
  "resources": [
    {
      "resource_id": "RES-20250607-001",     // 终端侧唯一ID（去重用）
      "type": "qrcode",                       // qrcode / paylink / card_key
      "product_id": "jd_e100",                // 关联货品ID
      "face_value": 100,                      // 面值（积分）
      "content": {                            // 支付资源内容
        "qrcode_base64": "data:image/png;base64,...",
        "pay_url": "https://...",
        "expire_at": "2025-06-07T12:30:00Z"
      },
      "platform_info": {                      // 第三方平台信息
        "platform": "jd",                     // 来源平台
        "account": "agent_a_jd_account",
        "order_id": "JD202506070001"
      },
      "generated_at": "2025-06-07T12:00:00Z"
    },
    {
      "resource_id": "RES-20250607-002",
      "type": "paylink",
      "product_id": "game_50",
      "face_value": 50,
      "content": {
        "pay_url": "https://...",
        "expire_at": "2025-06-07T13:00:00Z"
      },
      "platform_info": {
        "platform": "tb",
        "account": "agent_a_tb_account"
      },
      "generated_at": "2025-06-07T12:01:00Z"
    }
  ]
}

Response:
{
  "code": 0,
  "data": {
    "accepted": 2,              // 成功接收数
    "rejected": 0,              // 拒绝数
    "reject_reasons": [],
    "platform_resource_ids": [  // 平台侧资源ID
      "PRES-202506070001",
      "PRES-202506070002"
    ]
  }
}
```

**资源状态更新：**

```
POST /api/v1/terminal/resources/status

Request:
{
  "terminal_id": "TERM-XXXX-001",
  "updates": [
    {
      "resource_id": "RES-20250607-001",
      "status": "expired",      // available / used / expired / invalid
      "reason": "支付链接已过期",
      "checked_at": "2025-06-07T12:35:00Z"
    }
  ]
}
```

### 3.3 实时指令下发（WebSocket）

建立 WebSocket 连接后，平台可向终端推送以下指令：

```json
// 1. 交付指令 — 有API支付商下单了
{
  "type": "delivery_order",
  "data": {
    "command_id": "CMD-20250607-001",
    "order_id": "PO202506070001",
    "product_id": "jd_e100",
    "quantity": 1,
    "face_value": 100,
    "expire_at": "2025-06-07T12:30:00Z",
    "callback": {
      "type": "delivery_result",
      "require_confirm": true
    }
  },
  "timestamp": 1704067200
}

// 2. 终端需回复交付结果
{
  "type": "delivery_result",
  "data": {
    "command_id": "CMD-20250607-001",
    "order_id": "PO202506070001",
    "success": true,
    "deliveries": [
      {
        "type": "card_key",
        "content": "JD-XXXX-YYYY-ZZZZ",
        "delivered_at": "2025-06-07T12:00:05Z"
      }
    ]
  }
}

// 3. 配置更新
{
  "type": "config_update",
  "data": {
    "configs": {
      "heartbeat_interval": 30,
      "auto_upload": true,
      "captcha_provider": "local"
    }
  }
}

// 4. 远程操作指令（预留）
{
  "type": "remote_command",
  "data": {
    "command": "capture_packet",
    "params": {
      "platform": "jd",
      "target_url": "https://pay.jd.com/...",
      "duration_seconds": 60
    }
  }
}
```

---

## 四、终端数据模型（本地存储）

终端本地使用 SQLite 存储以下数据：

```sql
-- 终端自身信息
CREATE TABLE terminal_info (
    terminal_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    machine_code TEXT,
    version TEXT,
    token TEXT,
    bound_at DATETIME
);

-- 支付资源
CREATE TABLE payment_resources (
    resource_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,           -- qrcode / paylink / card_key
    product_id TEXT NOT NULL,
    face_value INTEGER,
    content TEXT,                 -- JSON
    platform TEXT,
    platform_account TEXT,
    platform_order_id TEXT,
    status TEXT DEFAULT 'available',  -- available / uploaded / used / expired
    uploaded INTEGER DEFAULT 0,       -- 是否已上传到平台
    platform_resource_id TEXT,        -- 平台返回的ID
    generated_at DATETIME,
    uploaded_at DATETIME,
    expired_at DATETIME
);

-- 指令记录
CREATE TABLE command_log (
    command_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    content TEXT,                  -- JSON
    status TEXT DEFAULT 'pending', -- pending / processing / done / failed
    received_at DATETIME,
    completed_at DATETIME,
    result TEXT                    -- JSON
);

-- 日志
CREATE TABLE operation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT DEFAULT 'info',     -- info / warn / error
    module TEXT,                   -- auth / upload / delivery / captcha
    message TEXT,
    detail TEXT,                   -- JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 五、通讯安全

### 5.1 认证机制

```
终端注册时：agent_id + agent_api_token → 获取 terminal_token
每次请求：Authorization: Bearer {terminal_token}
Token 过期：需重新认证
```

### 5.2 传输加密

| 层面 | 方案 |
|------|------|
| 传输层 | TLS 1.3（HTTPS / WSS） |
| 应用层 | 敏感字段（Cookie/Token）AES-256 加密后传输 |
| 签名 | 每次请求携带 HMAC-SHA256 签名，防重放 |

### 5.3 终端标识

每个终端有唯一的 `terminal_id` + `machine_code` 双重绑定，防止令牌泄露后被滥用。

---

## 六、与平台现有功能的对接关系

```
平台代理商后台               终端工具
  │                          │
  │  生成 API Token          │
  │─────────────────────────▶│  终端绑定
  │                          │
  │  ┌─ 授权货品列表 ──┐     │
  │  │ 京东卡100元      │     │  根据授权货品
  │  │ 游戏点卡50元     │◀────│  生成对应支付资源
  │  └─────────────────┘     │
  │                          │
  │  ┌─ 待交付订单 ────┐     │
  │  │ PO202506070001  │────▶│  WebSocket 实时推送
  │  │ 京东卡×1        │     │  终端自动交付或人工处理
  │  └─────────────────┘     │
  │                          │
  │  资源池状态同步           │
  │◀─────────────────────────│  上传支付资源
  │                          │
```

---

## 七、后续细化方向（预留功能说明）

| 功能模块 | 计划内容 | 优先级 |
|---------|---------|--------|
| **抓包模块** | 基于 mitmproxy 或 Scapy 实现第三方平台支付请求的拦截和解析 | P1 |
| **验证码识别** | 集成 OCR（PaddleOCR/Tesseract）+ 深度学习模型（YOLO/CNN）识别图形验证码 | P1 |
| **文字点选** | 模拟点击验证码中的指定文字，基于目标检测 | P1 |
| **滑块验证** | 模拟滑块的轨迹生成和验证逻辑 | P2 |
| **自动登录** | Cookie 持久化、Session 保持、自动续期 | P1 |
| **GUI界面** | PyQt6 / Tauri 桌面应用，包含终端状态显示、日志、手动操作界面 | P2 |
| **多账号管理** | 同时管理多个第三方平台账号 | P2 |
| **插件系统** | 每个第三方平台作为独立的适配器插件热加载 | P3 |
