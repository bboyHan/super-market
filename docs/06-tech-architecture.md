# VBox B2B2B — 技术选型与架构设计

> 本文档基于 VBox B2B2B 的产品设计，完成技术选型、系统架构、模块划分和关键设计决策。后端以 Python 为主，前端和其他组件根据需求选择。

---

## 一、技术选型总览

### 1.1 选型矩阵

| 层面 | 选型 | 版本 | 理由 |
|------|------|------|------|
| **后端框架** | FastAPI | ≥0.115 | 异步原生、高性能、自动 OpenAPI 文档、内置 WebSocket、Pydantic 验证 |
| **ORM** | SQLAlchemy 2.0 | ≥2.0 | 最成熟的 Python ORM、异步支持、灵活的查询构建 |
| **数据验证** | Pydantic v2 | ≥2.5 | FastAPI 原生集成、极致性能（Rust 核心）、复杂校验 |
| **数据库** | PostgreSQL 16 | 16.x | JSONB、窗口函数、分区表、BRIN 索引、高并发 |
| **缓存 / 实时** | Redis 7 | ≥7.0 | Stream（消息队列）、Pub/Sub（WebSocket 桥接）、Sorted Set（排行/路由） |
| **任务队列** | Arq | ≥0.26 | 异步原生、Redis 驱动、轻量、比 Celery 更适合异步项目 |
| **消息队列** | Redis Streams / Kafka | — | Phase 1 用 Streams，量级提升后迁 Kafka |
| **异步 HTTP** | httpx | ≥0.27 | 异步 HTTP 客户端，用于平台适配器外部调用 |
| **测试** | pytest + httpx + pytest-asyncio | — | 行业标准 |
| **API 文档** | 自动（FastAPI + OpenAPI + ReDoc） | — | 零成本生成 |
| **前端** | Vue 3 + Nuxt 3 / React + Next.js | — | 视团队情况选择（本文不深入前端选型） |
| **代理终端** | Python + PyQt6 / Tauri (Rust) | — | 后续细化 |
| **部署** | Docker + Docker Compose → K8s | — | 渐进式 |
| **监控** | Prometheus + Grafana + Loki | — | 指标 + 日志聚合 |

### 1.2 为什么是 FastAPI 而不是 Django

| 维度 | FastAPI | Django | 对本项目的意义 |
|------|---------|--------|--------------|
| 异步原生 | ✅ 全异步 | ⚠️ 同步为核心，异步为补丁 | 高并发订单、WebSocket 推送 |
| 性能 | 高（uvicorn + async） | 中 | 10万+日订单量至关重要 |
| WebSocket | 内置支持 | 需 Channels 扩展 | 代理商终端实时推送 |
| API 文档 | 自动生成（零成本） | DRF + drf-spectacular | 面向 API 支付商的文档至关重要 |
| 项目体积 | 轻量，按需扩展 | 大而全 | 团队可更灵活地掌控代码 |
| ORM | 自由选择 | 内置 ORM（绑定较紧） | 我们需要 SQLAlchemy 2.0 的能力 |
| 社区/生态 | 快速发展 | 极其成熟 | 两者都够用 |

> **结论**：FastAPI 更适合本项目的 API-first、高并发、实时推送的特性。Django 的优势（admin、生态）可以用 FastAPI + 自定义后台弥补。

---

## 二、系统架构

### 2.1 整体架构

