import json

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pathlib import Path
from pydantic import ValidationError
from starlette.templating import Jinja2Templates
import tiktoken

from app.database import get_db
from app.models import Candidate, WorkExperience
from app.services.candidate_loader import get_candidate, load_candidates, save_candidate, save_profile

router = APIRouter(tags=["work_experience"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


async def _get_candidate_with_reload(candidate_id: str):
    candidate = get_candidate(candidate_id)
    if candidate is None:
        await load_candidates()
        candidate = get_candidate(candidate_id)
    return candidate


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

    candidate = await _get_candidate_with_reload(candidate_id) if candidate_id else None
    profile = candidate.work_experience if candidate else None
    profile_json = json.dumps(profile.model_dump(), default=str) if profile else "null"
    display_name = ""
    page_title = "Work Experience"
    page_subtitle = ""
    if candidate:
        display_name = next((c["display_name"] for c in candidates if c["id"] == candidate_id), "")
        first = (candidate.first_name or "").strip()
        middle = (candidate.middle_name or "").strip()
        last = (candidate.last_name or "").strip()
        if first or middle or last:
            middle_initial = f"{middle[0]}." if middle else ""
            profile_name = " ".join(part for part in (first, middle_initial, last) if part)
            page_title = profile_name or display_name or page_title
            if candidate.location:
                city = (candidate.location.city or "").strip()
                country = (candidate.location.country or "").strip()
                page_subtitle = ", ".join(part for part in (city, country) if part)
        else:
            page_title = display_name or page_title

    return templates.TemplateResponse("work_experience.html.j2", {
        "request": request,
        "candidates": candidates,
        "candidate_id": candidate_id,
        "display_name": display_name,
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "profile_json": profile_json,
    })


@router.put("/api/candidates/{candidate_id}/work-experience")
async def update_work_experience(candidate_id: str, body: WorkExperience):
    candidate = await _get_candidate_with_reload(candidate_id)
    existing = candidate.work_experience if candidate else None
    if existing is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    await save_profile(candidate_id, body)
    return JSONResponse({"ok": True})


@router.get("/api/candidates/{candidate_id}/work-experience/download")
async def download_work_experience(candidate_id: str):
    candidate = await _get_candidate_with_reload(candidate_id)
    profile = candidate.work_experience if candidate else None
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
    candidate = await _get_candidate_with_reload(candidate_id)
    existing = candidate.work_experience if candidate else None
    if existing is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    raw = await file.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Uploaded file must be UTF-8 JSON")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    required_keys = {"first_name", "middle_name", "last_name", "location", "work_experience"}
    if not isinstance(payload, dict) or not required_keys.issubset(payload.keys()):
        raise HTTPException(status_code=422, detail="Uploaded JSON must match Candidate schema")
    try:
        uploaded_candidate = Candidate.model_validate(payload)
    except ValidationError:
        raise HTTPException(status_code=422, detail="Uploaded JSON must match Candidate schema")
    await save_candidate(candidate_id, uploaded_candidate)
    return JSONResponse({"ok": True, "profile": uploaded_candidate.work_experience.model_dump()})

def _nr_tokens_from_string(string: str, encoding_name: str) -> int:
    encoding = tiktoken.get_encoding(encoding_name)
    nr_tokens = len(encoding.encode(string))
    return nr_tokens

@router.get("/api/candidates/{candidate_id}/work-experience/token-count")
async def get_nr_tokens(candidate_id: str):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT c.work_experience " \
        "FROM candidates c "
        "WHERE c.id = ?",
        (candidate_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Candidate not found")
    work_experience = rows[0]["work_experience"] or ""
    nr_tokens = _nr_tokens_from_string(work_experience, "cl100k_base")
    return JSONResponse({"nr_tokens": nr_tokens})
