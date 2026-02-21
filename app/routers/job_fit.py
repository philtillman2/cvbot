import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.templating import Jinja2Templates
from pathlib import Path

from app.database import get_db
from app.services.llm import stream_chat
from app.services.candidate_loader import get_profile_json
from app.services.cost_tracker import log_request
from app.models import JobFitRequest
from app.config import settings

router = APIRouter(tags=["job_fit"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def _build_job_fit_prompt(candidate_id: str, display_name: str, job_description: str) -> list[dict]:
    profile_json = get_profile_json(candidate_id)
    system = (
        f"You are an expert hiring consultant evaluating whether {display_name} "
        "is a good fit for a specific job. Analyze the candidate's profile against the "
        "job description and provide a structured assessment.\n\n"
        "Your response MUST include these sections with markdown headers:\n"
        "## Overall Assessment\nA brief summary of fit (1-2 sentences).\n\n"
        "## Strengths & Pros\nBullet points of why this candidate is a good fit, "
        "mapping their experience/skills to job requirements.\n\n"
        "## Weaknesses & Cons\nBullet points of gaps or areas where the candidate "
        "may not meet the requirements.\n\n"
        "## Verdict\nA final recommendation (Strong Fit / Good Fit / Partial Fit / Poor Fit) "
        "with a brief justification.\n\n"
        "Base your analysis ONLY on the candidate data provided. Be honest and balanced.\n\n"
        f"=== CANDIDATE DATA ===\n{profile_json}"
    )
    user = f"Please evaluate this candidate for the following job:\n\n{job_description}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


@router.get("/job-fit")
async def job_fit_page(request: Request):
    db = await get_db()
    candidates = await db.execute_fetchall("SELECT * FROM candidates ORDER BY display_name")
    return templates.TemplateResponse("job_fit.html", {
        "request": request,
        "candidates": candidates,
        "daily_limit_usd": settings.max_daily_cost_usd,
    })


@router.post("/api/job-fit")
async def job_fit_stream(body: JobFitRequest):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, display_name FROM candidates WHERE id = ?", (body.candidate_id,)
    )
    if not rows:
        return {"error": "Candidate not found"}

    candidate = rows[0]
    messages = _build_job_fit_prompt(
        body.candidate_id, candidate["display_name"], body.job_description
    )

    async def event_generator():
        async for chunk in stream_chat(messages, model=body.model):
            if chunk["type"] == "token":
                yield f"data: {json.dumps(chunk)}\n\n"
            elif chunk["type"] == "usage":
                cost_info = await log_request(
                    conversation_id=None,
                    model_id=body.model,
                    input_tokens=chunk["input_tokens"],
                    output_tokens=chunk["output_tokens"],
                )
                chunk.update(cost_info)
                yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
