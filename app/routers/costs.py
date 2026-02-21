from fastapi import APIRouter, Request
from starlette.templating import Jinja2Templates
from pathlib import Path

from app.services.cost_tracker import get_daily_costs, get_monthly_costs

router = APIRouter(tags=["costs"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/costs")
async def costs_page(request: Request):
    return templates.TemplateResponse("costs.html", {"request": request})


@router.get("/api/costs/daily")
async def daily_costs():
    return await get_daily_costs()


@router.get("/api/costs/monthly")
async def monthly_costs():
    return await get_monthly_costs()
