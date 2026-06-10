"""Pure HTTP QQ QR login — ported from vbox-gin's qq_login_qr.go.

Flow:
  1. GET ptlogin2.xui → get pt_login_sig cookie
  2. GET ptqrshow → get QR image (base64) + qrsig cookie
  3. Compute QrToken = hash33(qrsig)
  4. Poll ptqrlogin every 3s:
       - '65' = expired → restart
       - '66' = waiting → continue polling  
       - '67' = scanned → continue polling
       - '0'  = success → get redirect URL with uin
  5. GET redirect URL → extract p_uin, p_skey, pt4_token from Set-Cookie
  6. Compute G_Token = hash33(p_skey)
  7. POST graph.qq.com/oauth2.0/authorize → get access_token (openkey)
  8. GET graph.qq.com/oauth2.0/me → get openid

Returns: {"openid": "...", "openkey": "..."} on success
"""

import asyncio
import base64
import logging
import random
import re
import time
from typing import Optional

import httpx

# ── Constants ──────────────────────────────────────────────────

CLIENT_ID = "101502376"          # QQ互联 appid for pay.qq.com
PT_APPID = "716027609"           # ptlogin appid
DAID = "383"
PT_3RD_AID = "101502376"

LOGIN_SIG_URL = (
    "https://xui.ptlogin2.qq.com/cgi-bin/xlogin"
    "?appid=716027609&daid=383&style=33"
    "&login_text=%E7%99%BB%E5%BD%95"
    "&hide_title_bar=1&hide_border=1"
    "&target=self"
    "&s_url=https%3A%2F%2Fgraph.qq.com%2Foauth2.0%2Flogin_jump"
    "&pt_3rd_aid=101502376"
)

QR_IMG_URL = (
    "https://ssl.ptlogin2.qq.com/ptqrshow"
    "?appid=716027609&e=2&l=M&s=3&d=72&v=4"
    "&daid=383&pt_3rd_aid=101502376"
    "&u1=https%3A%2F%2Fgraph.qq.com%2Foauth2.0%2Flogin_jump"
)

OAUTH_AUTHORIZE_URL = "https://graph.qq.com/oauth2.0/authorize"
OAUTH_ME_URL = "https://graph.qq.com/oauth2.0/me"

_log = logging.getLogger("qq_login")


# ── Hash functions ─────────────────────────────────────────────


def _hash33(s: str) -> int:
    """hash33 algorithm used by QQ login."""
    e = 0
    for ch in s:
        e += (e << 5) + ord(ch)
    return e & 0x7FFFFFFF


def _get_qr_token(qrsig: str) -> str:
    """Calculate QR token from qrsig."""
    return str(_hash33(qrsig))


def _get_g_token(p_skey: str) -> str:
    """Calculate G_Token from p_skey."""
    h = 5381
    for ch in p_skey:
        h = ((h << 5) + h) + ord(ch)
    return str(h & 0x7FFFFFFF)


# ── HTTP helpers ───────────────────────────────────────────────


def _extract_cookie(cookies_str: str, name: str) -> str:
    """Extract a cookie value from a Set-Cookie header string."""
    for part in cookies_str.split(";"):
        part = part.strip()
        if part.startswith(name + "="):
            return part[len(name) + 1:]
    return ""


def _parse_ptqrlogin_response(text: str) -> tuple[str, str, str]:
    """Parse ptqrlogin response like: ptuiCB('0','0','http://...','0','昵称','用户名');
    Returns (code, url, nickname)."""
    match = re.search(r"ptuiCB\('([^']+)','([^']+)','([^']*)','[^']*','([^']*)'.*", text)
    if match:
        return match.group(1), match.group(3), match.group(4)
    return "66", "", ""


def _extract_url_param(url: str, param: str) -> str:
    """Extract a query/fragment parameter from a URL.
    
    Matches param=value anywhere in URL, not just after ? or &.
    This is needed because OAuth 2.0 implicit grant puts access_token
    in the URL fragment (#access_token=xxx), not the query string.
    """
    # Try regex first
    match = re.search(r"[?&#]" + param + r"=([^&]+)", url)
    if match:
        return match.group(1)
    
    # Fallback: simple string search (matches #access_token=xxx too)
    start = url.find(param + "=")
    if start == -1:
        return ""
    start += len(param) + 1
    end = url.find("&", start)
    if end == -1:
        return url[start:]
    return url[start:end]


# ── QR Login Implementation ────────────────────────────────────


class QQLoginError(Exception):
    pass


