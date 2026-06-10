"""Agent Terminal 本地库存管理 API 路由。

职责：
  - 管理本地 SQLite 中的已采集资源
  - 上传资源到远端的 Super Market 平台
  - 删除/批量操作
"""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from storage.db import get_cursor, add_log
from config import settings
import httpx

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


# ── 模型 ─────────────────────────────────────


class ResourceItem(BaseModel):
    """单条库存项，对应 SQLite resources 表"""
    id: int
    resource_id: str
    task_id: str
    platform: str             # 平台/货品类型，如 qq_coin
    product_id: str           # 平台侧货品 ID
    resource_type: str        # 凭证类型：qrcode / link / code
    value: str                # 原始内容（base64 / URL / 卡密）
    content_preview: str      # 前端展示用截断字段
    status: str               # collected / uploaded / consumed
    expires_at: Optional[str]
    metadata: Optional[str]   # JSON 字符串
    created_at: str
    uploaded_at: Optional[str]


class ResourceListResponse(BaseModel):
    resources: list[ResourceItem]
    total: int
    page: int
    page_size: int


class DeleteRequest(BaseModel):
    resource_ids: list[str] = Field(..., min_length=1, max_length=200)


class DeleteResponse(BaseModel):
    deleted: int


class UploadResponse(BaseModel):
    uploaded: list[str]
    errors: list[dict]
    success_count: int
    error_count: int


# ── 辅助函数 ──────────────────────────────────


def _build_preview(value: str, max_len: int = 60) -> str:
    """生成前端预览文本。
    - base64 图片 → 标记为图片
    - URL → 截断展示
    - 普通文本 → 截断展示
    """
    if value.startswith("data:image"):
        return "[图片]"
    if value.startswith("http://") or value.startswith("https://"):
        return value[:max_len] + ("..." if len(value) > max_len else "")
    return value[:max_len] + ("..." if len(value) > max_len else "")


def _resource_row_to_item(row: dict) -> ResourceItem:
    """将 SQLite 行转成 ResourceItem"""
    value = row.get("value") or ""
    return ResourceItem(
        id=row["id"],
        resource_id=row["resource_id"],
        task_id=row["task_id"],
        platform=row["platform"],
        product_id=row["product_id"],
        resource_type=row["resource_type"],
        value=value,
        content_preview=_build_preview(value),
        status=row["status"],
        expires_at=row.get("expires_at"),
        metadata=row.get("metadata"),
        created_at=row["created_at"],
        uploaded_at=row.get("uploaded_at"),
    )


# ── 1. 列表 ──────────────────────────────────


