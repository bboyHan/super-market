"""平台适配器 — 识别各支付平台的凭证格式。

每个适配器负责：
  1. match(raw_data) → 判断原始数据是否属于本平台
  2. extract(raw_data) → 提取结构化凭证
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BasePlatformAdapter(ABC):
    """支付平台适配器基类。"""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台显示名称（如 QQ Midas / 微信支付 / 支付宝）。"""
        ...

    @abstractmethod
    def match(self, raw_data: dict) -> bool:
        """判断原始数据是否属于本平台。"""
        ...

    @abstractmethod
    def extract(self, raw_data: dict) -> Optional[dict]:
        """从原始数据中提取凭证。

        返回:
          {
            "type": "payment_url" | "payment_params" | "access_token" | ...,
            "value": str,
            "product_id": str (可选),
            "metadata": dict (可选),
          }
          或 None（无法识别）
        """
        ...

    def validate(self, credential: dict) -> bool:
        """验证凭证是否有效（可选覆盖）。"""
        return True


# 全局适配器注册表
_registry: dict[str, BasePlatformAdapter] = {}


def register(adapter: BasePlatformAdapter):
    """注册适配器。"""
    _registry[adapter.platform_name] = adapter


def get_all() -> list[BasePlatformAdapter]:
    """获取所有已注册的适配器。"""
    return list(_registry.values())


def get(name: str) -> Optional[BasePlatformAdapter]:
    """按名称获取适配器。"""
    return _registry.get(name)


def match_any(raw_data: dict) -> tuple[Optional[BasePlatformAdapter], Optional[dict]]:
    """遍历所有适配器，返回第一个匹配的 (adapter, result)。"""
    for adapter in get_all():
        if adapter.match(raw_data):
            result = adapter.extract(raw_data)
            if result:
                return adapter, result
    return None, None
