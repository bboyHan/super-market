"""Merchant API — supplier-facing, JWT-authenticated, uses user's supplier_id."""
from __future__ import annotations
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.postgres.session import get_db_session
from app.interfaces.api.auth.router import get_current_user

router = APIRouter(prefix="/api/merchant", tags=["merchant"])


# ── Auth helper ──────────────────────────────────────────────

async def _get_supplier_id(user: dict = Depends(get_current_user)) -> int:
    """Extract supplier_id from JWT. Supplier's ref_id = their supplier.id.
    Admin can pass ?as_supplier_id=N to impersonate."""
    role = user.get("role")
    ref_id = user.get("ref_id")
    if role == "ADMIN":
        return ref_id or 1  # default to supplier 1 for admin
    if role == "SUPPLIER":
        if not ref_id:
            raise HTTPException(status_code=403, detail="无效的供应商身份")
        return ref_id
    raise HTTPException(status_code=403, detail="无权访问")


async def _get_agent_id(user: dict = Depends(get_current_user)) -> int:
    """Extract agent_id from JWT."""
    if user.get("role") != "AGENT":
        raise HTTPException(status_code=403, detail="需要代理商权限")
    ref_id = user.get("ref_id")
    if not ref_id:
        raise HTTPException(status_code=403, detail="无效的代理商身份")
    return ref_id


# ── DTOs ─────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    nickname: str = Field(..., max_length=128)
    username: str = Field(default="", max_length=64)
    password: str = Field(default="", max_length=64)

class ApiPayerCreate(BaseModel):
    nickname: str = Field(..., max_length=128)


