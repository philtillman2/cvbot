from pathlib import Path
import time

import httpx
from fastapi import APIRouter, Form, Request
from starlette.templating import Jinja2Templates

from app.config import settings
from app.services.contact_email import send_contact_email

router = APIRouter(tags=["contact"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def _contact_context(
    request: Request,
    success: bool,
    error: str | None,
    form: dict | None = None,
    form_started_at: str | int | None = None,
):
    return {
        "request": request,
        "success": success,
        "error": error,
        "form": form or {},
        "form_started_at": form_started_at if form_started_at is not None else int(time.time()),
        "contact_turnstile_enabled": settings.contact_turnstile_enabled,
        "contact_turnstile_site_key": settings.contact_turnstile_site_key,
    }


async def _verify_turnstile_token(token: str, remote_ip: str | None) -> bool:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            settings.turnstile_challenge_url,
            data={
                "secret": settings.contact_turnstile_secret_key,
                "response": token,
                "remoteip": remote_ip or "",
            },
        )
    response.raise_for_status()
    verification = response.json()
    return bool(verification.get("success"))


@router.get("/contact")
async def contact_page(request: Request):
    return templates.TemplateResponse("contact.html.j2", _contact_context(request, success=False, error=None))


@router.post("/contact")
async def contact_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    website: str = Form(""),
    form_started_at: str = Form("0"),
    turnstile_response: str = Form("", alias="cf-turnstile-response"),
):
    now = int(time.time())
    form_data = {
        "name": name.strip(),
        "email": email.strip(),
        "subject": subject.strip(),
        "message": message.strip(),
        "form_started_at": form_started_at,
    }
    if website.strip():
        return templates.TemplateResponse(
            "contact.html.j2",
            _contact_context(
                request,
                success=False,
                error="Unable to send message. Please try again.",
                form=form_data,
                form_started_at=form_started_at,
            ),
            status_code=400,
        )
    started_at = int(form_started_at) if form_started_at.isdigit() else 0
    if settings.contact_min_submit_time_enabled and (now - started_at) < settings.contact_min_submit_time_seconds:
        return templates.TemplateResponse(
            "contact.html.j2",
            _contact_context(
                request,
                success=False,
                error="Please wait a moment before sending.",
                form=form_data,
                form_started_at=form_started_at,
            ),
            status_code=400,
        )
    if settings.contact_turnstile_enabled:
        if not turnstile_response:
            return templates.TemplateResponse(
                "contact.html.j2",
                _contact_context(
                    request,
                    success=False,
                    error="Please complete the verification challenge.",
                    form=form_data,
                    form_started_at=form_started_at,
                ),
                status_code=400,
            )
        remote_ip = request.client.host if request.client else None
        try:
            challenge_valid = await _verify_turnstile_token(turnstile_response, remote_ip)
        except (httpx.HTTPError, ValueError) as exc:
            return templates.TemplateResponse(
                "contact.html.j2",
                _contact_context(
                    request,
                    success=False,
                    error=f"Failed to verify challenge: {exc}",
                    form=form_data,
                    form_started_at=form_started_at,
                ),
                status_code=502,
            )
        if not challenge_valid:
            return templates.TemplateResponse(
                "contact.html.j2",
                _contact_context(
                    request,
                    success=False,
                    error="Verification challenge failed. Please try again.",
                    form=form_data,
                    form_started_at=form_started_at,
                ),
                status_code=400,
            )
    if not form_data["name"] or not form_data["subject"] or not form_data["message"] or "@" not in form_data["email"]:
        return templates.TemplateResponse(
            "contact.html.j2",
            _contact_context(
                request,
                success=False,
                error="Please fill in all fields with a valid email.",
                form=form_data,
                form_started_at=form_started_at,
            ),
            status_code=400,
        )

    try:
        send_contact_email(
            name=form_data["name"],
            email=form_data["email"],
            subject=form_data["subject"],
            message=form_data["message"],
        )
    except Exception as exc:
        return templates.TemplateResponse(
            "contact.html.j2",
            _contact_context(
                request,
                success=False,
                error=f"Failed to send message: {exc}",
                form=form_data,
                form_started_at=form_started_at,
            ),
            status_code=500,
        )

    return templates.TemplateResponse("contact.html.j2", _contact_context(request, success=True, error=None, form={}))
