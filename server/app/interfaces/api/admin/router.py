"""Admin API — simplified management with full CRUD + hierarchy."""
from __future__ import annotations
import secrets
import json
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.postgres.session import get_db_session, async_session_factory
from app.interfaces.api.auth.router import get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


# ── DTOs ─────────────────────────────────────────────────────

class SupplierCreate(BaseModel):
    nickname: str = Field(..., max_length=128)
    username: str = Field(default="", max_length=64)
    password: str = Field(default="", max_length=64)
    auto_generate: bool = False

class SupplierUpdate(BaseModel):
    nickname: str = Field(..., max_length=128)
    status: str = "ACTIVE"

class AgentCreate(BaseModel):
    supplier_id: int
    nickname: str = Field(..., max_length=128)
    username: str = Field(default="", max_length=64)
    password: str = Field(default="", max_length=64)

class AgentUpdate(BaseModel):
    nickname: str = ""
    status: str = "ACTIVE"

class ApiPayerCreate(BaseModel):
    supplier_id: int
    nickname: str = Field(..., max_length=128)

class ApiPayerUpdate(BaseModel):
    nickname: str = ""
    status: str = "ACTIVE"

class ProductCreate(BaseModel):
    name: str
    category: str = ""
    face_value: int = Field(default=0, ge=1, description="面值必须大于0")
    suggested_price: int = Field(default=0, ge=0)
    collection_config: str = "{}"

class ProductUpdate(BaseModel):
    name: str = ""
    category: str = ""
    face_value: int = Field(default=0, ge=1)
    suggested_price: int = Field(default=0, ge=0)
    collection_config: str = "{}"


# ── HELPERS ───────────────────────────────────────────────────

def rand_username() -> str:
    return "sup_" + secrets.token_hex(4)

def rand_password() -> str:
    return secrets.token_hex(8)


# ═══════════════════════════════════════════════════════════════
# SUPPLIERS
# ═══════════════════════════════════════════════════════════════

