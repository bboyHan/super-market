"""Terminal API — inventory management for agents with JWT auth."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.infrastructure.persistence.postgres.session import get_db_session
from app.interfaces.api.auth.router import get_current_user, create_jwt, decode_jwt
from app.interfaces.ws.terminal import manager

router = APIRouter(prefix="/api/terminal", tags=["terminal"])


# ── Auth helpers ─────────────────────────────────────────────

async def _get_agent_id(user: dict = Depends(get_current_user)) -> int:
    """Extract agent_id from JWT token. Returns 0 for admin users."""
    role = user.get("role")
    if role == "ADMIN":
        return 0  # Admin sees all
    if role != "AGENT":
        raise HTTPException(status_code=403, detail="需要代理商或管理员权限")
    ref_id = user.get("ref_id")
    if not ref_id:
        raise HTTPException(status_code=403, detail="无效的代理商身份")
    return ref_id


# ── DTOs ─────────────────────────────────────────────────────

class TerminalAuthRequest(BaseModel):
    agent_username: str
    agent_password: str


class TerminalAuthResponse(BaseModel):
    token: str
    agent_id: int
    supplier_id: int


class UploadItem(BaseModel):
    product_id: int
    content: str = Field(..., min_length=1, description="支付链接/二维码/卡密内容")
    expires_at: str = ""


class InventoryUploadRequest(BaseModel):
    items: list[UploadItem] = Field(..., min_length=1, max_length=1000)


# ── 1. Terminal Authentication ───────────────────────────────

@router.post("/auth")
async def terminal_auth(
    req: TerminalAuthRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Authenticate an agent terminal via username/password.
    Returns a JWT token with role=AGENT and ref_id=agent_id.
    """
    # Look up user by username
    row = await session.execute(
        text("SELECT id, username, password_hash, role, reference_id, status "
             "FROM users WHERE username = :username")
        .bindparams(username=req.agent_username)
    )
    user = row.first()

    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    uid, username, pw_hash, role, ref_id, status = user

    if role != "AGENT":
        raise HTTPException(status_code=403, detail="仅限代理商账号登录终端")
    if status != "ACTIVE":
        raise HTTPException(status_code=403, detail="账户已被禁用")

    # Verify password via pgcrypt
    verify = await session.execute(
        text("SELECT crypt(:pw, :hash) = :hash").bindparams(pw=req.agent_password, hash=pw_hash)
    )
    if not verify.scalar():
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    agent_id = ref_id
    if not agent_id:
        raise HTTPException(status_code=403, detail="代理商信息不完整")

    # Get agent's supplier_id
    agent_row = await session.execute(
        text("SELECT supplier_id FROM agents WHERE id=:aid").bindparams(aid=agent_id)
    )
    agent = agent_row.first()
    if not agent:
        raise HTTPException(status_code=404, detail="代理商不存在")
    supplier_id = agent[0]

    # Update last login
    await session.execute(
        text("UPDATE users SET last_login_at = NOW() WHERE id = :uid").bindparams(uid=uid)
    )
    await session.commit()

    # Create JWT with AGENT role
    token = create_jwt(uid, username, "AGENT", agent_id)

    return {
        "code": 0,
        "data": {
            "token": token,
            "agent_id": agent_id,
            "supplier_id": supplier_id,
        },
        "message": "登录成功",
    }


# ── 2. Authorized Products ───────────────────────────────────

