"""CDP 引擎 — 通过 Chrome DevTools Protocol 注入拦截脚本。

原理：利用 Chrome 的远程调试协议，在你正在浏览的页面中
自动注入 XHR 拦截脚本，无需手动 F12 粘贴。

使用流程：
  1. Chrome 以 --remote-debugging-port=9222 启动
  2. 工具端 POST /cdp/connect → 连接到 Chrome
  3. 在 Chrome 中正常打开支付页面
  4. 工具端 POST /cdp/inject → 注入拦截脚本
  5. 用户点击支付 → 自动捕获支付码
  6. 工具端 GET /cdp/poll → 取回捕获结果
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from typing import Any, Optional

import urllib.request
import urllib.parse

logger = logging.getLogger("agent-terminal.capture.cdp")

# XHR 拦截脚本（会被 CDP 注入到目标页面）
INJECT_SCRIPT = """
(function(){
const X=XMLHttpRequest.prototype.open;
const XS=XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.open=function(m,u){this._url=u;return X.apply(this,arguments)};
XMLHttpRequest.prototype.send=function(b){
const u=this._url||'';
if(u.includes('web_save')){
const x=this;const rb=typeof b==='string'?b:'';
x.addEventListener('load',function(){
try{
const t=x.responseText;
const idx=t.indexOf('weixin://wxpay/bizpayurl?pr=');
if(idx>=0){
const end=Math.min(idx+80,t.length);
const url=t.substring(idx,end).split('"')[0].split(' ')[0].split(')')[0];
const o=(rb.match(/openid=([A-F0-9]+)/)||[])[1]||'';
window.__captured=JSON.stringify({url:url,openid:o,body:rb.slice(0,1000)});
console.log('[CDP] captured');
}}catch(e){}});
}
return XS.apply(this,arguments)};
console.log('[CDP] ready');
})();
"""


class CDPEngine:
    """CDP 采集引擎。"""

    def __init__(self):
        self._connected = False
        self._cdp_port = 9222
        self._on_credential = None

    @property
    def is_running(self) -> bool:
        return self._connected

    def set_callback(self, callback):
        self._on_credential = callback

    async def connect(self, port: int = 9222) -> bool:
        """连接到 Chrome 的 CDP 端口。"""
        import json
        try:
            resp = self._http_get(f"http://localhost:{port}/json/version")
            data = json.loads(resp)
            if "Browser" in data:
                self._connected = True
                self._cdp_port = port
                logger.info(f"CDP connected: {data.get('Browser', '')}")
                return True
        except Exception as e:
            logger.error(f"CDP connect failed: {e}")
        return False

    def _http_get(self, url: str) -> str:
        return urllib.request.urlopen(url, timeout=5).read().decode()

    def _http_post(self, url: str, data: dict) -> dict:
        import json
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                      headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=10).read().decode())

    async def disconnect(self):
        self._connected = False
        logger.info("CDP disconnected")

    async def _cdp_send(self, page_id: str, method: str, params: dict = None) -> dict:
        """发送 CDP 命令到指定页面。"""
        payload = {"id": 1, "method": method, "params": params or {}}
        return self._http_post(
            f"http://localhost:{self._cdp_port}/devtools/page/{page_id}",
            payload,
        )

    async def get_active_page(self) -> Optional[dict]:
        """获取用户当前活动页面。"""
        import json
        try:
            resp = self._http_get(f"http://localhost:{self._cdp_port}/json")
            pages = json.loads(resp)
            pages.sort(key=lambda p: -p.get("lastActivity", 0))
            for p in pages:
                url = p.get("url", "")
                if url and "chrome-extension" not in url and "chrome://" not in url:
                    return p
            return pages[0] if pages else None
        except Exception as e:
            logger.error(f"Get active page error: {e}")
            return None

    async def inject_script(self, page_id: str) -> bool:
        """向页面注入 XHR 拦截脚本。"""
        try:
            result = await self._cdp_send(page_id, "Runtime.evaluate", {
                "expression": INJECT_SCRIPT,
                "awaitPromise": False,
            })
            return result.get("result", {}).get("result", {}).get("type") != "error"
        except Exception as e:
            logger.error(f"Inject error: {e}")
            return False

    async def poll_captured(self, page_id: str, timeout: int = 120) -> Optional[dict]:
        """轮询页面中的 __captured 变量。"""
        start = __import__("time").time()
        while __import__("time").time() - start < timeout:
            try:
                result = await self._cdp_send(page_id, "Runtime.evaluate", {
                    "expression": "window.__captured || null",
                    "awaitPromise": False,
                })
                value = result.get("result", {}).get("result", {}).get("value")
                if value:
                    data = json.loads(value)
                    # 清除捕获标记（避免重复读取）
                    await self._cdp_send(page_id, "Runtime.evaluate", {
                        "expression": "window.__captured = null",
                    })
                    return data
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return None

    async def inject_and_wait(self, timeout: int = 120) -> Optional[dict]:
        """注入脚本到当前页面并等待捕获。"""
        page = await self.get_active_page()
        if not page:
            logger.warning("No active page found")
            return None

        page_id = page.get("id")
        if not page_id:
            logger.warning("Page has no ID")
            return None

        logger.info(f"Injecting into: {page.get('url', '')[:60]}...")
        ok = await self.inject_script(page_id)
        if not ok:
            logger.warning("Script injection failed")
            return None

        logger.info(f"Waiting for payment capture (timeout={timeout}s)...")
        data = await self.poll_captured(page_id, timeout)
        return data

    async def collect(self, timeout: int = 120) -> Optional[Any]:
        """一键采集：注入 + 等待 + 回传。"""
        data = await self.inject_and_wait(timeout)
        if not data:
            return None

        # 识别账号
        openid = data.get("openid", "")
        account = self._identify_account(openid)

        # 构建凭证
        from models import Credential, CredentialType
        cred = Credential(
            type=CredentialType.PAYMENT_URL,
            value=data.get("url", ""),
            platform="QQ Midas",
            account_id=account.get("id"),
            account_name=account.get("nickname", "") or openid[:12] if openid else "未知账号",
            source_pipeline="cdp",
            metadata={"source": "cdp_web_save", "openid": openid, "account_name": account.get("nickname", "")},
        )

        if self._on_credential:
            await self._on_credential(cred)
        return cred

    @staticmethod
    def _identify_account(openid: str) -> dict:
        if not openid:
            return {"id": None, "nickname": "未知账号"}
        try:
            from storage.db import get_cursor
            with get_cursor() as cursor:
                row = cursor.execute(
                    "SELECT id, nickname FROM qq_accounts WHERE midas_openid=?",
                    (openid,),
                ).fetchone()
                if row:
                    return {"id": row["id"], "nickname": row["nickname"] or openid[:12]}
        except Exception:
            pass
        return {"id": None, "nickname": openid[:12]}

    @staticmethod
    def launch_chrome(port: int = 9222) -> Optional[subprocess.Popen]:
        """自动启动带调试端口的 Chrome。"""
        paths = [
            "C:/Program Files/Google/Chrome/Application/chrome.exe",
            "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
            os.path.expanduser("~/AppData/Local/Google/Chrome/Application/chrome.exe"),
        ]
        for path in paths:
            if os.path.isfile(path):
                try:
                    proc = subprocess.Popen(
                        [path, f"--remote-debugging-port={port}",
                         "--user-data-dir=C:/Users/1/.chrome-debug",
                         "--new-window"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    logger.info(f"Chrome launched on port {port}")
                    return proc
                except Exception as e:
                    logger.warning(f"Chrome launch failed: {e}")
        return None


engine = CDPEngine()
