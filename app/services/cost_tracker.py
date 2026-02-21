from app.database import get_db
from app.services.llm import fetch_models, get_model_pricing
from app.config import settings


async def log_request(
    conversation_id: int | None,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
):
    """Log an LLM request and compute cost."""
    pricing = get_model_pricing(model_id)
    if pricing is None:
        await fetch_models()
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


async def _backfill_missing_costs():
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, model_id, input_tokens, output_tokens FROM llm_requests WHERE cost_usd IS NULL"
    )
    if not rows:
        return

    if any(get_model_pricing(row["model_id"]) is None for row in rows):
        await fetch_models()

    updated = False
    for row in rows:
        pricing = get_model_pricing(row["model_id"])
        if not pricing:
            continue
        cost_usd = (
            row["input_tokens"] * pricing["input"]
            + row["output_tokens"] * pricing["output"]
        )
        await db.execute(
            "UPDATE llm_requests SET cost_usd = ? WHERE id = ?",
            (cost_usd, row["id"]),
        )
        updated = True

    if updated:
        await db.commit()


async def get_daily_costs() -> list[dict]:
    await _backfill_missing_costs()
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
    await _backfill_missing_costs()
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


async def is_daily_cost_limit_reached() -> bool:
    await _backfill_missing_costs()
    db = await get_db()
    row = await db.execute_fetchall(
        """
        SELECT COALESCE(SUM(cost_usd), 0) AS total
        FROM llm_requests
        WHERE cost_usd IS NOT NULL AND DATE(created_at) = DATE('now')
        """
    )
    return float(row[0]["total"]) >= settings.max_daily_cost_usd
