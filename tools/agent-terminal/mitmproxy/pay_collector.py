"""
Agent Terminal — mitmproxy payment collector script.

Filter rules for payment API traffic.
Attached to mitmdump via `-s` flag.
"""

import json
import logging
from datetime import datetime
from urllib.parse import urlparse

# ── Target domains ──
PAY_DOMAINS = [
    "api.unipay.qq.com",
    "pay.qq.com",
    "wx.tenpay.com",
    "tenpay.com",
    "api.mch.weixin.qq.com",
    "pay.weixin.qq.com",
]

BACKEND_URL = "http://localhost:8801/api/collect"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mitm_pay")


def is_payment(host):
    return any(d in host for d in PAY_DOMAINS)


def send_credential(cred):
    """Send captured credential to local backend (fire-and-forget)."""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect(("localhost", 8801))
        data = json.dumps(cred).encode() + b"\n"
        sock.sendall(data)
        sock.close()
    except Exception:
        pass  # backend might not be running


def request(flow):
    """Intercept outgoing requests to payment APIs."""
    host = flow.request.pretty_host
    if not is_payment(host):
        return

    cred = {
        "type": "api_request",
        "value": flow.request.pretty_url[:5000],
        "platform": "qq_midas",
        "product": "Q币",
        "source": "mitmproxy",
        "method": flow.request.method,
        "host": host,
        "path": flow.request.path,
        "headers": dict(flow.request.headers),
        "body": flow.request.text[:5000],
        "captured_at": datetime.utcnow().isoformat() + "Z",
    }
    logger.info(f"[mitm] REQ {flow.request.method} {host}{flow.request.path[:80]}")
    send_credential(cred)


def response(flow):
    """Intercept responses from payment APIs."""
    host = flow.request.pretty_host
    if not is_payment(host):
        return

    body = flow.response.text[:10000] if flow.response.text else ""

    # Check for payment URLs in response
    pay_urls = []
    import re
    for m in re.finditer(r'https?://wx\.tenpay\.com/[^\s"\'<>]+', body):
        pay_urls.append(m.group(0))

    for url in pay_urls[:3]:
        cred = {
            "type": "payment_url",
            "value": url,
            "platform": "qq_midas",
            "product": "Q币",
            "source": "mitmproxy_response",
            "api_url": flow.request.pretty_url,
            "captured_at": datetime.utcnow().isoformat() + "Z",
        }
        logger.info(f"[mitm] PAY URL FOUND: {url[:80]}")
        send_credential(cred)