class QQLoginSession:
    """Manages the entire QR login flow."""

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30, follow_redirects=False)
        self._cookies: dict[str, str] = {}
        self._qr_retry_count = 0
        self._max_qr_retries = 3

    async def _request(
        self, method: str, url: str,
        data=None,
        extra_headers: Optional[dict] = None,
    ) -> httpx.Response:
        """Make HTTP request with stored cookies."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
        }
        if extra_headers:
            headers.update(extra_headers)

        cookie_header = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
        if cookie_header:
            headers["Cookie"] = cookie_header

        resp = await self._client.request(method, url, headers=headers, data=data)

        # Update cookies from Set-Cookie headers
        for set_cookie in resp.headers.get_list("set-cookie"):
            for part in set_cookie.split(";"):
                part = part.strip()
                lower = part.lower()
                if "=" in part and not any(
                    lower.startswith(x) for x in
                    ["expires=", "path=", "domain=", "httponly", "secure", "samesite", "max-age="]
                ):
                    kv = part.split("=", 1)
                    self._cookies[kv[0]] = kv[1]

        return resp

    async def get_qr_code(self) -> tuple[str, str]:
        """Step 1-2: Get pt_login_sig and QR code image.
        Returns (qr_image_base64, qrsig)."""
        # Step 1: Get pt_login_sig
        resp = await self._request("GET", LOGIN_SIG_URL)
        login_sig = self._cookies.get("pt_login_sig", "")
        if not login_sig:
            raise QQLoginError("获取 pt_login_sig 失败")

        # Step 2: Get QR image
        t = str(random.random())
        qr_url = QR_IMG_URL + "&t=" + t
        resp = await self._request("GET", qr_url)

        qrsig = self._cookies.get("qrsig", "")
        if not qrsig:
            raise QQLoginError("获取 qrsig 失败")

        qr_b64 = base64.b64encode(resp.content).decode()
        qr_data_uri = f"data:image/png;base64,{qr_b64}"

        return qr_data_uri, qrsig

    async def poll_scan(self, qrsig: str, progress_callback=None) -> dict[str, str]:
        """Steps 3-4: Poll for QR scan completion.
        Returns dict with 'location' (redirect URL) and 'nickname' on success."""
        qr_token = _get_qr_token(qrsig)

        while True:
            timestamp = f"0-0-{int(time.time() * 1000)}"
            check_url = (
                "https://ssl.ptlogin2.qq.com/ptqrlogin"
                f"?u1={_url_encode('https://graph.qq.com/oauth2.0/login_jump')}"
                f"&ptqrtoken={qr_token}"
                "&ptredirect=0&h=1&t=1&g=1&from_ui=1&ptlang=2052"
                f"&action={timestamp}"
                f"&js_ver=23111510&js_type=1"
                f"&login_sig={self._cookies.get('pt_login_sig', '')}"
                "&pt_uistyle=40"
                f"&aid={PT_APPID}&daid={DAID}"
                f"&pt_3rd_aid={PT_3RD_AID}"
                "&o1vId=&pt_js_version=v1.48.1"
            )

            try:
                resp = await self._request("GET", check_url)
                text = resp.text
                code, url, nickname = _parse_ptqrlogin_response(text)

                if code == "0":
                    # Successfully logged in
                    return {"location": url, "nickname": nickname}

                elif code == "65":
                    # QR expired
                    raise QQLoginError("二维码已失效，请重新获取")

                elif code == "67":
                    if progress_callback:
                        progress_callback("scanned", "已扫描，请在手机上确认登录")

                # code == "66" or anything else: keep waiting
                await asyncio.sleep(3)

            except httpx.TimeoutException:
                await asyncio.sleep(3)
                continue

    async def get_credentials(self, location: str) -> Optional[dict[str, str]]:
        """Steps 5-7: Get credentials from login redirect.
        Returns {"openid": "...", "openkey": "..."} or None."""
        
        # ═══════════ Step 5 — Follow redirect, extract cookies from Set-Cookie ═══════════
        _log.info(f"[DEBUG] Step5: GET redirect location={location[:100]}...")
        
        # IMPORTANT: Use fresh httpx request (not _request) to avoid cookie jar pollution
        # The check_sig endpoint returns 302 with Set-Cookie headers.
        # We must parse Set-Cookie directly from this response (like Go's Credential func).
        fresh_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
        }
        resp = await self._client.request("GET", location, headers=fresh_headers)
        _log.info(f"[DEBUG] Step5: status={resp.status_code}")

        # Parse Set-Cookie directly from response (like Go's Credential func)
        # This avoids the issue where accumulated cookies get overwritten with empty values
        needs = ["p_uin", "pt4_token", "p_skey", "pt_oauth_token"]
        fresh_cookies: dict[str, str] = {}
        for set_cookie in resp.headers.get_list("set-cookie"):
            # Take the cookie name=value part before first ;
            first_part = set_cookie.split(";")[0].strip()
            if "=" in first_part:
                name, value = first_part.split("=", 1)
                if name in needs and value:
                    fresh_cookies[name] = value
        
        p_uin = fresh_cookies.get("p_uin", "")
        p_skey = fresh_cookies.get("p_skey", "")
        pt4_token = fresh_cookies.get("pt4_token", "")
        pt_oauth_token = fresh_cookies.get("pt_oauth_token", "")
        
        _log.info(f"[DEBUG] Step5 (fresh parse): p_uin={'✓' if p_uin else '✗'} "
                  f"p_skey={'✓' if p_skey else '✗'} "
                  f"pt4={'✓' if pt4_token else '✗'} "
                  f"pt_oauth={'✓' if pt_oauth_token else '✗'}")
        
        # Fallback: if fresh parse missed p_skey, try the cookie jar (might have earlier value)
        if not p_skey:
            jar_p_skey = self._cookies.get("p_skey", "")
            if jar_p_skey:
                _log.info(f"[DEBUG] Step5: p_skey found in cookie jar (value={jar_p_skey[:8]}...)")
                p_skey = jar_p_skey
                p_uin = self._cookies.get("p_uin", "")
                pt4_token = self._cookies.get("pt4_token", "")
                pt_oauth_token = self._cookies.get("pt_oauth_token", "")

        if not p_skey:
            _log.error("[DEBUG] ❌ FAILED at Step5: no p_skey from redirect")
            _log.info(f"[DEBUG] Step5 all cookies in jar: {list(self._cookies.keys())}")
            return None

        # Also update our cookie jar with the fresh values for subsequent requests
        for k, v in fresh_cookies.items():
            if v:
                self._cookies[k] = v

        # Step 6: Compute G_Token
        g_token = _get_g_token(p_skey)
        _log.info(f"[DEBUG] Step6: G_Token={g_token[:8]}... from p_skey={p_skey[:8]}...")

        # ═══════════ Step 7 — POST to OAuth authorize ═══════════
        timestamp = str(int(time.time() * 1000))
        post_data = (
            f"response_type=token"
            f"&client_id={CLIENT_ID}"
            f"&redirect_uri=https://pay.qq.com/h5/shop.shtml"
            f"&scope=all&state=&switch=&from_ptlogin=1"
            f"&src=1&update_auth=1&openapi=1010"
            f"&g_tk={g_token}&auth_time={timestamp}"
        )
        
        _log.info(f"[DEBUG] Step7: POSTing to OAuth authorize...")

        resp = await self._request(
            "POST",
            OAUTH_AUTHORIZE_URL,
            data=post_data,
            extra_headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        
        _log.info(f"[DEBUG] Step7: POST status={resp.status_code}")

        redirect_url = resp.headers.get("location", "")
        _log.info(f"[DEBUG] Step7: Location={redirect_url[:150]}...")
        
        openkey = _extract_url_param(redirect_url, "access_token")
        _log.info(f"[DEBUG] Step7: access_token={'✓ ('+openkey[:10]+'...)' if openkey else '✗ EMPTY'}")

        if not openkey:
            try:
                _log.info(f"[DEBUG] Step7: Response body (first 500): {resp.text[:500]}")
            except:
                pass
            return None

        # ═══════════ Step 8 — Get openid ═══════════
        _log.info(f"[DEBUG] Step8: GET /oauth2.0/me...")
        openid = await self._get_openid(openkey)
        _log.info(f"[DEBUG] Step8: openid={'✓ ('+openid[:10]+'...)' if openid else '✗ EMPTY'}")

        if not openid:
            return None

        return {"openid": openid, "openkey": openkey}

    async def _get_openid(self, access_token: str) -> str:
        """Get openid from access_token."""
        try:
            resp = await self._request("GET",
                f"{OAUTH_ME_URL}?access_token={access_token}"
            )
            match = re.search(r'"openid":"([^"]+)"', resp.text)
            if match:
                return match.group(1)
        except Exception:
            pass
        return ""

    async def close(self):
        await self._client.aclose()


def _url_encode(s: str) -> str:
    """Simple URL encoding for query parameters."""
    import urllib.parse
    return urllib.parse.quote(s, safe="")