```
                      ┌─────────────────────┐
                      │   负载均衡 (Nginx)   │
                      │  TLS Termination    │
                      │  Rate Limiting      │
                      └─────────┬───────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   Merchant API  │   │   Admin API     │   │   Agent WS      │
│  (FastAPI App)  │   │  (FastAPI App)  │   │  (FastAPI App)  │
│                 │   │                 │   │                 │
│  /api/v1/*      │   │  /admin/*       │   │  /ws/terminal/* │
│  供应商后台API  │   │  平台管理员API  │   │  终端WebSocket  │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
          ┌────────────────────▼─────────────────────┐
          │              核心业务层                    │
          │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │
          │  │ 订单引擎  │ │ 路由引擎  │ │ 风控引擎  │ │
          │  │ Order    │ │ Router   │ │ Risk     │ │
          │  └──────────┘ └──────────┘ └──────────┘ │
          │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │
          │  │ 积分引擎  │ │ 通知引擎  │ │ 调度引擎  │ │
          │  │ Wallet   │ │ Notify   │ │ Schedule │ │
          │  └──────────┘ └──────────┘ └──────────┘ │
          └──────────────────┬───────────────────────┘
                             │
          ┌──────────────────┴───────────────────────┐
          │              数据层                        │
          │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │
          │  │PostgreSQL│ │  Redis   │ │   Arq    │ │
          │  │ (主数据)  │ │ (缓存/   │ │ (任务    │ │
          │  │          │ │  消息)   │ │  队列)   │ │
          │  └──────────┘ └──────────┘ └──────────┘ │
          └─────────────────────────────────────────┘
```

### 2.2 应用内分层（六边形架构）

```
┌───────────────────────────────────────────────────────────────┐
│                     Interface Layer (接口层)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ REST 路由   │  │ WebSocket   │  │ 请求/响应    │          │
│  │ (APIRouter) │  │ (WS Handler)│  │ DTO        │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
├───────────────────────────────────────────────────────────────┤
│                   Application Layer (应用层)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ Use Cases   │  │ 命令/查询   │  │ 事件发布    │          │
│  │ (Service)   │  │ (CQRS)      │  │ (Event Pub) │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
├───────────────────────────────────────────────────────────────┤
│                    Domain Layer (领域层)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 聚合根/实体  │  │ 值对象      │  │ 领域事件    │          │
│  │ (Aggregate)  │  │ (Value Obj) │  │ (Domain    │          │
│  │              │  │             │  │  Events)   │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 仓储接口     │  │ 领域服务    │  │ 规格模式    │          │
│  │ (Repository) │  │ (Service)   │  │ (Spec)     │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
├───────────────────────────────────────────────────────────────┤
│                Infrastructure Layer (基础设施层)               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ PG Repo    │  │ Redis Cache │  │ Arq Worker  │          │
│  │ 实现        │  │ 实现        │  │ 实现        │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 平台适配器   │  │ 第三方 HTTP │  │ 事件总线    │          │
│  │ (Adapter)   │  │ 客户端      │  │ (Event Bus) │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└───────────────────────────────────────────────────────────────┘
```

---

## 三、详细技术选型分析

### 3.1 后端框架对比

| 特性 | FastAPI | Django + DRF | Litestar | Flask + extensions |
|------|---------|-------------|----------|-------------------|
| 异步原生 | ✅ | ⚠️ 需额外配置 | ✅ | ❌ 需插件 |
| 自动API文档 | ✅ OpenAPI | ⚠️ 需扩展 | ✅ OpenAPI | ❌ 需Flask-RESTX |
| WebSocket | ✅ 内置 | ⚠️ Channels | ✅ 内置 | ❌ 需Flask-SocketIO |
| Pydantic集成 | ✅ 原生 | ❌ 需drf-spectacular | ✅ 原生 | ❌ |
| 性能 (req/s) | ~28,000 | ~12,000 | ~26,000 | ~10,000 |
| 生态成熟度 | 高 | 极高 | 低 | 极高 |
| 学习成本 | 低 | 中 | 中 | 低 |

**选择 FastAPI + SQLAlchemy 2.0 组合。** FastAPI 处理 API 层，SQLAlchemy 2.0 提供成熟的 ORM 能力和异步查询。

### 3.2 数据库选型

PostgreSQL 16 对比其他：

| 特性 | PostgreSQL 16 | MySQL 8 | 说明 |
|------|-------------|---------|------|
| JSONB | ✅ 强 | ⚠️ JSON 较弱 | 订单的额外信息、平台适配器配置等需要灵活存储 |
| 窗口函数 | ✅ 完善 | ✅ 基本 | 日结统计、排行榜等需要 |
| 分区表 | ✅ 原生 | ✅ 原生 | 订单表按天分区（高频交易场景关键） |
| BRIN 索引 | ✅ | ❌ | 时序数据（订单按时间查询）的索引优化 |
| 并发写入 | ✅ MVCC 优秀 | ⚠️ 有锁问题 | 10万+日订单需要高并发写入 |
| 连接池 | ✅ PgBouncer | ✅ ProxySQL | 都需要连接池代理 |

