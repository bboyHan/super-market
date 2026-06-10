"""Recharge request model."""
from pydantic import BaseModel, Field


class RechargeRequest(BaseModel):
    amount: int = Field(..., gt=0, description="充值积分数量")
    remark: str = ""


class TransferRequest(BaseModel):
    agent_id: int = Field(..., description="代理商ID")
    amount: int = Field(..., gt=0, description="划转积分数量")