# ── Dashboard ────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    rows = await session.execute(text("""
        SELECT
            COALESCE(SUM(CASE WHEN o.status='SUCCESS' AND o.created_at>=CURRENT_DATE
                THEN o.amount ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN o.created_at>=CURRENT_DATE-INTERVAL'1 day'
                AND o.created_at<CURRENT_DATE AND o.status='SUCCESS'
                THEN o.amount ELSE 0 END), 0),
            (SELECT count(*) FROM agents WHERE supplier_id=:sid AND status='ACTIVE'),
            (SELECT count(*) FROM api_payers WHERE supplier_id=:sid AND status='ACTIVE'),
            (SELECT COALESCE(balance,0) FROM wallets WHERE owner_type='SUPPLIER' AND owner_id=:sid)
        FROM orders o WHERE o.supplier_id = :sid
    """).bindparams(sid=sid))
    r = rows.first()
    return {"code": 0, "data": {
        "today_amount": r[0] or 0, "yesterday_amount": r[1] or 0,
        "agent_count": r[2] or 0, "apayer_count": r[3] or 0,
        "wallet_balance": r[4] or 0,
    }}


# ── Orders ───────────────────────────────────────────────────

@router.get("/orders")
async def list_orders(
    status: str = "", page: int = 1, limit: int = 20,
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    where = f"o.supplier_id = {sid}"
    if status:
        where += f" AND o.status = '{status}'"
    
    total = await session.execute(text(f"SELECT count(*) FROM orders o WHERE {where}"))
    rows = await session.execute(text(f"""
        SELECT o.order_no, o.amount, o.status, o.confirm_mode, o.created_at,
               ap.name, p.name, a.name
        FROM orders o LEFT JOIN api_payers ap ON o.api_payer_id=ap.id
        LEFT JOIN products p ON o.product_id=p.id
        LEFT JOIN agents a ON o.agent_id=a.id
        WHERE {where} ORDER BY o.created_at DESC LIMIT {limit} OFFSET {(page-1)*limit}
    """))
    return {"code": 0, "data": {
        "items": [{"order_no": r[0], "amount": r[1], "status": r[2], "confirm_mode": r[3],
                    "created_at": str(r[4]) if r[4] else None, "api_payer_name": r[5],
                    "product_name": r[6], "agent_name": r[7]} for r in rows],
        "total": total.scalar() or 0, "page": page, "limit": limit,
    }}


@router.post("/orders/{order_no}/confirm")
async def confirm_payment(
    order_no: str,
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    row = await session.execute(
        text("SELECT id, status, supplier_id FROM orders WHERE order_no=:on FOR UPDATE")
        .bindparams(on=order_no)
    )
    o = row.first()
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    if o[2] != sid:
        raise HTTPException(status_code=403, detail="无权操作此订单")
    if o[1] != "PENDING":
        raise HTTPException(status_code=400, detail=f"当前状态 {o[1]} 不可确认")

    await session.execute(
        text("UPDATE orders SET status='DELIVERING', updated_at=NOW() WHERE order_no=:on")
        .bindparams(on=order_no)
    )
    await session.commit()
    # Enqueue callback for the status change
    from app.infrastructure.callback.worker import enqueue_callback
    await enqueue_callback(order_no, session)
    await session.commit()
    return {"code": 0, "data": {"order_no": order_no, "status": "DELIVERING"},
            "message": "已确认收款"}


@router.post("/orders/{order_no}/deliver")
async def agent_deliver(
    order_no: str, delivery_content: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    # Agent deliver doesn't need supplier_id check — agent delivers their own orders

    row = await session.execute(
        text("SELECT id, status, agent_id, amount, product_id, supplier_id, callback_url "
             "FROM orders WHERE order_no=:on FOR UPDATE").bindparams(on=order_no)
    )
    o = row.first()
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    if o[1] != "DELIVERING":
        raise HTTPException(status_code=400, detail=f"当前状态 {o[1]} 不可交付")

    aid, amount, pid = o[2], o[3], o[4]

    # Deduct frozen points
    w = await session.execute(
        text("SELECT id, frozen FROM wallets WHERE owner_type='AGENT' AND owner_id=:aid FOR UPDATE")
        .bindparams(aid=aid)
    )
    wal = w.first()
    if wal and wal[1] >= amount:
        await session.execute(
            text("UPDATE wallets SET frozen=frozen-:amt, total_consumed=total_consumed+:amt, "
                 "version=version+1, updated_at=NOW() WHERE id=:wid")
            .bindparams(amt=amount, wid=wal[0])
        )
        await session.execute(
            text("INSERT INTO wallet_transactions (wallet_id, type, amount, balance_before, balance_after, "
                 "remark, status, operator_type, related_order_no) VALUES "
                 "(:wid, 'CONSUME', :amt, :bb, :ba, :rm, 'COMPLETED', 'SYSTEM', :on)")
            .bindparams(wid=wal[0], amt=amount, bb=wal[1]+amount, ba=wal[1],
                       rm=f"订单 {order_no} 扣减", on=order_no)
        )
        await session.execute(
            text("UPDATE point_freeze_records SET status='DEDUCTED', deducted_at=NOW() WHERE order_no=:on")
            .bindparams(on=order_no)
        )

    # Save delivery
    content = delivery_content or f"AUTO-{order_no}-{__import__('time').time():.0f}"
    await session.execute(
        text("INSERT INTO order_deliveries (order_no, type, content) VALUES (:on, 'card_key', :c)")
        .bindparams(on=order_no, c=content)
    )

    # Mark inventory as used
    await session.execute(
        text("UPDATE inventory_items SET status='USED', order_no=:on WHERE id=("
             "SELECT id FROM inventory_items WHERE agent_id=:aid AND product_id=:pid AND status='AVAILABLE' LIMIT 1)")
        .bindparams(on=order_no, aid=aid, pid=pid)
    )

    # Mark order SUCCESS
    await session.execute(
        text("UPDATE orders SET status='SUCCESS', paid_at=NOW(), updated_at=NOW() WHERE order_no=:on")
        .bindparams(on=order_no)
    )
    await session.commit()

    # Enqueue proper callback with retry
    from app.infrastructure.callback.worker import enqueue_callback, process_one
    await enqueue_callback(order_no, session)
    await session.commit()

    # Try immediate send (non-blocking)
    import asyncio
    asyncio.create_task(_immediate_callback(order_no))

    return {"code": 0, "data": {"order_no": order_no, "status": "SUCCESS", "delivery_content": content},
            "message": "交付成功"}


async def _immediate_callback(order_no: str):
    """Quick first callback attempt. Falls back to retry queue on failure."""
    from app.infrastructure.persistence.postgres.session import async_session_factory
    async with async_session_factory() as session:
        try:
            from app.infrastructure.callback.worker import process_one
            await process_one(order_no, session)
        except Exception:
            await session.rollback()


@router.get("/orders/{order_no}/deliveries")
async def get_deliveries(order_no: str, session: AsyncSession = Depends(get_db_session)):
    rows = await session.execute(
        text("SELECT type, content, delivered_at FROM order_deliveries WHERE order_no=:on ORDER BY id")
        .bindparams(on=order_no)
    )
    return {"code": 0, "data": [{"type": r[0], "content": r[1],
                                  "delivered_at": str(r[2]) if r[2] else None} for r in rows]}


# ── Products ─────────────────────────────────────────────────

@router.get("/products")
async def list_products(
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    rows = await session.execute(
        text("SELECT p.id, p.name, p.category, p.face_value, p.suggested_price, "
             "p.collection_config, spa.status, p.status AS product_status "
             "FROM products p JOIN supplier_product_auth spa ON p.id=spa.product_id "
             "WHERE spa.supplier_id=:sid ORDER BY p.category")
        .bindparams(sid=sid))
    return {"code": 0, "data": [{"id": r[0], "name": r[1], "category": r[2],
                                  "face_value": r[3], "suggested_price": r[4],
                                  "collection_config": r[5] if isinstance(r[5], dict) else {},
                                  "authorized": bool(r[6]), "status": bool(r[7])} for r in rows]}


# ── Agents (supplier manages their own) ──────────────────────

@router.get("/agents")
async def list_agents(
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    rows = await session.execute(
        text("SELECT a.id, a.name, a.balance, a.frozen, a.status, "
             "COALESCE(u.username, '') as username "
             "FROM agents a LEFT JOIN users u ON u.role='AGENT' AND u.reference_id=a.id "
             "WHERE a.supplier_id=:sid ORDER BY a.id")
        .bindparams(sid=sid))
    return {"code": 0, "data": [{"id": r[0], "nickname": r[1], "balance": r[2],
                                  "frozen": r[3], "status": r[4], "username": r[5]} for r in rows]}


@router.post("/agents")
async def create_agent(
    req: AgentCreate,
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Create agent + user account with login credentials."""
    import secrets

    # Use custom credentials or auto-generate
    if req.username and req.username.strip():
        username = req.username.strip()
        # Check unique
        dup = await session.execute(text("SELECT id FROM users WHERE username=:u").bindparams(u=username))
        if dup.first():
            raise HTTPException(status_code=400, detail=f"用户名 {username} 已存在")
    else:
        username = f"agent_{secrets.token_hex(4)}"
        while await session.execute(text("SELECT id FROM users WHERE username=:u").bindparams(u=username)):
            username = f"agent_{secrets.token_hex(4)}"

    password = req.password or secrets.token_hex(8)

    row = await session.execute(
        text("INSERT INTO agents (supplier_id, name) VALUES (:sid, :n) RETURNING id")
        .bindparams(sid=sid, n=req.nickname))
    aid = row.scalar()

    await session.execute(
        text("INSERT INTO users (username, password_hash, role, reference_id) "
             "VALUES (:u, crypt(:pw, gen_salt('bf')), 'AGENT', :rid)")
        .bindparams(u=username, pw=password, rid=aid))

    await session.execute(
        text("INSERT INTO wallets (owner_type, owner_id, balance) VALUES ('AGENT', :aid, 0)")
        .bindparams(aid=aid))

    await session.commit()
    return {"code": 0, "data": {"id": aid, "nickname": req.nickname,
                                 "username": username, "password": password},
            "message": f"代理商 [{req.nickname}] 创建成功"}


