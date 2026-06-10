"""
支付采集器 — mitmproxy 内联脚本。

在 mitmdump 进程中运行，实时过滤和分析 HTTP/HTTPS 流量。
通过环境变量 BACKEND_URL 指定回调地址。

工作模式：
  1. 域名白名单过滤 — 只处理支付相关域名
  2. 请求拦截 — 记录支付 API 请求
  3. 响应分析 — 从响应体中提取支付 URL / 微信支付参数
  4. 回调后端 — 将提取的凭证 POST 到本地后端
"""

import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

# ── 配置 ──────────────────────────────────────────

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8800")
CAPTURE_API = f"{BACKEND_URL}/api/capture/ingest"

# 支付相关域名白名单
PAY_DOMAINS = [
    "api.unipay.qq.com",
    "pay.qq.com",
    "wx.tenpay.com",
    "tenpay.com",
    "api.mch.weixin.qq.com",
    "pay.weixin.qq.com",
    "qpay.qq.com",
    "ssl.gstatic.com",  # Google Pay
]

# 响应体中的支付 URL 正则
PAY_URL_PATTERN = re.compile(
    r'https?://wx\.tenpay\.com/[^\s"\'<>]+'
    r'|https?://pay\.qq\.com/[^\s"\'<>]+'
    r'|weixin://wxpay/bizpayurl\?[^\s"\'<>]+'
)

# 微信支付参数检测
WX_PAY_PARAMS = re.compile(
    r'(getBrandWCPayRequest|wx_appid|WeixinJSBridge)'
)

# web_save 请求体参数提取
RE_OPENID = re.compile(r'openid=([A-F0-9]+)')
RE_PAY_METHOD = re.compile(r'pay_method=(\w+)')
RE_OFFER_ID = re.compile(r'/v1/r/(\d+)/web_save')


def is_payment_host(host: str) -> bool:
    """检查请求的目标是否属于支付平台。"""
    return any(d in host for d in PAY_DOMAINS)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def send_to_backend(credential: dict):
    """将捕获的凭证发送到本地后端（fire-and-forget）。"""
    import socket
    try:
        data = json.dumps(credential).encode()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        # 解析 BACKEND_URL 的 host:port
        url = BACKEND_URL
        if url.startswith("http://"):
            url = url[7:]
        host, _, port_str = url.partition(":")
        port = int(port_str) if port_str else 8800
        sock.connect((host, port))

        # 构造简单的 HTTP POST 请求
        http_req = (
            f"POST {CAPTURE_API.replace(BACKEND_URL, '')} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(data)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode() + data

        sock.sendall(http_req)
        sock.close()
    except Exception:
        pass  # 后端可能未运行


# ── mitmproxy 事件钩子 ────────────────────────────


def request(flow):
    """拦截请求 — 记录支付 API 请求。"""
    host = flow.request.pretty_host
    if not is_payment_host(host):
        return

    credential = {
        "type": "api_request",
        "value": flow.request.pretty_url[:5000],
        "platform": "qq_midas",
        "product": "Q币",
        "source": "mitmproxy",
        "method": flow.request.method,
        "host": host,
        "path": flow.request.path,
        "headers": dict(flow.request.headers),
        "body": (flow.request.text or "")[:5000],
        "captured_at": now_iso(),
    }
    send_to_backend(credential)


def response(flow):
    """拦截响应 — 分析响应体提取支付凭证。"""
    host = flow.request.pretty_host
    if not is_payment_host(host):
        return

    body = (flow.response.text or "")[:50000]

    # ── 策略 1: 提取支付 URL ──
    for match in PAY_URL_PATTERN.finditer(body):
        pay_url = match.group(0)
        credential = {
            "type": "payment_url",
            "value": pay_url,
            "platform": "qq_midas",
            "product": "Q币",
            "source": "mitmproxy_response",
            "api_url": flow.request.pretty_url,
            "host": host,
            "path": flow.request.path,
            "captured_at": now_iso(),
        }
        send_to_backend(credential)

    # ── 策略 2: 检测到微信支付参数 ──
    if WX_PAY_PARAMS.search(body):
        credential = {
            "type": "payment_params",
            "value": body[:5000],
            "platform": "wechat",
            "product": "微信支付",
            "source": "mitmproxy_response",
            "api_url": flow.request.pretty_url,
            "host": host,
            "path": flow.request.path,
            "captured_at": now_iso(),
        }
        send_to_backend(credential)

    # ── 策略 3: web_save 响应（QQ 支付下单成功 → 含支付 URL）──
    if "web_save" in flow.request.path and flow.response.status_code == 200:
        # 从响应体中提取 weixin:// 支付 URL
        pay_match = PAY_URL_PATTERN.search(body)
        if not pay_match:
            return  # 无支付 URL 则跳过

        # 从请求体中提取 openid（关联 QQ 账号）
        req_text = flow.request.text or ""
        openid = ""
        m = RE_OPENID.search(req_text)
        if m:
            openid = m.group(1)

        pay_method = "wechat"
        m2 = RE_PAY_METHOD.search(req_text)
        if m2:
            pay_method = m2.group(1)

        offer_id = ""
        m3 = RE_OFFER_ID.search(flow.request.path)
        if m3:
            offer_id = m3.group(1)

        credential = {
            "type": "payment_url",
            "value": pay_match.group(0),
            "platform": "qq_midas",
            "product": "Q币",
            "product_id": offer_id,
            "source": "web_save",
            "openid": openid,
            "pay_method": pay_method,
            "body": req_text[:3000],
            "api_url": flow.request.pretty_url,
            "host": host,
            "path": flow.request.path,
            "captured_at": now_iso(),
        }
        send_to_backend(credential)
