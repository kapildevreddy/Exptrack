import re
import pytest
from database.db import create_user
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _new_user_id(suffix=""):
    """Insert a user with no expenses and return their id."""
    return create_user(
        f"Test User{suffix}",
        f"testuser{suffix}@example.com",
        "password123",
    )


# ------------------------------------------------------------------ #
# Unit tests — get_user_by_id                                        #
# ------------------------------------------------------------------ #

def test_get_user_by_id_returns_correct_fields():
    result = get_user_by_id(1)
    assert result is not None
    assert result["name"]  == "Demo User"
    assert result["email"] == "demo@spendly.com"
    assert re.match(r"[A-Za-z]+ \d{4}", result["member_since"]), (
        f"member_since not formatted as 'Month YYYY': {result['member_since']}"
    )


def test_get_user_by_id_missing_returns_none():
    assert get_user_by_id(999999) is None


# ------------------------------------------------------------------ #
# Unit tests — get_summary_stats                                     #
# ------------------------------------------------------------------ #

def test_get_summary_stats_seed_user():
    stats = get_summary_stats(1)
    assert abs(stats["total_spent"] - 356.24) < 0.01
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_no_expenses():
    uid   = _new_user_id("_stats")
    stats = get_summary_stats(uid)
    assert stats["total_spent"]       == 0
    assert stats["transaction_count"] == 0
    assert stats["top_category"]      == "—"


# ------------------------------------------------------------------ #
# Unit tests — get_recent_transactions                               #
# ------------------------------------------------------------------ #

def test_get_recent_transactions_returns_eight_rows():
    txns = get_recent_transactions(1)
    assert len(txns) == 8


def test_get_recent_transactions_ordered_newest_first():
    txns = get_recent_transactions(1)
    dates = [t["date"] for t in txns]
    assert dates == sorted(dates, reverse=True)


def test_get_recent_transactions_row_keys():
    txns = get_recent_transactions(1)
    for txn in txns:
        assert "date"        in txn
        assert "description" in txn
        assert "category"    in txn
        assert "amount"      in txn


def test_get_recent_transactions_no_expenses():
    uid = _new_user_id("_txns")
    assert get_recent_transactions(uid) == []


def test_get_recent_transactions_limit():
    txns = get_recent_transactions(1, limit=3)
    assert len(txns) == 3


# ------------------------------------------------------------------ #
# Unit tests — get_category_breakdown                                #
# ------------------------------------------------------------------ #

def test_get_category_breakdown_seven_categories():
    cats = get_category_breakdown(1)
    assert len(cats) == 7


def test_get_category_breakdown_sorted_by_amount_desc():
    cats = get_category_breakdown(1)
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)


def test_get_category_breakdown_percents_sum_to_100():
    cats = get_category_breakdown(1)
    assert sum(c["percent"] for c in cats) == 100


def test_get_category_breakdown_top_category_is_bills():
    cats = get_category_breakdown(1)
    assert cats[0]["name"] == "Bills"


def test_get_category_breakdown_row_keys():
    cats = get_category_breakdown(1)
    for cat in cats:
        assert "name"    in cat
        assert "amount"  in cat
        assert "percent" in cat


def test_get_category_breakdown_no_expenses():
    uid = _new_user_id("_cats")
    assert get_category_breakdown(uid) == []


# ------------------------------------------------------------------ #
# Route tests                                                         #
# ------------------------------------------------------------------ #

def test_profile_redirects_when_unauthenticated(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_returns_200_when_authenticated(logged_in_client):
    response = logged_in_client.get("/profile")
    assert response.status_code == 200


def test_profile_shows_real_name_and_email(logged_in_client):
    response = logged_in_client.get("/profile")
    assert b"Demo User"        in response.data
    assert b"demo@spendly.com" in response.data


def test_profile_shows_rupee_symbol(logged_in_client):
    html = logged_in_client.get("/profile").data.decode()
    assert "&#8377;" in html or "₹" in html


def test_profile_shows_total_spent(logged_in_client):
    assert b"356" in logged_in_client.get("/profile").data


def test_profile_shows_transaction_count(logged_in_client):
    assert b"8" in logged_in_client.get("/profile").data


def test_profile_shows_top_category(logged_in_client):
    assert b"Bills" in logged_in_client.get("/profile").data


def test_profile_transactions_newest_first(logged_in_client):
    html = logged_in_client.get("/profile").data.decode()
    assert html.index("Restaurant lunch") < html.index("Groceries")


def test_profile_shows_all_seven_categories(logged_in_client):
    html = logged_in_client.get("/profile").data.decode()
    for name in ("Bills", "Shopping", "Food", "Health", "Entertainment", "Transport", "Other"):
        assert name in html, f"Category '{name}' missing from profile page"
