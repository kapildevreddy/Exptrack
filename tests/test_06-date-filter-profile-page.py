"""
Tests for Step 06 — Date Filter for Profile Page
=================================================

Spec: .claude/specs/06-date-filter-profile-page.md

Covers:
- Route GET /profile: auth guard, default filter, all-time, custom range,
  empty range, invalid dates, last-3-months preset, filter bar HTML
- DB helpers in database/queries.py: get_summary_stats, get_recent_transactions,
  get_category_breakdown — all with optional from_date / to_date filtering

Seed data (demo user, id=1, seeded by seed_db()):
  2026-05-01  Food          42.50   Groceries
  2026-05-02  Transport     15.00   Bus pass top-up
  2026-05-03  Bills        120.00   Electricity bill
  2026-05-05  Health        35.00   Pharmacy
  2026-05-08  Entertainment 25.00   Movie tickets
  2026-05-10  Shopping      89.99   Clothes
  2026-05-12  Other         10.00   Miscellaneous
  2026-05-15  Food          18.75   Restaurant lunch
  Total: 356.24  /  8 rows  /  top category = Bills (120.00)

Today (project date): 2026-05-10 → current calendar month = May 2026
  first day of month : 2026-05-01
  last day of month  : 2026-05-31
  All 8 seed expenses fall within May 2026.
"""

import re
import pytest
from database.db import create_user, get_db
from database.queries import (
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #
# conftest.py provides: app, client, logged_in_client
# logged_in_client sets session user_id=1 (demo user) directly.


# ------------------------------------------------------------------ #
# Helper — isolated test users with custom expenses                  #
# ------------------------------------------------------------------ #

_uid_counter = {"n": 0}


def _make_user(tag: str) -> int:
    """Create a fresh user with no expenses and return their user_id."""
    _uid_counter["n"] += 1
    return create_user(
        f"Filter Test {tag}",
        f"filter_{tag}_{_uid_counter['n']}@test.example",
        "pw123",
    )


def _insert_expenses(user_id: int, rows: list) -> None:
    """
    Insert expense rows for a given user.
    Each element of rows must be a tuple: (amount, category, date_iso, description)
    Uses parameterized SQL; never formats values into the query string.
    """
    conn = get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        [(user_id, amt, cat, dt, desc) for amt, cat, dt, desc in rows],
    )
    conn.commit()
    conn.close()


# ==================================================================== #
# Section 1 — Route tests: GET /profile                                #
# ==================================================================== #


class TestAuthGuard:
    """Unauthenticated access must redirect to /login regardless of params."""

    def test_no_params_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, (
            "Unauthenticated GET /profile must return 302"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect location must point to /login"
        )

    def test_with_date_params_redirects_to_login(self, client):
        response = client.get("/profile?from=2026-05-01&to=2026-05-31")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"], (
            "Unauthenticated request with filter params must still redirect to /login"
        )

    def test_all_time_params_redirects_to_login(self, client):
        response = client.get("/profile?from=&to=")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_invalid_date_params_redirects_to_login(self, client):
        response = client.get("/profile?from=notadate&to=bad")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


