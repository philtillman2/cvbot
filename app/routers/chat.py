import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from starlette.templating import Jinja2Templates
from pathlib import Path

from app.database import get_db
from app.services.llm import stream_chat
from app.services.candidate_loader import get_profile_json
from app.services.cost_tracker import is_daily_cost_limit_reached, log_request
from app.config import settings
from app.models import ChatRequest

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/")
async def index():
    return RedirectResponse(url="/chat")


@router.get("/chat")
async def chat_page(request: Request):
    db = await get_db()
    conversations = await db.execute_fetchall(
        "SELECT c.*, ca.display_name as candidate_name FROM conversations c "
        "JOIN candidates ca ON c.candidate_id = ca.id ORDER BY c.updated_at DESC"
    )
    candidates = await db.execute_fetchall("SELECT * FROM candidates ORDER BY display_name")
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "conversations": conversations,
        "candidates": candidates,
        "active_conversation": None,
        "messages": [],
    })


@router.get("/chat/{conversation_id}")
async def chat_page_with_conversation(request: Request, conversation_id: int):
    db = await get_db()
    conversations = await db.execute_fetchall(
        "SELECT c.*, ca.display_name as candidate_name FROM conversations c "
        "JOIN candidates ca ON c.candidate_id = ca.id ORDER BY c.updated_at DESC"
    )
    candidates = await db.execute_fetchall("SELECT * FROM candidates ORDER BY display_name")
    active = await db.execute_fetchall(
        "SELECT c.*, ca.display_name as candidate_name FROM conversations c "
        "JOIN candidates ca ON c.candidate_id = ca.id WHERE c.id = ?",
        (conversation_id,),
    )
    active_conversation = active[0] if active else None
    messages = await db.execute_fetchall(
        "SELECT * FROM messages WHERE conversation_id = ? AND role != 'system' ORDER BY id",
        (conversation_id,),
    )
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "conversations": conversations,
        "candidates": candidates,
        "active_conversation": active_conversation,
        "messages": messages,
    })


def _build_system_prompt(candidate_id: str, display_name: str) -> str:
    profile_json = get_profile_json(candidate_id)
    return (
        f"You are an AI assistant representing the professional experience of {display_name}. "
        "Answer questions about their work experience, skills, education, and publications "
        "based ONLY on the following data. If information is not in the data, say so.\n\n"
        f"=== CANDIDATE DATA ===\n{profile_json}"
    )


async def _build_llm_messages(db, conversation_id: int, candidate_id: str, candidate_name: str):
    system_prompt = _build_system_prompt(candidate_id, candidate_name)
    history = await db.execute_fetchall(
        "SELECT role, content FROM messages WHERE conversation_id = ? AND role != 'system' ORDER BY id",
        (conversation_id,),
    )
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": row["role"], "content": row["content"]} for row in history)
    return messages


def _build_streaming_response(db, conversation_id: int, model: str, messages, user_message_id: int):
    async def event_generator():
        full_response = ""
        usage_info = None
        yield f"data: {json.dumps({'type': 'user_message', 'message_id': user_message_id})}\n\n"

        async for chunk in stream_chat(messages, model=model):
            if chunk["type"] == "token":
                full_response += chunk["content"]
                yield f"data: {json.dumps(chunk)}\n\n"
            elif chunk["type"] == "usage":
                usage_info = chunk

        # Save assistant message
        await db.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'assistant', ?)",
            (conversation_id, full_response),
        )
        await db.commit()

        # Log cost
        if usage_info:
            await log_request(
                conversation_id=conversation_id,
                model_id=model,
                input_tokens=usage_info["input_tokens"],
                output_tokens=usage_info["output_tokens"],
            )
            yield f"data: {json.dumps(usage_info)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/api/chat/{conversation_id}")
async def chat_stream(conversation_id: int, body: ChatRequest):
    db = await get_db()
    if await is_daily_cost_limit_reached():
        return JSONResponse(
            status_code=429,
            content={
                "error": (
                    f"Daily chat limit reached (${settings.max_daily_cost_usd:.2f}). "
                    "Please try again tomorrow."
                )
            },
        )

    # Get conversation and candidate info
    rows = await db.execute_fetchall(
        "SELECT c.*, ca.display_name as candidate_name FROM conversations c "
        "JOIN candidates ca ON c.candidate_id = ca.id WHERE c.id = ?",
        (conversation_id,),
    )
    if not rows:
        return {"error": "Conversation not found"}

    conv = rows[0]

    # Save user message
    cursor = await db.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
        (conversation_id, body.message),
    )
    user_message_id = cursor.lastrowid
    await db.execute(
        "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conversation_id,),
    )
    await db.commit()

    messages = await _build_llm_messages(
        db,
        conversation_id=conversation_id,
        candidate_id=conv["candidate_id"],
        candidate_name=conv["candidate_name"],
    )
    return _build_streaming_response(
        db,
        conversation_id=conversation_id,
        model=body.model,
        messages=messages,
        user_message_id=user_message_id,
    )


@router.post("/api/chat/{conversation_id}/edit/{message_id}")
async def edit_chat_stream(conversation_id: int, message_id: int, body: ChatRequest):
    db = await get_db()
    if await is_daily_cost_limit_reached():
        return JSONResponse(
            status_code=429,
            content={
                "error": (
                    f"Daily chat limit reached (${settings.max_daily_cost_usd:.2f}). "
                    "Please try again tomorrow."
                )
            },
        )

    rows = await db.execute_fetchall(
        "SELECT c.*, ca.display_name as candidate_name FROM conversations c "
        "JOIN candidates ca ON c.candidate_id = ca.id WHERE c.id = ?",
        (conversation_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_rows = await db.execute_fetchall(
        "SELECT id FROM messages WHERE id = ? AND conversation_id = ? AND role = 'user'",
        (message_id, conversation_id),
    )
    if not user_rows:
        raise HTTPException(status_code=404, detail="User message not found")

    await db.execute(
        "UPDATE messages SET content = ? WHERE id = ?",
        (body.message, message_id),
    )
    await db.execute(
        "DELETE FROM messages WHERE conversation_id = ? AND id > ?",
        (conversation_id, message_id),
    )
    await db.execute(
        "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conversation_id,),
    )
    await db.commit()

    conv = rows[0]
    messages = await _build_llm_messages(
        db,
        conversation_id=conversation_id,
        candidate_id=conv["candidate_id"],
        candidate_name=conv["candidate_name"],
    )
    return _build_streaming_response(
        db,
        conversation_id=conversation_id,
        model=body.model,
        messages=messages,
        user_message_id=message_id,
    )
