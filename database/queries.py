from datetime import datetime
from database.db import get_db


def _date_filter(from_date, to_date):
    if from_date and to_date:
        return " AND date BETWEEN ? AND ?", [from_date, to_date]
    return "", []


def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    member_since = datetime.strptime(row["created_at"][:10], "%Y-%m-%d").strftime("%B %Y")
    return {"name": row["name"], "email": row["email"], "member_since": member_since}


def get_summary_stats(user_id, from_date=None, to_date=None):
    date_clause, date_params = _date_filter(from_date, to_date)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total_spent, COUNT(*) AS transaction_count"
            " FROM expenses WHERE user_id = ?" + date_clause,
            [user_id] + date_params,
        ).fetchone()
        total_spent = float(row["total_spent"])
        transaction_count = int(row["transaction_count"])

        if transaction_count == 0:
            top_category = "—"
        else:
            top_row = conn.execute(
                "SELECT category FROM expenses WHERE user_id = ?"
                + date_clause + " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
                [user_id] + date_params,
            ).fetchone()
            top_category = top_row["category"]
    finally:
        conn.close()
    return {
        "total_spent": total_spent,
        "transaction_count": transaction_count,
        "top_category": top_category,
    }


def get_recent_transactions(user_id, limit=10, from_date=None, to_date=None):
    date_clause, date_params = _date_filter(from_date, to_date)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount"
            " FROM expenses WHERE user_id = ?" + date_clause + " ORDER BY date DESC LIMIT ?",
            [user_id] + date_params + [limit],
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_category_breakdown(user_id, from_date=None, to_date=None):
    date_clause, date_params = _date_filter(from_date, to_date)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category AS name, SUM(amount) AS amount"
            " FROM expenses WHERE user_id = ?" + date_clause + " GROUP BY category ORDER BY amount DESC",
            [user_id] + date_params,
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return []

    cats = [{"name": r["name"], "amount": float(r["amount"])} for r in rows]
    grand_total = sum(c["amount"] for c in cats)
    for cat in cats:
        cat["percent"] = round(100.0 * cat["amount"] / grand_total)

    remainder = 100 - sum(c["percent"] for c in cats)
    cats[0]["percent"] += remainder

    return cats
