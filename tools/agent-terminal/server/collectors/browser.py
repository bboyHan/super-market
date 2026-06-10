"""Browser automation collector using Playwright with platform-specific adapters."""

import asyncio
import json
import re
from typing import Any, AsyncGenerator, Optional

from collectors.base import BaseCollector


# ── Platform-specific selectors and URLs ──────────────────────

PLATFORM_CONFIGS: dict[str, dict] = {
    "jd": {
        "name": "京东",
        "base_url": "https://www.jd.com",
        "login_url": "https://passport.jd.com/new/login.aspx",
        "payment_timeout": 60,
        "selectors": {
            # Login page detection
            "login_detect": "a.link-login, div.login-form, input#loginname",
            "username_input": "input#loginname",
            "password_input": "input#nloginpwd",
            "login_btn": "button#loginsubmit, a#loginsubmit",
            # Product page
            "buy_btn": "a#btn-reservation, a.btn-buy, a#GotoShoppingCart, a.pay",
            "submit_order_btn": "a#order-submit, a.submit-btn, button.checkout-submit",
            # Payment page
            "payment_qrcode": "img#qr-img, div.qr-code img, canvas#qr-canvas",
            "payment_url_pattern": r"https?://pay\.jd\.com/.*",
            "pay_success": "div.pay-success, div.success-info, div.after-pay",
        },
    },
    "taobao": {
        "name": "淘宝",
        "base_url": "https://www.taobao.com",
        "login_url": "https://login.taobao.com",
        "payment_timeout": 60,
        "selectors": {
            "login_detect": "div.login-panel, iframe#taobao_login, a.J_Login2",
            "buy_btn": "a.J_Go, a.tb-submit, a.buy-link",
            "submit_order_btn": "a.submit-btn, button.submit-order, a.go-btn",
            "payment_qrcode": "div.qrcode-img img, img#barcode",
            "payment_url_pattern": r"https?://.*\.taobao\.com/.*pay.*|https?://wu.*\.alipay\.com/.*",
        },
    },
    "pdd": {
        "name": "拼多多",
        "base_url": "https://www.pinduoduo.com",
        "login_url": "https://mobile.yangkeduo.com/login.html",
        "payment_timeout": 45,
        "selectors": {
            "login_detect": "div.login-container, input#userName",
            "buy_btn": "a.buy-now, div.buy-btn, a.submit-order",
            "submit_order_btn": "button.submit, a.go-pay, div.pay-btn",
            "payment_qrcode": "img.qr-img, div.qrcode img",
            "payment_url_pattern": r"https?://mobile\.yangkeduo\.com/.*|https?://api\.pinduoduo\.com/.*pay.*",
        },
    },
}


