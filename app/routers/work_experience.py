import json

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pathlib import Path
from pydantic import ValidationError
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

    return templates.TemplateResponse("work_experience.html.j2", {
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


@router.get("/api/candidates/{candidate_id}/work-experience/download")
async def download_work_experience(candidate_id: str):
    profile = get_profile(candidate_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return Response(
        content=profile.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{candidate_id}_work_experience.json"'
        },
    )


@router.post("/api/candidates/{candidate_id}/work-experience/upload")
async def upload_work_experience(candidate_id: str, file: UploadFile = File(...)):
    existing = get_profile(candidate_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    raw = await file.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Uploaded file must be UTF-8 JSON")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    try:
        profile = WorkExperience.model_validate(payload)
    except ValidationError:
        raise HTTPException(status_code=422, detail="Uploaded JSON does not match WorkExperience schema")
    await save_profile(candidate_id, profile)
    return JSONResponse({"ok": True, "profile": profile.model_dump()})
