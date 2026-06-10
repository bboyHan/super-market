"""Open API — API Payer facing endpoints with MD5/HMAC signature verification.

Signature Algorithm (MD5 legacy, matching vbox-gin's PayDoc.vue):
  1. Sort all params by ASCII key ascending (excluding 'sign')
  2. Concatenate as key=value&key=value
  3. Append &key={API_Secret}
  4. MD5 hash → lowercase hex
"""
from __future__ import annotations
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.routing.engine import RoutingEngine
from app.infrastructure.persistence.postgres.session import get_db_session

router = APIRouter(prefix="/api/open", tags=["open"])


# ── Error codes matching API doc ──────────────────────────────

class OpenAPIError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


def err(code: int, msg: str):
    return {"code": code, "data": None, "msg": msg}


# ── Signature verification ────────────────────────────────────

SIGN_ERRORS = {
    40001: "签名错误",
    40002: "参数缺失",
    40004: "账户不存在",
    40003: "IP被限制",
}


def _sort_params(params: dict) -> str:
    """Sort params by ASCII key, concat as key=value&key=value."""
    return "&".join(f"{k}={params[k]}" for k in sorted(params.keys()))


def _md5_sign(payload: str, secret: str) -> str:
    """MD5 sign: payload + '&key=' + secret → MD5 lowercase."""
    return hashlib.md5((payload + f"&key={secret}").encode()).hexdigest()


def _verify_md5(params: dict, sign: str, secret: str) -> bool:
    """Verify MD5 signature."""
    payload = _sort_params({k: v for k, v in params.items() if k != "sign"})
    expected = _md5_sign(payload, secret)
    return expected == sign.lower()


async def _authenticate_payer(
    account: str,
    request: Request,
    session: AsyncSession,
) -> tuple | dict:
    """Verify API Key + IP whitelist. Returns (api_payer_row, secret) on success,
    or error dict on failure."""
    row = await session.execute(
        text("SELECT id, supplier_id, api_secret, callback_url, ip_whitelist, status "
             "FROM api_payers WHERE api_key=:ak").bindparams(ak=account))
    p = row.first()
    if not p:
        return err(40004, SIGN_ERRORS[40004])

    pid, sid, secret, cb_url, ip_wl, status = p
    if status != "ACTIVE":
        return err(40004, "账户已停用")

    # IP whitelist check
    client_ip = request.client.host if request.client else ""
    import json
    try:
        whitelist = json.loads(ip_wl) if isinstance(ip_wl, str) else (ip_wl or [])
    except (json.JSONDecodeError, TypeError):
        whitelist = []
    if whitelist and client_ip not in whitelist:
        return err(40003, SIGN_ERRORS[40003])

    return p, secret


# ── Helper: generate platform order_no ────────────────────────

def _gen_order_no() -> str:
    ts = __import__("time").time()
    rand = secrets.token_hex(3)
    return f"PO{int(ts)}{rand}"


# ── Endpoints ──────────────────────────────────────────────────

