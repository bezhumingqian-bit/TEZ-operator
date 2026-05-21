"""接口人路由器 API。

GET  /api/v1/contacts/route?q=...     核心：输入场景描述→返回接口人
GET  /api/v1/contacts/search?q=...    模糊搜索接口人
GET  /api/v1/contacts                 接口人列表
POST /api/v1/contacts                 新增接口人
GET  /api/v1/contacts/{id}            接口人详情
PUT  /api/v1/contacts/{id}            更新接口人
GET  /api/v1/contacts/categories      事项分类列表
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_db_session
from app.schemas.contact import (
    CategoryInfo,
    ContactCreate,
    ContactInfo,
    ContactSearchResponse,
    ContactUpdate,
    RouteResponse,
)
from app.services.contact_service import ContactService

router = APIRouter(prefix="/contacts", tags=["contacts"])


async def _get_service(session=Depends(get_db_session)):
    return ContactService(session)


@router.get(
    "/route",
    response_model=RouteResponse,
    summary="接口人路由 — 输入场景描述，返回负责人",
)
async def route_query(
    q: str = Query(..., description="场景描述，如'母机故障'", min_length=1),
    service: ContactService = Depends(_get_service),
) -> RouteResponse:
    """核心功能：输入"我要做什么"，返回接口人+备份+升级路径。"""
    results = await service.route(q)
    return RouteResponse(query=q, results=results, total=len(results))


@router.get(
    "/search",
    response_model=ContactSearchResponse,
    summary="模糊搜索接口人",
)
async def search_contacts(
    q: str = Query(..., description="搜索关键词", min_length=1),
    service: ContactService = Depends(_get_service),
) -> ContactSearchResponse:
    contacts = await service.search_contacts(q)
    return ContactSearchResponse(
        query=q,
        contacts=contacts,
        total=len(contacts),
    )


@router.get(
    "",
    response_model=list[ContactInfo],
    summary="接口人列表",
)
async def list_contacts(
    status: str | None = Query(None, description="过滤状态: active/vacation/left"),
    service: ContactService = Depends(_get_service),
) -> list[ContactInfo]:
    return await service.list_contacts(status=status)


@router.post(
    "",
    response_model=ContactInfo,
    status_code=201,
    summary="新增接口人",
)
async def create_contact(
    payload: ContactCreate,
    service: ContactService = Depends(_get_service),
) -> ContactInfo:
    contact = await service.create_contact(payload)
    await service.session.commit()
    return contact


@router.get(
    "/categories",
    response_model=list[CategoryInfo],
    summary="事项分类列表",
)
async def list_categories(
    service: ContactService = Depends(_get_service),
) -> list[CategoryInfo]:
    return await service.list_categories()


@router.get(
    "/{contact_id}",
    response_model=ContactInfo,
    summary="接口人详情",
)
async def get_contact(
    contact_id: int,
    service: ContactService = Depends(_get_service),
) -> ContactInfo:
    contact = await service.get_contact(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="接口人不存在")
    return contact


@router.put(
    "/{contact_id}",
    response_model=ContactInfo,
    summary="更新接口人",
)
async def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    service: ContactService = Depends(_get_service),
) -> ContactInfo:
    contact = await service.update_contact(contact_id, payload)
    if not contact:
        raise HTTPException(status_code=404, detail="接口人不存在")
    await service.session.commit()
    return contact
