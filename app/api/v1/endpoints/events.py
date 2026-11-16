from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.tables import Evento

router = APIRouter()


@router.get("/")
async def list_events(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Evento).order_by(Evento.created_at.desc()).limit(limit)
    )
    return result.scalars().all()