> 选择 PostgreSQL 的核心原因：JSONB + 窗口函数 + 分区表 + BRIN 索引，这四点对这个积分类交易平台的灵活数据存储和统计查询至关重要。

### 3.3 缓存与消息选型

```
Redis 7 在本项目的多角色：

┌─────────────────────────────────────────────────────────┐
│                     Redis 7                               │
│                                                          │
│  String/Hash ──→ 缓存：产品信息、用户会话、配置缓存       │
│                                                          │
│  Sorted Set ──→ 路由引擎：代理商权重轮询排序            │
│                                                          │
│  Stream ──────→ 消息队列：订单创建事件、回调事件          │
│                                                          │
│  Pub/Sub ─────→ 实时推送：WebSocket 跨进程广播           │
│                                                          │
│  HyperLogLog ─→ UV 统计：每日独立 API 支付商访问量        │
│                                                          │
│  Bitmap ──────→ 日活统计：代理商/API支付商每日在线状态    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 3.4 任务队列选型

| 特性 | Arq | Celery | Dramatiq |
|------|-----|--------|----------|
| 异步原生 | ✅ | ⚠️ 需额外配置 | ⚠️ 部分异步 |
| Redis 驱动 | ✅ 原生 | ✅ | ✅ |
| 重试机制 | ✅ 内置 | ✅ 内置 | ✅ 内置 |
| 定时任务 | ✅ 内置 | ✅ Beat | ❌ 需扩展 |
| 任务依赖 | ⚠️ 有限 | ✅ Canvas | ⚠️ 有限 |
| 监控 | ⚠️ 基础 | ✅ Flower | ✅ 内置 |
| 配置复杂度 | 低 | 高 | 中 |

> Phase 1 选择 **Arq**，轻量、异步原生、与 FastAPI 生态匹配。如果需要更复杂的任务 DAG 或更完善的监控，后续可以迁移到 Celery。

### 3.5 ORM 选型

| 特性 | SQLAlchemy 2.0 | Tortoise-ORM | Gino | SQLModel |
|------|---------------|-------------|------|----------|
| 异步原生 | ✅ 2.0 | ✅ | ✅ | ⚠️ 依赖SQLAlchemy |
| 成熟度 | 极高 | 中 | 低 | 中 |
| 复杂查询 | ✅ 极强 | ⚠️ 有限 | ⚠️ 有限 | ⚠️ 有限 |
| 迁移工具 | ✅ Alembic | ✅ Aerich | ❌ | ⚠️ 需Alembic |
| Pydantic结合 | ✅ 可手动 | ❌ | ❌ | ✅ 原生 |
| 学习曲线 | 高 | 低 | 低 | 中 |

> 选择 **SQLAlchemy 2.0 + Alembic**。它的复杂查询能力（窗口函数、CTE、子查询）对这个平台的统计报表功能至关重要。SQLModel 虽然与 FastAPI 结合更自然，但在复杂查询场景下受限。

---

## 四、项目目录结构

```
vbox-server/
├── app/
│   ├── __init__.py
│   │
│   ├── main.py                    # FastAPI 应用入口
│   ├── config.py                  # 配置管理（Pydantic Settings）
│   ├── container.py               # DI 容器（依赖注入）
│   │
│   ├── interfaces/                # 接口层
│   │   ├── api/                   # REST API
│   │   │   ├── __init__.py
│   │   │   ├── merchant/          # 商户/供应商 API
│   │   │   │   ├── router.py
│   │   │   │   ├── order.py       # 订单接口
│   │   │   │   ├── wallet.py      # 钱包接口
│   │   │   │   ├── product.py     # 货品接口
│   │   │   │   └── agent.py       # 代理商接口
│   │   │   ├── admin/             # 平台管理 API
│   │   │   │   ├── router.py
│   │   │   │   ├── supplier.py
│   │   │   │   ├── product_manage.py
│   │   │   │   └── system.py
│   │   │   ├── open/              # 开放 API（面向 API 支付商）
│   │   │   │   ├── router.py
│   │   │   │   ├── order.py
│   │   │   │   └── auth.py
│   │   │   └── terminal/          # 代理商终端 API
│   │   │       ├── router.py
│   │   │       └── resource.py
│   │   │
│   │   ├── ws/                    # WebSocket
│   │   │   ├── terminal.py        # 终端连接管理
│   │   │   └── notification.py    # 实时通知
│   │   │
│   │   └── dto/                   # 数据传输对象
│   │       ├── order_dto.py
│   │       ├── wallet_dto.py
│   │       └── product_dto.py
│   │
│   ├── application/               # 应用层（用例）
│   │   ├── order/
│   │   │   ├── create_order.py        # 创建订单用例
│   │   │   ├── confirm_payment.py     # 确认支付用例
│   │   │   ├── query_order.py         # 查询订单用例
│   │   │   └── callback_order.py      # 回调处理用例
│   │   ├── wallet/
│   │   │   ├── recharge.py            # 充值用例
│   │   │   ├── transfer.py            # 划转用例
│   │   │   └── settle.py              # 结算用例
│   │   ├── product/
│   │   │   ├── authorize_supplier.py  # 授权供应商用例
│   │   │   └── authorize_agent.py     # 授权代理商用例
│   │   └── terminal/
│   │       ├── bind_terminal.py       # 终端绑定用例
│   │       └── upload_resource.py     # 上传支付资源用例
│   │
│   ├── domain/                    # 领域层
│   │   ├── order/                 # 订单域
│   │   │   ├── entity.py          # Order 聚合根
│   │   │   ├── value_object.py    # OrderStatus, Money, etc.
│   │   │   ├── event.py           # OrderCreated, OrderPaid
│   │   │   ├── repository.py      # OrderRepository 接口
│   │   │   └── service.py         # OrderDomainService
│   │   ├── wallet/                # 钱包域
│   │   │   ├── entity.py          # Wallet, Transaction
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   ├── product/               # 货品域
│   │   │   ├── entity.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   ├── agent/                 # 代理商域
│   │   │   ├── entity.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   └── routing/               # 路由域
│   │       ├── entity.py          # RoutingRule
│   │       ├── service.py         # RoutingEngine
│   │       └── strategy.py        # RoundRobin, Priority, Weighted
│   │
│   ├── infrastructure/            # 基础设施层
│   │   ├── persistence/           # 持久化实现
│   │   │   ├── postgres/
│   │   │   │   ├── order_repo.py
│   │   │   │   ├── wallet_repo.py
│   │   │   │   └── ...
│   │   │   └── migrations/        # Alembic 迁移
│   │   │       ├── versions/
│   │   │       └── env.py
│   │   ├── cache/                 # 缓存实现
│   │   │   ├── redis_cache.py
│   │   │   └── redis_stream.py
│   │   ├── queue/                 # 消息队列
│   │   │   ├── event_bus.py
│   │   │   └── arq_worker.py
│   │   ├── adapters/              # 平台适配器
│   │   │   ├── base.py            # 适配器基类/SPI
│   │   │   ├── registry.py        # 适配器注册中心
│   │   │   ├── jd/
│   │   │   │   └── adapter.py
│   │   │   ├── tb/
│   │   │   │   └── adapter.py
│   │   │   └── dy/
│   │   │       └── adapter.py
│   │   └── auth/                  # 认证实现
│   │       ├── signature.py       # 签名验证
│   │       └── jwt_handler.py
│   │
│   ├── shared/                    # 共享模块
│   │   ├── exceptions/            # 统一异常
│   │   │   ├── error_code.py      # 错误码定义
│   │   │   └── handlers.py
│   │   ├── utils/
│   │   │   ├── money.py           # 金额/积分计算
│   │   │   ├── id_generator.py    # 分布式ID
│   │   │   └── pagination.py
│   │   └── constants.py
│   │
│   └── worker/                    # 后台工作者
│       ├── order_worker.py        # 订单处理
│       ├── callback_worker.py     # 回调重试
│       ├── stats_worker.py        # 统计聚合
│       └── settlement_worker.py   # 结算处理
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── deploy/
│   ├── Dockerfile
│   ├── docker-compose.yaml
│   └── k8s/
│
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 五、关键设计决策

