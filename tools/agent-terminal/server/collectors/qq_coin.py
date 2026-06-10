"""QQ Coin collector — three modes: add_account, collect, batch_collect.

Mode add_account:
  1. HTTP QR login via QQLoginSession (from qq_login.py)
  2. User scans QR code with QQ mobile
  3. Save midas_openid + midas_openkey to qq_accounts table
  4. Optional: generate 1 payment QR code

Mode collect:
  1. Load account's midas_openid + midas_openkey from DB
  2. Launch Playwright, inject cookies into .pay.qq.com domain
  3. Navigate to payment page, capture QR code
  4. On redirect to login → mark account EXPIRED

Mode batch_collect:
  1. Load all ACTIVE accounts from DB
  2. Reuse one browser; create fresh context per account with cookies
  3. Each account generates 1 payment QR code
  4. Mark expired accounts
"""

import asyncio
import base64
import json
import time
import uuid
from typing import Any, AsyncGenerator, Optional

from collectors.base import BaseCollector
from collectors.qq_login import QQLoginSession
from config import settings
from storage.db import get_cursor, get_setting

import httpx

# ── Constants ──────────────────────────────────────────────────

MIDAS_APPID = "1450000186"
PF = "mds_storeopen_qb-__mds_default_v1_0_0.qb-html5"


def _now() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"


def _progress_step(step: str, progress: int, message: str) -> dict:
    return {"step": step, "status": "running", "message": message, "progress": progress}


def _error_step(message: str) -> dict:
    return {"step": "error", "status": "failed", "message": message, "progress": 0}