@router.get("/list", response_model=ResourceListResponse)
async def list_resources(
    status: Optional[str] = Query(None, description="按状态筛选"),
    platform: Optional[str] = Query(None, description="按货品类型筛选"),
    product: Optional[str] = Query(None, description="按产品 ID 筛选"),
    search: Optional[str] = Query(None, description="搜索凭证内容"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """列出本地已采集的资源，支持筛选、搜索、分页。"""
    with get_cursor() as cursor:
        query = "SELECT * FROM resources WHERE 1=1"
        params: list = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if product:
            query += " AND product_id = ?"
            params.append(product)
        if search:
            query += " AND (value LIKE ? OR resource_id LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like])

        # 总数
        count_query = query.replace("SELECT *", "SELECT COUNT(*) as cnt")
        total = cursor.execute(count_query, params).fetchone()["cnt"]

        # 分页
        offset = (page - 1) * page_size
        ordering = " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([page_size, offset])

        rows = cursor.execute(query + ordering, params).fetchall()

    return ResourceListResponse(
        resources=[_resource_row_to_item(dict(r)) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── 2. 删除（单条 / 批量）────────────────────


@router.post("/delete", response_model=DeleteResponse)
async def delete_resources(req: DeleteRequest):
    """从本地 SQLite 删除指定的资源（硬删除）。"""
    placeholders = ",".join("?" for _ in req.resource_ids)
    deleted = 0
    with get_cursor() as cursor:
        cursor.execute(
            f"DELETE FROM resources WHERE resource_id IN ({placeholders})",
            req.resource_ids,
        )
        deleted = cursor.rowcount

    if deleted > 0:
        add_log("info", "system", f"删除 {deleted} 条本地库存")

    return DeleteResponse(deleted=deleted)


# ── 3. 上传到平台 ────────────────────────────


@router.post("/upload-to-platform", response_model=UploadResponse)
async def upload_to_platform(resource_ids: list[str]):
    """将本地已采集的凭证上传到 Super Market 平台。
    调用平台 POST /api/terminal/inventory/upload，自动冻结积分。
    """
    if not resource_ids:
        raise HTTPException(status_code=400, detail="未选择任何资源")

    uploaded = []
    errors = []

    # 按 product_id 分组，批量上传
    groups: dict[str, list[dict]] = {}

    with get_cursor() as cursor:
        placeholders = ",".join("?" for _ in resource_ids)
        rows = cursor.execute(
            f"SELECT * FROM resources WHERE resource_id IN ({placeholders})",
            resource_ids,
        ).fetchall()

        for r in rows:
            row = dict(r)
            pid = row["product_id"]
            if pid not in groups:
                groups[pid] = []
            groups[pid].append({
                "resource_id": row["resource_id"],
                "content": row["value"],
                "expires_at": row.get("expires_at") or "",
            })

    # 逐 product 分组上传
    async with httpx.AsyncClient(timeout=60) as client:
        for pid, items in groups.items():
            payload = {
                "items": [
                    {
                        "product_id": int(pid),
                        "content": item["content"],
                        "expires_at": item["expires_at"],
                    }
                    for item in items
                ]
            }

            try:
                from storage.db import get_setting as _get_setting
                _token = _get_setting("agent_token", "") or settings.AGENT_TOKEN
                _headers = {"Content-Type": "application/json"}
                if _token:
                    _headers["Authorization"] = f"Bearer {_token}"
                resp = await client.post(
                    f"{settings.PLATFORM_API_BASE}/api/terminal/inventory/upload",
                    json=payload, headers=_headers,
                )

                if resp.status_code in (200, 201):
                    body = resp.json()
                    if body.get("code") == 0:
                        # 全部成功
                        now = datetime.utcnow().isoformat() + "Z"
                        with get_cursor() as cursor:
                            for item in items:
                                cursor.execute(
                                    "UPDATE resources SET status='uploaded', uploaded_at=? WHERE resource_id=?",
                                    (now, item["resource_id"]),
                                )
                        uploaded.extend(i["resource_id"] for i in items)
                        add_log(
                            "info",
                            "system",
                            f"上传 {len(items)} 条库存到平台成功（货品 {pid}）",
                        )
                    else:
                        # 平台业务错误
                        for item in items:
                            errors.append({
                                "resource_id": item["resource_id"],
                                "error": body.get("message", "平台拒绝"),
                            })
                else:
                    detail = await resp.text()
                    for item in items:
                        errors.append({
                            "resource_id": item["resource_id"],
                            "error": f"HTTP {resp.status_code}: {detail[:200]}",
                        })
            except httpx.RequestError as e:
                for item in items:
                    errors.append({
                        "resource_id": item["resource_id"],
                        "error": f"连接失败: {str(e)}",
                    })

    return UploadResponse(
        uploaded=uploaded,
        errors=errors,
        success_count=len(uploaded),
        error_count=len(errors),
    )


# ── 4. 统计 ──────────────────────────────────


class InventoryStats(BaseModel):
    total_resources: int
    collected_count: int
    uploaded_count: int
    consumed_count: int
    by_platform: dict[str, int]
    expired_count: int


@router.get("/stats", response_model=InventoryStats)
async def get_inventory_stats():
    """库存统计：总数 / 按状态 / 按平台"""
    with get_cursor() as cursor:
        total = cursor.execute("SELECT COUNT(*) as cnt FROM resources").fetchone()["cnt"]
        collected = cursor.execute("SELECT COUNT(*) as cnt FROM resources WHERE status='collected'").fetchone()["cnt"]
        uploaded = cursor.execute("SELECT COUNT(*) as cnt FROM resources WHERE status='uploaded'").fetchone()["cnt"]
        consumed = cursor.execute("SELECT COUNT(*) as cnt FROM resources WHERE status='consumed'").fetchone()["cnt"]

        by_platform_rows = cursor.execute(
            "SELECT platform, COUNT(*) as cnt FROM resources GROUP BY platform"
        ).fetchall()
        by_platform = {r["platform"]: r["cnt"] for r in by_platform_rows}

        now = datetime.utcnow().isoformat() + "Z"
        expired = cursor.execute(
            "SELECT COUNT(*) as cnt FROM resources WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        ).fetchone()["cnt"]

    return InventoryStats(
        total_resources=total,
        collected_count=collected,
        uploaded_count=uploaded,
        consumed_count=consumed,
        by_platform=by_platform,
        expired_count=expired,
    )


# ── 5. 仪表盘概览 ────────────────────────────


@router.get("/summary")
async def get_inventory_summary():
    """按货品分组的库存健康度（供 Dashboard 使用）"""
    with get_cursor() as cursor:
        rows = cursor.execute("""
            SELECT r.platform, r.product_id, r.resource_type,
                   COUNT(*) as total,
                   SUM(CASE WHEN r.status='collected' THEN 1 ELSE 0 END) as collected,
                   SUM(CASE WHEN r.status='uploaded' THEN 1 ELSE 0 END) as uploaded
            FROM resources r
            GROUP BY r.platform, r.product_id, r.resource_type
            ORDER BY collected DESC
        """).fetchall()

        items = []
        for r in rows:
            total = r["total"] or 0
            collected = r["collected"] or 0
            uploaded = r["uploaded"] or 0
            pct = int((uploaded / total * 100)) if total > 0 else 0
            items.append({
                "product_name": f"{r['platform']} #{r['product_id']}" if r['product_id'] else (r['platform'] or '未知'),
                "resource_type": r["resource_type"] or "",
                "total": total,
                "collected": collected,
                "uploaded": uploaded,
                "percentage": pct,
            })
        return {"code": 0, "data": items}
