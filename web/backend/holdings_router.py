"""API routes for portfolio holdings management."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .holdings_manager import HoldingsManager

router = APIRouter()

_hm: Optional[HoldingsManager] = None


def get_holdings_manager() -> HoldingsManager:
    global _hm
    if _hm is None:
        _hm = HoldingsManager()
    return _hm


def init_holdings_manager() -> HoldingsManager:
    global _hm
    _hm = HoldingsManager()
    return _hm


# ── Request Models ─────────────────────────────────────────────────

class AddHoldingRequest(BaseModel):
    ticker: str = Field(..., description="股票代码，如 600000.SH")
    name: str = Field("", description="股票名称")
    quantity: int = Field(..., ge=0, description="持仓数量（股）")
    cost_price: float = Field(..., ge=0, description="成本价（元）")
    notes: str = Field("", description="备注")


class UpdateHoldingRequest(BaseModel):
    quantity: int = Field(..., ge=0, description="持仓数量（股）")
    cost_price: float = Field(..., ge=0, description="成本价（元）")
    notes: str = Field("", description="备注")


# ── Routes ─────────────────────────────────────────────────────────

@router.get("/api/holdings")
async def list_holdings():
    return get_holdings_manager().list_holdings()


@router.post("/api/holdings")
async def add_holding(req: AddHoldingRequest):
    return get_holdings_manager().add_holding(
        ticker=req.ticker,
        name=req.name,
        quantity=req.quantity,
        cost_price=req.cost_price,
        notes=req.notes,
    )


@router.put("/api/holdings/{holding_id}")
async def update_holding(holding_id: int, req: UpdateHoldingRequest):
    ok = get_holdings_manager().update_holding(
        holding_id=holding_id,
        quantity=req.quantity,
        cost_price=req.cost_price,
        notes=req.notes,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="持仓记录不存在")
    return {"ok": True}


@router.delete("/api/holdings/{holding_id}")
async def remove_holding(holding_id: int):
    ok = get_holdings_manager().remove_holding(holding_id)
    if not ok:
        raise HTTPException(status_code=404, detail="持仓记录不存在")
    return {"ok": True}


@router.get("/api/holdings/ticker/{ticker}")
async def get_holding_by_ticker(ticker: str):
    holding = get_holdings_manager().get_holding_by_ticker(ticker)
    return holding if holding else None