class QQCoinCollector(BaseCollector):
    """Collects Q-coin recharge credentials — supports add_account / collect / batch_collect."""

    def __init__(self, task_id: str, config: dict[str, Any]):
        super().__init__(task_id, config)
        self._playwright = None
        self._browser = None

    @property
    def name(self) -> str:
        return "qq_coin"

    # ═══════════════════════════════════════════════════════════
    # Entry point — dispatch by mode
    # ═══════════════════════════════════════════════════════════

    async def execute(self) -> AsyncGenerator[dict, None]:
        mode = self.config.get("mode", "collect")
        try:
            if mode == "add_account":
                async for step in self._mode_add_account():
                    yield step
            elif mode == "batch_collect":
                async for step in self._mode_batch_collect():
                    yield step
            else:  # "collect"
                async for step in self._mode_collect():
                    yield step
        except Exception as e:
            yield _error_step(f"采集中断: {e}")
        finally:
            await self.cleanup()

    # ═══════════════════════════════════════════════════════════
    # Mode 1: add_account — QR login + save credentials
    # ═══════════════════════════════════════════════════════════

    async def _mode_add_account(self) -> AsyncGenerator[dict, None]:
        """Playwright PC OAuth QR login → save ALL cookies → optional payment QR."""
        yield _progress_step("login_qr", 5, "正在启动浏览器...")

        # Lazy-launch browser
        await self._ensure_browser_path()
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.config.get("headless", False),
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        context.set_default_timeout(15000)
        page = await context.new_page()

        try:
            # Step 1: Navigate to PC pay page (triggers OAuth iframe with QR)
            yield _progress_step("login_qr", 10, "正在打开 PC 充值中心...")
            await page.goto(
                "https://pay.qq.com/ipay/index.shtml?c=qqacct_save",
                wait_until="domcontentloaded", timeout=30000,
            )
            await asyncio.sleep(3)
            qr_data_uri = None
            nickname = ""

            # Step 2: Wait for ptlogin iframe with QR code
            yield _progress_step("login_qr", 15, "等待登录二维码...")
            for _ in range(20):
                for fr in page.frames:
                    if "ptlogin2.qq.com" in fr.url:
                        qr_img = fr.locator("#qrlogin_img")
                        if await qr_img.count() > 0:
                            src = await qr_img.get_attribute("src") or ""
                            if src:
                                qr_data_uri = src
                            break
                if qr_data_uri:
                    break
                await asyncio.sleep(1)

            if not qr_data_uri:
                yield _error_step("获取二维码失败")
                return

            yield {
                "step": "login_qr",
                "status": "running",
                "message": "请用手机QQ扫码登录",
                "progress": 20,
                "data": {"qr_image": qr_data_uri, "qr_code": qr_data_uri},
            }

            # Step 3: Wait for login (poll for pay_openid cookie)
            yield _progress_step("login_wait", 30, "等待扫码登录...")
            for i in range(120):
                cookies = await context.cookies()
                ck = {c["name"]: c["value"] for c in cookies}
                if ck.get("pay_openid") and ck.get("pay_openkey"):
                    nickname = ck.get("pay_qq_nickname", "unknown")
                    yield _progress_step(
                        "login_creds", 50,
                        f"扫码成功 ({nickname})，正在提取凭据...",
                    )
                    break
                if i % 10 == 0:
                    yield _progress_step("login_wait", 30, f"等待扫码... ({i}s)")
                await asyncio.sleep(1)
            else:
                yield _error_step("扫码登录超时")
                return

            # Step 4: Extract ALL cookies
            cookies = await context.cookies()
            ck = {c["name"]: c["value"] for c in cookies}

            uin = ck.get("p_uin", "")
            p_skey = ck.get("p_skey", "")
            # midas_openid is actually pay_openid in PC OAuth flow
            pay_openid = ck.get("pay_openid", "")
            pay_openkey = ck.get("pay_openkey", "")
            pay_session_id = ck.get("pay_session_id", "")
            pay_session_type = ck.get("pay_session_type", "")
            pay_qq_appid = ck.get("pay_qq_appid", "")
            pay_qq_nickname = ck.get("pay_qq_nickname", nickname)
            pt4_token = ck.get("pt4_token", "")
            pt_oauth_token = ck.get("pt_oauth_token", "")
            # Also capture midas_openid/openkey from graph.qq.com if available
            midas_openid = ck.get("midas_openid", pay_openid)
            midas_openkey = ck.get("midas_openkey", pay_openkey)

            yield _progress_step("login_creds", 60,
                                 f"凭据提取完成: uin={uin[:10]}..., pay_openid={pay_openid[:10]}...")

            # Step 5: Save to db
            yield _progress_step("save_account", 65, "保存账号凭据...")
            account_id = self._save_account(
                nickname=pay_qq_nickname,
                uin=uin,
                openid=midas_openid,
                openkey=midas_openkey,
                p_uin=uin,
                p_skey=p_skey,
                pay_openid=pay_openid,
                pay_openkey=pay_openkey,
                pay_session_id=pay_session_id,
                pay_session_type=pay_session_type,
                pay_qq_appid=pay_qq_appid,
                pay_qq_nickname=pay_qq_nickname,
                pt4_token=pt4_token,
                pt_oauth_token=pt_oauth_token,
            )
            yield _progress_step("save_account", 70, f"账号已保存 (ID={account_id})")

            # Step 6 (optional): generate payment QR using saved cookies
            payment_data = None
            if self.config.get("generate_payment", True):
                yield _progress_step("payment", 75, "正在进入商城下单...")
                # Navigate to shop (may show /auth on first load)
                await page.goto(
                    "https://pay.qq.com/h5/shop.shtml",
                    wait_until="domcontentloaded", timeout=30000,
                )
                await asyncio.sleep(2)
                # If /auth, override hash instead of reloading
                if "/auth" in page.url:
                    await page.evaluate('window.location.hash = "#/"')
                    await asyncio.sleep(3)
                # Fallback reload
                if "/auth" in page.url:
                    await page.goto("https://pay.qq.com/h5/shop.shtml",
                                    wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)
                    if "/auth" in page.url:
                        await page.evaluate('window.location.hash = "#/"')
                        await asyncio.sleep(3)

                # Click 60 Q币 button
                for sel in [
                    'button:has-text("60")',
                    'text=60 Q币',
                    '[class*="qb"] button:first-child',
                ]:
                    try:
                        btn = page.locator(sel)
                        if await btn.count() > 0 and await btn.first.is_visible():
                            await btn.first.click()
                            await asyncio.sleep(3)
                            payment_data = {
                                "value": page.url,
                                "resource_type": "payment_link",
                                "metadata": json.dumps({
                                    "product": "Q币",
                                    "amount": 60,
                                    "source": "shop_qb_click",
                                }, ensure_ascii=False),
                            }
                            yield _progress_step("payment", 85, "已进入支付页面")
                            break
                    except:
                        pass

                if payment_data:
                    rid = f"res_{uuid.uuid4().hex[:12]}"
                    with get_cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO resources (resource_id, task_id, platform, product_id, "
                            "resource_type, value, status, metadata, created_at) "
                            "VALUES (?,?,?,?,?,?,?,?,?)",
                            (rid, self.task_id, "qq_coin",
                             self.config.get("product_id", ""),
                             payment_data["resource_type"], payment_data["value"],
                             "collected", payment_data.get("metadata", "{}"), _now()),
                        )
                        payment_data["resource_id"] = rid
                    yield {
                        "step": "payment",
                        "status": "completed",
                        "message": "已进入支付页",
                        "progress": 85,
                        "data": {"resource": payment_data},
                    }
                else:
                    yield _progress_step("payment", 85, "未找到 Q币按钮，跳过")

            payment_resources = [payment_data] if payment_data else []

            # Upload
            uploaded_ids, pending_ids = [], []
            try:
                yield _progress_step("upload", 90, "上传到平台...")
                uploaded_ids, pending_ids = await self._upload_to_platform(
                    payment_resources, self.config.get("product_id", ""),
                )
            except Exception:
                pass

            yield {
                "step": "complete",
                "status": "completed",
                "message": f"账号 {pay_qq_nickname or uin} 绑定完成",
                "progress": 100,
                "data": {
                    "account_id": account_id,
                    "nickname": pay_qq_nickname,
                    "uin": uin,
                    "pay_openid": pay_openid,
                    "resources": payment_resources,
                    "uploaded_ids": uploaded_ids,
                    "pending_ids": pending_ids,
                },
            }
        finally:
            await context.close()

    # ═══════════════════════════════════════════════════════════
    # Mode 2: collect — use saved account's midas token
    # ═══════════════════════════════════════════════════════════

    async def _mode_collect(self) -> AsyncGenerator[dict, None]:
        """Load saved account → inject cookies → capture payment QR."""
        account_id = self.config.get("account_id")
        if not account_id:
            yield _error_step("collect 模式需要指定 account_id")
            return

        yield _progress_step("load_account", 5, f"加载账号 (ID={account_id})...")
        account = self._load_account(account_id)
        if not account:
            yield _error_step(f"账号(ID={account_id})不存在")
            return
        if account["status"] != "ACTIVE":
            yield _error_step(
                f"账号状态为 {account['status']}，不可用: "
                f"{account.get('error_message', '')}"
            )
            return

        openid = account["midas_openid"]
        openkey = account["midas_openkey"]
        nickname = account.get("nickname", "") or account.get("uin", "")
        yield _progress_step("load_account", 10, f"已加载账号: {nickname}")

        quantity = self.config.get("quantity", 1)
        collected = []

        for i in range(quantity):
            if self._cancelled:
                return
            base_progress = 15 + (i * 70 // quantity)
            yield _progress_step(
                "payment", base_progress,
                f"采集支付码 ({i+1}/{quantity})...",
            )

            payment_data = await self._collect_with_creds(
                openid, openkey,
                self.config.get("collection_config", {}).get("implementation", {}),
                extra_cookies={
                    "p_uin": account.get("p_uin", ""),
                    "p_skey": account.get("p_skey", ""),
                    "uin": account.get("uin", ""),
                    "pt4_token": account.get("pt4_token", ""),
                    "pt_oauth_token": account.get("pt_oauth_token", ""),
                    "pay_openid": account.get("pay_openid", ""),
                    "pay_openkey": account.get("pay_openkey", ""),
                    "pay_session_id": account.get("pay_session_id", ""),
                    "pay_session_type": account.get("pay_session_type", ""),
                    "pay_qq_appid": account.get("pay_qq_appid", ""),
                },
            )
            if payment_data:
                collected.append(payment_data)
                yield {
                    "step": "payment",
                    "status": "completed",
                    "message": f"已获取支付凭证 ({i+1}/{quantity})",
                    "progress": base_progress + 20,
                    "data": {"resource": payment_data},
                }
            else:
                yield _progress_step(
                    "payment", base_progress + 20,
                    "Token 已过期，标记账号失效",
                )
                self._mark_account_expired(
                    account_id, "midas Token 已过期或无效",
                )
                yield _error_step(f"账号 {nickname} 的 Token 已失效")
                return

        if not collected:
            yield _error_step("未获取到任何支付凭证")
            return

        # Save locally
        yield _progress_step("save_local", 90, f"保存 {len(collected)} 条凭证...")
        with get_cursor() as cursor:
            for res in collected:
                rid = f"res_{uuid.uuid4().hex[:12]}"
                cursor.execute(
                    "INSERT INTO resources (resource_id, task_id, platform, product_id, "
                    "resource_type, value, status, metadata, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (rid, self.task_id, "qq_coin",
                     self.config.get("product_id", ""),
                     res["resource_type"], res["value"], "collected",
                     res.get("metadata", "{}"), _now()),
                )
                res["resource_id"] = rid

        # Upload
        yield _progress_step("upload", 95, "上传到平台...")
        uploaded_ids, pending_ids = await self._upload_to_platform(
            collected, self.config.get("product_id", ""),
        )

        yield {
            "step": "complete",
            "status": "completed",
            "message": f"采集完成，共 {len(collected)} 条凭证",
            "progress": 100,
            "data": {
                "resources": collected,
                "uploaded_ids": uploaded_ids,
                "pending_ids": pending_ids,
            },
        }

    # ═══════════════════════════════════════════════════════════
    # Mode 3: batch_collect — rotate through all active accounts
    # ═══════════════════════════════════════════════════════════

    async def _mode_batch_collect(self) -> AsyncGenerator[dict, None]:
        """Load all ACTIVE accounts → each generates 1 payment QR."""
        yield _progress_step("load_accounts", 5, "加载所有有效账号...")
        accounts = self._load_active_accounts()
        if not accounts:
            yield _error_step("没有 ACTIVE 状态的账号可用")
            return

        total = len(accounts)
        yield _progress_step("load_accounts", 10, f"共 {total} 个有效账号")

        collected = []
        expired_ids = []

        for idx, account in enumerate(accounts):
            if self._cancelled:
                break

            base_progress = 12 + (idx * 80 // total)
            aid = account["id"]
            openid = account["midas_openid"]
            openkey = account["midas_openkey"]
            nickname = account.get("nickname", "") or account.get("uin", "")

            yield _progress_step(
                "batch", base_progress,
                f"[{idx+1}/{total}] {nickname}：采集支付码...",
            )

            payment_data = await self._collect_with_creds(
                openid, openkey,
                self.config.get("collection_config", {}).get("implementation", {}),
                extra_cookies={
                    "p_uin": account.get("p_uin", ""),
                    "p_skey": account.get("p_skey", ""),
                    "uin": account.get("uin", ""),
                    "pt4_token": account.get("pt4_token", ""),
                    "pt_oauth_token": account.get("pt_oauth_token", ""),
                    "pay_openid": account.get("pay_openid", ""),
                    "pay_openkey": account.get("pay_openkey", ""),
                    "pay_session_id": account.get("pay_session_id", ""),
                    "pay_session_type": account.get("pay_session_type", ""),
                    "pay_qq_appid": account.get("pay_qq_appid", ""),
                },
            )

            if payment_data:
                payment_data["_account_id"] = aid
                payment_data["_nickname"] = nickname
                collected.append(payment_data)
                yield {
                    "step": "batch",
                    "status": "completed",
                    "message": f"[{idx+1}/{total}] {nickname}：已获取支付码",
                    "progress": base_progress + 10,
                    "data": {"resource": payment_data, "account_id": aid},
                }
            else:
                expired_ids.append(aid)
                self._mark_account_expired(
                    aid, "midas Token 已过期或无效 (batch_collect)",
                )
                yield _progress_step(
                    "batch", base_progress + 10,
                    f"[{idx+1}/{total}] {nickname}：Token 失效，已标记",
                )

        if not collected:
            yield _error_step("所有账号均已失效，未获取到任何支付凭证")
            return

        # Save locally
        yield _progress_step("save_local", 92, f"保存 {len(collected)} 条凭证...")
        with get_cursor() as cursor:
            for res in collected:
                rid = f"res_{uuid.uuid4().hex[:12]}"
                cursor.execute(
                    "INSERT INTO resources (resource_id, task_id, platform, product_id, "
                    "resource_type, value, status, metadata, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (rid, self.task_id, "qq_coin",
                     self.config.get("product_id", ""),
                     res["resource_type"], res["value"], "collected",
                     res.get("metadata", "{}"), _now()),
                )
                res["resource_id"] = rid

        # Upload
        yield _progress_step("upload", 95, "上传到平台...")
        uploaded_ids, pending_ids = await self._upload_to_platform(
            collected, self.config.get("product_id", ""),
        )

        summary = (
            f"批量采集完成：成功 {len(collected)}/{total}，"
            f"失效 {len(expired_ids)}/{total}"
        )
        yield {
            "step": "complete",
            "status": "completed",
            "message": summary,
            "progress": 100,
            "data": {
                "resources": collected,
                "uploaded_ids": uploaded_ids,
                "pending_ids": pending_ids,
                "expired_accounts": expired_ids,
                "total_accounts": total,
            },
        }

    # ═══════════════════════════════════════════════════════════
    # Core: collect payment QR using midas credentials
    # ═══════════════════════════════════════════════════════════

    async def _collect_with_creds(
        self, openid: str, openkey: str, impl_config: dict,
        extra_cookies: dict[str, str] | None = None,
    ) -> Optional[dict]:
        """Validate saved cookies → return token as credential.

        Injects all saved cookies → navigates to shop → if login state
        is recognized (via hash override), token is VALID and returned
        as a credential resource. If /auth persists, token EXPIRED.
        """
        if not openid or not openkey:
            return None

        headless = self.config.get("headless", True)

        # Lazy-launch browser
        if not self._browser:
            try:
                await self._ensure_browser_path()
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            except Exception:
                return None

        try:
            context = await self._browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/133.0.0.0 Safari/537.36"
                ),
            )

            # ── Inject ALL cookies ──
            cookie_list = []
            # 1. pay.qq.com cookies (payment auth)
            pay_cookies = {
                "pay_openid": openid,
                "pay_openkey": openkey,
                "pay_session_id": "openid",
                "pay_session_type": "kp_accesstoken",
                "pay_qq_appid": "101502376",
            }
            if extra_cookies:
                pay_cookies.update({
                    k: extra_cookies.get(k, v)
                    for k, v in pay_cookies.items()
                })
                if extra_cookies.get("pay_session_id"):
                    pay_cookies["pay_session_id"] = extra_cookies["pay_session_id"]
                if extra_cookies.get("pay_session_type"):
                    pay_cookies["pay_session_type"] = extra_cookies["pay_session_type"]
                if extra_cookies.get("pay_qq_appid"):
                    pay_cookies["pay_qq_appid"] = extra_cookies["pay_qq_appid"]

            for name, value in pay_cookies.items():
                if value:
                    cookie_list.append({
                        "name": name, "value": value,
                        "domain": ".pay.qq.com", "path": "/",
                    })

            # 2. .qq.com cookies (uin, p_uin, p_skey, skey, pt4_token, pt_oauth_token)
            if extra_cookies:
                for ck_name in ["p_uin", "p_skey", "uin", "skey",
                                "pt4_token", "pt_oauth_token"]:
                    val = extra_cookies.get(ck_name)
                    if val:
                        cookie_list.append({
                            "name": ck_name, "value": val,
                            "domain": ".qq.com", "path": "/",
                        })

            # 3. midas_txcz cookies on .pay.qq.com
            cookie_list.extend([
                {"name": "midas_txcz_openid", "value": openid,
                 "domain": ".pay.qq.com", "path": "/"},
                {"name": "midas_txcz_openkey", "value": openkey,
                 "domain": ".pay.qq.com", "path": "/"},
                {"name": "midas_txcz_sessiontype", "value": "kp_accesstoken",
                 "domain": ".pay.qq.com", "path": "/"},
            ])

            await context.add_cookies(cookie_list)
            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', "
                "{ get: () => undefined });"
            )

            # ── Validate: navigate to shop → check login state ──
            try:
                await page.goto(
                    "https://pay.qq.com/h5/shop.shtml",
                    wait_until="domcontentloaded", timeout=30000,
                )
                await asyncio.sleep(2)
            except Exception:
                await context.close()
                return None

            # If /auth, try hash override to bypass SPA
            if "/auth" in page.url:
                await page.evaluate('window.location.hash = "#/"')
                await asyncio.sleep(3)

            # Verify login state: check URL for /auth
            if "/auth" in page.url:
                # Token expired
                await context.close()
                return None

            # ── Token is VALID — return as credential ──
            nickname = "unknown"
            if extra_cookies:
                nickname = extra_cookies.get("pay_qq_nickname",
                            extra_cookies.get("uin", openid[:8]))

            result = {
                "value": json.dumps({
                    "openid": openid,
                    "openkey": openkey,
                    "session_id": pay_cookies.get("pay_session_id", "openid"),
                    "session_type": pay_cookies.get("pay_session_type", "kp_accesstoken"),
                    "uin": (extra_cookies or {}).get("uin", ""),
                    "nickname": nickname,
                }, ensure_ascii=False),
                "resource_type": "credential",
                "metadata": json.dumps({
                    "product": "Q币",
                    "source": "pc_oauth_token",
                    "nickname": nickname,
                    "validated_at": _now(),
                }, ensure_ascii=False),
            }
            await context.close()
            return result

        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════
    # Playwright lifecycle helpers
    # ═══════════════════════════════════════════════════════════

    async def _ensure_browser_path(self):
        """Set PLAYWRIGHT_BROWSERS_PATH if not already set."""
        import os
        if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
            return
        for p in [
            "/root/.cache/ms-playwright",
            "/root/.hermes/profiles/super-market/home/.cache/ms-playwright",
        ]:
            if os.path.isdir(p):
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = p
                break

    # ── Capture payment credential ─────────────────────────────

    async def _capture_payment_credential(
        self, page, timeout: int = 30,
    ) -> Optional[dict]:
        """Try to capture QR code or payment URL from the payment page.

        Strategies: QR image → click pay tab → iframes → screenshot.
        """
        for _ in range(timeout):
            if self._cancelled:
                return None

            # Strategy 1: Find QR code image / canvas
            for sel in [
                "img[src*=qr]", "img[src*=qrcode]",
                "[class*=qrcode] img", "div.qr-code img",
                "img[id*=qr]", "canvas",
            ]:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        src = await el.get_attribute("src")
                        if src and src.startswith("data:image"):
                            return {
                                "value": src, "resource_type": "qrcode",
                                "metadata": json.dumps({
                                    "source": "payment_qrcode",
                                    "page_url": page.url,
                                }, ensure_ascii=False),
                            }
                except Exception:
                    pass

            # Strategy 2: Click a payment tab to reveal QR code
            for sel in [
                "text=微信支付", "text=QQ钱包", "text=扫码支付",
                "[class*=wechat]", "button:has-text('支付')",
            ]:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        await asyncio.sleep(2)
                        break
                except Exception:
                    pass

            # Strategy 3: Look inside iframes
            try:
                for ifr in await page.query_selector_all("iframe"):
                    try:
                        frame = await ifr.content_frame()
                        if frame:
                            for item in await frame.query_selector_all(
                                "img[src*=qr], canvas",
                            ):
                                src = await item.get_attribute("src")
                                if src:
                                    return {
                                        "value": src, "resource_type": "qrcode",
                                        "metadata": json.dumps({
                                            "source": "iframe_qrcode",
                                            "page_url": page.url,
                                        }, ensure_ascii=False),
                                    }
                    except Exception:
                        pass
            except Exception:
                pass

            await asyncio.sleep(1)

        # Fallback: screenshot
        try:
            b64 = base64.b64encode(
                await page.screenshot(type="png", full_page=False)
            ).decode()
            return {
                "value": f"data:image/png;base64,{b64}",
                "resource_type": "qrcode",
                "metadata": json.dumps(
                    {"source": "page_screenshot", "note": "截图替代"},
                    ensure_ascii=False,
                ),
            }
        except Exception:
            pass
        return None

    # ── Upload to platform ─────────────────────────────────────

    async def _upload_to_platform(
        self, resources: list[dict], product_id: str,
    ) -> tuple[list, list]:
        """Upload collected resources to platform.

        Returns (uploaded_ids, pending_ids).
        """
        uploaded = []
        pending = []
        token = settings.AGENT_TOKEN or get_setting("agent_token", "")

        for res in resources:
            if self._cancelled:
                break
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    headers = {"Content-Type": "application/json"}
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                    pid = (
                        int(product_id)
                        if str(product_id).isdigit()
                        else product_id
                    )
                    resp = await client.post(
                        f"{settings.PLATFORM_API_BASE}/api/terminal/inventory/upload",
                        json={
                            "items": [{
                                "product_id": pid,
                                "content": res["value"],
                                "expires_at": res.get("expires_at", ""),
                            }],
                        },
                        headers=headers,
                        timeout=15,
                    )
                    if resp.status_code in (200, 201):
                        ids = resp.json().get("platform_resource_ids", [])
                        uploaded.extend(ids)
                        with get_cursor() as c:
                            c.execute(
                                "UPDATE resources SET status='uploaded', "
                                "uploaded_at=? WHERE resource_id=?",
                                (_now(), res["resource_id"]),
                            )
                    else:
                        pending.append(res["resource_id"])
            except Exception:
                pending.append(res["resource_id"])
        return uploaded, pending

    # ── DB helpers ─────────────────────────────────────────────

    def _load_account(self, account_id: int) -> Optional[dict]:
        """Load a single QQ account from DB by ID."""
        with get_cursor() as cursor:
            row = cursor.execute(
                "SELECT * FROM qq_accounts WHERE id = ?", (account_id,),
            ).fetchone()
            return dict(row) if row else None

    def _load_active_accounts(self) -> list[dict]:
        """Load all ACTIVE QQ accounts, oldest-verified first."""
        with get_cursor() as cursor:
            rows = cursor.execute(
                "SELECT * FROM qq_accounts WHERE status = 'ACTIVE' "
                "ORDER BY last_verified_at ASC",
            ).fetchall()
            return [dict(r) for r in rows]

    def _save_account(
        self,
        nickname: str,
        uin: str,
        openid: str,
        openkey: str,
        p_uin: str,
        p_skey: str,
        pay_openid: str = "",
        pay_openkey: str = "",
        pay_session_id: str = "",
        pay_session_type: str = "",
        pay_qq_appid: str = "",
        pay_qq_nickname: str = "",
        pt4_token: str = "",
        pt_oauth_token: str = "",
    ) -> int:
        """Upsert a QQ account into qq_accounts. Returns account id."""
        with get_cursor() as cursor:
            existing = cursor.execute(
                "SELECT id FROM qq_accounts WHERE uin=? OR midas_openid=?",
                (uin, openid),
            ).fetchone()

            if existing:
                cursor.execute(
                    "UPDATE qq_accounts SET nickname=?, midas_openid=?, "
                    "midas_openkey=?, p_uin=?, p_skey=?, status='ACTIVE', "
                    "last_verified_at=?, error_message='', updated_at=?, "
                    "pay_openid=?, pay_openkey=?, pay_session_id=?, "
                    "pay_session_type=?, pay_qq_appid=?, pay_qq_nickname=?, "
                    "pt4_token=?, pt_oauth_token=? "
                    "WHERE id=?",
                    (nickname, openid, openkey, p_uin, p_skey,
                     _now(), _now(),
                     pay_openid, pay_openkey, pay_session_id,
                     pay_session_type, pay_qq_appid, pay_qq_nickname,
                     pt4_token, pt_oauth_token,
                     existing["id"]),
                )
                return existing["id"]
            else:
                cursor.execute(
                    "INSERT INTO qq_accounts (nickname, uin, midas_openid, "
                    "midas_openkey, p_uin, p_skey, status, last_verified_at, "
                    "created_at, updated_at, "
                    "pay_openid, pay_openkey, pay_session_id, "
                    "pay_session_type, pay_qq_appid, pay_qq_nickname, "
                    "pt4_token, pt_oauth_token) "
                    "VALUES (?,?,?,?,?,?,'ACTIVE',?,?,?,"
                    "?,?,?,?,?,?,?,?)",
                    (nickname, uin, openid, openkey, p_uin, p_skey,
                     _now(), _now(), _now(),
                     pay_openid, pay_openkey, pay_session_id,
                     pay_session_type, pay_qq_appid, pay_qq_nickname,
                     pt4_token, pt_oauth_token),
                )
                return cursor.lastrowid or 0

    def _mark_account_expired(self, account_id: int, error_message: str):
        """Mark a QQ account as EXPIRED with error message."""
        with get_cursor() as cursor:
            cursor.execute(
                "UPDATE qq_accounts SET status='EXPIRED', "
                "error_message=?, updated_at=? WHERE id=?",
                (error_message, _now(), account_id),
            )

    # ── Cleanup ────────────────────────────────────────────────

    async def cleanup(self):
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