@router.get("/products")
async def terminal_products(
    agent_id: int = Depends(_get_agent_id),
    session: AsyncSession = Depends(get_db_session),
):
    """List products authorized for this agent's supplier.
    Admin users (agent_id=0) see all products."""
    if agent_id == 0:
        # Admin: show all active products
        rows = await session.execute(text(
            "SELECT p.id, p.name, p.category, p.face_value, "
            "p.collection_config::text, p.suggested_price "
            "FROM products p WHERE p.status = TRUE ORDER BY p.category, p.id"
        ))
        return {
            "code": 0,
            "data": [
                {
                    "product_id": r[0], "id": r[0],
                    "name": r[1], "category": r[2],
                    "face_value": r[3],
                    "collection_config": json.loads(r[4]) if r[4] else {},
                    "settlement_price": r[5],
                }
                for r in rows
            ],
            "message": "ok",
        }

    # Agent: get supplier_id and filter by auth
    agent_row = await session.execute(
        text("SELECT supplier_id FROM agents WHERE id=:aid").bindparams(aid=agent_id)
    )
    agent = agent_row.first()
    if not agent:
        raise HTTPException(status_code=404, detail="代理商不存在")
    supplier_id = agent[0]

    rows = await session.execute(
        text("""
            SELECT p.id, p.name, p.category, p.face_value,
                   p.collection_config::text, p.suggested_price
            FROM products p
            JOIN supplier_product_auth spa ON p.id = spa.product_id
            WHERE spa.supplier_id = :sid AND spa.status = TRUE AND p.status = TRUE
            ORDER BY p.category, p.id
        """).bindparams(sid=supplier_id)
    )

    return {
        "code": 0,
        "data": [
            {
                "id": r[0], "name": r[1], "category": r[2],
                "face_value": r[3],
                "product_id": r[0],  # alias for frontend compatibility
                "collection_config": json.loads(r[4]) if r[4] else {},
                "settlement_price": r[5],
            }
            for r in rows
        ],
        "message": "ok",
    }


# ── 3. Inventory Upload (with points freeze) ─────────────────