class BrowserCollector(BaseCollector):
    """Collects credentials by automating a browser with Playwright.
    
    Supports platform-specific selectors. The flow:
    1. Launch Playwright Chromium (headed or headless)
    2. Inject session cookie (if provided) or prompt manual login
    3. Navigate to product page
    4. Submit order → capture payment QR code / payment URL
    5. Validate and return collected data
    """

    @property
    def name(self) -> str:
        return "browser"

    def __init__(self, task_id: str, config: dict[str, Any]):
        super().__init__(task_id, config)
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None

    async def execute(self) -> AsyncGenerator[dict, None]:
        config = self.config
        platform = config.get("platform", "jd")  # default to jd
        product_id = config.get("product_id", "")
        quantity = config.get("quantity", 1)
        headless = config.get("headless", False)
        cookie = config.get("cookie", "")
        impl_config = config.get("collection_config", {}).get("implementation", {})
        
        # Resolve platform config
        plat_cfg = PLATFORM_CONFIGS.get(platform)
        if not plat_cfg:
            yield error_step(f"不支持的平台: {platform}")
            return
        sel = plat_cfg["selectors"]

        collected = []
        try:
            # ── Step 1: Launch browser ──
            yield progress_step("launch", 10, f"启动浏览器（headless={headless}）...")
            
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self._page = await self._context.new_page()
            
            # Disable web driver detection
            await self._page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)
            
            yield progress_step("launch", 15, "浏览器已启动")

            # ── Step 2: Inject cookie ──
            if cookie:
                yield progress_step("cookie", 20, "注入会话 Cookie...")
                try:
                    cookie_data = json.loads(cookie) if isinstance(cookie, str) else cookie
                    if isinstance(cookie_data, list):
                        await self._context.add_cookies(cookie_data)
                    else:
                        await self._context.add_cookies([cookie_data])
                except (json.JSONDecodeError, TypeError) as e:
                    yield progress_step("cookie", 20, f"Cookie 格式错误: {e}，跳过注入")
            
            # ── Step 3: Navigate to base and verify login ──
            yield progress_step("navigate", 25, f"访问 {plat_cfg['name']}...")
            
            # First go to homepage to set cookies
            await self._page.goto(plat_cfg["base_url"], wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # Check if need login
            needs_login = False
            try:
                login_el = await self._page.query_selector(sel.get("login_detect", ""))
                if login_el:
                    page_text = await self._page.inner_text("body")
                    login_keywords = ["登录", "注册", "login", "sign in"]
                    if any(kw in (page_text or "").lower() for kw in login_keywords):
                        needs_login = True
            except Exception:
                pass
            
            if needs_login and not cookie:
                yield progress_step("navigate", 30, "需要登录，请在浏览器窗口中手动登录")
                # Wait up to 5 minutes for manual login
                await self._wait_for_login_success(self._page, plat_cfg, timeout=300)
            
            yield progress_step("navigate", 35, "登录验证通过")

            # ── Steps 4-8: Collect payment credentials ──
            for i in range(quantity):
                if self._cancelled:
                    yield progress_step("cancelled", 0, "任务已取消")
                    return

                base_progress = 35 + (i * 60 // quantity)

                # Step 4: Navigate to product page
                yield progress_step("product", base_progress, f"跳转到商品页 ({i+1}/{quantity})...")
                product_url = impl_config.get("product_url") or self._get_product_url(platform, product_id)
                
                try:
                    await self._page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
                except Exception as e:
                    yield error_step(f"商品页加载失败: {e}")
                    continue
                await asyncio.sleep(1.5)

                yield progress_step("product", base_progress + 5, f"已到达商品页 ({i+1}/{quantity})")

                # Step 5: Click buy/submit order
                yield progress_step("order", base_progress + 10, f"提交订单 ({i+1}/{quantity})...")
                
                await self._try_click_any(self._page, [
                    sel.get("buy_btn", ""),
                    sel.get("submit_order_btn", ""),
                    # Fallback: common buy buttons
                    "text=立即购买", "text=立即下单", "text=提交订单",
                    "text=去结算", "text=结算", "text=Buy Now",
                    "button:has-text('buy')", "a:has-text('buy')",
                    "[class*=buy]", "[class*=submit]",
                ])
                await asyncio.sleep(2)

                # Step 6: Wait for payment page
                yield progress_step("payment", base_progress + 20, f"等待支付页面 ({i+1}/{quantity})...")
                
                # Wait for QR code or payment URL
                payment_data = await self._capture_payment(self._page, plat_cfg, timeout=30)
                
                if payment_data:
                    collected.append(payment_data)
                    yield {
                        "step": "payment",
                        "status": "completed",
                        "message": f"已获取支付凭证 ({i+1}/{quantity})",
                        "progress": base_progress + 30,
                        "data": {"resource": payment_data},
                    }
                else:
                    # Fallback: capture current URL as payment link
                    fallback = {
                        "value": self._page.url,
                        "resource_type": "payment_link",
                        "metadata": json.dumps({
                            "platform": platform,
                            "product_id": product_id,
                            "method": "browser",
                            "page_title": await self._page.title(),
                        }, ensure_ascii=False),
                    }
                    collected.append(fallback)
                    yield {
                        "step": "payment",
                        "status": "completed",
                        "message": f"已获取支付链接 ({i+1}/{quantity})",
                        "progress": base_progress + 30,
                        "data": {"resource": fallback},
                    }

                # Step 7: Validate
                yield progress_step("validate", base_progress + 35, f"验证采集结果 ({i+1}/{quantity})")

            # ── Step 8: Complete ──
            yield {
                "step": "complete",
                "status": "completed",
                "message": f"采集完成，共 {len(collected)} 条",
                "progress": 100,
                "data": {"resources": collected},
            }

        except Exception as e:
            yield error_step(f"浏览器采集中断: {type(e).__name__}: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Close browser and release resources."""
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

    async def _wait_for_login_success(self, page, plat_cfg: dict, timeout: int = 300):
        """Wait for user to complete manual login. Polls navigation/URL changes."""
        sel = plat_cfg["selectors"]
        start_url = page.url
        for _ in range(timeout):
            if self._cancelled:
                return
            try:
                current = page.url
                # Check if we've navigated away from login page
                if current != start_url and "login" not in current.lower():
                    return
                # Check for logged-in indicator
                login_el = await page.query_selector(sel.get("login_detect", ""))
                if not login_el:
                    return
            except Exception:
                pass
            await asyncio.sleep(1)

    async def _capture_payment(self, page, plat_cfg: dict, timeout: int = 30) -> Optional[dict]:
        """Try to capture QR code or payment URL from the payment page."""
        sel = plat_cfg["selectors"]
        
        for _ in range(timeout):
            if self._cancelled:
                return None
            
            # 1. Try to find a QR code image
            qr_selectors = [
                sel.get("payment_qrcode", ""),
                "img[src*=qr]", "img[src*=qrcode]", "img[src*=pay]",
                "canvas", "div.qrcode img", "[class*=qrcode] img",
                "img[id*=qr]", "img[id*=code]",
            ]
            for qs in qr_selectors:
                if not qs:
                    continue
                try:
                    img = await page.query_selector(qs)
                    if img:
                        src = await img.get_attribute("src")
                        if src and src.startswith("data:image"):
                            return {
                                "value": src,
                                "resource_type": "qrcode",
                                "metadata": json.dumps({
                                    "source": "page_qrcode",
                                    "page_url": page.url,
                                }, ensure_ascii=False),
                            }
                except Exception:
                    pass

            # 2. Check if current URL matches payment pattern
            url_pattern = sel.get("payment_url_pattern", "")
            if url_pattern and re.search(url_pattern, page.url):
                return {
                    "value": page.url,
                    "resource_type": "payment_link",
                    "metadata": json.dumps({
                        "source": "payment_url",
                        "page_title": await page.title(),
                    }, ensure_ascii=False),
                }

            await asyncio.sleep(1)

        # 3. Last resort: return current URL
        current = page.url
        if current and "http" in current:
            return {
                "value": current,
                "resource_type": "payment_link",
                "metadata": json.dumps({
                    "source": "fallback_url",
                    "page_title": await page.title(),
                }, ensure_ascii=False),
            }
        return None

    async def _try_click_any(self, page, selectors: list[str]):
        """Try clicking any of the given selectors."""
        for selector in selectors:
            if not selector:
                continue
            try:
                el = await page.query_selector(selector)
                if el:
                    await el.click()
                    return True
            except Exception:
                pass
        return False

    def _get_product_url(self, platform: str, product_id: str) -> str:
        """Get product URL from product_id or implementation config."""
        config = self.config
        impl = config.get("collection_config", {}).get("implementation", {})
        if impl.get("product_url"):
            return impl["product_url"]
        
        templates = {
            "jd": f"https://item.jd.com/{product_id}.html",
            "taobao": f"https://item.taobao.com/item.htm?id={product_id}",
            "pdd": f"https://mobile.yangkeduo.com/goods.html?goods_id={product_id}",
        }
        return templates.get(platform, f"https://{platform}.com/products/{product_id}")


# ── Helper functions ──────────────────────────────────────────

def progress_step(step: str, progress: int, message: str) -> dict:
    return {"step": step, "status": "running", "message": message, "progress": progress}

def error_step(message: str) -> dict:
    return {"step": "error", "status": "failed", "message": message, "progress": 0}
