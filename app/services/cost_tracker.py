from app.database import get_db
from app.services.llm import fetch_models, get_model_pricing
from app.config import settings


async def log_request(
    conversation_id: int | None,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
) -> dict[str, float | int]:
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
    daily_totals_row = await db.execute_fetchall(
        """
        SELECT
            COALESCE(SUM(cost_usd), 0) AS total,
            COALESCE(SUM(input_tokens), 0) AS input_tokens,
            COALESCE(SUM(output_tokens), 0) AS output_tokens
        FROM llm_requests
        WHERE DATE(created_at) = DATE('now')
        """
    )
    return {
        "request_cost_usd": float(cost_usd or 0.0),
        "daily_total_usd": float(daily_totals_row[0]["total"]),
        "daily_input_tokens": int(daily_totals_row[0]["input_tokens"]),
        "daily_output_tokens": int(daily_totals_row[0]["output_tokens"]),
        "daily_limit_usd": float(settings.max_daily_cost_usd),
    }


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
        SELECT
            DATE(created_at) as day,
            model_id,
            SUM(cost_usd) as total,
            COUNT(*) as calls,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens
        FROM llm_requests
        WHERE cost_usd IS NOT NULL
        GROUP BY DATE(created_at), model_id
        ORDER BY day, model_id
        """
    )
    model_ids = {row["model_id"] for row in rows}
    if any(get_model_pricing(model_id) is None for model_id in model_ids):
        await fetch_models()
    return [
        {
            "date": row["day"],
            "model": row["model_id"],
            "total": round(row["total"], 6),
            "calls": int(row["calls"]),
            "input_tokens": int(row["input_tokens"]),
            "output_tokens": int(row["output_tokens"]),
            "total_tokens": int(row["input_tokens"]) + int(row["output_tokens"]),
            "input_cost_per_1m": round((pricing["input"] * 1_000_000), 6)
            if (pricing := get_model_pricing(row["model_id"]))
            else None,
            "output_cost_per_1m": round((pricing["output"] * 1_000_000), 6)
            if pricing
            else None,
        }
        for row in rows
    ]


async def get_monthly_costs() -> list[dict]:
    await _backfill_missing_costs()
    db = await get_db()
    rows = await db.execute_fetchall(
        """
        SELECT
            strftime('%Y-%m', created_at) as month,
            model_id,
            SUM(cost_usd) as total,
            COUNT(*) as calls,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens
        FROM llm_requests
        WHERE cost_usd IS NOT NULL
        GROUP BY strftime('%Y-%m', created_at), model_id
        ORDER BY month, model_id
        """
    )
    model_ids = {row["model_id"] for row in rows}
    if any(get_model_pricing(model_id) is None for model_id in model_ids):
        await fetch_models()
    return [
        {
            "month": row["month"],
            "model": row["model_id"],
            "total": round(row["total"], 6),
            "calls": int(row["calls"]),
            "input_tokens": int(row["input_tokens"]),
            "output_tokens": int(row["output_tokens"]),
            "total_tokens": int(row["input_tokens"]) + int(row["output_tokens"]),
            "input_cost_per_1m": round((pricing["input"] * 1_000_000), 6)
            if (pricing := get_model_pricing(row["model_id"]))
            else None,
            "output_cost_per_1m": round((pricing["output"] * 1_000_000), 6)
            if pricing
            else None,
        }
        for row in rows
    ]


async def get_today_cost_usage() -> dict[str, float | int]:
    await _backfill_missing_costs()
    db = await get_db()
    row = await db.execute_fetchall(
        """
        SELECT
            COALESCE(SUM(CASE WHEN DATE(created_at) = DATE('now') THEN cost_usd END), 0) AS daily_total,
            COALESCE(SUM(CASE WHEN DATE(created_at) = DATE('now') THEN input_tokens END), 0) AS daily_input_tokens,
            COALESCE(SUM(CASE WHEN DATE(created_at) = DATE('now') THEN output_tokens END), 0) AS daily_output_tokens,
            COALESCE(SUM(cost_usd), 0) AS total
        FROM llm_requests
        """
    )
    return {
        "daily_total_usd": float(row[0]["daily_total"]),
        "daily_input_tokens": int(row[0]["daily_input_tokens"]),
        "daily_output_tokens": int(row[0]["daily_output_tokens"]),
        "total_cost_usd": float(row[0]["total"]),
        "daily_limit_usd": float(settings.max_daily_cost_usd),
    }


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
