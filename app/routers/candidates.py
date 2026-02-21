from fastapi import APIRouter
from app.database import get_db

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.get("")
async def list_candidates():
    db = await get_db()
    rows = await db.execute_fetchall("SELECT id, display_name FROM candidates ORDER BY display_name")
    return [dict(r) for r in rows]