@router.get("/suppliers")
async def list_suppliers(
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    rows = await session.execute(text("""
        SELECT s.id, s.name AS nickname, s.status, s.created_at,
               (SELECT count(*) FROM agents a WHERE a.supplier_id=s.id) AS agent_count,
               (SELECT count(*) FROM api_payers ap WHERE ap.supplier_id=s.id) AS payer_count,
               COALESCE(u.username, '') AS username
        FROM suppliers s
        LEFT JOIN users u ON u.role='SUPPLIER' AND u.reference_id=s.id
        ORDER BY s.id
    """))
    return {"code": 0, "data": [
        {"id": r[0], "nickname": r[1], "status": r[2],
         "created_at": str(r[3]) if r[3] else None,
         "agent_count": r[4], "api_payer_count": r[5], "username": r[6]} for r in rows
    ]}


@router.post("/suppliers")
async def create_supplier(
    req: SupplierCreate,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    username = req.username or rand_username()
    password = req.password or rand_password()

    # Check username
    exist = await session.execute(
        text("SELECT id FROM users WHERE username=:u").bindparams(u=username)
    )
    if exist.first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    # Create supplier
    row = await session.execute(
        text("INSERT INTO suppliers (name) VALUES (:n) RETURNING id")
        .bindparams(n=req.nickname)
    )
    sid = row.scalar()

    # Create user
    await session.execute(
        text("INSERT INTO users (username, password_hash, role, reference_id) "
             "VALUES (:u, crypt(:pw, gen_salt('bf')), 'SUPPLIER', :rid)")
        .bindparams(u=username, pw=password, rid=sid)
    )

    # Wallet
    await session.execute(
        text("INSERT INTO wallets (owner_type, owner_id, balance) VALUES ('SUPPLIER', :sid, 0)")
        .bindparams(sid=sid)
    )

    await session.commit()
    return {"code": 0, "data": {"id": sid, "nickname": req.nickname,
                                 "username": username, "password": password},
            "message": f"供应商 [{req.nickname}] 创建成功"}


@router.put("/suppliers/{sid}")
async def update_supplier(
    sid: int, req: SupplierUpdate,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    await session.execute(
        text("UPDATE suppliers SET name=:n, status=:s WHERE id=:id")
        .bindparams(n=req.nickname, s=req.status, id=sid)
    )
    await session.commit()
    return {"code": 0, "message": "更新成功"}


@router.delete("/suppliers/{sid}")
async def delete_supplier(
    sid: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    await session.execute(text("UPDATE suppliers SET status='INACTIVE' WHERE id=:id").bindparams(id=sid))
    await session.commit()
    return {"code": 0, "message": "已停用"}


# ═══════════════════════════════════════════════════════════════
# AGENTS  (belong to supplier)
# ═══════════════════════════════════════════════════════════════

@router.get("/agents")
async def list_agents(
    supplier_id: int = 0,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    where = "WHERE 1=1"
    if supplier_id:
        where += f" AND a.supplier_id = {supplier_id}"

    rows = await session.execute(text(
        "SELECT a.id, a.name AS nickname, a.supplier_id, s.name AS supplier_name, "
        "a.balance, a.frozen, a.status, "
        "COALESCE(u.username, '') AS username "
        "FROM agents a "
        "JOIN suppliers s ON a.supplier_id = s.id "
        "LEFT JOIN users u ON u.role='AGENT' AND u.reference_id=a.id "
        f"{where} ORDER BY a.id"
    ))
    return {"code": 0, "data": [
        {"id": r[0], "nickname": r[1], "supplier_id": r[2], "supplier_name": r[3],
         "balance": r[4], "frozen": r[5], "status": r[6], "username": r[7]} for r in rows
    ]}


@router.post("/agents")
async def create_agent(
    req: AgentCreate,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    import secrets
    username = req.username or f"agent_{secrets.token_hex(4)}"
    password = req.password or secrets.token_hex(8)

    # Ensure unique username
    if req.username:
        dup = await session.execute(
            text("SELECT id FROM users WHERE username=:u").bindparams(u=req.username))
        if dup.first():
            raise HTTPException(status_code=400, detail="用户名已存在")
    else:
        while await session.execute(
                text("SELECT id FROM users WHERE username=:u").bindparams(u=username)):
            username = f"agent_{secrets.token_hex(4)}"

    s = await session.execute(text("SELECT id FROM suppliers WHERE id=:id").bindparams(id=req.supplier_id))
    if not s.first():
        raise HTTPException(status_code=404, detail="供应商不存在")

    row = await session.execute(
        text("INSERT INTO agents (supplier_id, name) VALUES (:sid, :n) RETURNING id")
        .bindparams(sid=req.supplier_id, n=req.nickname)
    )
    aid = row.scalar()

    await session.execute(
        text("INSERT INTO users (username, password_hash, role, reference_id) "
             "VALUES (:u, crypt(:pw, gen_salt('bf')), 'AGENT', :rid)")
        .bindparams(u=username, pw=password, rid=aid))

    await session.execute(
        text("INSERT INTO wallets (owner_type, owner_id, balance) VALUES ('AGENT', :aid, 0)")
        .bindparams(aid=aid)
    )
    await session.commit()
    return {"code": 0, "data": {"id": aid, "nickname": req.nickname,
                                 "username": username, "password": password},
            "message": f"代理商 [{req.nickname}] 创建成功"}


@router.put("/agents/{aid}")
async def update_agent(
    aid: int, req: AgentUpdate,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    await session.execute(
        text("UPDATE agents SET name=:n, status=:s WHERE id=:id")
        .bindparams(n=req.nickname, s=req.status, id=aid)
    )
    await session.commit()
    return {"code": 0, "message": "更新成功"}


@router.delete("/agents/{aid}")
async def delete_agent(
    aid: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    await session.execute(text("UPDATE agents SET status='INACTIVE' WHERE id=:id").bindparams(id=aid))
    await session.commit()
    return {"code": 0, "message": "已停用"}


# ═══════════════════════════════════════════════════════════════
# API PAYERS  (belong to supplier)
# ═══════════════════════════════════════════════════════════════

@router.get("/api-payers")
async def list_api_payers(
    supplier_id: int = 0,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    where = "WHERE 1=1"
    if supplier_id:
        where += f" AND ap.supplier_id = {supplier_id}"

    rows = await session.execute(text(f"""
        SELECT ap.id, ap.name AS nickname, ap.supplier_id, s.name AS supplier_name,
               ap.api_key, ap.api_secret, ap.callback_url, ap.status
        FROM api_payers ap JOIN suppliers s ON ap.supplier_id = s.id {where}
        ORDER BY ap.id
    """))
    return {"code": 0, "data": [
        {"id": r[0], "nickname": r[1], "supplier_id": r[2], "supplier_name": r[3],
         "api_key": r[4], "api_secret": r[5], "callback_url": r[6], "status": r[7]}
        for r in rows
    ]}


@router.post("/api-payers")
async def create_api_payer(
    req: ApiPayerCreate,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    s = await session.execute(text("SELECT id FROM suppliers WHERE id=:id").bindparams(id=req.supplier_id))
    if not s.first():
        raise HTTPException(status_code=404, detail="供应商不存在")

    api_key = f"sk_{secrets.token_hex(16)}"
    api_secret = f"ss_{secrets.token_hex(32)}"

    row = await session.execute(
        text("""
        INSERT INTO api_payers (supplier_id, name, api_key, api_secret)
        VALUES (:sid, :n, :ak, :secret_val) RETURNING id
        """).bindparams(sid=req.supplier_id, n=req.nickname, ak=api_key, secret_val=api_secret)
    )
    pid = row.scalar()
    await session.commit()
    return {
        "code": 0,
        "data": {"id": pid, "nickname": req.nickname, "api_key": api_key, "api_secret": api_secret},
        "message": f"API支付商 [{req.nickname}] 创建成功",
    }


@router.put("/api-payers/{pid}")
async def update_api_payer(
    pid: int, req: ApiPayerUpdate,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    await session.execute(
        text("UPDATE api_payers SET name=:n, status=:s WHERE id=:id")
        .bindparams(n=req.nickname, s=req.status, id=pid)
    )
    await session.commit()
    return {"code": 0, "message": "更新成功"}


@router.delete("/api-payers/{pid}")
async def delete_api_payer(
    pid: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    await session.execute(text("UPDATE api_payers SET status='INACTIVE' WHERE id=:id").bindparams(id=pid))
    await session.commit()
    return {"code": 0, "message": "已停用"}


# ═══════════════════════════════════════════════════════════════
# PRODUCTS (unchanged)
# ═══════════════════════════════════════════════════════════════

@router.get("/products")
async def list_products(
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    rows = await session.execute(text("""
        SELECT id, name, category, face_value, suggested_price,
               delivery_mode, confirm_mode, status, created_at,
               COALESCE(collection_config, '{}'::jsonb) AS collection_config,
               (SELECT count(*) FROM supplier_product_auth spa WHERE spa.product_id=products.id AND spa.status=TRUE) AS supplier_count
        FROM products ORDER BY category, id
    """))
    return {"code": 0, "data": [
        {"id": r[0], "name": r[1], "category": r[2], "face_value": r[3],
         "suggested_price": r[4], "delivery_mode": r[5], "confirm_mode": r[6],
         "status": bool(r[7]), "created_at": str(r[8]) if r[8] else None,
         "collection_config": r[9] if isinstance(r[9], dict) else {},
         "supplier_count": r[10] or 0} for r in rows
    ]}


@router.post("/products")
async def create_product(
    req: ProductCreate,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    try:
        cfg = json.loads(req.collection_config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="collection_config 必须为合法 JSON")

    row = await session.execute(
        text("INSERT INTO products (name, category, face_value, suggested_price, collection_config) "
             "VALUES (:n, :c, :fv, :sp, CAST(:cc AS jsonb)) RETURNING id")
        .bindparams(n=req.name, c=req.category, fv=req.face_value, sp=req.suggested_price, cc=json.dumps(cfg))
    )
    pid = row.scalar()
    await session.commit()
    return {"code": 0, "data": {"id": pid, "name": req.name}}


@router.post("/products/{pid}/authorize-supplier")
async def authorize_supplier(
    pid: int, supplier_id: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    await session.execute(
        text("INSERT INTO supplier_product_auth (supplier_id, product_id) "
             "VALUES (:sid, :pid) ON CONFLICT DO NOTHING")
        .bindparams(sid=supplier_id, pid=pid)
    )
    await session.commit()
    return {"code": 0, "message": "授权成功"}


# ═══════════════════════════════════════════════════════════════
# SIMULATE — order simulation
# ═══════════════════════════════════════════════════════════════

from pydantic import BaseModel


class SimOrderCreate(BaseModel):
    api_payer_id: int
    product_id: int
    quantity: int = 1
    client_order_id: str = ""
    callback_url: str = ""


@router.get("/simulate/api-payers")
async def sim_list_api_payers(
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    rows = await session.execute(
        text("SELECT id, name, supplier_id, api_key, callback_url FROM api_payers WHERE status='ACTIVE' ORDER BY id")
    )
    return {"code": 0, "data": [
        {"id": r[0], "name": r[1], "supplier_id": r[2], "api_key": r[3], "callback_url": r[4]}
        for r in rows
    ]}


@router.get("/simulate/products")
async def sim_list_products(
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    rows = await session.execute(
        text("SELECT id, name, category, face_value, suggested_price, status FROM products ORDER BY category, id")
    )
    return {"code": 0, "data": [
        {"id": r[0], "name": r[1], "category": r[2], "face_value": r[3],
         "suggested_price": r[4], "status": r[5]} for r in rows
    ]}


@router.post("/simulate/create-order")
async def sim_create_order(
    req: SimOrderCreate,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    import time

    payer = await session.execute(
        text("SELECT id, supplier_id, callback_url FROM api_payers WHERE id=:pid").bindparams(pid=req.api_payer_id)
    )
    p = payer.first()
    if not p:
        raise HTTPException(status_code=404, detail="API支付商不存在")

    prod = await session.execute(
        text("SELECT id, name, face_value, confirm_mode FROM products WHERE id=:pid AND status=TRUE")
        .bindparams(pid=req.product_id)
    )
    pr = prod.first()
    if not pr:
        raise HTTPException(status_code=404, detail="货品不存在")

    # Check inventory availability
    inv_count = await session.execute(
        text("SELECT count(*) FROM inventory_items WHERE product_id=:pid AND status='AVAILABLE'")
        .bindparams(pid=req.product_id)
    )
    if inv_count.scalar() == 0:
        raise HTTPException(status_code=400, detail=f"货品 [{pr[1]}] 库存不足，请先让代理商上架资源")

    agent = await session.execute(
        text("SELECT a.id, a.name FROM agents a JOIN inventory_items i ON i.agent_id=a.id "
             "WHERE i.product_id=:pid AND i.status='AVAILABLE' AND a.supplier_id=:sid AND a.status='ACTIVE' LIMIT 1")
        .bindparams(pid=req.product_id, sid=p[1])
    )
    ag = agent.first()
    if not ag:
        fb = await session.execute(
            text("SELECT id, name FROM agents WHERE supplier_id=:sid AND status='ACTIVE' LIMIT 1")
            .bindparams(sid=p[1])
        )
        ag = fb.first()
        if not ag:
            raise HTTPException(status_code=400, detail="无可用的代理商")

    total_amt = pr[2] * req.quantity
    ts = int(time.time())
    order_no = f"SIM{ts}"
    cb = req.callback_url or p[2] or f"https://sim-cb.local/{order_no}"

    await session.execute(
        text(f"""
        INSERT INTO orders (order_no, client_order_id, api_payer_id, supplier_id, agent_id,
            product_id, quantity, amount, status, confirm_mode, callback_url, callback_status,
            expired_at, created_at, updated_at)
        VALUES (:on, :co, :apid, :sid, :aid, :prid, :qty, :amt, 'PENDING', :cm, :cb, 'PENDING',
            NOW()+INTERVAL '30 minutes', NOW(), NOW())
        """).bindparams(on=order_no, co=req.client_order_id, apid=req.api_payer_id,
                        sid=p[1], aid=ag[0], prid=req.product_id, qty=req.quantity,
                        amt=total_amt, cm=pr[3], cb=cb)
    )

    # Freeze agent points
    wal = await session.execute(
        text("SELECT id, balance, frozen FROM wallets WHERE owner_type='AGENT' AND owner_id=:aid FOR UPDATE")
        .bindparams(aid=ag[0])
    )
    w = wal.first()
    if w and w[1] >= total_amt:
        nb = w[1] - total_amt
        nf = w[2] + total_amt
        await session.execute(
            text("UPDATE wallets SET balance=:b, frozen=:f, version=version+1, updated_at=NOW() WHERE id=:wid")
            .bindparams(b=nb, f=nf, wid=w[0])
        )
        await session.execute(
            text("INSERT INTO wallet_transactions (wallet_id, type, amount, balance_before, balance_after, remark, status, operator_type, related_order_no) "
                 "VALUES (:wid, 'FREEZE', :amt, :bb, :ba, :rm, 'COMPLETED', 'SYSTEM', :on)")
            .bindparams(wid=w[0], amt=total_amt, bb=w[1], ba=nb, rm=f"订单 {order_no} 冻结", on=order_no)
        )
        await session.execute(
            text("INSERT INTO point_freeze_records (wallet_id, order_no, agent_id, amount, status) "
                 "VALUES (:wid, :on, :aid, :amt, 'FROZEN')")
            .bindparams(wid=w[0], on=order_no, aid=ag[0], amt=total_amt)
        )
        await session.execute(
            text("UPDATE agents SET frozen=frozen+:amt WHERE id=:aid").bindparams(amt=total_amt, aid=ag[0])
        )

    await session.commit()
    return {"code": 0, "data": {
        "platform_order_id": order_no, "client_order_id": req.client_order_id or order_no,
        "product_name": pr[1], "quantity": req.quantity, "total_amount": total_amt,
        "status": "PENDING", "agent_name": ag[1], "callback_url": cb,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, "message": "订单创建成功（模拟）"}


@router.get("/simulate/orders")
async def sim_list_orders(
    page: int = 1, limit: int = 20,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    total = await session.execute(text("SELECT count(*) FROM orders"))
    rows = await session.execute(text(f"""
        SELECT o.order_no, o.amount, o.status, o.client_order_id,
               ap.name, p.name, COALESCE(a.name,'-'),
               o.callback_url, o.callback_status, o.callback_cnt, o.created_at
        FROM orders o JOIN api_payers ap ON o.api_payer_id=ap.id
        JOIN products p ON o.product_id=p.id LEFT JOIN agents a ON o.agent_id=a.id
        ORDER BY o.created_at DESC LIMIT {limit} OFFSET {(page-1)*limit}
    """))
    return {"code": 0, "data": {"items": [
        {"order_no": r[0], "amount": r[1], "status": r[2], "client_order_id": r[3],
         "api_payer_name": r[4], "product_name": r[5], "agent_name": r[6],
         "callback_url": r[7], "callback_status": r[8], "callback_cnt": r[9],
         "created_at": str(r[10]) if r[10] else None} for r in rows
    ], "total": total.scalar() or 0, "page": page, "limit": limit}}


@router.post("/simulate/callback/{order_no}")
async def sim_trigger_callback(
    order_no: str,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    row = await session.execute(
        text("SELECT callback_url, callback_status, status FROM orders WHERE order_no=:on")
        .bindparams(on=order_no)
    )
    o = row.first()
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    if o[2] != "SUCCESS":
        raise HTTPException(status_code=400, detail="只有已完成订单才能触发回调")
    await session.execute(
        text("UPDATE orders SET callback_status='SUCCESS', callback_cnt=callback_cnt+1, callback_at=NOW() WHERE order_no=:on")
        .bindparams(on=order_no)
    )
    await session.commit()
    return {"code": 0, "message": "回调已触发（模拟）"}


# ── USDT Deposit Review ───────────────────────────────────────

@router.get("/deposit-addresses")
async def admin_list_deposit_addresses(
    owner_type: str = "", owner_id: int = 0,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """List all deposit addresses. Optional filter by owner."""
    where = "TRUE"
    if owner_type:
        where += f" AND owner_type='{owner_type}'"
    if owner_id:
        where += f" AND owner_id={owner_id}"

    rows = await session.execute(text(f"""
        SELECT da.id, da.owner_type, da.owner_id, da.chain, da.address, da.label, da.status, da.created_at,
               CASE
                 WHEN da.owner_type='SUPPLIER' THEN COALESCE(s.name, '?')
                 WHEN da.owner_type='AGENT' THEN COALESCE(a.name, '?')
                 WHEN da.owner_type='PLATFORM' THEN '平台钱包'
                 ELSE '?'
               END as owner_name
        FROM deposit_addresses da
        LEFT JOIN suppliers s ON da.owner_type='SUPPLIER' AND da.owner_id=s.id
        LEFT JOIN agents a ON da.owner_type='AGENT' AND da.owner_id=a.id
        WHERE {where} ORDER BY da.owner_type, da.owner_id, da.chain
    """))
    return {"code": 0, "data": [{"id": r[0], "owner_type": r[1], "owner_id": r[2], "chain": r[3],
                                  "address": r[4], "label": r[5], "status": r[6],
                                  "created_at": str(r[7]) if r[7] else None,
                                  "owner_name": r[8]} for r in rows]}


@router.post("/deposit-addresses")
async def admin_create_deposit_address(
    owner_type: str, owner_id: int, chain: str, address: str, label: str = "",
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Create a deposit address for a supplier or agent."""
    if owner_type not in ("SUPPLIER", "AGENT", "PLATFORM"):
        raise HTTPException(status_code=400, detail="owner_type 必须为 SUPPLIER/AGENT/PLATFORM")
    if chain not in ("TRC20", "ERC20", "BSC"):
        raise HTTPException(status_code=400, detail="chain 必须为 TRC20/ERC20/BSC")
    if not address:
        raise HTTPException(status_code=400, detail="地址不能为空")

    # Verify owner exists (skip for PLATFORM)
    if owner_type != "PLATFORM":
        tbl = "suppliers" if owner_type == "SUPPLIER" else "agents"
        owner = await session.execute(text(f"SELECT id FROM {tbl} WHERE id=:oid").bindparams(oid=owner_id))
        if not owner.first():
            raise HTTPException(status_code=404, detail=f"{owner_type} #{owner_id} 不存在")

    try:
        row = await session.execute(
            text("INSERT INTO deposit_addresses (owner_type, owner_id, chain, address, label) "
                 "VALUES (:ot, :oi, :ch, :addr, :lbl) RETURNING id")
            .bindparams(ot=owner_type, oi=owner_id, ch=chain, addr=address, lbl=label))
        did = row.scalar()
        await session.commit()
        return {"code": 0, "data": {"id": did}, "message": "充值地址创建成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建失败: {str(e)}")


@router.put("/deposit-addresses/{did}")
async def admin_update_deposit_address(
    did: int, status: str = "", label: str = "",
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Update deposit address status or label."""
    if status and status not in ("ACTIVE", "DISABLED"):
        raise HTTPException(status_code=400, detail="status 必须为 ACTIVE 或 DISABLED")

    sets = []
    params = {"did": did}
    if status:
        sets.append("status=:s")
        params["s"] = status
    if label:
        sets.append("label=:lbl")
        params["lbl"] = label
    if not sets:
        raise HTTPException(status_code=400, detail="无更新字段")

    await session.execute(
        text(f"UPDATE deposit_addresses SET {', '.join(sets)}, updated_at=NOW() WHERE id=:did")
        .bindparams(**params))
    await session.commit()
    return {"code": 0, "message": "更新成功"}


@router.delete("/deposit-addresses/{did}")
async def admin_delete_deposit_address(
    did: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Delete a deposit address."""
    r = await session.execute(
        text("DELETE FROM deposit_addresses WHERE id=:did").bindparams(did=did))
    await session.commit()
    if r.rowcount == 0:
        raise HTTPException(status_code=404, detail="地址不存在")
    return {"code": 0, "message": "已删除"}


# ═══════════════════════════════════════════════════
# Product Configuration Management (Admin)
# ═══════════════════════════════════════════════════

@router.get("/product-configs")
async def admin_list_product_configs(
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """List all products with their collection configs."""
    rows = await session.execute(text("""
        SELECT id, name, category, face_value, suggested_price, status,
               COALESCE(collection_config, '{}'::jsonb) as config,
               created_at
        FROM products ORDER BY id
    """))
    return {"code": 0, "data": [{
        "id": r[0], "name": r[1], "category": r[2],
        "face_value": r[3], "suggested_price": r[4],
        "status": "ACTIVE" if r[5] else "INACTIVE",
        "collection_config": r[6] if isinstance(r[6], dict) else {},
        "created_at": str(r[7]) if r[7] else None,
    } for r in rows]}


@router.put("/product-configs/{pid}")
async def admin_update_product_config(
    pid: int,
    collection_config: str = "{}",
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Update product collection configuration."""
    try:
        import json
        cfg = json.loads(collection_config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="collection_config 必须为合法 JSON")

    row = await session.execute(
        text("UPDATE products SET collection_config=CAST(:cfg AS jsonb), updated_at=NOW() WHERE id=:pid RETURNING id")
        .bindparams(cfg=json.dumps(cfg), pid=pid))
    if not row.first():
        raise HTTPException(status_code=404, detail="商品不存在")
    await session.commit()
    return {"code": 0, "message": "采集配置已更新"}


@router.put("/product-configs/{pid}/status")
async def admin_toggle_product_status(
    pid: int, status: bool = True,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Enable or disable a product."""
    row = await session.execute(
        text("UPDATE products SET status=:st, updated_at=NOW() WHERE id=:pid RETURNING id")
        .bindparams(st=status, pid=pid))
    if not row.first():
        raise HTTPException(status_code=404, detail="商品不存在")
    await session.commit()
    return {"code": 0, "message": f"商品已{'启用' if status else '停用'}"}


@router.get("/exchange-rates")
async def admin_get_exchange_rates(
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Get current exchange rates."""
    rows = await session.execute(text("SELECT id, currency_from, currency_to, rate, source, updated_at FROM exchange_rates"))
    return {"code": 0, "data": [{"id": r[0], "from": r[1], "to": r[2], "rate": float(r[3]),
                                  "source": r[4], "updated_at": str(r[5]) if r[5] else None}
                                 for r in rows]}


@router.put("/exchange-rates/{eid}")
async def admin_update_exchange_rate(
    eid: int, rate: float,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Update exchange rate."""
    if rate <= 0:
        raise HTTPException(status_code=400, detail="汇率必须大于0")
    await session.execute(
        text("UPDATE exchange_rates SET rate=:r, source='FALLBACK', updated_at=NOW() WHERE id=:eid")
        .bindparams(r=rate, eid=eid))
    await session.commit()
    return {"code": 0, "message": "汇率已更新"}

@router.get("/deposits")
async def admin_list_deposits(
    status: str = "",
    page: int = 1, limit: int = 20,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """List all deposit requests."""
    where_status = "TRUE"
    if status:
        where_status = f"d.status='{status}'"
    total = await session.execute(text(f"SELECT count(*) FROM deposits d WHERE {where_status}"))
    rows = await session.execute(text(f"""
        SELECT d.id, d.owner_type, d.owner_id, d.amount, d.tx_hash, d.currency,
               d.status, d.admin_note, d.remark, d.chain, d.created_at, d.confirmed_at,
               COALESCE(s.name, a.name, '?') as owner_name
        FROM deposits d
        LEFT JOIN suppliers s ON d.owner_type='SUPPLIER' AND d.owner_id=s.id
        LEFT JOIN agents a ON d.owner_type='AGENT' AND d.owner_id=a.id
        WHERE {where_status} ORDER BY d.created_at DESC LIMIT {limit} OFFSET {(page-1)*limit}
    """))
    return {"code": 0, "data": {
        "items": [{"id": r[0], "owner_type": r[1], "owner_id": r[2], "amount": r[3],
                   "tx_hash": r[4], "currency": r[5], "status": r[6],
                   "admin_note": r[7], "remark": r[8], "chain": r[9],
                   "created_at": str(r[10]) if r[10] else None,
                   "confirmed_at": str(r[11]) if r[11] else None,
                   "owner_name": r[12]} for r in rows],
        "total": total.scalar() or 0, "page": page, "limit": limit,
    }}


@router.post("/deposits/{did}/confirm")
async def confirm_deposit(
    did: int, admin_note: str = "",
    session: AsyncSession = Depends(get_db_session),
    user: dict = Depends(_require_admin),
):
    """Confirm a deposit → credit points to wallet."""
    row = await session.execute(
        text("SELECT id, status, wallet_id, amount, owner_type, owner_id FROM deposits WHERE id=:did FOR UPDATE")
        .bindparams(did=did))
    d = row.first()
    if not d:
        raise HTTPException(status_code=404, detail="充值记录不存在")
    if d[1] != "PENDING":
        raise HTTPException(status_code=400, detail=f"当前状态 {d[1]} 不可确认")

    admin_id = user.get("ref_id", 0) or user.get("id", 0)

    # Credit points to wallet
    w = await session.execute(
        text("SELECT id, balance FROM wallets WHERE id=:wid FOR UPDATE")
        .bindparams(wid=d[2]))
    wal = w.first()
    if not wal:
        raise HTTPException(status_code=404, detail="钱包不存在")
    wid, old_bal = wal
    new_bal = old_bal + d[3]

    await session.execute(
        text("UPDATE wallets SET balance=:b, total_recharge=total_recharge+:amt, "
             "version=version+1, updated_at=NOW() WHERE id=:wid")
        .bindparams(b=new_bal, amt=d[3], wid=wid))

    await session.execute(
        text("INSERT INTO wallet_transactions (wallet_id, type, amount, balance_before, balance_after, "
             "remark, status, operator_type, deposit_id) "
             "VALUES (:wid, 'RECHARGE', :amt, :bb, :ba, :rm, 'COMPLETED', 'ADMIN', :did)")
        .bindparams(wid=wid, amt=d[3], bb=old_bal, ba=new_bal,
                   rm=f"USDT充值审核通过（#{did}）", did=did))

    await session.execute(
        text("UPDATE deposits SET status='CONFIRMED', admin_id=:aid, admin_note=:note, "
             "confirmed_at=NOW() WHERE id=:did")
        .bindparams(aid=admin_id, note=admin_note, did=did))

    if d[4] == "AGENT":
        await session.execute(
            text("UPDATE agents SET balance=balance+:amt WHERE id=:aid")
            .bindparams(amt=d[3], aid=d[5]))

    await session.commit()
    return {"code": 0, "data": {"deposit_id": did, "status": "CONFIRMED", "credited": d[3],
                                "wallet_balance": new_bal},
            "message": f"充值确认成功，已到账 {d[3]} 积分"}


@router.post("/deposits/{did}/reject")
async def reject_deposit(
    did: int, admin_note: str = "",
    session: AsyncSession = Depends(get_db_session),
    user: dict = Depends(_require_admin),
):
    """Reject a deposit request."""
    admin_id = user.get("ref_id", 0) or user.get("id", 0)
    r = await session.execute(
        text("UPDATE deposits SET status='REJECTED', admin_id=:aid, admin_note=:note "
             "WHERE id=:did AND status='PENDING'")
        .bindparams(aid=admin_id, note=admin_note, did=did))
    await session.commit()
    if r.rowcount == 0:
        raise HTTPException(status_code=400, detail="充值记录不存在或状态不可驳回")
    return {"code": 0, "data": {"deposit_id": did, "status": "REJECTED"},
            "message": "充值申请已驳回"}


# ═══════════════════════════════════════════════════
# Blockchain Monitor Admin APIs
# ═══════════════════════════════════════════════════

@router.get("/blockchain/addresses")
async def admin_blockchain_addresses(
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """List platform wallet addresses with balance info."""
    rows = await session.execute(text("""
        SELECT da.id, da.chain, da.address, da.label, da.status,
               COALESCE(da.last_balance, 0) as balance,
               da.balance_updated_at,
               COALESCE(ms.last_block, 0) as last_block,
               COALESCE(ms.poll_count, 0) as poll_count,
               ms.last_error, ms.updated_at as monitor_updated_at
        FROM deposit_addresses da
        LEFT JOIN blockchain_monitor_state ms ON ms.address=da.address AND ms.chain=da.chain
        WHERE da.owner_type='PLATFORM'
        ORDER BY da.chain, da.id
    """))
    return {"code": 0, "data": [{
        "id": r[0], "chain": r[1], "address": r[2], "label": r[3],
        "status": r[4], "balance": float(r[5]) if r[5] else 0,
        "balance_updated_at": str(r[6]) if r[6] else None,
        "last_block": r[7] or 0, "poll_count": r[8] or 0,
        "last_error": r[9], "monitor_updated_at": str(r[10]) if r[10] else None,
    } for r in rows]}


@router.get("/blockchain/transactions")
async def admin_blockchain_transactions(
    status: str = "", limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """List detected blockchain transactions."""
    where = "TRUE"
    if status:
        where = f"status='{status}'"

    total = await session.execute(text(f"SELECT count(*) FROM blockchain_txns WHERE {where}"))
    rows = await session.execute(text(f"""
        SELECT id, chain, tx_hash, from_address, to_address, amount, block_number,
               status, deposit_id, remark, created_at
        FROM blockchain_txns WHERE {where} ORDER BY block_number DESC LIMIT {limit}
    """))
    return {"code": 0, "data": {
        "items": [{
            "id": r[0], "chain": r[1], "tx_hash": r[2],
            "from_address": r[3], "to_address": r[4],
            "amount": float(r[5]), "block_number": r[6],
            "status": r[7], "deposit_id": r[8], "remark": r[9],
            "created_at": str(r[10]) if r[10] else None,
        } for r in rows],
        "total": total.scalar() or 0,
    }}


@router.post("/blockchain/claim")
async def admin_blockchain_claim(
    txn_id: int, deposit_id: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Manually claim an unmatched blockchain transaction to a deposit."""
    # Verify the blockchain txn
    txn = await session.execute(
        text("SELECT id, chain, tx_hash, amount, status FROM blockchain_txns WHERE id=:id")
        .bindparams(id=txn_id))
    t = txn.first()
    if not t:
        raise HTTPException(status_code=404, detail="交易记录不存在")
    if t[4] in ("MATCHED", "CLAIMED_MANUAL"):
        raise HTTPException(status_code=400, detail="该交易已被认领")

    # Verify the deposit exists and is pending
    dep = await session.execute(
        text("SELECT id, status, wallet_id FROM deposits WHERE id=:id")
        .bindparams(id=deposit_id))
    d = dep.first()
    if not d:
        raise HTTPException(status_code=404, detail="充值记录不存在")
    if d[1] != "PENDING":
        raise HTTPException(status_code=400, detail="充值记录状态不是待审核")

    # Link them
    await session.execute(
        text("UPDATE blockchain_txns SET status='CLAIMED_MANUAL', deposit_id=:did WHERE id=:id")
        .bindparams(did=deposit_id, id=txn_id))

    # Auto-confirm deposit and credit wallet
    wallet_id = d[2]
    amount = float(t[3])
    await session.execute(
        text("UPDATE deposits SET status='CONFIRMED', confirmed_at=NOW(), "
             "admin_note='手动认领链上交易' WHERE id=:id")
        .bindparams(id=deposit_id))

    if wallet_id:
        await session.execute(
            text("UPDATE wallets SET balance=balance+:amt, updated_at=NOW() WHERE id=:wid")
            .bindparams(amt=int(amount), wid=wallet_id))
        await session.execute(
            text("INSERT INTO wallet_transactions (wallet_id, type, amount, "
                 "balance_before, balance_after, related_order_no, remark, created_at) "
                 "SELECT :wid, 'DEPOSIT', :amt, balance-:amt2, balance, NULL, "
                 "'手动认领: 链上自动充值', NOW() FROM wallets WHERE id=:wid3")
            .bindparams(wid=wallet_id, amt=int(amount), amt2=int(amount), wid3=wallet_id))

    await session.commit()
    return {"code": 0, "data": {"txn_id": txn_id, "deposit_id": deposit_id},
            "message": "认领成功，积分已发放"}


@router.post("/blockchain/ignore")
async def admin_blockchain_ignore(
    txn_id: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Mark a blockchain transaction as ignored."""
    await session.execute(
        text("UPDATE blockchain_txns SET status='IGNORED' WHERE id=:id")
        .bindparams(id=txn_id))
    await session.commit()
    return {"code": 0, "message": "已忽略"}


@router.post("/blockchain/refresh-balance")
async def admin_refresh_balance(
    da_id: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Refresh USDT balance for a platform address via blockchain API."""
    from app.infrastructure.blockchain.trongrid_client import TrongridClient

    row = await session.execute(
        text("SELECT chain, address FROM deposit_addresses WHERE id=:id AND owner_type='PLATFORM'")
        .bindparams(id=da_id))
    r = row.first()
    if not r:
        raise HTTPException(status_code=404, detail="地址不存在")

    chain, address = r
    from app.infrastructure.blockchain.chain_client import create_chain_client
    client = create_chain_client(chain)
    if client is None:
        raise HTTPException(status_code=400, detail=f"不支持的链或不支持余额查询: {chain}")

    # Check if client has get_balance
    bal_fn = getattr(client, 'get_balance', None) or getattr(client, 'get_account_balance', None)
    if bal_fn is None:
        raise HTTPException(status_code=400, detail=f"{chain} 不支持余额查询")

    balance = await asyncio.get_event_loop().run_in_executor(
        None, bal_fn, address)

    if balance is None:
        raise HTTPException(status_code=502, detail="链上查询失败")

    await session.execute(
        text("UPDATE deposit_addresses SET last_balance=:bal, balance_updated_at=NOW() WHERE id=:id")
        .bindparams(bal=float(balance), id=da_id))
    await session.commit()

    return {"code": 0, "data": {"balance": balance}, "message": f"余额: {balance} USDT"}


# ═══════════════════════════════════════════════════
# WebSocket — real-time blockchain monitoring
# ═══════════════════════════════════════════════════

@router.websocket("/ws/blockchain")
async def ws_blockchain(ws: WebSocket):
    """WebSocket endpoint for real-time blockchain monitoring updates."""
    from app.infrastructure.blockchain.ws_manager import get_ws_manager
    manager = get_ws_manager()
    await manager.connect(ws)
    try:
        # Keep connection alive - listen for pings
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(ws)


@router.post("/blockchain/simulate-txn")
async def admin_simulate_blockchain_txn(
    da_id: int, tx_hash: str = "", amount: int = 100,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Simulate a detected blockchain transaction for testing purposes."""
    import time

    # Get the platform address
    row = await session.execute(
        text("SELECT chain, address FROM deposit_addresses WHERE id=:id AND owner_type='PLATFORM'")
        .bindparams(id=da_id))
    r = row.first()
    if not r:
        raise HTTPException(status_code=404, detail="地址不存在")

    chain, address = r
    txn_hash = tx_hash or f"sim_{int(time.time())}_{amount}"

    # Check if already exists
    existing = await session.execute(
        text("SELECT id FROM blockchain_txns WHERE chain=:ch AND tx_hash=:h")
        .bindparams(ch=chain, h=txn_hash))
    if existing.first():
        raise HTTPException(status_code=400, detail="tx_hash 已存在")

    # Try to match against pending deposits
    from app.infrastructure.blockchain.monitor import BlockchainMonitorWorker
    worker = BlockchainMonitorWorker()
    deposit_id = await worker._match_deposit(session, txn_hash, float(amount))
    status = "MATCHED" if deposit_id else "UNMATCHED"

    # Insert transaction record
    await session.execute(text(
        "INSERT INTO blockchain_txns (chain, tx_hash, from_address, to_address, "
        "amount, block_number, status, deposit_id, created_at) "
        "VALUES (:ch, :h, :f, :to, :amt, :bn, :st, :did, NOW())"
    ).bindparams(
        ch=chain, h=txn_hash, f=f"0xsim_{amount}", to=address,
        amt=float(amount), bn=int(time.time()), st=status,
        did=deposit_id or 0,
    ))

    # Auto-confirm if matched
    matched_info = ""
    if deposit_id:
        await worker._auto_confirm_deposit(session, deposit_id, txn_hash, float(amount))
        matched_info = f"自动匹配到充值 #{deposit_id}，积分已发放"

    await session.commit()

    return {
        "code": 0,
        "data": {"txn_id": 0, "tx_hash": txn_hash, "status": status,
                 "deposit_id": deposit_id},
        "message": f"模拟交易已记录，状态: {status}。" + matched_info,
    }


# ── Auth Tokens (工具授权) ──────────────────────────────────

class AuthTokenCreate(BaseModel):
    agent_id: Optional[int] = None  # NULL when owner_type='admin'
    name: str = ""
    owner_type: str = "agent"  # 'agent' or 'admin'


@router.get("/auth-tokens")
async def list_auth_tokens(
    session: AsyncSession = Depends(get_db_session),
    _: dict = Depends(_require_admin),
):
    """List all auth tokens with owner info."""
    rows = await session.execute(text(
        "SELECT at.id, at.agent_id, at.owner_type, at.token, at.name, "
        "at.status, at.last_used_at, at.expires_at, at.created_at "
        "FROM auth_tokens at "
        "ORDER BY at.created_at DESC"
    ))
    tokens = []
    for r in rows:
        # Get display name
        agent_name = ""
        if r[1]:  # agent_id is set
            ag = await session.execute(
                text("SELECT name FROM agents WHERE id=:aid").bindparams(aid=r[1])
            )
            agent_row = ag.first()
            if agent_row:
                agent_name = agent_row[0]
        elif r[2] == 'admin':
            agent_name = "管理员"

        tokens.append({
            "id": r[0], "agent_id": r[1], "owner_type": r[2],
            "token": r[3], "name": r[4] or "", "status": r[5],
            "agent_name": agent_name,
            "last_used_at": str(r[6]) if r[6] else None,
            "expires_at": str(r[7]) if r[7] else None,
            "created_at": str(r[8]) if r[8] else None,
        })
    return {"code": 0, "data": tokens, "message": "ok"}


@router.post("/auth-tokens")
async def create_auth_token(
    req: AuthTokenCreate,
    session: AsyncSession = Depends(get_db_session),
    _: dict = Depends(_require_admin),
):
    """Generate a new API key for an agent or admin."""
    owner_name = ""
    owner_type = req.owner_type or "agent"

    if owner_type == "admin":
        # Admin self-token — no agent_id needed
        owner_name = "管理员"
    else:
        # Verify agent exists
        if not req.agent_id:
            raise HTTPException(status_code=400, detail="代理商ID不能为空")
        agent = await session.execute(
            text("SELECT id, name FROM agents WHERE id=:aid").bindparams(aid=req.agent_id)
        )
        ag = agent.first()
        if not ag:
            raise HTTPException(status_code=404, detail="代理商不存在")
        owner_name = ag[1]

    # Generate secure random token
    raw_token = f"sk_{secrets.token_hex(24)}"

    row = await session.execute(
        text(
            "INSERT INTO auth_tokens (agent_id, owner_type, token, name) "
            "VALUES (:aid, :ot, :tk, :nm) RETURNING id"
        ).bindparams(
            aid=req.agent_id if owner_type != "admin" else None,
            ot=owner_type,
            tk=raw_token,
            nm=req.name
        )
    )
    tid = row.scalar()
    await session.commit()

    return {
        "code": 0,
        "data": {"id": tid, "agent_id": req.agent_id, "owner_type": owner_type,
                 "token": raw_token, "name": req.name, "status": "ACTIVE"},
        "message": f"已为「{owner_name}」生成 API Key",
    }


@router.delete("/auth-tokens/{token_id}")
async def delete_auth_token(
    token_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: dict = Depends(_require_admin),
):
    """Revoke an auth token."""
    await session.execute(
        text("UPDATE auth_tokens SET status='INACTIVE', updated_at=NOW() WHERE id=:id")
        .bindparams(id=token_id)
    )
    await session.commit()
    return {"code": 0, "message": "授权码已失效"}


@router.get("/agent-list")
async def list_agents_for_token(
    session: AsyncSession = Depends(get_db_session),
    _: dict = Depends(_require_admin),
):
    """List all agents for the auth token dropdown."""
    rows = await session.execute(
        text("SELECT a.id, a.name, s.name AS supplier_name "
             "FROM agents a JOIN suppliers s ON a.supplier_id = s.id "
             "WHERE a.status='ACTIVE' ORDER BY a.name")
    )
    agents = [{"id": r[0], "name": r[1], "supplier": r[2]} for r in rows]
    return {"code": 0, "data": agents, "message": "ok"}


# ═══════════════════════════════════════════════════
# SUPPLIER-PRODUCT AUTHORIZATION
# ═══════════════════════════════════════════════════

class SupplierAuthCreate(BaseModel):
    supplier_id: int
    status: bool = True


@router.get("/products/{pid}/suppliers")
async def list_product_suppliers(
    pid: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """查询某商品已授权的供应商列表"""
    # Verify product exists
    prod = await session.execute(
        text("SELECT id FROM products WHERE id=:pid").bindparams(pid=pid)
    )
    if not prod.first():
        raise HTTPException(status_code=404, detail="商品不存在")

    rows = await session.execute(text("""
        SELECT spa.id, spa.supplier_id, s.name AS supplier_name,
               spa.status, spa.created_at
        FROM supplier_product_auth spa
        JOIN suppliers s ON s.id = spa.supplier_id
        WHERE spa.product_id = :pid
        ORDER BY spa.id
    """).bindparams(pid=pid))
    return {"code": 0, "data": [
        {"id": r[0], "supplier_id": r[1], "supplier_name": r[2],
         "status": bool(r[3]),
         "created_at": str(r[4]) if r[4] else None} for r in rows
    ]}


@router.post("/products/{pid}/suppliers")
async def authorize_product_supplier(
    pid: int,
    req: SupplierAuthCreate,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """授权供应商（INSERT or UPDATE）"""
    # Verify product exists
    prod = await session.execute(
        text("SELECT id FROM products WHERE id=:pid").bindparams(pid=pid)
    )
    if not prod.first():
        raise HTTPException(status_code=404, detail="商品不存在")

    # Verify supplier exists
    sup = await session.execute(
        text("SELECT id FROM suppliers WHERE id=:sid").bindparams(sid=req.supplier_id)
    )
    if not sup.first():
        raise HTTPException(status_code=404, detail="供应商不存在")

    await session.execute(
        text("""
            INSERT INTO supplier_product_auth (supplier_id, product_id, status)
            VALUES (:sid, :pid, :st)
            ON CONFLICT (supplier_id, product_id)
            DO UPDATE SET status=EXCLUDED.status
        """).bindparams(sid=req.supplier_id, pid=pid, st=req.status)
    )
    await session.commit()
    return {"code": 0, "message": "授权成功"}



@router.delete("/products/{pid}/suppliers/{sid}")
async def delete_supplier_auth(
    pid: int,
    sid: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """取消授权（soft delete, status=false）"""
    row = await session.execute(
        text("""
            UPDATE supplier_product_auth
            SET status=FALSE
            WHERE product_id=:pid AND supplier_id=:sid
            RETURNING id
        """).bindparams(pid=pid, sid=sid)
    )
    if not row.first():
        raise HTTPException(status_code=404, detail="供应商授权记录不存在")
    await session.commit()
    return {"code": 0, "message": "已取消授权"}


@router.put("/products/{pid}")
async def update_product(
    pid: int,
    req: ProductUpdate,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """更新商品信息"""
    try:
        cfg = json.loads(req.collection_config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="collection_config 必须为合法 JSON")

    row = await session.execute(
        text("""
            UPDATE products
            SET name=:n, category=:c, face_value=:fv, suggested_price=:sp,
                collection_config=CAST(:cc AS jsonb), updated_at=NOW()
            WHERE id=:pid
            RETURNING id
        """).bindparams(n=req.name, c=req.category, fv=req.face_value,
                        sp=req.suggested_price, cc=json.dumps(cfg), pid=pid)
    )
    if not row.first():
        raise HTTPException(status_code=404, detail="商品不存在")
    await session.commit()
    return {"code": 0, "message": "商品信息已更新"}


# ═══════════════════════════════════════════════════════════════
# SUPPLIER-SPECIFIC AGENTS & API PAYERS
# ═══════════════════════════════════════════════════════════════


@router.get("/suppliers/{sid}/agents")
async def list_supplier_agents(
    sid: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """List all agents belonging to a specific supplier."""
    rows = await session.execute(text(
        "SELECT a.id, a.name AS nickname, a.supplier_id, "
        "a.balance, a.frozen, a.status, "
        "COALESCE(u.username, '') AS username "
        "FROM agents a "
        "LEFT JOIN users u ON u.role='AGENT' AND u.reference_id=a.id "
        "WHERE a.supplier_id=:sid ORDER BY a.id"
    ).bindparams(sid=sid))
    return {"code": 0, "data": [
        {"id": r[0], "nickname": r[1], "supplier_id": r[2],
         "balance": r[3], "frozen": r[4], "status": r[5], "username": r[6]}
        for r in rows
    ]}


@router.get("/suppliers/{sid}/api-payers")
async def list_supplier_api_payers(
    sid: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """List all API payers belonging to a specific supplier."""
    rows = await session.execute(text(
        "SELECT ap.id, ap.name AS nickname, ap.supplier_id, "
        "ap.api_key, ap.api_secret, ap.callback_url, ap.status "
        "FROM api_payers ap "
        "WHERE ap.supplier_id=:sid ORDER BY ap.id"
    ).bindparams(sid=sid))
    return {"code": 0, "data": [
        {"id": r[0], "nickname": r[1], "supplier_id": r[2],
         "api_key": r[3], "api_secret": r[4], "callback_url": r[5], "status": r[6]}
        for r in rows
    ]}


# ═══════════════════════════════════════════════════════════════
# PASSWORD / SECRET RESET
# ═══════════════════════════════════════════════════════════════


class ResetPasswordRequest(BaseModel):
    user_id: int
    new_password: str = Field(..., min_length=4, max_length=64)


@router.put("/users/reset-password")
async def admin_reset_password(
    req: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Reset a user's password. Accepts user_id OR reference_id."""
    uid = req.user_id
    # Try direct user_id match first
    row = await session.execute(
        text("UPDATE users SET password_hash=crypt(:pw, gen_salt('bf')) WHERE id=:uid RETURNING id")
        .bindparams(pw=req.new_password, uid=uid))
    if not row.first():
        # Fallback: try matching by reference_id (supplier/agent ID)
        row = await session.execute(
            text("UPDATE users SET password_hash=crypt(:pw, gen_salt('bf')) "
                 "WHERE reference_id=:rid RETURNING id")
            .bindparams(pw=req.new_password, rid=uid))
        if not row.first():
            raise HTTPException(status_code=404, detail="用户不存在")
    await session.commit()
    return {"code": 0, "message": "密码已重置", "new_password": req.new_password}


@router.post("/agents/{aid}/reset-password")
async def reset_agent_password(
    aid: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Reset an agent's login password. Returns the new password."""
    import secrets
    new_pw = secrets.token_hex(8)
    row = await session.execute(
        text("UPDATE users SET password_hash=crypt(:pw, gen_salt('bf')) WHERE reference_id=:aid AND role='AGENT' RETURNING id")
        .bindparams(pw=new_pw, aid=aid))
    if not row.first():
        raise HTTPException(status_code=404, detail="未找到关联的用户账号")
    await session.commit()
    return {"code": 0, "message": "密码已重置", "new_password": new_pw}


@router.post("/api-payers/{apid}/reset-secret")
async def reset_api_payer_secret(
    apid: int,
    session: AsyncSession = Depends(get_db_session),
    _=Depends(_require_admin),
):
    """Reset an API payer's API secret."""
    import secrets
    new_secret = f"ss_{secrets.token_hex(24)}"
    row = await session.execute(
        text("UPDATE api_payers SET api_secret=:sec WHERE id=:apid RETURNING id")
        .bindparams(sec=new_secret, apid=apid))
    if not row.first():
        raise HTTPException(status_code=404, detail="API支付商不存在")
    await session.commit()
    return {"code": 0, "message": "密钥已重置", "api_secret": new_secret}

