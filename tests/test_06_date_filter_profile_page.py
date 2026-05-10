"""
Tests for Step 06 — Date Filter for Profile Page
=================================================
Covers:
- Route: GET /profile with various query-string combinations
- DB helpers: get_summary_stats, get_recent_transactions, get_category_breakdown
  — all with optional from_date / to_date filtering

Seed data (demo user, id=1):
  2026-05-01  Food          42.50  Groceries
  2026-05-02  Transport     15.00  Bus pass top-up
  2026-05-03  Bills        120.00  Electricity bill
  2026-05-05  Health        35.00  Pharmacy
  2026-05-08  Entertainment 25.00  Movie tickets
  2026-05-10  Shopping      89.99  Clothes
  2026-05-12  Other         10.00  Miscellaneous
  2026-05-15  Food          18.75  Restaurant lunch
  Total: 356.24  /  8 rows  / top category = Bills

Today (from env): 2026-05-10  → current calendar month = May 2026
"""

import pytest
from database.db import create_user, get_db
from database.queries import (
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

# ------------------------------------------------------------------ #
# Unique-email helper for isolated test users                        #
# ------------------------------------------------------------------ #

_counter = {"n": 0}


def _make_user(tag: str) -> int:
    """Create a fresh user with no expenses and return their user_id."""
    _counter["n"] += 1
    return create_user(
        f"Filter Test {tag}",
        f"filter_{tag}_{_counter['n']}@test.example",
        "pw",
    )


def _insert_expenses(user_id: int, rows: list[tuple]) -> None:
    """
    Insert expense rows for a user.
    Each row: (amount, category, date_iso, description)
    """
    conn = get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        [(user_id, amt, cat, dt, desc) for amt, cat, dt, desc in rows],
    )
    conn.commit()
    conn.close()


# ================================================================== #
# Section 1 — Route tests                                            #
# ================================================================== #


class TestProfileAuthGuard:
    """Unauthenticated access must redirect to /login."""

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, "Expected 302 redirect for unauthenticated user"
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_unauthenticated_with_filter_params_redirects(self, client):
        response = client.get("/profile?from=2026-05-01&to=2026-05-31")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


