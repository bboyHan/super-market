"""统一凭证数据模型 — 支付采集器的核心类型定义。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class CredentialType(str, Enum):
    """凭证类型枚举"""
    PAYMENT_URL = "payment_url"          # 支付链接 (https://wx.tenpay.com/...)
    PAYMENT_PARAMS = "payment_params"    # 结构化支付参数 (WeChatJSBridge 参数)
    ACCESS_TOKEN = "access_token"        # API 访问令牌 (pay_openid + pay_openkey)
    QR_IMAGE = "qr_image"               # 支付二维码 base64
    CARD_KEY = "card_key"               # 卡密 (JD-XXXX-XXXX)
    ORDER_ID = "order_id"               # 订单号
    RAW_DATA = "raw_data"               # 原始数据（未识别的待处理）


class CredentialStatus(str, Enum):
    """凭证生命周期状态"""
    COLLECTED = "collected"     # 已采集（本地存储）
    PENDING = "pending"         # 待处理
    VALIDATED = "validated"     # 已验证通过
    DUPLICATED = "duplicated"   # 重复（已存在）
    REJECTED = "rejected"       # 验证未通过
    UPLOADED = "uploaded"       # 已上传到平台
    CONSUMED = "consumed"       # 已被订单消耗


class PipelineType(str, Enum):
    """采集管道类型"""
    BROWSER = "browser"    # 内置浏览器采集
    PROXY = "proxy"        # mitmproxy 代理采集（PC端游/手机端）
    MANUAL = "manual"      # 手动输入


@dataclass
class Credential:
    """统一凭证结构 — 所有采集管道输出的标准格式。"""

    # 核心字段
    id: str = field(default_factory=lambda: f"cred_{uuid.uuid4().hex[:16]}")
    type: CredentialType = CredentialType.RAW_DATA
    value: str = ""                    # 凭证值（URL / Token / base64 / 卡密）
    platform: str = ""                 # 平台标识（qq_midas / wechat / alipay）
    product_id: str = ""               # 平台货品 ID

    # 来源信息
    source_pipeline: str = ""          # 来源管道名称
    account_id: Optional[int] = None   # 采集所用账号 ID
    account_name: str = ""             # 账号显示名称

    # 元数据
    raw_data: dict = field(default_factory=dict)  # 原始采集数据
    metadata: dict = field(default_factory=dict)   # 扩展元数据
    status: CredentialStatus = CredentialStatus.COLLECTED

    # 时间戳
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None

    def to_dict(self) -> dict:
        """转为字典（用于序列化到 SQLite / JSON）。"""
        return {
            "id": self.id,
            "type": self.type.value,
            "value": self.value,
            "platform": self.platform,
            "product_id": self.product_id,
            "source_pipeline": self.source_pipeline,
            "account_id": self.account_id,
            "account_name": self.account_name,
            "raw_data": self.raw_data,
            "metadata": self.metadata,
            "status": self.status.value,
            "captured_at": self.captured_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Credential:
        """从字典反序列化。"""
        return cls(
            id=data.get("id", f"cred_{uuid.uuid4().hex[:16]}"),
            type=CredentialType(data.get("type", "raw_data")),
            value=data.get("value", ""),
            platform=data.get("platform", ""),
            product_id=str(data.get("product_id", "")),
            source_pipeline=data.get("source_pipeline", ""),
            account_id=data.get("account_id"),
            account_name=data.get("account_name", ""),
            raw_data=data.get("raw_data", {}),
            metadata=data.get("metadata", {}),
            status=CredentialStatus(data.get("status", "collected")),
            captured_at=data.get("captured_at", datetime.now(timezone.utc).isoformat()),
            expires_at=data.get("expires_at"),
        )

    @property
    def is_expired(self) -> bool:
        """检查凭证是否已过期。"""
        if not self.expires_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return exp < datetime.now(timezone.utc)
        except (ValueError, TypeError):
            return False

    @property
    def short_id(self) -> str:
        """短 ID（用于显示）。"""
        return self.id[-12:]
