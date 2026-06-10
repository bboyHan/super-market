"""Platform communication API router - interfaces with Super Market platform."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

import httpx
from config import settings
from storage.db import get_setting, set_setting, add_log

router = APIRouter(prefix="/api/platform", tags=["platform"])


# ── Auth Token Login (proxy to platform) ────────────────────

class AuthTokenLoginRequest(BaseModel):
    api_key: str


@router.post("/auth-token-login")
async def auth_token_login(req: AuthTokenLoginRequest):
    """Authenticate via API key by proxying to the platform."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{PLATFORM_BASE}/api/terminal/auth-token-login",
                json={"api_key": req.api_key},
            )
            result = resp.json()
            if result.get("code") == 0 and result.get("data") and result["data"].get("token"):
                token = result["data"]["token"]
                set_setting("agent_token", token)
                set_setting("agent_username", result["data"].get("agent_name", ""))
                add_log("info", "system", "Authenticated via API key")
            return result
    except httpx.RequestError as e:
        return {"code": 500, "data": None, "msg": f"无法连接平台: {str(e)}"}


# --- Models ---

class PlatformStatusResponse(BaseModel):
    connected: bool
    platform_url: str
    agent_name: Optional[str] = None
    version: Optional[str] = None
    error: Optional[str] = None


class BindRequest(BaseModel):
    agent_username: str = Field(..., description="Super Market agent username")
    agent_password: str = Field(..., description="Super Market agent password")


class BindResponse(BaseModel):
    success: bool
    message: str
    agent_name: Optional[str] = None


class ProductItem(BaseModel):
    product_id: int
    name: str
    category: str = ""
    face_value: int = 0
    settlement_price: int = 0
    collection_config: dict = {}


class ProductListResponse(BaseModel):
    products: list[ProductItem]
    total: int


class UploadResourceRequest(BaseModel):
    items: list[dict] = Field(..., description="List of {product_id, content, expires_at}")


class UploadResourceResponse(BaseModel):
    success: bool
    platform_resource_ids: list[str] = []
    error: Optional[str] = None


# --- Helpers ---

def _get_headers() -> dict:
    """Get headers with auth token for platform API calls.
    Priority: 运行时登录获取的 token > 配置文件中的默认值（通常为空）。
    """
    token = get_setting("agent_token", "") or settings.AGENT_TOKEN
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


PLATFORM_BASE = "http://localhost:8000"


# --- Endpoints ---

@router.get("/status", response_model=PlatformStatusResponse)
async def get_platform_status():
    """Check connection status with the Super Market platform."""
    token = get_setting("agent_token", "") or settings.AGENT_TOKEN
    if not token:
        return PlatformStatusResponse(
            connected=False,
            platform_url=PLATFORM_BASE,
            error="Not authenticated. Please bind first.",
        )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{PLATFORM_BASE}/api/terminal/products",
                headers=_get_headers(),
            )
            if resp.status_code == 200:
                return PlatformStatusResponse(
                    connected=True,
                    platform_url=PLATFORM_BASE,
                    agent_name=get_setting("agent_username", ""),
                    version="1.0.0",
                )
            else:
                return PlatformStatusResponse(
                    connected=False,
                    platform_url=PLATFORM_BASE,
                    error=f"Token invalid or expired (status {resp.status_code})",
                )
    except httpx.RequestError as e:
        return PlatformStatusResponse(
            connected=False,
            platform_url=PLATFORM_BASE,
            error=str(e),
        )


@router.post("/bind", response_model=BindResponse)
async def bind_to_platform(req: BindRequest):
    """Bind this agent terminal to the Super Market platform with username/password."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Step 1: Login to get token
            login_resp = await client.post(
                f"{PLATFORM_BASE}/api/auth/login",
                json={"username": req.agent_username, "password": req.agent_password},
            )
            if login_resp.status_code != 200:
                error_detail = login_resp.text[:500]
                return BindResponse(
                    success=False,
                    message=f"Login failed: {error_detail}",
                )

            login_data = login_resp.json()
            token = login_data.get("access_token")
            if not token:
                return BindResponse(
                    success=False,
                    message="Login succeeded but no access_token returned",
                )

            # Store the token
            set_setting("agent_token", token)
            set_setting("agent_username", req.agent_username)

            # Step 2: Verify token works by calling products endpoint
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            verify_resp = await client.get(
                f"{PLATFORM_BASE}/api/terminal/products",
                headers=headers,
            )
            if verify_resp.status_code != 200:
                return BindResponse(
                    success=True,
                    message=f"Token stored but verification returned {verify_resp.status_code}",
                    agent_name=req.agent_username,
                )

            add_log("info", "system",
                    f"Successfully bound to platform as {req.agent_username}")
            return BindResponse(
                success=True,
                message="Agent bound to platform successfully",
                agent_name=req.agent_username,
            )

    except httpx.RequestError as e:
        return BindResponse(
            success=False,
            message=f"Cannot reach platform: {str(e)}",
        )


@router.get("/products", response_model=ProductListResponse)
async def get_authorized_products():
    """Get the list of products this agent is authorized to collect for."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{PLATFORM_BASE}/api/terminal/products",
                headers=_get_headers(),
            )
            if resp.status_code == 200:
                raw = resp.json()
                # Platform returns {"code":0, "data":[{id,name,category,face_value,...}]}
                raw_products = raw.get("data", []) if isinstance(raw, dict) else raw
                if isinstance(raw_products, dict):
                    raw_products = raw_products.get("items", raw_products.get("data", []))
                products = []
                for p in raw_products:
                    if isinstance(p, dict):
                        products.append(ProductItem(
                            product_id=p.get("id", 0),
                            name=p.get("name", ""),
                            category=p.get("category", ""),
                            face_value=p.get("face_value", 0),
                            settlement_price=p.get("settlement_price", 0),
                            collection_config=p.get("collection_config", {}),
                        ))
                return ProductListResponse(
                    products=products,
                    total=len(products),
                )
            else:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Platform returned: {resp.text[:300]}",
                )
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Cannot reach platform: {str(e)}")


@router.post("/upload-resource", response_model=UploadResourceResponse)
async def upload_single_resource(req: UploadResourceRequest):
    """Upload resources to the platform via inventory upload endpoint."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{PLATFORM_BASE}/api/terminal/inventory/upload",
                json={"items": req.items},
                headers=_get_headers(),
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                # Platform returns {"code":0, "data":{"items":[{"id":...}]}}
                items = []
                if isinstance(data, dict):
                    resp_data = data.get("data", data)
                    if isinstance(resp_data, dict):
                        items = resp_data.get("items", [resp_data])
                    elif isinstance(resp_data, list):
                        items = resp_data
                ids = [str(item.get("id", "")) for item in items if isinstance(item, dict)]
                return UploadResourceResponse(
                    success=True,
                    platform_resource_ids=ids,
                )
            else:
                return UploadResourceResponse(
                    success=False,
                    error=f"Platform returned {resp.status_code}: {resp.text[:300]}",
                )
    except httpx.RequestError as e:
        return UploadResourceResponse(
            success=False,
            error=str(e),
        )
