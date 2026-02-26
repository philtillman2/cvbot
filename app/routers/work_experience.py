import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pathlib import Path
from starlette.templating import Jinja2Templates

from app.database import get_db
from app.models import WorkExperience
from app.services.candidate_loader import get_profile, save_profile

router = APIRouter(tags=["work_experience"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/work-experience")
async def work_experience_page(request: Request, candidate_id: str | None = None):
    db = await get_db()
    candidates = await db.execute_fetchall(
        "SELECT id, TRIM(first_name || ' ' || COALESCE(middle_name || ' ', '') || last_name) "
        "AS display_name FROM candidates ORDER BY display_name"
    )
    candidates = [dict(c) for c in candidates]

    if not candidate_id and candidates:
        candidate_id = candidates[0]["id"]

    profile = get_profile(candidate_id) if candidate_id else None
    profile_json = json.dumps(profile.model_dump(), default=str) if profile else "null"
    display_name = ""
    if profile:
        display_name = next((c["display_name"] for c in candidates if c["id"] == candidate_id), "")

    return templates.TemplateResponse("work_experience.html", {
        "request": request,
        "candidates": candidates,
        "candidate_id": candidate_id,
        "display_name": display_name,
        "profile_json": profile_json,
    })


@router.put("/api/candidates/{candidate_id}/work-experience")
async def update_work_experience(candidate_id: str, body: WorkExperience):
    existing = get_profile(candidate_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    await save_profile(candidate_id, body)
    return JSONResponse({"ok": True})
