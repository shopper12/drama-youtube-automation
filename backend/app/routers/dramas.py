from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal, get_db
from ..models import Drama
from ..schemas import DramaCreate, DramaRead, DramaUpdate

router = APIRouter(prefix="/dramas", tags=["dramas"])


async def start_drama_workflow(drama_id: int) -> None:
    from ..services.email_service import register_and_send_license_request
    from ..services.script_generator_service import enqueue_script_generation

    async with AsyncSessionLocal() as db:
        await register_and_send_license_request(drama_id, db)
        await enqueue_script_generation(drama_id, db)
        await db.commit()


@router.post("", response_model=DramaRead, status_code=status.HTTP_201_CREATED)
async def create_drama(
    payload: DramaCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Drama:
    drama = Drama(**payload.model_dump())
    db.add(drama)
    await db.commit()
    await db.refresh(drama)
    background_tasks.add_task(start_drama_workflow, drama.id)
    return drama


@router.get("", response_model=list[DramaRead])
async def list_dramas(db: AsyncSession = Depends(get_db)) -> list[Drama]:
    return list((await db.scalars(select(Drama).order_by(Drama.id.desc()))).all())


@router.get("/{drama_id}", response_model=DramaRead)
async def get_drama(drama_id: int, db: AsyncSession = Depends(get_db)) -> Drama:
    drama = await db.get(Drama, drama_id)
    if drama is None:
        raise HTTPException(404, "Drama not found")
    return drama


@router.patch("/{drama_id}", response_model=DramaRead)
async def update_drama(
    drama_id: int,
    payload: DramaUpdate,
    db: AsyncSession = Depends(get_db),
) -> Drama:
    drama = await db.get(Drama, drama_id)
    if drama is None:
        raise HTTPException(404, "Drama not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(drama, key, value)
    await db.commit()
    await db.refresh(drama)
    return drama


@router.delete("/{drama_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_drama(drama_id: int, db: AsyncSession = Depends(get_db)) -> None:
    drama = await db.get(Drama, drama_id)
    if drama is None:
        raise HTTPException(404, "Drama not found")
    await db.delete(drama)
    await db.commit()
