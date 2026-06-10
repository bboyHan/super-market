"""Task management API router."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from services import task_manager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# --- Request / Response Models ---

class CreateTaskRequest(BaseModel):
    platform: str = Field(..., description="Platform name (e.g., jd, taobao)")
    product_id: str = Field(..., description="Product ID on the platform")
    quantity: int = Field(default=1, ge=1, le=100, description="Number of credentials to collect")
    method: str = Field(default="browser", pattern="^(browser|emulator|cdp|manual)$")
    auto_mode: str = Field(default="semi", pattern="^(full|semi|assisted)$")
    account_id: Optional[int] = Field(default=None, description="QQ account ID for collect/batch modes")
    mode: Optional[str] = Field(default=None, description="QQ coin collection mode: add_account|collect|batch_collect")


class CreateTaskResponse(BaseModel):
    task_id: str
    status: str = "pending"


class TaskResponse(BaseModel):
    task_id: str
    platform: str
    product_id: str
    quantity: int
    method: str
    auto_mode: str
    account_id: Optional[int] = None
    mode: Optional[str] = None
    status: str
    progress: int
    current_step: str
    error_message: Optional[str]
    result: Optional[str]
    logs: list[str] = []
    qr_image: str = ""
    created_at: str
    updated_at: str
    completed_at: Optional[str]


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int


# --- Endpoints ---

@router.post("/create", response_model=CreateTaskResponse)
async def create_task(req: CreateTaskRequest):
    """Create a new credential collection task."""
    try:
        config = req.model_dump()
        task_id = task_manager.create_task(config)
        return CreateTaskResponse(task_id=task_id, status="pending")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=TaskListResponse)
async def list_tasks(status: Optional[str] = None):
    """List all tasks, optionally filtered by status."""
    try:
        tasks = task_manager.list_tasks(status_filter=status)
        return TaskListResponse(
            tasks=[TaskResponse(**{k: t[k] for k in t if k in TaskResponse.model_fields}) for t in tasks],
            total=len(tasks),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get detailed information about a specific task."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    # Fetch recent logs for this task
    logs = []
    from storage.db import get_cursor
    with get_cursor() as cursor:
        log_rows = cursor.execute(
            "SELECT message FROM logs WHERE source = ? ORDER BY id DESC LIMIT 50",
            (task_id,),
        ).fetchall()
        logs = [r[0] for r in reversed(log_rows)]
    
    result = {k: task[k] for k in task if k in TaskResponse.model_fields}
    result["logs"] = logs
    return TaskResponse(**result)


@router.post("/{task_id}/pause")
async def pause_task(task_id: str):
    """Pause a running task."""
    success = await task_manager.pause_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause task {task_id}: not currently running",
        )
    return {"status": "paused", "task_id": task_id}


@router.post("/{task_id}/resume")
async def resume_task(task_id: str):
    """Resume a paused task."""
    success = await task_manager.resume_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume task {task_id}: not currently paused",
        )
    return {"status": "running", "task_id": task_id}


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a task."""
    success = await task_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found",
        )
    return {"status": "cancelled", "task_id": task_id}


# --- Manual Input Endpoint ---

class TaskInputRequest(BaseModel):
    values: list[str] = Field(..., description="List of user-pasted values (URLs, QR codes, card keys)")


class TaskInputResponse(BaseModel):
    received: int
    message: str


@router.post("/{task_id}/input", response_model=TaskInputResponse)
async def provide_task_input(task_id: str, req: TaskInputRequest):
    """Provide manual input values to a task waiting for user input."""
    success = await task_manager.provide_input(task_id, req.values)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot provide input for task {task_id}: task not found or not awaiting input",
        )
    return TaskInputResponse(
        received=len(req.values),
        message=f"Received {len(req.values)} values for task {task_id}",
    )
