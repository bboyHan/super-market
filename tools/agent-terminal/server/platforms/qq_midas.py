"""QQ Midas 支付平台适配器。

识别腾讯 Midas 支付体系的凭证：
- pay.qq.com 域名的支付链接
- api.unipay.qq.com 的 API 响应（web_save）
- postMessage 中的支付参数 (wechat_wapbuy / wechat_buy)

关键功能：从 web_save 请求中提取 openid，关联到本地 QQ 账号库。
"""

from __future__ import annotations

import json
import re
from typing import Optional

from platforms import BasePlatformAdapter
from storage.db import get_cursor

# Midas 域名特征
MIDAS_DOMAINS = [
    "pay.qq.com",
    "api.unipay.qq.com",
    "qpay.qq.com",
    "graph.qq.com",
]

# 支付 URL 正则
PAY_URL_RE = re.compile(
    r'https?://wx\.tenpay\.com/[^\s"\'<>]+'
    r'|weixin://wxpay/bizpayurl\?[^\s"\'<>]+'
)

# web_save 请求体中的 openid 提取正则
OPENID_RE = re.compile(r'openid=([A-F0-9]+)')

# Midas 货品映射（offer_id → 货品名）
OFFER_PRODUCT_MAP = {
    "1450000186": "Q币",
    "1450000238": "DNF点券",
    "1450015040": "QQ飞车点券",
    "1450026248": "天涯明月刀点券",
    "1450029577": "英雄联盟手游点券",
    "1450030204": "金铲铲之战点券",
}


