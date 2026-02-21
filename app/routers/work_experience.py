from fastapi import APIRouter, Request
from pathlib import Path
from starlette.templating import Jinja2Templates

from app.database import get_db
from app.services.candidate_loader import get_profile

router = APIRouter(tags=["work_experience"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")

MONTH_NAMES = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _format_date(d) -> str:
    if getattr(d, "present", False):
        return "Present"
    year = getattr(d, "year", None)
    month = getattr(d, "month", None)
    if year and month:
        return f"{MONTH_NAMES[month]} {year}"
    if year:
        return str(year)
    return ""


@router.get("/work-experience")
async def work_experience_page(request: Request, candidate_id: str | None = None):
    db = await get_db()
    candidates = await db.execute_fetchall("SELECT id, display_name FROM candidates ORDER BY display_name")
    candidates = [dict(c) for c in candidates]

    if not candidate_id and candidates:
        candidate_id = candidates[0]["id"]

    profile = get_profile(candidate_id) if candidate_id else None
    work_entries = []
    display_name = ""

    education_entries = []
    publication_entries = []

    if profile:
        display_name = next((c["display_name"] for c in candidates if c["id"] == candidate_id), "")
        for entry in profile.work:
            roles = []
            for role in entry.roles:
                items = [{"title": it.title, "description": it.description, "contribution": it.contribution} for it in role.items]
                roles.append({
                    "title": role.title,
                    "employment_type": role.employment_type,
                    "start": _format_date(role.start),
                    "end": _format_date(role.end),
                    "work_items": items,
                })
            work_entries.append({
                "employer": {
                    "name": entry.employer.name,
                    "description": entry.employer.description,
                    "link": entry.employer.link,
                    "sector": entry.employer.sector,
                    "location": entry.employer.location,
                },
                "start": _format_date(entry.start),
                "end": _format_date(entry.end),
                "roles": roles,
            })

        for edu in profile.education:
            dissertation = None
            if edu.dissertation:
                dissertation = {
                    "title": edu.dissertation.title,
                    "description": edu.dissertation.description,
                    "advisors": edu.dissertation.advisors,
                    "primary_research": edu.dissertation.primary_research,
                }
            education_entries.append({
                "degree": edu.degree,
                "institution": edu.institution,
                "subjects": edu.subjects,
                "gpa": edu.GPA,
                "notes": edu.notes,
                "completed": edu.completed,
                "start": _format_date(edu.start),
                "end": _format_date(edu.end),
                "dissertation": dissertation,
            })

        for pub in profile.publications:
            date_str = ""
            if pub.date:
                yr = pub.date.get("year")
                mo = pub.date.get("month")
                if yr and mo:
                    date_str = f"{MONTH_NAMES[mo]} {yr}"
                elif yr:
                    date_str = str(yr)
            publication_entries.append({
                "title": pub.title,
                "abstract": pub.abstract,
                "authors": [f"{a.first_name} {a.last_name}" for a in pub.authors],
                "date": date_str,
                "publication": pub.publication or pub.journal,
                "volume": pub.volume,
                "issue": pub.issue,
                "pages_start": pub.pages.start if pub.pages else None,
                "pages_end": pub.pages.end if pub.pages else None,
                "publisher": pub.publisher,
                "editor": pub.editor,
                "doi": pub.doi,
                "links": pub.links,
            })

    return templates.TemplateResponse("work_experience.html", {
        "request": request,
        "candidates": candidates,
        "candidate_id": candidate_id,
        "display_name": display_name,
        "work_entries": work_entries,
        "education_entries": education_entries,
        "publication_entries": publication_entries,
    })