@router.post("/v1/products")
async def list_products(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Query purchasable products. Params: account, sign"""
    params = dict(await request.form()) or dict(request.query_params)
    account = params.get("account", "")
    sign = params.get("sign", "")

    if not account:
        return err(40002, "缺少 account 参数")
    if not sign:
        return err(40002, "缺少 sign 参数")

    try:
        result = await _authenticate_payer(account, request, session)
    except HTTPException as e:
        return e.detail if hasattr(e, 'detail') else err(40004, "验证失败")

    if isinstance(result, dict):
        return result
    payer, secret = result

    if not _verify_md5(params, sign, secret):
        return err(40001, SIGN_ERRORS[40001])

    sid = payer[1]
    rows = await session.execute(
        text("SELECT p.id, p.name, p.category, p.suggested_price "
             "FROM products p JOIN supplier_product_auth spa ON p.id=spa.product_id "
             "WHERE spa.supplier_id=:sid AND p.status=TRUE ORDER BY p.category")
        .bindparams(sid=sid))
    products = [
        {"product_id": str(r[0]), "product_name": r[1], "category": r[2],
         "price": r[3], "stock_status": "available"}
        for r in rows
    ]
    return {"code": 0, "data": products, "msg": "查询成功"}


@router.post("/v1/order/create")
async def create_order(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Create an order. Params: account, product_id, quantity, order_id, notify_url, sign"""
    params = dict(await request.form()) or dict(request.query_params)
    account = params.get("account", "")
    sign = params.get("sign", "")
    product_id = params.get("product_id", "")
    quantity_str = params.get("quantity", "1")
    client_order_id = params.get("order_id", "")
    notify_url = params.get("notify_url", "")

    # Validate required params
    missing = [k for k in ["account", "product_id", "order_id", "sign"] if not params.get(k)]
    if missing:
        return err(40002, f"缺少参数: {', '.join(missing)}")

    try:
        quantity = int(quantity_str)
    except ValueError:
        return err(40002, "quantity 必须为整数")
    if quantity < 1:
        return err(40002, "quantity 最小为1")

    try:
        result = await _authenticate_payer(account, request, session)
    except HTTPException as e:
        return e.detail if hasattr(e, 'detail') else err(40004, "验证失败")

    if isinstance(result, dict):
        return result
    payer_info, secret = result

    if not _verify_md5(params, sign, secret):
        return err(40001, SIGN_ERRORS[40001])

    pid, sid, _, default_cb_url, _, _ = payer_info

    # Check product exists and supplier is authorized
    prod = await session.execute(
        text("SELECT p.id, p.name, p.suggested_price, p.confirm_mode "
             "FROM products p JOIN supplier_product_auth spa ON p.id=spa.product_id "
             "WHERE spa.supplier_id=:sid AND p.id=:pid AND p.status=TRUE")
        .bindparams(sid=sid, pid=int(product_id)))
    pr = prod.first()
    if not pr:
        return err(40401, "货品不存在或无权访问")

    # Check duplicate client_order_id
    dup = await session.execute(
        text("SELECT id FROM orders WHERE client_order_id=:co AND api_payer_id=:apid AND supplier_id=:sid")
        .bindparams(co=client_order_id, apid=pid, sid=sid))
    if dup.first():
        return err(40005, "订单号重复")

    # Check inventory
    inv_count = await session.execute(
        text("SELECT count(*) FROM inventory_items WHERE product_id=:prid AND status='AVAILABLE'")
        .bindparams(prid=pr[0]))
    if inv_count.scalar() == 0:
        return err(50001, "库存不足")

    # Route to agent via RoutingEngine (with fallback to first-available)
    engine = RoutingEngine(session)
    agent_id = await engine.select_agent(pr[0], sid)

    if agent_id is not None:
        ag_row = await session.execute(
            text("SELECT id, name FROM agents WHERE id=:aid")
            .bindparams(aid=agent_id))
        ag = ag_row.first()
    else:
        # Fallback: first available agent with inventory
        agent = await session.execute(
            text("SELECT a.id, a.name FROM agents a JOIN inventory_items i ON i.agent_id=a.id "
                 "WHERE i.product_id=:prid AND i.status='AVAILABLE' AND a.supplier_id=:sid AND a.status='ACTIVE' LIMIT 1")
            .bindparams(prid=pr[0], sid=sid))
        ag = agent.first()
        if not ag:
            # Fallback: any active agent
            fb = await session.execute(
                text("SELECT id, name FROM agents WHERE supplier_id=:sid AND status='ACTIVE' LIMIT 1")
                .bindparams(sid=sid))
            ag = fb.first()
            if not ag:
                return err(50001, "无可用的代理商")

    total_amt = pr[2] * quantity
    order_no = _gen_order_no()
    cb_url = notify_url or default_cb_url or ""

    # Create order
    await session.execute(
        text("""INSERT INTO orders (order_no, client_order_id, api_payer_id, supplier_id, agent_id,
            product_id, quantity, amount, status, confirm_mode, callback_url, callback_status,
            expired_at)
        VALUES (:on, :co, :apid, :sid, :aid, :prid, :qty, :amt, 'PENDING', :cm, :cb, 'PENDING',
            NOW()+INTERVAL '30 minutes')""")
        .bindparams(on=order_no, co=client_order_id, apid=pid, sid=sid, aid=ag[0],
                    prid=pr[0], qty=quantity, amt=total_amt, cm=pr[3], cb=cb_url))

    # Freeze agent points
    wal = await session.execute(
        text("SELECT id, balance, frozen FROM wallets WHERE owner_type='AGENT' AND owner_id=:aid FOR UPDATE")
        .bindparams(aid=ag[0]))
    w = wal.first()
    if w and w[1] >= total_amt:
        nb = w[1] - total_amt
        nf = w[2] + total_amt
        await session.execute(
            text("UPDATE wallets SET balance=:b, frozen=:f, version=version+1, updated_at=NOW() WHERE id=:wid")
            .bindparams(b=nb, f=nf, wid=w[0]))
        await session.execute(
            text("INSERT INTO wallet_transactions (wallet_id, type, amount, balance_before, balance_after, "
                 "remark, status, operator_type, related_order_no) "
                 "VALUES (:wid, 'FREEZE', :amt, :bb, :ba, :rm, 'COMPLETED', 'SYSTEM', :on)")
            .bindparams(wid=w[0], amt=total_amt, bb=w[1], ba=nb, rm=f"订单 {order_no} 冻结", on=order_no))
        await session.execute(
            text("INSERT INTO point_freeze_records (wallet_id, order_no, agent_id, amount, status) "
                 "VALUES (:wid, :on, :aid, :amt, 'FROZEN')")
            .bindparams(wid=w[0], on=order_no, aid=ag[0], amt=total_amt))
        await session.execute(
            text("UPDATE agents SET frozen=frozen+:amt WHERE id=:aid").bindparams(amt=total_amt, aid=ag[0]))

    # ── 自动交付：消耗库存 → 写入交付记录 → 回调 ──
    deliveries_made = 0
    if ag and ag[0]:
        # 选取该代理商名下 AVAILABLE 的库存
        inv_rows = await session.execute(
            text("""SELECT id, content FROM inventory_items
                   WHERE agent_id=:aid AND product_id=:prid AND status='AVAILABLE'
                   ORDER BY created_at ASC LIMIT :qty FOR UPDATE""")
            .bindparams(aid=ag[0], prid=pr[0], qty=quantity))
        items = inv_rows.all()

        for inv_item in items:
            inv_id, content = inv_item
            # 标记库存为已消耗
            await session.execute(
                text("UPDATE inventory_items SET status='USED', order_no=:on WHERE id=:iid")
                .bindparams(on=order_no, iid=inv_id))
            # 写入交付记录
            await session.execute(
                text("INSERT INTO order_deliveries (order_no, type, content) VALUES (:on, :tp, :ct)")
                .bindparams(on=order_no, tp=pr[3] if pr[3] else 'card_key', ct=content))
            deliveries_made += 1

        if deliveries_made > 0:
            # 更新订单状态为 SUCCESS
            await session.execute(
                text("UPDATE orders SET status='SUCCESS', updated_at=NOW() WHERE order_no=:on")
                .bindparams(on=order_no))
            # 解冻对应积分
            wal2 = await session.execute(
                text("SELECT id, frozen FROM wallets WHERE owner_type='AGENT' AND owner_id=:aid FOR UPDATE")
                .bindparams(aid=ag[0]))
            w2 = wal2.first()
            if w2 and w2[1] >= total_amt:
                nf2 = w2[1] - total_amt
                await session.execute(
                    text("UPDATE wallets SET frozen=:f, version=version+1, updated_at=NOW() WHERE id=:wid")
                    .bindparams(f=nf2, wid=w2[0]))
                await session.execute(
                    text("UPDATE agents SET frozen=frozen-:amt WHERE id=:aid")
                    .bindparams(amt=total_amt, aid=ag[0]))
                await session.execute(
                    text("UPDATE point_freeze_records SET status='UNFROZEN' WHERE order_no=:on AND status='FROZEN'")
                    .bindparams(on=order_no))

    await session.commit()

    # ── 异步回调通知 API 支付商 ──
    if deliveries_made > 0 and cb_url:
        try:
            await _fire_callback(order_no, cb_url, {
                "order_no": order_no,
                "client_order_id": client_order_id,
                "product_id": product_id,
                "quantity": quantity,
                "total_price": total_amt,
                "status": "SUCCESS",
                "deliveries": deliveries_made,
            })
        except Exception:
            pass  # 回调失败由后台定时重试

    return {
        "code": 0,
        "data": {
            "platform_order_id": order_no,
            "client_order_id": client_order_id,
            "product_id": product_id,
            "quantity": quantity,
            "total_price": total_amt,
            "status": "SUCCESS" if deliveries_made > 0 else "PENDING",
            "deliveries": deliveries_made,
        },
        "msg": "创建成功" + (f"，已交付 {deliveries_made} 条" if deliveries_made > 0 else "，等待交付"),
    }


@router.post("/v1/order/query")
async def query_order(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Query order status and deliveries. Params: account, order_id, sign"""
    params = dict(await request.form()) or dict(request.query_params)
    account = params.get("account", "")
    sign = params.get("sign", "")
    client_order_id = params.get("order_id", "")

    if not account:
        return err(40002, "缺少 account 参数")
    if not sign:
        return err(40002, "缺少 sign 参数")
    if not client_order_id:
        return err(40002, "缺少 order_id 参数")

    try:
        result = await _authenticate_payer(account, request, session)
    except HTTPException as e:
        return e.detail if hasattr(e, 'detail') else err(40004, "验证失败")

    if isinstance(result, dict):
        return result
    payer_info, secret = result

    if not _verify_md5(params, sign, secret):
        return err(40001, SIGN_ERRORS[40001])

    pid = payer_info[0]

    # Find order
    row = await session.execute(
        text("SELECT order_no, client_order_id, product_id, quantity, amount, status, "
             "created_at, updated_at FROM orders "
             "WHERE client_order_id=:co AND api_payer_id=:apid")
        .bindparams(co=client_order_id, apid=pid))
    o = row.first()
    if not o:
        return err(40402, "订单不存在")

    # Get deliveries if SUCCESS
    deliveries = []
    if o[5] == "SUCCESS":
        d_rows = await session.execute(
            text("SELECT type, content, delivered_at FROM order_deliveries WHERE order_no=:on")
            .bindparams(on=o[0]))
        deliveries = [
            {"type": r[0], "content": r[1],
             "delivered_at": str(r[2]) if r[2] else None}
            for r in d_rows
        ]

    return {
        "code": 0,
        "data": {
            "platform_order_id": o[0],
            "client_order_id": o[1],
            "product_id": str(o[2]),
            "quantity": o[3],
            "total_price": o[4],
            "status": o[5],
            "deliveries": deliveries,
            "created_at": str(o[6]) if o[6] else None,
            "updated_at": str(o[7]) if o[7] else None,
        },
        "msg": "查询成功",
    }


# ── 异步回调 ──────────────────────────────────────


async def _fire_callback(order_no: str, callback_url: str, payload: dict) -> bool:
    """向 API 支付商发送订单回调通知（异步，fire-and-forget）。"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(callback_url, json=payload)
            if resp.status_code == 200:
                return True
            return False
    except Exception:
        return False
