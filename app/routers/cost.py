"""机型成本 API。"""

from fastapi import APIRouter

from app.data.machine_cost import MACHINE_COST_DATA

router = APIRouter(prefix="/api/v1/cost", tags=["cost"])


@router.get("/machines", summary="获取机型成本数据")
async def get_machine_costs():
    return {"items": MACHINE_COST_DATA, "total": len(MACHINE_COST_DATA)}