@router.post("/inventory/upload")
async def upload_inventory(
    req: InventoryUploadRequest,
    agent_id: int = Depends(_get_agent_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Upload inventory items. For each item, freeze corresponding points from agent wallet."""
    # Verify agent exists and is active
    agent_row = await session.execute(
        text("SELECT id, supplier_id, status FROM agents WHERE id=:aid")
        .bindparams(aid=agent_id)
    )
    agent = agent_row.first()
    if not agent:
        raise HTTPException(status_code=404, detail="代理商不存在")
    if agent[2] != "ACTIVE":
        raise HTTPException(status_code=403, detail="代理商已被禁用")
    supplier_id = agent[1]

    # Group items by product_id for points calculation
    from collections import defaultdict
    product_counts: dict[int, list[UploadItem]] = defaultdict(list)
    for item in req.items:
        product_counts[item.product_id].append(item)

    # Pre-fetch all product face_values
    product_ids = list(product_counts.keys())
    placeholders = ",".join(f":pid{i}" for i in range(len(product_ids)))
    params = {f"pid{i}": pid for i, pid in enumerate(product_ids)}
    prod_rows = await session.execute(
        text(f"SELECT id, face_value, status FROM products WHERE id IN ({placeholders})")
        .bindparams(**params)
    )
    product_map: dict[int, int] = {}
    for r in prod_rows:
        if r[2]:  # status == TRUE (active)
            product_map[r[0]] = r[1]

    # Check all products exist and are active
    for pid in product_ids:
        if pid not in product_map:
            raise HTTPException(status_code=400, detail=f"货品 ID {pid} 不存在或已停用")

    # Calculate total points needed and check authorization
    total_points_needed = 0
    for pid, items_list in product_counts.items():
        face_value = product_map[pid]
        count = len(items_list)
        total_points_needed += face_value * count

    # Also verify agent is authorized for these products (through supplier)
    for pid in product_ids:
        auth_row = await session.execute(
            text("SELECT id FROM supplier_product_auth "
                 "WHERE supplier_id=:sid AND product_id=:pid AND status=TRUE")
            .bindparams(sid=supplier_id, pid=pid)
        )
        if not auth_row.first():
            raise HTTPException(status_code=400, detail=f"未授权货品 ID {pid}")

    # Check wallet and freeze points
    wallet_row = await session.execute(
        text("SELECT id, balance, frozen FROM wallets "
             "WHERE owner_type='AGENT' AND owner_id=:aid FOR UPDATE")
        .bindparams(aid=agent_id)
    )
    wallet = wallet_row.first()
    if not wallet:
        raise HTTPException(status_code=404, detail="钱包不存在")
    wid, balance, frozen = wallet

    if balance < total_points_needed:
        raise HTTPException(
            status_code=400,
            detail=f"积分不足，需要 {total_points_needed}，当前余额 {balance}",
        )

    new_balance = balance - total_points_needed
    new_frozen = frozen + total_points_needed

    # Update wallet
    await session.execute(
        text("UPDATE wallets SET balance=:b, frozen=:f, version=version+1, updated_at=NOW() "
             "WHERE id=:wid")
        .bindparams(b=new_balance, f=new_frozen, wid=wid)
    )

    # Create wallet transaction for the freeze
    await session.execute(
        text("INSERT INTO wallet_transactions (wallet_id, type, amount, balance_before, "
             "balance_after, remark, status, operator_type) "
             "VALUES (:wid, 'FREEZE', :amt, :bb, :ba, :rm, 'COMPLETED', 'AGENT')")
        .bindparams(
            wid=wid,
            amt=total_points_needed,
            bb=balance,
            ba=new_balance,
            rm=f"上传库存冻结 {total_points_needed} 积分",
        )
    )

    # Insert inventory items
    accepted = 0
    rejected = 0
    items_result = []

    for pid, items_list in product_counts.items():
        for item in items_list:
            try:
                row = await session.execute(
                    text("""
                        INSERT INTO inventory_items (agent_id, product_id, content, expires_at)
                        VALUES (:aid, :pid, :c, :ea) RETURNING id, status, created_at
                    """).bindparams(
                        aid=agent_id,
                        pid=pid,
                        c=item.content,
                        ea=item.expires_at or None,
                    )
                )
                r = row.first()
                accepted += 1
                items_result.append({
                    "id": r[0],
                    "product_id": pid,
                    "content_preview": item.content[:40] + ("..." if len(item.content) > 40 else ""),
                })
            except Exception:
                rejected += 1

    await session.commit()

    # Broadcast notification to agent's WebSocket
    await manager.send_to_agent(str(agent_id), {
        "type": "inventory_uploaded",
        "accepted": accepted,
        "rejected": rejected,
        "points_frozen": total_points_needed,
    })

    return {
        "code": 0,
        "data": {
            "accepted": accepted,
            "rejected": rejected,
            "items": items_result,
        },
        "message": f"成功上传 {accepted} 条，失败 {rejected} 条，冻结 {total_points_needed} 积分",
    }


# ── 4. Agent's Inventory List ────────────────────────────────

@router.get("/inventory")
async def terminal_list_inventory(
    product_id: int = 0,
    status: str = "",
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    agent_id: int = Depends(_get_agent_id),
    session: AsyncSession = Depends(get_db_session),
):
    """List inventory items for the authenticated agent."""
    where = ["i.agent_id = :aid"]
    params: dict = {"aid": agent_id}

    if product_id:
        where.append("i.product_id = :pid")
        params["pid"] = product_id
    if status:
        where.append("i.status = :s")
        params["s"] = status

    w = " AND ".join(where)

    total = await session.execute(
        text(f"SELECT count(*) FROM inventory_items i WHERE {w}").bindparams(**params)
    )
    count = total.scalar() or 0

    rows = await session.execute(
        text(f"""
            SELECT i.id, i.agent_id, a.name AS agent_name,
                   i.product_id, p.name AS product_name,
                   i.content, i.status, i.created_at, i.expires_at
            FROM inventory_items i
            JOIN agents a ON i.agent_id = a.id
            JOIN products p ON i.product_id = p.id
            WHERE {w}
            ORDER BY i.created_at DESC
            LIMIT {limit} OFFSET {(page - 1) * limit}
        """).bindparams(**params)
    )

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "agent_id": r[1],
            "agent_name": r[2],
            "product_id": r[3],
            "product_name": r[4],
            "content": r[5],
            "status": r[6],
            "created_at": str(r[7]) if r[7] else None,
            "expires_at": str(r[8]) if r[8] else None,
        })

    return {
        "code": 0,
        "data": {
            "items": items,
            "total": count,
            "page": page,
            "limit": limit,
        },
    }


# ── 5. WebSocket (authenticated) ─────────────────────────────

@router.websocket("/ws")
async def terminal_ws(
    websocket: WebSocket,
    token: str = Query(...),
):
    """Authenticated WebSocket endpoint for terminal notifications.
    Pass ?token=JWT in query string. Agent receives order notifications.
    """
    # Authenticate via query param token
    try:
        user = decode_jwt(token)
        role = user.get("role")
        ref_id = user.get("ref_id")
        if role != "AGENT" or not ref_id:
            await websocket.close(code=4001, reason="Unauthorized: not an agent")
            return
        agent_id = str(ref_id)
    except HTTPException:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await manager.connect(agent_id, websocket)
    try:
        # Send a welcome message
        await websocket.send_json({
            "type": "connected",
            "agent_id": agent_id,
            "message": "终端已连接，等待通知...",
        })

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            logger.debug("Terminal WS msg | agent={} data={}", agent_id, message)
            await websocket.send_json({"type": "echo", "data": message})
    except WebSocketDisconnect:
        logger.info("Terminal WS disconnected | agent={}", agent_id)
    except Exception:
        logger.exception("Terminal WS error | agent={}", agent_id)
    finally:
        manager.disconnect(agent_id)


# ── Legacy unauthenticated endpoints (kept for backward compat) ──

class InventoryItemCreate(BaseModel):
    agent_id: int
    product_id: int
    content: str = Field(..., min_length=1, description="支付链接/二维码/卡密内容")
    expires_at: str = ""


class BatchInventoryCreate(BaseModel):
    agent_id: int
    product_id: int
    items: list[str] = Field(..., min_length=1, max_length=1000)


@router.post("/inventory")
async def add_inventory_legacy(
    req: InventoryItemCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """Add a single inventory item (legacy, no auth)."""
    agent = await session.execute(
        text("SELECT id, status FROM agents WHERE id=:id").bindparams(id=req.agent_id)
    )
    if not agent.first():
        raise HTTPException(status_code=404, detail="代理商不存在")

    prod = await session.execute(
        text("SELECT id, status FROM products WHERE id=:id").bindparams(id=req.product_id)
    )
    if not prod.first():
        raise HTTPException(status_code=404, detail="货品不存在")

    row = await session.execute(
        text("""
        INSERT INTO inventory_items (agent_id, product_id, content, expires_at)
        VALUES (:aid, :pid, :c, :ea) RETURNING id, status, created_at
        """).bindparams(aid=req.agent_id, pid=req.product_id, c=req.content,
                       ea=req.expires_at or None)
    )
    r = row.first()
    await session.commit()
    return {"code": 0, "data": {
        "id": r[0], "agent_id": req.agent_id, "product_id": req.product_id,
        "content": req.content[:40] + ("..." if len(req.content) > 40 else ""),
        "status": r[1], "created_at": str(r[2]) if r[2] else None,
    }, "message": "库存添加成功"}


@router.post("/inventory/batch")
async def batch_add_inventory(
    req: BatchInventoryCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """Batch add inventory items."""
    agent = await session.execute(
        text("SELECT id FROM agents WHERE id=:id").bindparams(id=req.agent_id)
    )
    if not agent.first():
        raise HTTPException(status_code=404, detail="代理商不存在")

    added = 0
    for content in req.items:
        await session.execute(
            text("INSERT INTO inventory_items (agent_id, product_id, content) "
                 "VALUES (:aid, :pid, :c)")
            .bindparams(aid=req.agent_id, pid=req.product_id, c=content)
        )
        added += 1

    await session.commit()
    return {"code": 0, "data": {"added": added}, "message": f"成功添加 {added} 条库存"}


@router.get("/inventory/summary")
async def inventory_summary(
    agent_id: int = 0,
    session: AsyncSession = Depends(get_db_session),
):
    """Get inventory summary grouped by product."""
    where = "WHERE 1=1"
    if agent_id:
        where += f" AND i.agent_id = {agent_id}"

    rows = await session.execute(text(f"""
        SELECT i.product_id, p.name AS product_name,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE i.status='AVAILABLE') AS available,
               COUNT(*) FILTER (WHERE i.status='USED') AS used
        FROM inventory_items i
        JOIN products p ON i.product_id = p.id
        {where}
        GROUP BY i.product_id, p.name
        ORDER BY product_name
    """))
    return {"code": 0, "data": [
        {"product_id": r[0], "product_name": r[1],
         "total": r[2], "available": r[3], "used": r[4]} for r in rows
    ]}


@router.delete("/inventory/{item_id}")
async def delete_inventory(
    item_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Soft-delete (mark expired) an inventory item."""
    await session.execute(
        text("UPDATE inventory_items SET status='EXPIRED' WHERE id=:id").bindparams(id=item_id)
    )
    await session.commit()
    return {"code": 0, "message": "已移除"}


# ── Auth Token Login (工具端通过 API Key 登录) ──────────────

class AuthTokenLoginRequest(BaseModel):
    api_key: str = Field(..., min_length=8)


@router.post("/auth-token-login")
async def terminal_login_via_token(
    req: AuthTokenLoginRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Authenticate a terminal via API key auth token.
    Returns a JWT token for subsequent API calls.
    Supports both agent tokens and admin tokens.
    """
    # Look up the token
    row = await session.execute(
        text("SELECT at.id, at.agent_id, at.owner_type, at.status, at.expires_at "
             "FROM auth_tokens at "
             "WHERE at.token = :tk")
        .bindparams(tk=req.api_key)
    )
    t = row.first()
    if not t:
        return {"code": 40001, "data": None, "msg": "授权码无效"}

    tid, agent_id, owner_type, status, expires_at = t

    if status != "ACTIVE":
        return {"code": 40001, "data": None, "msg": "授权码已失效"}

    if expires_at and expires_at < __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc):
        return {"code": 40001, "data": None, "msg": "授权码已过期"}

    from app.interfaces.api.auth.router import create_jwt

    if owner_type == "admin":
        # Admin token — create an ADMIN role JWT
        # Find the admin user
        user_row = await session.execute(
            text("SELECT id, username FROM users WHERE role='ADMIN' ORDER BY id LIMIT 1")
        )
        admin_user = user_row.first()
        if not admin_user:
            return {"code": 50003, "data": None, "msg": "未找到管理员账号"}

        user_id, username = admin_user

        # Update last_used_at
        await session.execute(
            text("UPDATE auth_tokens SET last_used_at=NOW() WHERE id=:id")
            .bindparams(id=tid)
        )

        jwt_token = create_jwt(user_id, username, "ADMIN", None)

        await session.commit()

        return {
            "code": 0,
            "data": {
                "token": jwt_token,
                "user_id": user_id,
                "username": username,
                "role": "ADMIN",
            },
            "msg": "授权成功（管理员）",
        }
    else:
        # Agent token — existing logic
        # Get agent info
        agent_row = await session.execute(
            text("SELECT name, supplier_id FROM agents WHERE id=:aid")
            .bindparams(aid=agent_id)
        )
        agent = agent_row.first()
        if not agent:
            return {"code": 40001, "data": None, "msg": "关联的代理商不存在"}

        agent_name, supplier_id = agent

        # Get the user_id from users table
        user_row = await session.execute(
            text("SELECT id FROM users WHERE reference_id=:rid AND role='AGENT'")
            .bindparams(rid=agent_id)
        )
        user = user_row.first()
        if not user:
            return {"code": 50003, "data": None, "msg": "未找到关联的用户账号"}

        user_id = user[0]

        # Update last_used_at
        await session.execute(
            text("UPDATE auth_tokens SET last_used_at=NOW() WHERE id=:id")
            .bindparams(id=tid)
        )

        jwt_token = create_jwt(user_id, agent_name, "AGENT", agent_id)

        await session.commit()

        return {
            "code": 0,
            "data": {
                "token": jwt_token,
                "agent_id": agent_id,
                "supplier_id": supplier_id,
                "agent_name": agent_name,
            },
            "msg": "授权成功",
        }