### 5.1 订单号生成

```python
# 雪花算法变体 — 42位时间戳 + 10位worker + 12位序列号
# 趋势递增，适合数据库索引

class SnowflakeID:
    def __init__(self, worker_id: int = 1):
        self.worker_id = worker_id
        self.epoch = 1704067200000  # 2025-01-01 00:00:00 UTC
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = asyncio.Lock()

    async def generate(self) -> int:
        async with self.lock:
            timestamp = int(time.time() * 1000) - self.epoch
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & 0xFFF
            else:
                self.sequence = 0
            self.last_timestamp = timestamp
            return (timestamp << 22) | (self.worker_id << 12) | self.sequence
```

### 5.2 订单表分区设计

```sql
-- 按天分区，支持自动创建新分区
CREATE TABLE vbox_orders (
    id BIGINT NOT NULL,
    order_no VARCHAR(64) NOT NULL,
    merchant_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    amount INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- ... 其他字段
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- 每月一个分区
CREATE TABLE vbox_orders_202506 PARTITION OF vbox_orders
    FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');

CREATE TABLE vbox_orders_202507 PARTITION OF vbox_orders
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');

-- 复合索引
CREATE INDEX idx_orders_merchant_status ON vbox_orders(merchant_id, status, created_at DESC);
CREATE INDEX idx_orders_channel_status ON vbox_orders(channel_code, status, created_at DESC);
CREATE INDEX idx_orders_created_at ON vbox_orders(created_at DESC);
```