class QQMidassAdapter(BasePlatformAdapter):
    """QQ Midas 支付平台适配器。"""

    @property
    def platform_name(self) -> str:
        return "QQ Midas"

    def match(self, raw_data: dict) -> bool:
        host = raw_data.get("host", "")
        url = raw_data.get("url", "") or raw_data.get("api_url", "") or raw_data.get("value", "")
        origin = raw_data.get("origin", "")
        source = raw_data.get("source", "")

        # web_save 来源（content.js 捕获）
        if source == 'web_save':
            return True

        # 域名匹配
        if any(d in host for d in MIDAS_DOMAINS):
            return True
        if any(d in url for d in MIDAS_DOMAINS):
            return True
        if any(d in origin for d in MIDAS_DOMAINS):
            return True

        # postMessage 中的 action 匹配
        action = raw_data.get("action", "")
        if action in ("wechat_wapbuy", "wechat_buy", "MidasJSBridge_call"):
            return True

        return False

    def extract(self, raw_data: dict) -> Optional[dict]:
        source = raw_data.get("source", "")

        # ── web_save 源（content.js 捕获：请求体 + 响应体）──
        if source == 'web_save':
            return self._extract_from_web_save(raw_data)

        # ── mitmproxy 响应 → 支付 URL ──
        if "mitmproxy" in source:
            return self._extract_from_mitm(raw_data)

        # ── postMessage → 支付参数 ──
        action = raw_data.get("action", "")
        if action in ("wechat_wapbuy", "wechat_buy", "MidasJSBridge_call"):
            return self._extract_from_postmessage(raw_data)

        # ── API 请求/响应 → 原始数据 ──
        body = raw_data.get("body", "")
        response_body = raw_data.get("response_body", "")
        content = body or response_body

        # 检查 body 中是否包含支付 URL
        if content:
            pay_match = PAY_URL_RE.search(content)
            if pay_match:
                return {
                    "type": "payment_url",
                    "value": pay_match.group(0),
                    "product_id": self._detect_product(raw_data),
                    "metadata": {
                        "source": source,
                        "api_url": raw_data.get("api_url", ""),
                    },
                }

        return None

    def _extract_from_web_save(self, raw_data: dict) -> Optional[dict]:
        """从 web_save 请求-响应配对中提取带账号信息的凭证。

        content.js 发送的数据结构：
        {
            type: 'payment_url',
            value: 'weixin://wxpay/bizpayurl?pr=XXX',
            source: 'web_save',
            openid: 'B7C04C6D...',       ← 来自请求体
            pay_method: 'wechat',
            product_id: '1450049871',
            body: 'openid=...&pay_method=...',  ← 原始请求体
        }
        """
        value = raw_data.get("value", "")
        if not value:
            return None

        openid = raw_data.get("openid", "")
        pay_method = raw_data.get("pay_method", "wechat")
        product_id = raw_data.get("product_id", "")

        # 如果请求体中包含更多参数，尝试从中提取
        req_body = raw_data.get("body", "")
        if not openid and req_body:
            m = OPENID_RE.search(req_body)
            if m:
                openid = m.group(1)

        # 查询本地 QQ 账号库，获取账号昵称
        account_id = None
        account_name = None
        if openid:
            account_id, account_name = self._lookup_account(openid)

        if not account_name:
            account_name = (openid[:16] + "...") if openid else "未知账号"

        metadata = {
            "source": "web_save",
            "pay_method": pay_method,
            "openid": openid or "",
            "account_name": account_name,
        }
        if account_id:
            metadata["account_id"] = account_id

        return {
            "type": "payment_url",
            "value": value,
            "product_id": product_id or self._detect_product(raw_data),
            "account_id": account_id,
            "account_name": account_name,
            "metadata": metadata,
        }

    @staticmethod
    def _lookup_account(openid: str) -> tuple:
        """根据 openid 在本地 QQ 账号库中查询账号信息。

        返回 (account_id, nickname) 或 (None, None)。
        """
        try:
            with get_cursor() as cursor:
                # 优先精确匹配 midas_openid
                row = cursor.execute(
                    "SELECT id, nickname, uin FROM qq_accounts WHERE midas_openid=?",
                    (openid,),
                ).fetchone()
                if row:
                    return (row["id"], row["nickname"] or f"QQ_{row['uin'][:8]}")

                # 尝试匹配 uin（QQ号）
                row = cursor.execute(
                    "SELECT id, nickname FROM qq_accounts WHERE uin=?",
                    (openid,),
                ).fetchone()
                if row:
                    return (row["id"], row["nickname"] or f"QQ_{openid[:8]}")

                # 未找到 → 返回 None，后续会自动用 openid 前缀显示
                return (None, None)
        except Exception:
            return (None, None)

    def _extract_from_mitm(self, raw_data: dict) -> Optional[dict]:
        """从 mitmproxy 捕获中提取凭证。"""
        raw_type = raw_data.get("type", "")

        if raw_type == "payment_url":
            return {
                "type": "payment_url",
                "value": raw_data.get("value", ""),
                "product_id": self._detect_product(raw_data),
                "metadata": {
                    "source": raw_data.get("source", ""),
                    "api_url": raw_data.get("api_url", ""),
                },
            }

        if raw_type == "payment_params":
            return {
                "type": "payment_params",
                "value": raw_data.get("value", ""),
                "product_id": "",
                "metadata": {
                    "source": raw_data.get("source", ""),
                    "api_url": raw_data.get("api_url", ""),
                },
            }

        return None

    def _extract_from_postmessage(self, raw_data: dict) -> Optional[dict]:
        """从 postMessage 中提取支付凭证。"""
        action = raw_data.get("action", "")
        msg_data = raw_data.get("data", {})

        if action == "wechat_wapbuy":
            pay_url = msg_data.get("url", "")
            if pay_url:
                return {
                    "type": "payment_url",
                    "value": pay_url,
                    "product_id": self._detect_product(raw_data),
                    "metadata": {"action": "wechat_wapbuy"},
                }

        if action == "wechat_buy":
            info = msg_data.get("info", {})
            return {
                "type": "payment_params",
                "value": json.dumps(info, ensure_ascii=False),
                "product_id": "",
                "metadata": {"action": "wechat_buy"},
            }

        if action == "MidasJSBridge_call":
            params = msg_data.get("params", {})
            return {
                "type": "payment_params",
                "value": json.dumps(params, ensure_ascii=False),
                "product_id": "",
                "metadata": {"action": "MidasJSBridge_call", "cmd": msg_data.get("cmd", "")},
            }

        return None

    @staticmethod
    def _detect_product(raw_data: dict) -> str:
        """从原始数据中推断货品 ID。"""
        path = raw_data.get("path", "") or raw_data.get("api_url", "")
        for offer_id, product_name in OFFER_PRODUCT_MAP.items():
            if offer_id in path:
                return offer_id
        return ""