class TestProfileDefaultFilter:
    """No query params → default to current calendar month (May 2026)."""

    def test_no_params_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert response.status_code == 200, "Profile page must return 200 when logged in"

    def test_no_params_highlights_this_month_preset(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        # The active preset button must contain both 'filter-btn' and 'active'
        # and the text 'This Month'
        import re
        active_buttons = re.findall(r'class="filter-btn\s+active"[^>]*>(.*?)<', html)
        assert any("This Month" in btn for btn in active_buttons), (
            "Expected 'This Month' button to have active class when no query params"
        )

    def test_no_params_filter_bar_is_rendered(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert "filter-btn" in html, "Filter bar preset buttons must be in the HTML"
        assert "filter-presets" in html, "filter-presets container must be rendered"

    def test_no_params_shows_seed_expenses_in_may(self, logged_in_client):
        # Today is 2026-05-10; all seed expenses are in May 2026.
        # Expenses up to and including 2026-05-10 are within the window
        # (last day of May = 2026-05-31, so all 8 are inside the month).
        html = logged_in_client.get("/profile").data.decode()
        # At minimum the expenses before today should appear
        assert "Groceries" in html, "May expense 'Groceries' should appear in this-month filter"
        assert "Electricity bill" in html

    def test_no_params_stat_card_has_transaction_count(self, logged_in_client):
        # All 8 seed expenses fall in May 2026
        html = logged_in_client.get("/profile").data.decode()
        assert "8" in html, "Transaction count stat should be 8 for the full May dataset"

    def test_no_params_from_input_is_first_of_month(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        # The from date input should be pre-populated with 2026-05-01
        assert 'value="2026-05-01"' in html, (
            "From-date input must be pre-populated with first day of current month"
        )

    def test_no_params_to_input_is_last_of_month(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert 'value="2026-05-31"' in html, (
            "To-date input must be pre-populated with last day of current month"
        )


class TestProfileAllTimeFilter:
    """`?from=&to=` → All Time mode."""

    def test_all_time_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=&to=")
        assert response.status_code == 200

    def test_all_time_highlights_all_time_preset(self, logged_in_client):
        import re
        html = logged_in_client.get("/profile?from=&to=").data.decode()
        active_buttons = re.findall(r'class="filter-btn\s+active"[^>]*>(.*?)<', html)
        assert any("All Time" in btn for btn in active_buttons), (
            "Expected 'All Time' button to have active class when ?from=&to="
        )

    def test_all_time_this_month_button_is_not_active(self, logged_in_client):
        import re
        html = logged_in_client.get("/profile?from=&to=").data.decode()
        active_buttons = re.findall(r'class="filter-btn\s+active"[^>]*>(.*?)<', html)
        assert not any("This Month" in btn for btn in active_buttons), (
            "'This Month' button must NOT be active in All Time mode"
        )

    def test_all_time_shows_all_seed_transactions(self, logged_in_client):
        html = logged_in_client.get("/profile?from=&to=").data.decode()
        for description in (
            "Groceries",
            "Bus pass top-up",
            "Electricity bill",
            "Pharmacy",
            "Movie tickets",
            "Clothes",
            "Miscellaneous",
            "Restaurant lunch",
        ):
            assert description in html, f"All-Time mode must show '{description}'"

    def test_all_time_total_matches_seed_sum(self, logged_in_client):
        html = logged_in_client.get("/profile?from=&to=").data.decode()
        # 42.50+15.00+120.00+35.00+25.00+89.99+10.00+18.75 = 356.24
        assert "356.24" in html, "All-Time total spent must be 356.24"

    def test_all_time_from_input_is_empty(self, logged_in_client):
        html = logged_in_client.get("/profile?from=&to=").data.decode()
        # When all-time, from_date and to_date are None → template renders empty string
        assert 'value=""' in html, (
            "Date inputs must have empty value attributes in All Time mode"
        )


class TestProfileCustomDateFilter:
    """Custom ?from=YYYY-MM-DD&to=YYYY-MM-DD filtering."""

    def test_custom_range_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=2026-05-01&to=2026-05-05")
        assert response.status_code == 200

    def test_custom_range_shows_only_matching_expenses(self, logged_in_client):
        # 2026-05-01 to 2026-05-05 covers: Groceries, Bus pass, Electricity bill, Pharmacy
        html = logged_in_client.get("/profile?from=2026-05-01&to=2026-05-05").data.decode()
        assert "Groceries" in html
        assert "Bus pass top-up" in html
        assert "Electricity bill" in html
        assert "Pharmacy" in html

    def test_custom_range_excludes_out_of_range_expenses(self, logged_in_client):
        # Expenses after 2026-05-05 must not appear
        html = logged_in_client.get("/profile?from=2026-05-01&to=2026-05-05").data.decode()
        assert "Movie tickets" not in html, "Expense from 2026-05-08 must be excluded"
        assert "Clothes" not in html, "Expense from 2026-05-10 must be excluded"
        assert "Restaurant lunch" not in html, "Expense from 2026-05-15 must be excluded"

    def test_custom_range_shows_correct_transaction_count(self, logged_in_client):
        # 4 expenses from 2026-05-01 to 2026-05-05
        html = logged_in_client.get("/profile?from=2026-05-01&to=2026-05-05").data.decode()
        assert ">4<" in html or "4 transaction" in html.lower() or \
               '<span class="stat-value">4</span>' in html, (
            "Transaction count must be 4 for 2026-05-01 to 2026-05-05"
        )

    def test_custom_range_total_spent_correct(self, logged_in_client):
        # 42.50 + 15.00 + 120.00 + 35.00 = 212.50
        html = logged_in_client.get("/profile?from=2026-05-01&to=2026-05-05").data.decode()
        assert "212.50" in html, "Total spent for 2026-05-01 to 2026-05-05 must be 212.50"

    def test_custom_range_highlights_custom_preset(self, logged_in_client):
        import re
        # A range that doesn't match any preset → active_preset == 'custom'
        html = logged_in_client.get("/profile?from=2026-05-01&to=2026-05-05").data.decode()
        active_buttons = re.findall(r'class="filter-btn\s+active"[^>]*>(.*?)<', html)
        # No preset button should have the active class for a custom range
        assert not any(
            btn.strip() in ("This Month", "Last Month", "Last 3 Months", "All Time")
            for btn in active_buttons
        ), "No standard preset button should be active for a custom date range"

    def test_custom_range_inputs_are_prepopulated(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-05-02&to=2026-05-10").data.decode()
        assert 'value="2026-05-02"' in html, "From-date input must be pre-populated"
        assert 'value="2026-05-10"' in html, "To-date input must be pre-populated"

    def test_single_day_range_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=2026-05-08&to=2026-05-08")
        assert response.status_code == 200

    def test_single_day_range_shows_only_that_day(self, logged_in_client):
        # Only 2026-05-08 = Movie tickets
        html = logged_in_client.get("/profile?from=2026-05-08&to=2026-05-08").data.decode()
        assert "Movie tickets" in html
        assert "Groceries" not in html


class TestProfileEmptyDateRange:
    """Date range with no matching expenses must not crash and show zero values."""

    def test_no_match_returns_200(self, logged_in_client):
        # January 2026 has no seed data
        response = logged_in_client.get("/profile?from=2026-01-01&to=2026-01-31")
        assert response.status_code == 200, "Empty result range must not crash the page"

    def test_no_match_shows_zero_total(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-01-01&to=2026-01-31").data.decode()
        assert "0.00" in html, "Empty range must show ₹0.00 total spent"

    def test_no_match_shows_zero_transaction_count(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-01-01&to=2026-01-31").data.decode()
        assert "<span" in html  # page rendered; stat value for 0 count is present
        # The stat card for transactions should contain 0
        assert ">0<" in html or ">0 <" in html or "stat-value\">0" in html, (
            "Transaction count must display 0 for an empty range"
        )

    def test_no_match_shows_em_dash_top_category(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-01-01&to=2026-01-31").data.decode()
        assert "—" in html, "Top category must display em-dash when no expenses exist"

    def test_no_match_has_empty_category_breakdown(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-01-01&to=2026-01-31").data.decode()
        # No category bar elements should be rendered
        assert "cat-bar-" not in html, (
            "Category breakdown bars must be absent when no expenses match the range"
        )

    def test_future_range_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=2099-01-01&to=2099-12-31")
        assert response.status_code == 200


class TestProfileInvalidDates:
    """Invalid / unparseable date strings must not crash the app."""

    def test_both_invalid_dates_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=notadate&to=bad")
        assert response.status_code == 200, "Invalid dates must not cause a 500 error"

    def test_both_invalid_falls_back_to_this_month(self, logged_in_client):
        import re
        html = logged_in_client.get("/profile?from=notadate&to=bad").data.decode()
        active_buttons = re.findall(r'class="filter-btn\s+active"[^>]*>(.*?)<', html)
        assert any("This Month" in btn for btn in active_buttons), (
            "Invalid dates must fall back to 'This Month' preset"
        )

    def test_invalid_from_only_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=notadate&to=2026-05-31")
        assert response.status_code == 200

    def test_invalid_to_only_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=2026-05-01&to=INVALID")
        assert response.status_code == 200

    def test_invalid_dates_show_page_content(self, logged_in_client):
        html = logged_in_client.get("/profile?from=99-99-99&to=abc").data.decode()
        assert "Total Spent" in html, "Page must still render stats section after invalid dates"

    def test_wrong_format_date_returns_200(self, logged_in_client):
        # Wrong format: DD/MM/YYYY instead of YYYY-MM-DD
        response = logged_in_client.get("/profile?from=01/05/2026&to=31/05/2026")
        assert response.status_code == 200

    def test_empty_from_only_returns_200(self, logged_in_client):
        # Only from is absent but to is provided — partial params
        response = logged_in_client.get("/profile?to=2026-05-31")
        assert response.status_code == 200


class TestProfileFilterBarHTML:
    """HTML structure of the filter bar."""

    def test_filter_form_uses_get_method(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert 'method="get"' in html.lower() or "method=get" in html.lower(), (
            "Custom date form must use GET method"
        )

    def test_filter_form_action_is_profile(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert 'action="/profile"' in html, (
            "Custom date form must submit to /profile"
        )

    def test_filter_bar_has_from_input(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert 'name="from"' in html, "Filter form must have an input named 'from'"

    def test_filter_bar_has_to_input(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert 'name="to"' in html, "Filter form must have an input named 'to'"

    def test_filter_bar_has_apply_button(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert "Apply" in html, "Filter bar must have an Apply button"

    def test_filter_bar_has_all_four_presets(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert "This Month" in html
        assert "Last Month" in html
        assert "All Time" in html

    def test_filter_bar_preset_links_are_anchors(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert '<a href=' in html and "filter-btn" in html, (
            "Preset buttons must be anchor tags with class 'filter-btn'"
        )

    def test_only_one_active_class_on_presets(self, logged_in_client):
        import re
        html = logged_in_client.get("/profile").data.decode()
        active_buttons = re.findall(r'class="filter-btn\s+active"', html)
        assert len(active_buttons) == 1, (
            f"Exactly one preset button should be active at a time, found {len(active_buttons)}"
        )


# ================================================================== #
# Section 2 — DB helper unit tests                                   #
# ================================================================== #


class TestGetSummaryStatsWithDateFilter:
    """Unit tests for get_summary_stats(user_id, from_date, to_date)."""

    def test_date_filter_returns_only_matching_total(self):
        # 2026-05-01 to 2026-05-05: 42.50 + 15.00 + 120.00 + 35.00 = 212.50
        stats = get_summary_stats(1, from_date="2026-05-01", to_date="2026-05-05")
        assert abs(stats["total_spent"] - 212.50) < 0.01, (
            f"Expected 212.50, got {stats['total_spent']}"
        )

    def test_date_filter_returns_correct_transaction_count(self):
        stats = get_summary_stats(1, from_date="2026-05-01", to_date="2026-05-05")
        assert stats["transaction_count"] == 4, (
            f"Expected 4 transactions, got {stats['transaction_count']}"
        )

    def test_date_filter_returns_correct_top_category(self):
        # In 2026-05-01 to 2026-05-05, Bills (120.00) is the top category
        stats = get_summary_stats(1, from_date="2026-05-01", to_date="2026-05-05")
        assert stats["top_category"] == "Bills", (
            f"Expected 'Bills' as top category, got '{stats['top_category']}'"
        )

    def test_no_matching_dates_returns_zero_total(self):
        stats = get_summary_stats(1, from_date="2020-01-01", to_date="2020-01-31")
        assert stats["total_spent"] == 0, "Total spent must be 0 when no expenses match"

    def test_no_matching_dates_returns_zero_count(self):
        stats = get_summary_stats(1, from_date="2020-01-01", to_date="2020-01-31")
        assert stats["transaction_count"] == 0

    def test_no_matching_dates_returns_em_dash_top_category(self):
        stats = get_summary_stats(1, from_date="2020-01-01", to_date="2020-01-31")
        assert stats["top_category"] == "—", (
            f"Expected em-dash for empty result, got '{stats['top_category']}'"
        )

    def test_no_date_filter_returns_all_time_totals(self):
        # Passing no filter params returns lifetime totals
        stats = get_summary_stats(1)
        assert abs(stats["total_spent"] - 356.24) < 0.01
        assert stats["transaction_count"] == 8
        assert stats["top_category"] == "Bills"

    def test_single_day_filter(self):
        stats = get_summary_stats(1, from_date="2026-05-08", to_date="2026-05-08")
        assert stats["transaction_count"] == 1
        assert abs(stats["total_spent"] - 25.00) < 0.01
        assert stats["top_category"] == "Entertainment"

    def test_isolated_user_no_expenses_with_date_filter(self):
        uid = _make_user("stats_iso")
        stats = get_summary_stats(uid, from_date="2026-05-01", to_date="2026-05-31")
        assert stats["total_spent"] == 0
        assert stats["transaction_count"] == 0
        assert stats["top_category"] == "—"

    def test_date_filter_with_expenses_in_and_out_of_range(self):
        uid = _make_user("stats_range")
        _insert_expenses(uid, [
            (50.00, "Food",  "2026-03-15", "In range"),
            (30.00, "Bills", "2026-04-20", "Out of range"),
        ])
        stats = get_summary_stats(uid, from_date="2026-03-01", to_date="2026-03-31")
        assert stats["transaction_count"] == 1
        assert abs(stats["total_spent"] - 50.00) < 0.01

    @pytest.mark.parametrize("from_dt,to_dt,expected_count,expected_total", [
        ("2026-05-01", "2026-05-01", 1, 42.50),    # only first expense
        ("2026-05-15", "2026-05-15", 1, 18.75),    # only last expense
        ("2026-05-06", "2026-05-09", 1, 25.00),    # only Entertainment
        ("2026-05-01", "2026-05-15", 8, 356.24),   # full seed range
        ("2026-04-01", "2026-04-30", 0, 0.00),     # no data in April
    ])
    def test_parametrized_date_ranges(self, from_dt, to_dt, expected_count, expected_total):
        stats = get_summary_stats(1, from_date=from_dt, to_date=to_dt)
        assert stats["transaction_count"] == expected_count, (
            f"Range {from_dt} to {to_dt}: expected {expected_count} transactions, "
            f"got {stats['transaction_count']}"
        )
        assert abs(stats["total_spent"] - expected_total) < 0.01, (
            f"Range {from_dt} to {to_dt}: expected {expected_total}, "
            f"got {stats['total_spent']}"
        )


class TestGetRecentTransactionsWithDateFilter:
    """Unit tests for get_recent_transactions(user_id, from_date, to_date)."""

    def test_date_filter_returns_only_matching_rows(self):
        txns = get_recent_transactions(1, from_date="2026-05-08", to_date="2026-05-12")
        dates = [t["date"] for t in txns]
        for d in dates:
            assert "2026-05-08" <= d <= "2026-05-12", (
                f"Transaction date {d} is outside the requested range"
            )

    def test_date_filter_count_is_correct(self):
        # 2026-05-08 to 2026-05-12 covers: Movie tickets, Clothes, Miscellaneous = 3
        txns = get_recent_transactions(1, from_date="2026-05-08", to_date="2026-05-12")
        assert len(txns) == 3, f"Expected 3 transactions, got {len(txns)}"

    def test_date_filter_ordered_newest_first(self):
        txns = get_recent_transactions(1, from_date="2026-05-01", to_date="2026-05-15")
        dates = [t["date"] for t in txns]
        assert dates == sorted(dates, reverse=True), "Transactions must be ordered newest-first"

    def test_date_filter_excludes_earlier_expenses(self):
        txns = get_recent_transactions(1, from_date="2026-05-10", to_date="2026-05-15")
        descriptions = [t["description"] for t in txns]
        assert "Groceries" not in descriptions, "Groceries (2026-05-01) must be excluded"
        assert "Electricity bill" not in descriptions

    def test_date_filter_excludes_later_expenses(self):
        txns = get_recent_transactions(1, from_date="2026-05-01", to_date="2026-05-03")
        descriptions = [t["description"] for t in txns]
        assert "Movie tickets" not in descriptions
        assert "Restaurant lunch" not in descriptions

    def test_no_matching_range_returns_empty_list(self):
        txns = get_recent_transactions(1, from_date="2020-01-01", to_date="2020-12-31")
        assert txns == [], f"Expected empty list, got {txns}"

    def test_no_date_filter_returns_all_rows(self):
        txns = get_recent_transactions(1)
        assert len(txns) == 8

    def test_date_filter_row_keys_present(self):
        txns = get_recent_transactions(1, from_date="2026-05-01", to_date="2026-05-15")
        for txn in txns:
            assert "date" in txn
            assert "description" in txn
            assert "category" in txn
            assert "amount" in txn

    def test_date_filter_isolated_user_no_data(self):
        uid = _make_user("txns_iso")
        txns = get_recent_transactions(uid, from_date="2026-05-01", to_date="2026-05-31")
        assert txns == []

    def test_date_filter_boundary_dates_inclusive(self):
        # from_date itself must be included (boundary is inclusive)
        txns = get_recent_transactions(1, from_date="2026-05-15", to_date="2026-05-15")
        assert len(txns) == 1
        assert txns[0]["description"] == "Restaurant lunch"

    def test_date_filter_with_limit_respected(self):
        # Range has 8 rows but limit=3 should still apply
        txns = get_recent_transactions(1, limit=3, from_date="2026-05-01", to_date="2026-05-15")
        assert len(txns) == 3

    @pytest.mark.parametrize("from_dt,to_dt,expected_count", [
        ("2026-05-01", "2026-05-02", 2),
        ("2026-05-03", "2026-05-05", 2),
        ("2026-05-10", "2026-05-15", 3),
        ("2026-05-13", "2026-05-14", 0),
    ])
    def test_parametrized_transaction_counts(self, from_dt, to_dt, expected_count):
        txns = get_recent_transactions(1, from_date=from_dt, to_date=to_dt)
        assert len(txns) == expected_count, (
            f"Range {from_dt} to {to_dt}: expected {expected_count}, got {len(txns)}"
        )


class TestGetCategoryBreakdownWithDateFilter:
    """Unit tests for get_category_breakdown(user_id, from_date, to_date)."""

    def test_date_filter_returns_only_matching_categories(self):
        # 2026-05-01 to 2026-05-05: Food, Transport, Bills, Health only
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-05")
        names = {c["name"] for c in cats}
        assert names == {"Food", "Transport", "Bills", "Health"}, (
            f"Expected only categories in range, got {names}"
        )

    def test_date_filter_excludes_out_of_range_categories(self):
        # Entertainment (2026-05-08), Shopping (2026-05-10), Other (2026-05-12),
        # and second Food (2026-05-15) are outside 2026-05-01 to 2026-05-05
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-05")
        names = {c["name"] for c in cats}
        assert "Entertainment" not in names, "Entertainment must be excluded from this range"
        assert "Shopping" not in names, "Shopping must be excluded from this range"
        assert "Other" not in names, "Other must be excluded from this range"

    def test_date_filter_percents_sum_to_100(self):
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-15")
        total = sum(c["percent"] for c in cats)
        assert total == 100, f"Category percents must sum to 100, got {total}"

    def test_date_filter_single_category_is_100_percent(self):
        # Only Entertainment on 2026-05-08
        cats = get_category_breakdown(1, from_date="2026-05-08", to_date="2026-05-08")
        assert len(cats) == 1
        assert cats[0]["percent"] == 100

    def test_no_matching_range_returns_empty_list(self):
        cats = get_category_breakdown(1, from_date="2019-01-01", to_date="2019-12-31")
        assert cats == [], f"Expected empty list, got {cats}"

    def test_no_date_filter_returns_all_categories(self):
        cats = get_category_breakdown(1)
        assert len(cats) == 7

    def test_date_filter_sorted_by_amount_desc(self):
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-15")
        amounts = [c["amount"] for c in cats]
        assert amounts == sorted(amounts, reverse=True), (
            "Categories must be sorted by amount descending"
        )

    def test_date_filter_row_keys_present(self):
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-15")
        for cat in cats:
            assert "name" in cat
            assert "amount" in cat
            assert "percent" in cat

    def test_date_filter_isolated_user_no_data(self):
        uid = _make_user("cats_iso")
        cats = get_category_breakdown(uid, from_date="2026-05-01", to_date="2026-05-31")
        assert cats == []

    def test_date_filter_amounts_are_floats(self):
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-15")
        for cat in cats:
            assert isinstance(cat["amount"], float), (
                f"Amount for {cat['name']} must be a float"
            )

    def test_date_filter_top_category_is_correct(self):
        # In 2026-05-01 to 2026-05-05 the highest is Bills (120.00)
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-05")
        assert cats[0]["name"] == "Bills"

    def test_date_filter_partial_range_for_multi_entry_category(self):
        # Food appears on 2026-05-01 (42.50) and 2026-05-15 (18.75).
        # Filter to 2026-05-01 only → Food amount must be 42.50, not 61.25
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-01")
        food = next((c for c in cats if c["name"] == "Food"), None)
        assert food is not None
        assert abs(food["amount"] - 42.50) < 0.01, (
            f"Food amount with single-day filter must be 42.50, got {food['amount']}"
        )

    def test_date_filter_isolated_user_with_own_expenses(self):
        uid = _make_user("cats_own")
        _insert_expenses(uid, [
            (100.00, "Food",      "2026-06-10", "Groceries"),
            (200.00, "Transport", "2026-06-15", "Flight"),
            (50.00,  "Food",      "2026-07-01", "Lunch"),   # outside range
        ])
        cats = get_category_breakdown(uid, from_date="2026-06-01", to_date="2026-06-30")
        names = {c["name"] for c in cats}
        assert names == {"Food", "Transport"}, f"Expected only June categories, got {names}"
        total_pct = sum(c["percent"] for c in cats)
        assert total_pct == 100