### 5.3 日结统计方案

```
┌────────────────────────────────────────────────────────────┐
│  日结统计 — 三级缓存架构                                    │
│                                                            │
│  实时：Redis 计数（今日数据，毫秒级更新）                   │
│    │                                                       │
│  定时落盘：每 5 分钟 → 写 PostgreSQL 明细表               │
│    │                                                       │
│  聚合层：每小时 → 预聚合统计表（供快速查询）               │
│                                                            │
│  查询路径：                                                │
│  ┌────────┐     ┌────────┐     ┌────────┐                 │
│  │ "今日" │────▶│ Redis  │     │ 毫秒级  │                 │
│  │ "昨日" │────▶│ 预聚合  │────▶│ 秒级   │                 │
│  │ "前日" │────▶│  表    │     │ 秒级   │                 │
│  └────────┘     └────────┘     └────────┘                 │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 5.4 路由引擎设计

```python
# 策略模式实现三种分配规则
from abc import ABC, abstractmethod

class RoutingStrategy(ABC):
    """路由策略接口"""
    
    @abstractmethod
    async def select_agent(
        self, 
        product_id: int, 
        candidates: list[AgentInventory],
        context: RoutingContext
    ) -> AgentInventory:
        ...

class RoundRobinStrategy(RoutingStrategy):
    """轮询策略 — 基于 Redis Sorted Set 实现"""
    async def select_agent(self, product_id, candidates, context):
        key = f"routing:rr:{product_id}"
        # 取分数最小的（最久未分配）
        agent = await redis.zpopmin(key)
        # 重新插入（分数=当前时间戳）
        await redis.zadd(key, {agent.id: time.time()})
        return agent

class PriorityStrategy(RoutingStrategy):
    """优先策略 — 按优先级顺序分配"""
    async def select_agent(self, product_id, candidates, context):
        # 按 supplier 设置的优先级排序
        candidates.sort(key=lambda a: a.priority_score)
        # 选择优先级最高且有库存的
        for agent in candidates:
            if agent.available_count > 0:
                return agent
        raise InsufficientInventoryError()

