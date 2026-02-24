from pathlib import Path

from fastapi import APIRouter, Form, Request
from starlette.templating import Jinja2Templates

from app.services.contact_email import send_contact_email

router = APIRouter(tags=["contact"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/contact")
async def contact_page(request: Request):
    return templates.TemplateResponse("contact.html.j2", {"request": request, "success": False, "error": None})


@router.post("/contact")
async def contact_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
):
    form_data = {
        "name": name.strip(),
        "email": email.strip(),
        "subject": subject.strip(),
        "message": message.strip(),
    }
    if not form_data["name"] or not form_data["subject"] or not form_data["message"] or "@" not in form_data["email"]:
        return templates.TemplateResponse(
            "contact.html.j2",
            {"request": request, "success": False, "error": "Please fill in all fields with a valid email.", "form": form_data},
            status_code=400,
        )

    try:
        send_contact_email(**form_data)
    except Exception as exc:
        return templates.TemplateResponse(
            "contact.html.j2",
            {"request": request, "success": False, "error": f"Failed to send message: {exc}", "form": form_data},
            status_code=500,
        )

    return templates.TemplateResponse("contact.html.j2", {"request": request, "success": True, "error": None, "form": {}})
