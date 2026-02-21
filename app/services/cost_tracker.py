from app.database import get_db
from app.services.llm import get_model_pricing


async def log_request(
    conversation_id: int | None,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
):
    """Log an LLM request and compute cost."""
    pricing = get_model_pricing(model_id)
    cost_usd = None
    if pricing:
        cost_usd = (
            input_tokens * pricing["input"] + output_tokens * pricing["output"]
        )

    db = await get_db()
    await db.execute(
        "INSERT INTO llm_requests (conversation_id, model_id, input_tokens, output_tokens, cost_usd) "
        "VALUES (?, ?, ?, ?, ?)",
        (conversation_id, model_id, input_tokens, output_tokens, cost_usd),
    )
    await db.commit()


async def get_daily_costs() -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        """
        SELECT DATE(created_at) as day, SUM(cost_usd) as total
        FROM llm_requests
        WHERE cost_usd IS NOT NULL
        GROUP BY DATE(created_at)
        ORDER BY day
        """
    )
    cumulative = 0.0
    result = []
    for row in rows:
        cumulative += row["total"]
        result.append({"date": row["day"], "cumulative": round(cumulative, 6)})
    return result


async def get_monthly_costs() -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        """
        SELECT strftime('%Y-%m', created_at) as month, SUM(cost_usd) as total
        FROM llm_requests
        WHERE cost_usd IS NOT NULL
        GROUP BY strftime('%Y-%m', created_at)
        ORDER BY month
        """
    )
    return [{"month": row["month"], "total": round(row["total"], 6)} for row in rows]