class WeightedStrategy(RoutingStrategy):
    """权重策略 — 按比例分配"""
    async def select_agent(self, product_id, candidates, context):
        key = f"routing:w:{product_id}:counter"
        total = sum(a.weight for a in candidates)
        # 统计当前各代理商已分配数
        counts = await redis.hgetall(key)
        # 选择实际分配比例最低的
        scores = []
        for agent in candidates:
            assigned = int(counts.get(str(agent.id), 0))
            expected_ratio = agent.weight / total
            actual_ratio = assigned / max(sum(counts.values()), 1)
            scores.append((actual_ratio - expected_ratio, agent))
        scores.sort(key=lambda x: x[0])
        selected = scores[0][1]
        await redis.hincrby(key, str(selected.id), 1)
        return selected
```

### 5.5 WebSocket 连接管理

```python
# WebSocket 连接管理器（跨进程通过 Redis Pub/Sub 广播）
class ConnectionManager:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.local_connections: dict[str, WebSocket] = {}
    
    async def connect(self, terminal_id: str, ws: WebSocket):
        self.local_connections[terminal_id] = ws
        # 订阅该终端的专属频道
        await self.redis.subscribe(f"ws:terminal:{terminal_id}")
    
    async def send_to_terminal(self, terminal_id: str, message: dict):
        # 先查本地连接
        if terminal_id in self.local_connections:
            await self.local_connections[terminal_id].send_json(message)
            return
        # 不在本地 → 发布到 Redis，由其他进程实例投递
        await self.redis.publish(f"ws:terminal:{terminal_id}", json.dumps(message))
    
    async def broadcast(self, message: dict):
        """广播给所有在线终端（如配置更新）"""
        await self.redis.publish("ws:terminal:broadcast", json.dumps(message))
```

---

## 六、可参考的开源项目

### 6.1 架构参考

| 项目 | 语言 | 参考价值 |
|------|------|---------|
| **Saleor** | Python/Django | 电商核心的订单管理、多租户设计模式 |
| **FastAPI** 官方示例 | Python | 六边形架构的 FastAPI 实现方式 |
| **LemonSqueezy** | Laravel | 数字商品分销平台的业务模型（收费参考） |
| **Gunroad** | Ruby | 数字商品销售平台（产品模式参考） |

### 6.2 直接可用的库

| 库 | 用途 | 集成方式 |
|----|------|---------|
| **Pydantic v2** | 数据验证 + Settings 管理 | 直接引入 |
| **SQLAlchemy 2.0** | ORM + 查询构建 | 直接引入 |
| **Alembic** | 数据库迁移 | 直接引入 |
| **Arq** | 异步任务队列 | 直接引入 |
| **httpx** | 异步 HTTP 客户端（平台适配器） | 直接引入 |
| **redis-py** | Redis 客户端 | 直接引入 |
| **python-jose** | JWT 处理 | 直接引入 |
| **prometheus-client** | 指标暴露 | FastAPI middleware |
| **loguru** | 结构化日志 | 替代标准 logging |

---

## 七、部署方案

### 7.1 Phase 1：单体 + Docker Compose

```
docker-compose.yaml
├── api           # FastAPI 应用 (uvicorn)
│   ├── port: 8000
│   └── replicas: 2
├── worker        # Arq Worker (后台任务)
│   └── replicas: 2
├── postgres      # PostgreSQL 16
├── redis         # Redis 7
├── nginx         # 反向代理 + TLS
└── grafana + prometheus + loki  # 监控栈
```

### 7.2 Phase 2：Kubernetes

当需要水平扩展时迁移到 K8s，使用 Helm chart 管理。

### 7.3 CI/CD

```
GitHub Actions:
  ├── lint + test (pytest)     ← PR 触发
  ├── build + push image       ← merge 到 main 触发
  └── deploy to staging/prod   ← tag 触发
```

---

## 八、关键性能指标目标

| 指标 | 目标 | 验证方式 |
|------|------|---------|
| 订单创建 QPS | > 500/s（单实例） | locust 压测 |
| 订单查询 QPS | > 2000/s（缓存命中率 > 90%） | locust + 监控 |
| WebSocket 连接数 | > 5000 并发终端 | 长连接压测 |
| 日结统计查询 | < 200ms | 预聚合表 + 索引优化 |
| API 响应时间 P99 | < 300ms | Prometheus 监控 |
| 订单写入 TPS | > 1000/s | 批量写入 + 分区表 |
| 数据库可用性 | 99.95% | PgBouncer + 流复制 |