@router.put("/agents/{aid}")
async def update_agent_status(
    aid: int, status: str,
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    await session.execute(
        text("UPDATE agents SET status=:s WHERE id=:aid AND supplier_id=:sid")
        .bindparams(s=status, aid=aid, sid=sid))
    await session.commit()
    return {"code": 0, "message": "更新成功"}


@router.get("/agents/{aid}/credentials")
async def get_agent_credentials(
    aid: int,
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Get agent login username. Password is masked — use reset endpoint to change."""
    agent = await session.execute(
        text("SELECT id FROM agents WHERE id=:aid AND supplier_id=:sid").bindparams(aid=aid, sid=sid))
    if not agent.first():
        raise HTTPException(status_code=404, detail="代理商不存在")

    row = await session.execute(
        text("SELECT username FROM users WHERE role='AGENT' AND reference_id=:aid").bindparams(aid=aid))
    u = row.first()
    if not u:
        raise HTTPException(status_code=404, detail="未找到登录账号")
    return {"code": 0, "data": {"agent_id": aid, "username": u[0]}}


@router.post("/agents/{aid}/reset-password")
async def reset_agent_password(
    aid: int,
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Reset agent password. Returns new password."""
    import secrets
    agent = await session.execute(
        text("SELECT id FROM agents WHERE id=:aid AND supplier_id=:sid").bindparams(aid=aid, sid=sid))
    if not agent.first():
        raise HTTPException(status_code=404, detail="代理商不存在")

    new_pw = secrets.token_hex(8)
    await session.execute(
        text("UPDATE users SET password_hash=crypt(:pw, gen_salt('bf')) WHERE role='AGENT' AND reference_id=:aid")
        .bindparams(pw=new_pw, aid=aid))
    await session.commit()

    row = await session.execute(
        text("SELECT username FROM users WHERE role='AGENT' AND reference_id=:aid").bindparams(aid=aid))
    username = row.scalar() or "-"
    return {"code": 0, "data": {"agent_id": aid, "username": username, "new_password": new_pw},
            "message": "密码已重置"}


# ── API Payers (supplier manages their own) ──────────────────

@router.get("/api-payers")
async def list_api_payers(
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    rows = await session.execute(
        text("SELECT id, name, api_key, api_secret, callback_url, status FROM api_payers "
             "WHERE supplier_id=:sid ORDER BY id").bindparams(sid=sid))
    return {"code": 0, "data": [{"id": r[0], "nickname": r[1], "api_key": r[2],
                                  "api_secret": r[3], "callback_url": r[4], "status": r[5]}
                                 for r in rows]}


@router.post("/api-payers")
async def create_api_payer(
    req: ApiPayerCreate,
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    api_key = f"sk_{secrets.token_hex(16)}"
    api_secret = f"ss_{secrets.token_hex(32)}"
    row = await session.execute(
        text("INSERT INTO api_payers (supplier_id, name, api_key, api_secret) "
             "VALUES (:sid, :n, :ak, :sec) RETURNING id")
        .bindparams(sid=sid, n=req.nickname, ak=api_key, sec=api_secret))
    pid = row.scalar()
    await session.commit()
    return {"code": 0, "data": {"id": pid, "nickname": req.nickname,
                                 "api_key": api_key, "api_secret": api_secret},
            "message": "API支付商创建成功"}


@router.put("/api-payers/{pid}")
async def update_api_payer_status(
    pid: int, status: str,
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    await session.execute(
        text("UPDATE api_payers SET status=:s WHERE id=:pid AND supplier_id=:sid")
        .bindparams(s=status, pid=pid, sid=sid))
    await session.commit()
    return {"code": 0, "message": "更新成功"}


# ── Wallet ───────────────────────────────────────────────────

@router.get("/wallet")
async def get_wallet(
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    row = await session.execute(
        text("SELECT id, balance, frozen, total_recharge, total_consumed, total_transferred_out "
             "FROM wallets WHERE owner_type='SUPPLIER' AND owner_id=:sid").bindparams(sid=sid))
    w = row.first()
    if not w:
        raise HTTPException(status_code=404, detail="钱包不存在")
    return {"code": 0, "data": {"wallet_id": w[0], "balance": w[1], "frozen": w[2],
                                 "total_recharge": w[3], "total_consumed": w[4],
                                 "total_transferred_out": w[5], "available": w[1]-w[2]}}


@router.post("/wallet/recharge")
async def recharge(
    amount: int, remark: str = "",
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="金额必须大于0")
    w = await session.execute(
        text("SELECT id, balance FROM wallets WHERE owner_type='SUPPLIER' AND owner_id=:sid FOR UPDATE")
        .bindparams(sid=sid))
    wal = w.first()
    if not wal:
        raise HTTPException(status_code=404, detail="钱包不存在")
    wid, old_bal = wal
    new_bal = old_bal + amount
    await session.execute(
        text("UPDATE wallets SET balance=:b, total_recharge=total_recharge+:amt, "
             "version=version+1, updated_at=NOW() WHERE id=:wid")
        .bindparams(b=new_bal, amt=amount, wid=wid))
    await session.execute(
        text("INSERT INTO wallet_transactions (wallet_id, type, amount, balance_before, balance_after, remark, status, operator_type) "
             "VALUES (:wid, 'RECHARGE', :amt, :bb, :ba, :rm, 'COMPLETED', 'SUPPLIER')")
        .bindparams(wid=wid, amt=amount, bb=old_bal, ba=new_bal, rm=remark or "USDT充值"))
    await session.commit()
    return {"code": 0, "data": {"balance": new_bal, "amount": amount}}


@router.post("/wallet/transfer")
async def transfer_to_agent(
    agent_id: int, amount: int,
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="金额必须大于0")
    # Verify agent belongs to this supplier
    ag = await session.execute(
        text("SELECT id FROM agents WHERE id=:aid AND supplier_id=:sid").bindparams(aid=agent_id, sid=sid))
    if not ag.first():
        raise HTTPException(status_code=404, detail="代理商不存在或不属于你")

    s = await session.execute(
        text("SELECT id, balance FROM wallets WHERE owner_type='SUPPLIER' AND owner_id=:sid FOR UPDATE")
        .bindparams(sid=sid))
    sw = s.first()
    if not sw or sw[1] < amount:
        raise HTTPException(status_code=400, detail="积分不足")

    a = await session.execute(
        text("SELECT id, balance FROM wallets WHERE owner_type='AGENT' AND owner_id=:aid FOR UPDATE")
        .bindparams(aid=agent_id))
    aw = a.first()
    if not aw:
        raise HTTPException(status_code=404, detail="代理商钱包不存在")

    sw_id, sw_bal = sw
    aw_id, aw_bal = aw
    new_sw = sw_bal - amount
    new_aw = aw_bal + amount

    await session.execute(
        text("UPDATE wallets SET balance=:b, total_transferred_out=total_transferred_out+:amt, version=version+1, updated_at=NOW() WHERE id=:wid")
        .bindparams(b=new_sw, amt=amount, wid=sw_id))
    await session.execute(
        text("UPDATE wallets SET balance=:b, total_transferred_in=total_transferred_in+:amt, version=version+1, updated_at=NOW() WHERE id=:wid")
        .bindparams(b=new_aw, amt=amount, wid=aw_id))

    await session.execute(
        text("INSERT INTO wallet_transactions (wallet_id, type, amount, balance_before, balance_after, remark, status, operator_type) "
             "VALUES (:wid, 'TRANSFER_OUT', :amt, :bb, :ba, :rm, 'COMPLETED', 'SUPPLIER')")
        .bindparams(wid=sw_id, amt=amount, bb=sw_bal, ba=new_sw, rm=f"划转代理商#{agent_id}"))
    await session.execute(
        text("INSERT INTO wallet_transactions (wallet_id, type, amount, balance_before, balance_after, remark, status, operator_type) "
             "VALUES (:wid, 'TRANSFER_IN', :amt, :bb, :ba, :rm, 'COMPLETED', 'SYSTEM')")
        .bindparams(wid=aw_id, amt=amount, bb=aw_bal, ba=new_aw, rm="接收供应商划转"))

    await session.execute(
        text("UPDATE agents SET balance=balance+:amt WHERE id=:aid").bindparams(amt=amount, aid=agent_id))
    await session.commit()
    return {"code": 0, "data": {"supplier_balance": new_sw, "agent_balance": new_aw, "amount": amount}}


@router.get("/wallet/transactions")
async def get_transactions(
    page: int = 1, limit: int = 20, type_filter: str = "",
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    where = f"w.owner_type='SUPPLIER' AND w.owner_id={sid}"
    if type_filter:
        where += f" AND wt.type='{type_filter}'"
    total = await session.execute(text(f"SELECT count(*) FROM wallet_transactions wt JOIN wallets w ON wt.wallet_id=w.id WHERE {where}"))
    rows = await session.execute(text(f"""
        SELECT wt.id, wt.type, wt.amount, wt.balance_before, wt.balance_after, wt.remark, wt.status, wt.created_at
        FROM wallet_transactions wt JOIN wallets w ON wt.wallet_id=w.id
        WHERE {where} ORDER BY wt.created_at DESC LIMIT {limit} OFFSET {(page-1)*limit}
    """))
    return {"code": 0, "data": {"items": [{"id": r[0], "type": r[1], "amount": r[2], "balance_before": r[3],
                                            "balance_after": r[4], "remark": r[5], "status": r[6],
                                            "created_at": str(r[7]) if r[7] else None} for r in rows],
                                 "total": total.scalar() or 0, "page": page, "limit": limit}}


# ── Agent Orders ──────────────────────────────────────────────

@router.get("/agent/orders")
async def list_agent_orders(
    status: str = "", page: int = 1, limit: int = 20,
    aid: int = Depends(_get_agent_id),
    session: AsyncSession = Depends(get_db_session),
):
    """List orders assigned to this agent (DELIVERING)."""
    where = f"o.agent_id = {aid}"
    if status:
        where += f" AND o.status = '{status}'"

    total = await session.execute(text(f"SELECT count(*) FROM orders o WHERE {where}"))
    rows = await session.execute(text(f"""
        SELECT o.order_no, o.amount, o.status, o.created_at,
               ap.name, p.name
        FROM orders o LEFT JOIN api_payers ap ON o.api_payer_id=ap.id
        LEFT JOIN products p ON o.product_id=p.id
        WHERE {where} ORDER BY o.created_at DESC LIMIT {limit} OFFSET {(page-1)*limit}
    """))
    return {"code": 0, "data": {
        "items": [{"order_no": r[0], "amount": r[1], "status": r[2],
                    "created_at": str(r[3]) if r[3] else None, "api_payer_name": r[4],
                    "product_name": r[5]} for r in rows],
        "total": total.scalar() or 0, "page": page, "limit": limit,
    }}


# ── Agent Wallet ──────────────────────────────────────────────


@router.get("/agent/wallet")
async def get_agent_wallet(
    aid: int = Depends(_get_agent_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Get the authenticated agent's wallet information."""
    row = await session.execute(
        text("SELECT id, balance, frozen, total_recharge, total_consumed "
             "FROM wallets WHERE owner_type='AGENT' AND owner_id=:aid")
        .bindparams(aid=aid))
    w = row.first()
    if not w:
        row = await session.execute(
            text("INSERT INTO wallets (owner_type, owner_id, balance, frozen) "
                 "VALUES ('AGENT', :aid, 0, 0) RETURNING id, balance, frozen")
            .bindparams(aid=aid))
        w = row.first()
    return {"code": 0, "data": {
        "wallet_id": w[0], "balance": w[1], "frozen": w[2],
        "total_recharge": w[3] if len(w) > 3 else 0,
        "total_consumed": w[4] if len(w) > 4 else 0,
        "available": w[1] - w[2],
    }}


# ── Finance Stats ────────────────────────────────────────────

@router.get("/finance/merchant-stats")
async def get_merchant_stats(
    days: int = 3,
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    rows = await session.execute(text(f"""
        SELECT ap.name, DATE(o.created_at), COUNT(*),
               COUNT(*) FILTER (WHERE o.status='SUCCESS'),
               COALESCE(SUM(o.amount),0), COALESCE(SUM(o.amount) FILTER (WHERE o.status='SUCCESS'),0)
        FROM orders o JOIN api_payers ap ON o.api_payer_id=ap.id
        WHERE o.supplier_id={sid} AND o.created_at>=CURRENT_DATE-{days}::INTERVAL
        GROUP BY ap.name, DATE(o.created_at) ORDER BY ap.name, stat_date DESC
    """))
    return {"code": 0, "data": [{"merchant_name": r[0], "date": str(r[1]) if r[1] else None,
                                  "total_orders": r[2], "success_orders": r[3],
                                  "total_amount": r[4], "success_amount": r[5]} for r in rows]}


@router.get("/finance/category-stats")
async def get_category_stats(
    days: int = 3,
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    rows = await session.execute(text(f"""
        SELECT p.name, p.category, DATE(o.created_at), COUNT(*), COALESCE(SUM(o.amount),0)
        FROM orders o JOIN products p ON o.product_id=p.id
        WHERE o.supplier_id={sid} AND o.created_at>=CURRENT_DATE-{days}::INTERVAL
        GROUP BY p.name, p.category, DATE(o.created_at) ORDER BY p.category, stat_date DESC
    """))
    return {"code": 0, "data": [{"product_name": r[0], "category": r[1], "date": str(r[2]) if r[2] else None,
                                  "total_orders": r[3], "total_amount": r[4]} for r in rows]}


# ── Daily Stats (对账看板) ────────────────────────────────────

@router.get("/daily-stats/merchant")
async def daily_stats_merchant(
    date: str = "",
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    """按API支付商日结。如果当天无统计数据，则从 orders 表实时查询。"""
    target_date = date or str(__import__("datetime").date.today())

    # Try daily_stats_merchant first
    rows = await session.execute(text("""
        SELECT d.api_payer_id, ap.name,
               d.total_orders, d.success_orders,
               d.total_amount, d.success_amount
        FROM daily_stats_merchant d
        JOIN api_payers ap ON d.api_payer_id = ap.id
        WHERE d.supplier_id = :sid AND d.stat_date = CAST(:dt AS DATE)
        ORDER BY ap.name
    """).bindparams(sid=sid, dt=target_date))
    result = rows.all()
    if result:
        return {"code": 0, "data": [{
            "api_payer_id": r[0], "merchant_name": r[1],
            "total_orders": r[2], "success_orders": r[3],
            "total_amount": r[4], "success_amount": r[5],
        } for r in result]}

    # Fallback: query from orders
    rows = await session.execute(text("""
        SELECT o.api_payer_id, ap.name,
               COUNT(*) AS total_orders,
               COUNT(*) FILTER (WHERE o.status = 'SUCCESS') AS success_orders,
               COALESCE(SUM(o.amount), 0) AS total_amount,
               COALESCE(SUM(o.amount) FILTER (WHERE o.status = 'SUCCESS'), 0) AS success_amount
        FROM orders o
        JOIN api_payers ap ON o.api_payer_id = ap.id
        WHERE o.supplier_id = :sid
          AND o.created_at >= CAST(:dt AS DATE)
          AND o.created_at < (CAST(:dt AS DATE) + INTERVAL '1 day')
        GROUP BY o.api_payer_id, ap.name
        ORDER BY ap.name
    """).bindparams(sid=sid, dt=target_date))
    return {"code": 0, "data": [{
        "api_payer_id": r[0], "merchant_name": r[1],
        "total_orders": r[2], "success_orders": r[3],
        "total_amount": r[4], "success_amount": r[5],
    } for r in rows]}


@router.get("/daily-stats/category")
async def daily_stats_category(
    date: str = "",
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    """按品类日结。如果当天无统计数据，则从 orders 表实时查询。"""
    target_date = date or str(__import__("datetime").date.today())

    # Try daily_stats_category first
    rows = await session.execute(text("""
        SELECT d.product_id, p.name, p.category,
               d.total_orders, d.total_amount
        FROM daily_stats_category d
        JOIN products p ON d.product_id = p.id
        WHERE d.supplier_id = :sid AND d.stat_date = CAST(:dt AS DATE)
        ORDER BY p.category, p.name
    """).bindparams(sid=sid, dt=target_date))
    result = rows.all()
    if result:
        return {"code": 0, "data": [{
            "product_id": r[0], "product_name": r[1], "category": r[2],
            "total_orders": r[3], "total_amount": r[4],
        } for r in result]}

    # Fallback: query from orders
    rows = await session.execute(text("""
        SELECT o.product_id, p.name, p.category,
               COUNT(*) AS total_orders,
               COALESCE(SUM(o.amount), 0) AS total_amount
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.supplier_id = :sid
          AND o.created_at >= CAST(:dt AS DATE)
          AND o.created_at < (CAST(:dt AS DATE) + INTERVAL '1 day')
        GROUP BY o.product_id, p.name, p.category
        ORDER BY p.category, p.name
    """).bindparams(sid=sid, dt=target_date))
    return {"code": 0, "data": [{
        "product_id": r[0], "product_name": r[1], "category": r[2],
        "total_orders": r[3], "total_amount": r[4],
    } for r in rows]}


@router.post("/daily-stats/refresh")
async def daily_stats_refresh(
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    """刷新当日统计到 daily_stats 表。"""
    today = str(__import__("datetime").date.today())

    # Refresh daily_stats_merchant
    await session.execute(text(
        "DELETE FROM daily_stats_merchant WHERE supplier_id=:sid AND stat_date=CURRENT_DATE"
    ).bindparams(sid=sid))
    await session.execute(text("""
        INSERT INTO daily_stats_merchant (supplier_id, api_payer_id, stat_date, total_orders, success_orders, total_amount, success_amount)
        SELECT :sid, o.api_payer_id, CURRENT_DATE,
               COUNT(*),
               COUNT(*) FILTER (WHERE o.status = 'SUCCESS'),
               COALESCE(SUM(o.amount), 0),
               COALESCE(SUM(o.amount) FILTER (WHERE o.status = 'SUCCESS'), 0)
        FROM orders o
        WHERE o.supplier_id = :sid
          AND o.created_at >= CURRENT_DATE
          AND o.created_at < CURRENT_DATE + INTERVAL '1 day'
        GROUP BY o.api_payer_id
    """).bindparams(sid=sid))

    # Refresh daily_stats_category
    await session.execute(text(
        "DELETE FROM daily_stats_category WHERE supplier_id=:sid AND stat_date=CURRENT_DATE"
    ).bindparams(sid=sid))
    await session.execute(text("""
        INSERT INTO daily_stats_category (supplier_id, product_id, stat_date, total_orders, total_amount)
        SELECT :sid, o.product_id, CURRENT_DATE,
               COUNT(*),
               COALESCE(SUM(o.amount), 0)
        FROM orders o
        WHERE o.supplier_id = :sid
          AND o.created_at >= CURRENT_DATE
          AND o.created_at < CURRENT_DATE + INTERVAL '1 day'
        GROUP BY o.product_id
    """).bindparams(sid=sid))

    await session.commit()
    return {"code": 0, "message": "当日统计已刷新"}


# ── USDT Deposit (Supplier-facing) ────────────────────────────

@router.get("/deposit-addresses")
async def get_deposit_addresses(
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Get deposit addresses for current supplier."""
    rows = await session.execute(
        text("SELECT id, chain, address, label, status FROM deposit_addresses "
             "WHERE owner_type='SUPPLIER' AND owner_id=:sid AND status='ACTIVE' ORDER BY chain")
        .bindparams(sid=sid))
    return {"code": 0, "data": [{"id": r[0], "chain": r[1], "address": r[2],
                                  "label": r[3], "status": r[4]} for r in rows]}


@router.get("/exchange-rate")
async def get_exchange_rate(
    session: AsyncSession = Depends(get_db_session),
):
    """Get current USDT→POINT exchange rate."""
    row = await session.execute(
        text("SELECT rate, source, updated_at FROM exchange_rates ORDER BY id LIMIT 1"))
    r = row.first()
    if not r:
        return {"code": 0, "data": {"rate": 1.0, "source": "FALLBACK",
                                     "updated_at": None}}
    return {"code": 0, "data": {"rate": float(r[0]), "source": r[1],
                                 "updated_at": str(r[2]) if r[2] else None}}


# ── USDT Deposit ──────────────────────────────────────────────

@router.post("/deposits")
async def submit_deposit(
    amount: int, tx_hash: str = "", chain: str = "TRC20", remark: str = "",
    sid: int = Depends(_get_supplier_id),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Submit USDT deposit request. Requires admin confirmation to credit points."""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="金额必须大于0")
    if not tx_hash:
        raise HTTPException(status_code=400, detail="请输入链上交易哈希")

    # Check wallet exists
    w = await session.execute(
        text("SELECT id FROM wallets WHERE owner_type='SUPPLIER' AND owner_id=:sid")
        .bindparams(sid=sid))
    wal = w.first()
    if not wal:
        raise HTTPException(status_code=404, detail="钱包不存在")

    # Check duplicate tx_hash
    dup = await session.execute(
        text("SELECT id FROM deposits WHERE tx_hash=:h AND status!='REJECTED'").bindparams(h=tx_hash))
    if dup.first():
        raise HTTPException(status_code=400, detail="该交易哈希已提交或已确认")

    row = await session.execute(
        text("INSERT INTO deposits (owner_type, owner_id, wallet_id, amount, tx_hash, chain, remark) "
             "VALUES ('SUPPLIER', :sid, :wid, :amt, :h, :ch, :rm) RETURNING id")
        .bindparams(sid=sid, wid=wal[0], amt=amount, h=tx_hash, ch=chain, rm=remark))
    did = row.scalar()
    await session.commit()
    return {"code": 0, "data": {"deposit_id": did, "amount": amount, "status": "PENDING"},
            "message": "充值申请已提交，等待管理员审核"}


@router.get("/deposits")
async def list_deposits(
    status: str = "", page: int = 1, limit: int = 20,
    sid: int = Depends(_get_supplier_id),
    session: AsyncSession = Depends(get_db_session),
):
    """List supplier's deposit requests."""
    where = f"owner_type='SUPPLIER' AND owner_id={sid}"
    if status:
        where += f" AND status='{status}'"

    total = await session.execute(text(f"SELECT count(*) FROM deposits WHERE {where}"))
    rows = await session.execute(text(f"""
        SELECT id, amount, tx_hash, currency, chain, status, admin_note, remark, created_at, confirmed_at
        FROM deposits WHERE {where} ORDER BY created_at DESC LIMIT {limit} OFFSET {(page-1)*limit}
    """))
    return {"code": 0, "data": {
        "items": [{"id": r[0], "amount": r[1], "tx_hash": r[2], "currency": r[3],
                   "chain": r[4], "status": r[5], "admin_note": r[6], "remark": r[7],
                   "created_at": str(r[8]) if r[8] else None,
                   "confirmed_at": str(r[9]) if r[9] else None} for r in rows],
        "total": total.scalar() or 0, "page": page, "limit": limit,
    }}


# ── Agent Auth Tokens ─────────────────────────────────────────

class AgentTokenCreate(BaseModel):
    name: str = ""


@router.get("/agent/auth-tokens")
async def list_agent_tokens(
    aid: int = Depends(_get_agent_id),
    session: AsyncSession = Depends(get_db_session),
):
    """List auth tokens for the current agent."""
    rows = await session.execute(text(
        "SELECT id, agent_id, owner_type, token, name, "
        "status, last_used_at, expires_at, created_at "
        "FROM auth_tokens WHERE agent_id=:aid AND owner_type='agent' "
        "ORDER BY created_at DESC"
    ).bindparams(aid=aid))
    tokens = []
    for r in rows:
        tokens.append({
            "id": r[0], "agent_id": r[1], "owner_type": r[2],
            "token": r[3], "name": r[4] or "", "status": r[5],
            "last_used_at": str(r[6]) if r[6] else None,
            "expires_at": str(r[7]) if r[7] else None,
            "created_at": str(r[8]) if r[8] else None,
        })
    return {"code": 0, "data": tokens, "message": "ok"}


@router.post("/agent/auth-tokens")
async def create_agent_token(
    req: AgentTokenCreate,
    aid: int = Depends(_get_agent_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Create an auth token for the current agent."""
    raw_token = f"sk_{secrets.token_hex(24)}"
    row = await session.execute(
        text("INSERT INTO auth_tokens (agent_id, owner_type, token, name) "
             "VALUES (:aid, 'agent', :tk, :nm) RETURNING id")
        .bindparams(aid=aid, tk=raw_token, nm=req.name)
    )
    tid = row.scalar()
    await session.commit()
    return {
        "code": 0,
        "data": {"id": tid, "token": raw_token, "name": req.name, "status": "ACTIVE"},
        "message": "授权码已生成",
    }


@router.delete("/agent/auth-tokens/{token_id}")
async def revoke_agent_token(
    token_id: int,
    aid: int = Depends(_get_agent_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Revoke an auth token owned by the current agent."""
    row = await session.execute(
        text("SELECT id FROM auth_tokens WHERE id=:tid AND agent_id=:aid AND owner_type='agent'")
        .bindparams(tid=token_id, aid=aid)
    )
    if not row.first():
        raise HTTPException(status_code=404, detail="授权码不存在或不属于当前代理商")
    await session.execute(
        text("UPDATE auth_tokens SET status='INACTIVE', updated_at=NOW() WHERE id=:id")
        .bindparams(id=token_id)
    )
    await session.commit()
    return {"code": 0, "message": "授权码已失效"}
