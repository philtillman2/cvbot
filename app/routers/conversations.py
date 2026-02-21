from fastapi import APIRouter
from app.database import get_db
from app.models import ConversationCreate, ConversationOut

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("")
async def create_conversation(body: ConversationCreate):
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO conversations (candidate_id, title) VALUES (?, ?)",
        (body.candidate_id, "New Chat"),
    )
    await db.commit()
    conv_id = cursor.lastrowid
    row = await db.execute_fetchall(
        "SELECT * FROM conversations WHERE id = ?", (conv_id,)
    )
    return dict(row[0])


@router.get("")
async def list_conversations():
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT c.*, ca.display_name as candidate_name FROM conversations c "
        "JOIN candidates ca ON c.candidate_id = ca.id ORDER BY c.updated_at DESC"
    )
    return [dict(r) for r in rows]


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int):
    db = await get_db()
    await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    await db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    await db.commit()
    return {"ok": True}