class TestDefaultFilter:
    """
    No query params → defaults to current calendar month (May 2026).
    'This Month' preset must be highlighted; date inputs pre-populated.
    """

    def test_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert response.status_code == 200, (
            "GET /profile with no params must return 200 for an authenticated user"
        )

    def test_this_month_preset_is_active(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        # Template emits: class="filter-btn active">This Month</a>
        active_anchors = re.findall(
            r'class="filter-btn active"[^>]*>(.*?)<', html
        )
        assert any("This Month" in a for a in active_anchors), (
            "The 'This Month' anchor must carry the 'active' class when no params are given"
        )

    def test_from_input_prepopulated_with_first_of_month(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert 'value="2026-05-01"' in html, (
            "The from-date input must be pre-populated with 2026-05-01 (first of May 2026)"
        )

    def test_to_input_prepopulated_with_last_of_month(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert 'value="2026-05-31"' in html, (
            "The to-date input must be pre-populated with 2026-05-31 (last of May 2026)"
        )

    def test_shows_may_expenses(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        # All 8 seed expenses are in May 2026, so all should appear
        assert "Groceries" in html, "Groceries (2026-05-01) must appear in May default view"
        assert "Electricity bill" in html
        assert "Restaurant lunch" in html

    def test_transaction_count_stat_is_eight(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        # stat-value span holds the count
        assert '<span class="stat-value">8</span>' in html, (
            "Transaction count stat-value must be 8 for all May 2026 seed expenses"
        )

    def test_total_spent_stat_shows_seed_total(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        # All 8 seed expenses: 42.50+15.00+120.00+35.00+25.00+89.99+10.00+18.75 = 356.24
        assert "356.24" in html, (
            "Total spent must be 356.24 when no date params filter a month containing all seeds"
        )

    def test_top_category_is_bills(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert "Bills" in html, "Top category must be 'Bills' (120.00) for the full May dataset"

    def test_filter_presets_container_is_rendered(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert "filter-presets" in html, (
            "'filter-presets' container must be present in the rendered HTML"
        )


class TestAllTimeFilter:
    """
    ?from=&to= → All Time mode: no date restriction, all seed expenses shown.
    'All Time' preset must be highlighted.
    """

    def test_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=&to=")
        assert response.status_code == 200, (
            "GET /profile?from=&to= must return 200"
        )

    def test_all_time_preset_is_active(self, logged_in_client):
        html = logged_in_client.get("/profile?from=&to=").data.decode()
        active_anchors = re.findall(
            r'class="filter-btn active"[^>]*>(.*?)<', html
        )
        assert any("All Time" in a for a in active_anchors), (
            "The 'All Time' anchor must carry the 'active' class when ?from=&to="
        )

    def test_this_month_preset_is_not_active(self, logged_in_client):
        html = logged_in_client.get("/profile?from=&to=").data.decode()
        active_anchors = re.findall(
            r'class="filter-btn active"[^>]*>(.*?)<', html
        )
        assert not any("This Month" in a for a in active_anchors), (
            "'This Month' must NOT be active in All Time mode"
        )

    def test_all_seed_descriptions_present(self, logged_in_client):
        html = logged_in_client.get("/profile?from=&to=").data.decode()
        expected = [
            "Groceries",
            "Bus pass top-up",
            "Electricity bill",
            "Pharmacy",
            "Movie tickets",
            "Clothes",
            "Miscellaneous",
            "Restaurant lunch",
        ]
        for desc in expected:
            assert desc in html, (
                f"All Time mode must show all seed expenses; '{desc}' is missing"
            )

    def test_total_spent_is_full_seed_sum(self, logged_in_client):
        html = logged_in_client.get("/profile?from=&to=").data.decode()
        assert "356.24" in html, (
            "All Time total must equal the full seed sum of 356.24"
        )

    def test_transaction_count_is_eight(self, logged_in_client):
        html = logged_in_client.get("/profile?from=&to=").data.decode()
        assert '<span class="stat-value">8</span>' in html, (
            "All Time transaction count must be 8"
        )

    def test_date_inputs_have_empty_values(self, logged_in_client):
        html = logged_in_client.get("/profile?from=&to=").data.decode()
        # Both inputs must carry empty value attributes when in all-time mode
        from_empty = re.search(r'<input[^>]+name="from"[^>]+value=""', html)
        to_empty = re.search(r'<input[^>]+name="to"[^>]+value=""', html)
        assert from_empty is not None, (
            "From-date input must have value=\"\" in All Time mode"
        )
        assert to_empty is not None, (
            "To-date input must have value=\"\" in All Time mode"
        )


class TestCustomDateRangeFilter:
    """Custom ?from=YYYY-MM-DD&to=YYYY-MM-DD filtering."""

    def test_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=2026-05-01&to=2026-05-05")
        assert response.status_code == 200

    def test_shows_only_in_range_expenses(self, logged_in_client):
        # 2026-05-01 to 2026-05-05: Groceries, Bus pass top-up, Electricity bill, Pharmacy
        html = logged_in_client.get("/profile?from=2026-05-01&to=2026-05-05").data.decode()
        for desc in ("Groceries", "Bus pass top-up", "Electricity bill", "Pharmacy"):
            assert desc in html, f"'{desc}' must appear in 2026-05-01 to 2026-05-05 range"

    def test_excludes_out_of_range_expenses(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-05-01&to=2026-05-05").data.decode()
        for desc in ("Movie tickets", "Clothes", "Miscellaneous", "Restaurant lunch"):
            assert desc not in html, (
                f"'{desc}' must NOT appear when filtered to 2026-05-01 – 2026-05-05"
            )

    def test_correct_total_for_range(self, logged_in_client):
        # 42.50 + 15.00 + 120.00 + 35.00 = 212.50
        html = logged_in_client.get("/profile?from=2026-05-01&to=2026-05-05").data.decode()
        assert "212.50" in html, (
            "Total spent for 2026-05-01 to 2026-05-05 must be 212.50"
        )

    def test_correct_transaction_count_for_range(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-05-01&to=2026-05-05").data.decode()
        assert '<span class="stat-value">4</span>' in html, (
            "Transaction count must be 4 for the 2026-05-01 to 2026-05-05 range"
        )

    def test_no_preset_is_active_for_custom_range(self, logged_in_client):
        # 2026-05-01 to 2026-05-05 matches no preset
        html = logged_in_client.get("/profile?from=2026-05-01&to=2026-05-05").data.decode()
        active_anchors = re.findall(
            r'class="filter-btn active"[^>]*>(.*?)<', html
        )
        preset_labels = {"This Month", "Last Month", "Last 3 Months", "All Time"}
        active_labels = {a.strip() for a in active_anchors}
        assert not active_labels.intersection(preset_labels), (
            "No standard preset button should be active for a custom date range; "
            f"found active: {active_labels}"
        )

    def test_inputs_prepopulated_with_query_dates(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-05-02&to=2026-05-10").data.decode()
        assert 'value="2026-05-02"' in html, (
            "From-date input must be pre-populated with the requested from date"
        )
        assert 'value="2026-05-10"' in html, (
            "To-date input must be pre-populated with the requested to date"
        )

    def test_single_day_range_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=2026-05-08&to=2026-05-08")
        assert response.status_code == 200

    def test_single_day_shows_only_that_day(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-05-08&to=2026-05-08").data.decode()
        assert "Movie tickets" in html, "Movie tickets (2026-05-08) must appear on single-day filter"
        assert "Groceries" not in html, "Groceries (2026-05-01) must not appear on 2026-05-08 filter"
        assert "Clothes" not in html, "Clothes (2026-05-10) must not appear on 2026-05-08 filter"

    def test_from_after_to_falls_back_to_this_month(self, logged_in_client):
        # from > to is invalid; the route must fall back to the current month
        response = logged_in_client.get("/profile?from=2026-05-31&to=2026-05-01")
        assert response.status_code == 200, (
            "Inverted date range must not crash the server"
        )
        html = response.data.decode()
        active_anchors = re.findall(r'class="filter-btn active"[^>]*>(.*?)<', html)
        assert any("This Month" in a for a in active_anchors), (
            "Inverted date range must fall back to 'This Month' default"
        )


class TestEmptyDateRange:
    """A date range with no matching expenses must render cleanly with zero values."""

    def test_no_match_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=2026-01-01&to=2026-01-31")
        assert response.status_code == 200, (
            "A date range with no matching expenses must still return 200"
        )

    def test_no_match_total_is_zero(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-01-01&to=2026-01-31").data.decode()
        assert "0.00" in html, "Total spent must display 0.00 when no expenses match the range"

    def test_no_match_transaction_count_is_zero(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-01-01&to=2026-01-31").data.decode()
        assert '<span class="stat-value">0</span>' in html, (
            "Transaction count stat-value must be 0 when no expenses match the range"
        )

    def test_no_match_top_category_is_em_dash(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-01-01&to=2026-01-31").data.decode()
        assert "—" in html or "—" in html, (
            "Top category must show an em-dash (—) when no expenses exist in the range"
        )

    def test_no_match_category_bars_absent(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-01-01&to=2026-01-31").data.decode()
        assert "cat-bar-" not in html, (
            "No category bar elements should be rendered when no expenses match the range"
        )

    def test_no_match_expense_descriptions_absent(self, logged_in_client):
        html = logged_in_client.get("/profile?from=2026-01-01&to=2026-01-31").data.decode()
        for desc in ("Groceries", "Electricity bill", "Movie tickets"):
            assert desc not in html, (
                f"'{desc}' must not appear when the date range contains no matching expenses"
            )

    def test_future_range_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=2099-01-01&to=2099-12-31")
        assert response.status_code == 200, (
            "A future date range with no matching expenses must return 200"
        )


class TestInvalidDateHandling:
    """Invalid / unparseable date strings must not crash the app."""

    def test_both_invalid_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=notadate&to=bad")
        assert response.status_code == 200, (
            "?from=notadate&to=bad must not raise a 500 error"
        )

    def test_both_invalid_falls_back_to_this_month(self, logged_in_client):
        html = logged_in_client.get("/profile?from=notadate&to=bad").data.decode()
        active_anchors = re.findall(r'class="filter-btn active"[^>]*>(.*?)<', html)
        assert any("This Month" in a for a in active_anchors), (
            "Invalid dates must fall back to the 'This Month' default preset"
        )

    def test_invalid_from_only_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=notadate&to=2026-05-31")
        assert response.status_code == 200

    def test_invalid_to_only_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile?from=2026-05-01&to=INVALID")
        assert response.status_code == 200

    def test_wrong_format_returns_200(self, logged_in_client):
        # DD/MM/YYYY instead of YYYY-MM-DD
        response = logged_in_client.get("/profile?from=01/05/2026&to=31/05/2026")
        assert response.status_code == 200

    def test_wrong_format_falls_back_to_this_month(self, logged_in_client):
        html = logged_in_client.get(
            "/profile?from=01/05/2026&to=31/05/2026"
        ).data.decode()
        active_anchors = re.findall(r'class="filter-btn active"[^>]*>(.*?)<', html)
        assert any("This Month" in a for a in active_anchors), (
            "Wrong date format must fall back to 'This Month' preset"
        )

    def test_partial_param_only_to_returns_200(self, logged_in_client):
        # Only 'to' is provided; 'from' is absent — not the same as from=&to=
        response = logged_in_client.get("/profile?to=2026-05-31")
        assert response.status_code == 200

    def test_invalid_dates_page_still_renders_stats_section(self, logged_in_client):
        html = logged_in_client.get("/profile?from=99-99-99&to=abc").data.decode()
        assert "Total Spent" in html, (
            "Stats section heading must still be rendered when dates are invalid"
        )

    def test_sql_injection_attempt_does_not_crash(self, logged_in_client):
        # Parameterized queries should handle this safely; the route should not crash
        response = logged_in_client.get(
            "/profile?from=2026-05-01'; DROP TABLE expenses;--&to=2026-05-31"
        )
        assert response.status_code == 200, (
            "SQL injection attempt in query string must not crash the server"
        )


class TestLastThreeMonthsPreset:
    """
    The 'Last 3 Months' preset URL must be highlighted when its exact date range
    is passed as query params.
    Today = 2026-05-10 → last 3 months = 2026-02-01 to 2026-04-30.
    """

    def test_last_3_months_preset_is_active(self, logged_in_client):
        # first_3m = 2026-02-01, last_last = 2026-04-30
        response = logged_in_client.get("/profile?from=2026-02-01&to=2026-04-30")
        assert response.status_code == 200
        html = response.data.decode()
        active_anchors = re.findall(r'class="filter-btn active"[^>]*>(.*?)<', html)
        assert any("Last 3 Months" in a for a in active_anchors), (
            "The 'Last 3 Months' anchor must be active when its exact range is requested"
        )

    def test_last_3_months_other_presets_not_active(self, logged_in_client):
        html = logged_in_client.get(
            "/profile?from=2026-02-01&to=2026-04-30"
        ).data.decode()
        active_anchors = re.findall(r'class="filter-btn active"[^>]*>(.*?)<', html)
        for label in ("This Month", "Last Month", "All Time"):
            assert not any(label in a for a in active_anchors), (
                f"'{label}' must NOT be active when 'Last 3 Months' range is selected"
            )

    def test_last_3_months_range_returns_empty_for_seed_data(self, logged_in_client):
        # No seed expenses exist before May 2026, so the breakdown must be empty
        html = logged_in_client.get(
            "/profile?from=2026-02-01&to=2026-04-30"
        ).data.decode()
        assert "cat-bar-" not in html, (
            "Category bars must be absent: no seed expenses fall in Feb–Apr 2026"
        )
        assert "0.00" in html, "Total must be 0.00 for the last-3-months range with no data"


class TestFilterBarHTML:
    """Structural correctness of the rendered filter bar."""

    def test_form_uses_get_method(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        # Template: <form class="filter-custom" method="get" action="...">
        assert 'method="get"' in html, (
            "The custom date form must use method=\"get\""
        )

    def test_form_action_is_profile_route(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert 'action="/profile"' in html, (
            "The custom date form action must be '/profile'"
        )

    def test_from_input_name_attribute(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert 'name="from"' in html, (
            "The filter form must contain an input with name=\"from\""
        )

    def test_to_input_name_attribute(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert 'name="to"' in html, (
            "The filter form must contain an input with name=\"to\""
        )

    def test_apply_button_present(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert "Apply" in html, (
            "The filter form must contain an 'Apply' submit button"
        )

    def test_this_month_preset_link_present(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert "This Month" in html, "Filter bar must render a 'This Month' preset"

    def test_last_month_preset_link_present(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert "Last Month" in html, "Filter bar must render a 'Last Month' preset"

    def test_last_3_months_preset_link_present(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert "Last 3 Months" in html, "Filter bar must render a 'Last 3 Months' preset"

    def test_all_time_preset_link_present(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        assert "All Time" in html, "Filter bar must render an 'All Time' preset"

    def test_preset_links_are_anchor_tags(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        # Verify the filter-btn class appears on <a> elements
        assert '<a href=' in html and "filter-btn" in html, (
            "Preset buttons must be <a> anchor tags carrying the 'filter-btn' class"
        )

    def test_exactly_one_active_preset_at_a_time(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        active_matches = re.findall(r'class="filter-btn active"', html)
        assert len(active_matches) == 1, (
            f"Exactly one preset button must carry the 'active' class; "
            f"found {len(active_matches)}"
        )

    def test_exactly_one_active_in_all_time_mode(self, logged_in_client):
        html = logged_in_client.get("/profile?from=&to=").data.decode()
        active_matches = re.findall(r'class="filter-btn active"', html)
        assert len(active_matches) == 1, (
            f"Exactly one 'active' class in All Time mode; found {len(active_matches)}"
        )

    def test_exactly_one_active_in_custom_range(self, logged_in_client):
        # Custom range: none of the four presets match → template should still
        # render at most one active marker (zero is acceptable; never more than one)
        html = logged_in_client.get(
            "/profile?from=2026-05-01&to=2026-05-05"
        ).data.decode()
        active_matches = re.findall(r'class="filter-btn active"', html)
        assert len(active_matches) <= 1, (
            "At most one preset may carry the 'active' class for a custom date range"
        )

    def test_filter_date_inputs_are_type_date(self, logged_in_client):
        html = logged_in_client.get("/profile").data.decode()
        # Both inputs should be type="date" as per the spec
        date_inputs = re.findall(r'<input[^>]+type="date"[^>]*/>', html)
        assert len(date_inputs) >= 2, (
            "The filter bar must include at least two type=\"date\" inputs (from and to)"
        )


# ==================================================================== #
# Section 2 — DB helper unit tests                                     #
# ==================================================================== #


class TestGetSummaryStatsDateFilter:
    """Unit tests for get_summary_stats(user_id, from_date=..., to_date=...)."""

    def test_range_total_is_correct(self):
        # 2026-05-01 to 2026-05-05: 42.50 + 15.00 + 120.00 + 35.00 = 212.50
        stats = get_summary_stats(1, from_date="2026-05-01", to_date="2026-05-05")
        assert abs(stats["total_spent"] - 212.50) < 0.01, (
            f"Expected total_spent=212.50, got {stats['total_spent']}"
        )

    def test_range_transaction_count_is_correct(self):
        stats = get_summary_stats(1, from_date="2026-05-01", to_date="2026-05-05")
        assert stats["transaction_count"] == 4, (
            f"Expected 4 transactions in range, got {stats['transaction_count']}"
        )

    def test_range_top_category_is_correct(self):
        # Bills (120.00) is the highest in 2026-05-01 to 2026-05-05
        stats = get_summary_stats(1, from_date="2026-05-01", to_date="2026-05-05")
        assert stats["top_category"] == "Bills", (
            f"Expected top_category='Bills', got '{stats['top_category']}'"
        )

    def test_empty_range_total_is_zero(self):
        stats = get_summary_stats(1, from_date="2020-01-01", to_date="2020-01-31")
        assert stats["total_spent"] == 0, (
            "total_spent must be 0 when no expenses match the date range"
        )

    def test_empty_range_count_is_zero(self):
        stats = get_summary_stats(1, from_date="2020-01-01", to_date="2020-01-31")
        assert stats["transaction_count"] == 0

    def test_empty_range_top_category_is_em_dash(self):
        stats = get_summary_stats(1, from_date="2020-01-01", to_date="2020-01-31")
        assert stats["top_category"] == "—", (
            f"top_category must be em-dash for an empty range, got '{stats['top_category']}'"
        )

    def test_no_filter_returns_all_time_totals(self):
        stats = get_summary_stats(1)
        assert abs(stats["total_spent"] - 356.24) < 0.01
        assert stats["transaction_count"] == 8
        assert stats["top_category"] == "Bills"

    def test_single_day_filter(self):
        stats = get_summary_stats(1, from_date="2026-05-08", to_date="2026-05-08")
        assert stats["transaction_count"] == 1
        assert abs(stats["total_spent"] - 25.00) < 0.01
        assert stats["top_category"] == "Entertainment"

    def test_boundary_dates_inclusive(self):
        # from_date and to_date themselves must be included (BETWEEN is inclusive)
        stats = get_summary_stats(1, from_date="2026-05-15", to_date="2026-05-15")
        assert stats["transaction_count"] == 1, (
            "Boundary date (to_date == from_date) must be included in the result"
        )
        assert abs(stats["total_spent"] - 18.75) < 0.01

    def test_full_seed_range_returns_all(self):
        stats = get_summary_stats(1, from_date="2026-05-01", to_date="2026-05-15")
        assert stats["transaction_count"] == 8
        assert abs(stats["total_spent"] - 356.24) < 0.01

    def test_result_has_required_keys(self):
        stats = get_summary_stats(1, from_date="2026-05-01", to_date="2026-05-15")
        assert "total_spent" in stats
        assert "transaction_count" in stats
        assert "top_category" in stats

    def test_total_spent_is_float(self):
        stats = get_summary_stats(1, from_date="2026-05-01", to_date="2026-05-15")
        assert isinstance(stats["total_spent"], float), (
            "total_spent must be a Python float"
        )

    def test_transaction_count_is_int(self):
        stats = get_summary_stats(1, from_date="2026-05-01", to_date="2026-05-15")
        assert isinstance(stats["transaction_count"], int)

    def test_isolated_user_no_expenses_with_date_filter(self):
        uid = _make_user("stats_iso")
        stats = get_summary_stats(uid, from_date="2026-05-01", to_date="2026-05-31")
        assert stats["total_spent"] == 0
        assert stats["transaction_count"] == 0
        assert stats["top_category"] == "—"

    def test_date_filter_respects_user_isolation(self):
        # Another user's expenses must not bleed into user_id=1's stats
        other_uid = _make_user("stats_other")
        _insert_expenses(other_uid, [
            (999.00, "Luxury", "2026-05-03", "Other user expense"),
        ])
        stats = get_summary_stats(1, from_date="2026-05-03", to_date="2026-05-03")
        # Only the seed user's Electricity bill (120.00) is on 2026-05-03
        assert abs(stats["total_spent"] - 120.00) < 0.01, (
            "Stats for user_id=1 must not include expenses belonging to another user"
        )

    def test_expenses_outside_range_not_counted(self):
        uid = _make_user("stats_range")
        _insert_expenses(uid, [
            (50.00, "Food",  "2026-03-15", "In range"),
            (30.00, "Bills", "2026-04-20", "Out of range"),
        ])
        stats = get_summary_stats(uid, from_date="2026-03-01", to_date="2026-03-31")
        assert stats["transaction_count"] == 1
        assert abs(stats["total_spent"] - 50.00) < 0.01

    @pytest.mark.parametrize("from_dt,to_dt,exp_count,exp_total", [
        ("2026-05-01", "2026-05-01", 1, 42.50),    # only Groceries
        ("2026-05-15", "2026-05-15", 1, 18.75),    # only Restaurant lunch
        ("2026-05-06", "2026-05-09", 1, 25.00),    # only Movie tickets
        ("2026-05-01", "2026-05-15", 8, 356.24),   # entire seed range
        ("2026-04-01", "2026-04-30", 0, 0.00),     # no data in April
        ("2026-05-10", "2026-05-12", 2, 99.99),    # Clothes + Miscellaneous
    ])
    def test_parametrized_ranges(self, from_dt, to_dt, exp_count, exp_total):
        stats = get_summary_stats(1, from_date=from_dt, to_date=to_dt)
        assert stats["transaction_count"] == exp_count, (
            f"{from_dt} to {to_dt}: expected {exp_count} txns, got {stats['transaction_count']}"
        )
        assert abs(stats["total_spent"] - exp_total) < 0.01, (
            f"{from_dt} to {to_dt}: expected {exp_total}, got {stats['total_spent']}"
        )


class TestGetRecentTransactionsDateFilter:
    """Unit tests for get_recent_transactions(user_id, from_date=..., to_date=...)."""

    def test_returns_only_rows_in_range(self):
        txns = get_recent_transactions(1, from_date="2026-05-08", to_date="2026-05-12")
        for t in txns:
            assert "2026-05-08" <= t["date"] <= "2026-05-12", (
                f"Transaction date {t['date']} is outside the requested range"
            )

    def test_count_is_correct_for_range(self):
        # 2026-05-08 to 2026-05-12: Movie tickets, Clothes, Miscellaneous = 3
        txns = get_recent_transactions(1, from_date="2026-05-08", to_date="2026-05-12")
        assert len(txns) == 3, (
            f"Expected 3 transactions for 2026-05-08 to 2026-05-12, got {len(txns)}"
        )

    def test_ordered_newest_first(self):
        txns = get_recent_transactions(1, from_date="2026-05-01", to_date="2026-05-15")
        dates = [t["date"] for t in txns]
        assert dates == sorted(dates, reverse=True), (
            "Transactions must be ordered newest-first (descending by date)"
        )

    def test_excludes_earlier_expenses(self):
        txns = get_recent_transactions(1, from_date="2026-05-10", to_date="2026-05-15")
        descriptions = {t["description"] for t in txns}
        assert "Groceries" not in descriptions, (
            "Groceries (2026-05-01) must be excluded when from_date=2026-05-10"
        )
        assert "Electricity bill" not in descriptions, (
            "Electricity bill (2026-05-03) must be excluded when from_date=2026-05-10"
        )

    def test_excludes_later_expenses(self):
        txns = get_recent_transactions(1, from_date="2026-05-01", to_date="2026-05-03")
        descriptions = {t["description"] for t in txns}
        assert "Movie tickets" not in descriptions, (
            "Movie tickets (2026-05-08) must be excluded when to_date=2026-05-03"
        )
        assert "Restaurant lunch" not in descriptions

    def test_empty_range_returns_empty_list(self):
        txns = get_recent_transactions(1, from_date="2020-01-01", to_date="2020-12-31")
        assert txns == [], (
            f"Expected [] for a range with no expenses, got {txns}"
        )

    def test_no_filter_returns_all_eight_rows(self):
        txns = get_recent_transactions(1)
        assert len(txns) == 8

    def test_row_keys_present(self):
        txns = get_recent_transactions(1, from_date="2026-05-01", to_date="2026-05-15")
        for txn in txns:
            assert "date" in txn, "Transaction row must have 'date' key"
            assert "description" in txn, "Transaction row must have 'description' key"
            assert "category" in txn, "Transaction row must have 'category' key"
            assert "amount" in txn, "Transaction row must have 'amount' key"

    def test_boundary_from_date_is_inclusive(self):
        # 2026-05-15 itself must be included
        txns = get_recent_transactions(1, from_date="2026-05-15", to_date="2026-05-15")
        assert len(txns) == 1
        assert txns[0]["description"] == "Restaurant lunch", (
            "The boundary from_date must be included in the result"
        )

    def test_boundary_to_date_is_inclusive(self):
        txns = get_recent_transactions(1, from_date="2026-05-01", to_date="2026-05-01")
        assert len(txns) == 1
        assert txns[0]["description"] == "Groceries", (
            "The boundary to_date must be included in the result"
        )

    def test_limit_is_still_respected_with_date_filter(self):
        txns = get_recent_transactions(1, limit=2, from_date="2026-05-01", to_date="2026-05-15")
        assert len(txns) == 2, (
            "limit parameter must still cap the result set even when date filter is active"
        )

    def test_returns_list_of_dicts(self):
        txns = get_recent_transactions(1, from_date="2026-05-01", to_date="2026-05-15")
        assert isinstance(txns, list)
        for row in txns:
            assert isinstance(row, dict)

    def test_isolated_user_no_data_returns_empty(self):
        uid = _make_user("txns_iso")
        txns = get_recent_transactions(uid, from_date="2026-05-01", to_date="2026-05-31")
        assert txns == []

    def test_user_isolation_with_date_filter(self):
        other_uid = _make_user("txns_other")
        _insert_expenses(other_uid, [
            (75.00, "Shopping", "2026-05-10", "Other user clothes"),
        ])
        # user_id=1 result for 2026-05-10 should only have Clothes (89.99)
        txns = get_recent_transactions(1, from_date="2026-05-10", to_date="2026-05-10")
        descriptions = [t["description"] for t in txns]
        assert "Other user clothes" not in descriptions, (
            "Transactions for other users must not appear in user_id=1's results"
        )

    @pytest.mark.parametrize("from_dt,to_dt,exp_count", [
        ("2026-05-01", "2026-05-02", 2),   # Groceries + Bus pass
        ("2026-05-03", "2026-05-05", 2),   # Electricity bill + Pharmacy
        ("2026-05-10", "2026-05-15", 3),   # Clothes + Miscellaneous + Restaurant
        ("2026-05-13", "2026-05-14", 0),   # gap — no expenses
        ("2026-05-01", "2026-05-15", 8),   # all seed expenses
    ])
    def test_parametrized_transaction_counts(self, from_dt, to_dt, exp_count):
        txns = get_recent_transactions(1, from_date=from_dt, to_date=to_dt)
        assert len(txns) == exp_count, (
            f"Range {from_dt} to {to_dt}: expected {exp_count} rows, got {len(txns)}"
        )


class TestGetCategoryBreakdownDateFilter:
    """Unit tests for get_category_breakdown(user_id, from_date=..., to_date=...)."""

    def test_returns_only_categories_in_range(self):
        # 2026-05-01 to 2026-05-05: Food, Transport, Bills, Health only
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-05")
        names = {c["name"] for c in cats}
        assert names == {"Food", "Transport", "Bills", "Health"}, (
            f"Expected exactly {{Food, Transport, Bills, Health}}, got {names}"
        )

    def test_excludes_out_of_range_categories(self):
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-05")
        names = {c["name"] for c in cats}
        for excluded in ("Entertainment", "Shopping", "Other"):
            assert excluded not in names, (
                f"'{excluded}' must be excluded when its expense is outside the date range"
            )

    def test_percents_sum_to_100(self):
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-15")
        total_pct = sum(c["percent"] for c in cats)
        assert total_pct == 100, (
            f"Category percents must sum to 100, got {total_pct}"
        )

    def test_single_category_range_is_100_percent(self):
        # Only Entertainment (25.00) on 2026-05-08
        cats = get_category_breakdown(1, from_date="2026-05-08", to_date="2026-05-08")
        assert len(cats) == 1
        assert cats[0]["percent"] == 100, (
            "A single-category result must show 100%"
        )

    def test_empty_range_returns_empty_list(self):
        cats = get_category_breakdown(1, from_date="2019-01-01", to_date="2019-12-31")
        assert cats == [], (
            f"Expected [] for a range with no matching expenses, got {cats}"
        )

    def test_no_filter_returns_all_seven_categories(self):
        cats = get_category_breakdown(1)
        assert len(cats) == 7

    def test_sorted_by_amount_descending(self):
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-15")
        amounts = [c["amount"] for c in cats]
        assert amounts == sorted(amounts, reverse=True), (
            "Categories must be sorted by amount in descending order"
        )

    def test_row_keys_present(self):
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-15")
        for cat in cats:
            assert "name" in cat, "Category row must have 'name' key"
            assert "amount" in cat, "Category row must have 'amount' key"
            assert "percent" in cat, "Category row must have 'percent' key"

    def test_amounts_are_floats(self):
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-15")
        for cat in cats:
            assert isinstance(cat["amount"], float), (
                f"Amount for category '{cat['name']}' must be a Python float"
            )

    def test_top_category_is_correct_for_range(self):
        # In 2026-05-01 to 2026-05-05, Bills (120.00) is the highest
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-05")
        assert cats[0]["name"] == "Bills", (
            f"First category must be 'Bills' (highest amount in range), got '{cats[0]['name']}'"
        )

    def test_partial_range_for_multi_entry_category(self):
        # Food: 2026-05-01 (42.50) and 2026-05-15 (18.75)
        # Filter to 2026-05-01 only → Food amount must be 42.50, not 61.25
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-01")
        food = next((c for c in cats if c["name"] == "Food"), None)
        assert food is not None, "Food category must be present on 2026-05-01"
        assert abs(food["amount"] - 42.50) < 0.01, (
            f"Food amount on 2026-05-01 only must be 42.50, got {food['amount']}"
        )

    def test_full_food_amount_includes_both_entries(self):
        # Both Food entries: 42.50 + 18.75 = 61.25
        cats = get_category_breakdown(1, from_date="2026-05-01", to_date="2026-05-15")
        food = next((c for c in cats if c["name"] == "Food"), None)
        assert food is not None
        assert abs(food["amount"] - 61.25) < 0.01, (
            f"Food total for full range must be 61.25 (both entries), got {food['amount']}"
        )

    def test_isolated_user_no_data_returns_empty(self):
        uid = _make_user("cats_iso")
        cats = get_category_breakdown(uid, from_date="2026-05-01", to_date="2026-05-31")
        assert cats == []

    def test_user_isolation_with_date_filter(self):
        other_uid = _make_user("cats_other")
        _insert_expenses(other_uid, [
            (500.00, "Luxury", "2026-05-10", "Luxury item"),
        ])
        cats = get_category_breakdown(1, from_date="2026-05-10", to_date="2026-05-10")
        names = {c["name"] for c in cats}
        assert "Luxury" not in names, (
            "A category belonging to another user must not appear in user_id=1's breakdown"
        )

    def test_isolated_user_with_own_expenses_in_range(self):
        uid = _make_user("cats_own")
        _insert_expenses(uid, [
            (100.00, "Food",      "2026-06-10", "Groceries"),
            (200.00, "Transport", "2026-06-15", "Flight"),
            (50.00,  "Food",      "2026-07-01", "Lunch"),  # outside range
        ])
        cats = get_category_breakdown(uid, from_date="2026-06-01", to_date="2026-06-30")
        names = {c["name"] for c in cats}
        assert names == {"Food", "Transport"}, (
            f"Only categories with expenses in June should appear, got {names}"
        )
        assert sum(c["percent"] for c in cats) == 100, (
            "Percents must sum to 100 for the filtered result"
        )

    @pytest.mark.parametrize("from_dt,to_dt,expected_count", [
        ("2026-05-01", "2026-05-02", 2),   # Food, Transport
        ("2026-05-03", "2026-05-05", 2),   # Bills, Health
        ("2026-05-08", "2026-05-12", 3),   # Entertainment, Shopping, Other
        ("2026-04-01", "2026-04-30", 0),   # no data → empty
    ])
    def test_parametrized_category_counts(self, from_dt, to_dt, expected_count):
        cats = get_category_breakdown(1, from_date=from_dt, to_date=to_dt)
        assert len(cats) == expected_count, (
            f"Range {from_dt} to {to_dt}: expected {expected_count} categories, "
            f"got {len(cats)}: {[c['name'] for c in cats]}"
        )
