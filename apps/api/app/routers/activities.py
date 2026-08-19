import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security.deps import CurrentUser, RequireAE
from app.models.crm import Activity
from app.schemas.crm import ActivityCreate, ActivityUpdate, ActivityOut

router = APIRouter(prefix="/activities", tags=["Activities"])


@router.get("", response_model=list[ActivityOut])
async def list_activities(
    _: Annotated[None, RequireAE],
    current_user: CurrentUser,
    opportunity_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Activity).where(Activity.owner_id == current_user.id)
    if opportunity_id:
        q = q.where(Activity.opportunity_id == opportunity_id)
    result = await db.execute(q.order_by(Activity.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
async def create_activity(
    body: ActivityCreate,
    _: Annotated[None, RequireAE],
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    activity = Activity(**body.model_dump(), owner_id=current_user.id)
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity


@router.get("/{activity_id}", response_model=ActivityOut)
async def get_activity(
    activity_id: uuid.UUID,
    _: Annotated[None, RequireAE],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


@router.patch("/{activity_id}", response_model=ActivityOut)
async def update_activity(
    activity_id: uuid.UUID,
    body: ActivityUpdate,
    _: Annotated[None, RequireAE],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(activity, k, v)
    await db.commit()
    await db.refresh(activity)
    return activity


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity(
    activity_id: uuid.UUID,
    _: Annotated[None, RequireAE],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    await db.delete(activity)
    await db.commit()
