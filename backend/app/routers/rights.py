from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Drama, RightsHolder
from ..schemas import RightsHolderCreate, RightsHolderRead

router = APIRouter(prefix="/rights", tags=["rights"])


@router.post(
    "/holders", response_model=RightsHolderRead, status_code=status.HTTP_201_CREATED
)
async def create_rights_holder(
    payload: RightsHolderCreate,
    db: AsyncSession = Depends(get_db),
) -> RightsHolder:
    if await db.get(Drama, payload.drama_id) is None:
        raise HTTPException(404, "Drama not found")
    holder = RightsHolder(**payload.model_dump())
    db.add(holder)
    await db.commit()
    await db.refresh(holder)
    return holder


@router.get("/holders", response_model=list[RightsHolderRead])
async def list_rights_holders(
    drama_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[RightsHolder]:
    query = select(RightsHolder).order_by(RightsHolder.id.desc())
    if drama_id is not None:
        query = query.where(RightsHolder.drama_id == drama_id)
    return list((await db.scalars(query)).all())


@router.delete("/holders/{holder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rights_holder(
    holder_id: int, db: AsyncSession = Depends(get_db)
) -> None:
    holder = await db.get(RightsHolder, holder_id)
    if holder is None:
        raise HTTPException(404, "Rights holder not found")
    await db.delete(holder)
    await db.commit()
