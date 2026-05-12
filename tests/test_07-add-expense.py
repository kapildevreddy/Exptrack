"""
Tests for Step 07 — Add Expense Feature
========================================

Spec: routes GET /expenses/add and POST /expenses/add

Covers:
- Auth guard: unauthenticated GET and POST redirect to /login
- GET: 200 status, form fields present, all categories listed, today pre-populated
- POST happy path: DB row inserted, redirect to /profile, success flash
- POST validation errors: zero/negative/non-numeric amount, invalid category,
  malformed date, description > 300 chars — all must re-render with error flash
- Form value preservation on validation failure
- No DB row inserted when validation fails
- User isolation: expense belongs to the correct user

Seed data (demo user, id=1, seeded by seed_db()):
  8 rows seeded in May 2026 with a total of 356.24.
  Tests that verify counts use a fresh isolated user to avoid coupling to seed state.
"""

import uuid
import pytest
from database.db import create_user, get_db
from database.queries import get_recent_transactions


def _make_test_user(tag: str = "add") -> tuple[int, str, str]:
    """
    Create a fresh user with a unique email and return (user_id, email, password).
    Uses uuid4 so emails never collide across test runs on the shared DB.
    """
    unique = uuid.uuid4().hex[:8]
    email = f"addexp_{tag}_{unique}@spendly.test"
    password = "testpass123"
    user_id = create_user(f"AddExp {tag} {unique}", email, password)
    return user_id, email, password


def _login(client, email: str, password: str):
    """POST to /login and return the response."""
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _count_expenses_for_user(user_id: int) -> int:
    """Return the number of rows in `expenses` for the given user_id."""
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def _get_expenses_for_user(user_id: int) -> list[dict]:
    """Return all expense rows for the given user_id as a list of dicts."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ #
# Valid payload used across multiple tests                            #
# ------------------------------------------------------------------ #
VALID_PAYLOAD = {
    "amount": "42.50",
    "category": "Food",
    "date": "2026-06-01",
    "description": "Weekly groceries",
}

ALL_VALID_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


# ==================================================================== #
# Section 1 — Auth guard                                               #
# ==================================================================== #


class TestAuthGuard:
    """Unauthenticated requests to GET and POST /expenses/add must redirect to /login."""

    def test_get_unauthenticated_returns_302(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/add must return 302"
        )

    def test_get_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET /expenses/add must redirect to /login"
        )

    def test_post_unauthenticated_returns_302(self, client):
        response = client.post("/expenses/add", data=VALID_PAYLOAD)
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/add must return 302"
        )

    def test_post_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/add", data=VALID_PAYLOAD)
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST /expenses/add must redirect to /login"
        )

    def test_post_unauthenticated_does_not_insert_row(self, client):
        """No row must be written to the DB when the request is unauthenticated."""
        user_id, email, password = _make_test_user("noauth")
        # Only created the user — no expenses yet; post without logging in
        before = _count_expenses_for_user(user_id)
        client.post("/expenses/add", data=VALID_PAYLOAD)
        after = _count_expenses_for_user(user_id)
        assert after == before, (
            "Unauthenticated POST must not insert any expense row"
        )


# ==================================================================== #
# Section 2 — GET /expenses/add (authenticated)                        #
# ==================================================================== #


class TestGetAddExpenseForm:
    """Authenticated GET must render the add-expense form correctly."""

    def test_returns_200(self, client):
        user_id, email, password = _make_test_user("get200")
        _login(client, email, password)
        response = client.get("/expenses/add")
        assert response.status_code == 200, (
            "Authenticated GET /expenses/add must return 200"
        )

    def test_page_contains_amount_field(self, client):
        user_id, email, password = _make_test_user("get_amount")
        _login(client, email, password)
        html = client.get("/expenses/add").data.decode()
        assert 'name="amount"' in html, (
            "Add-expense form must contain an input with name='amount'"
        )

    def test_page_contains_category_field(self, client):
        user_id, email, password = _make_test_user("get_cat")
        _login(client, email, password)
        html = client.get("/expenses/add").data.decode()
        assert 'name="category"' in html, (
            "Add-expense form must contain a select/input with name='category'"
        )

    def test_page_contains_date_field(self, client):
        user_id, email, password = _make_test_user("get_date")
        _login(client, email, password)
        html = client.get("/expenses/add").data.decode()
        assert 'name="date"' in html, (
            "Add-expense form must contain an input with name='date'"
        )

    def test_page_contains_description_field(self, client):
        user_id, email, password = _make_test_user("get_desc")
        _login(client, email, password)
        html = client.get("/expenses/add").data.decode()
        assert 'name="description"' in html, (
            "Add-expense form must contain an input/textarea with name='description'"
        )

    def test_all_categories_are_listed(self, client):
        user_id, email, password = _make_test_user("get_cats")
        _login(client, email, password)
        html = client.get("/expenses/add").data.decode()
        for category in ALL_VALID_CATEGORIES:
            assert category in html, (
                f"Category option '{category}' must appear in the add-expense form"
            )

    def test_form_uses_post_method(self, client):
        user_id, email, password = _make_test_user("get_method")
        _login(client, email, password)
        html = client.get("/expenses/add").data.decode()
        assert 'method="post"' in html.lower(), (
            "Add-expense form must use method='post' (or POST)"
        )

    def test_date_field_prepopulated_with_today(self, client):
        """The date input must be pre-filled with today's ISO date (2026-05-12)."""
        user_id, email, password = _make_test_user("get_today")
        _login(client, email, password)
        html = client.get("/expenses/add").data.decode()
        # Today per project date is 2026-05-12 (from currentDate context)
        assert "2026-05-12" in html, (
            "Date field must be pre-populated with today's date (2026-05-12)"
        )

    def test_form_action_points_to_add_expense(self, client):
        user_id, email, password = _make_test_user("get_action")
        _login(client, email, password)
        html = client.get("/expenses/add").data.decode()
        assert "/expenses/add" in html, (
            "Form action must point to the /expenses/add route"
        )


# ==================================================================== #
# Section 3 — POST /expenses/add happy path                            #
# ==================================================================== #


class TestPostAddExpenseHappyPath:
    """Valid POST must insert the row and redirect to /profile."""

    def test_valid_post_returns_302(self, client):
        user_id, email, password = _make_test_user("happy_302")
        _login(client, email, password)
        response = client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        assert response.status_code == 302, (
            "Valid POST /expenses/add must return a 302 redirect"
        )

    def test_valid_post_redirects_to_profile(self, client):
        user_id, email, password = _make_test_user("happy_loc")
        _login(client, email, password)
        response = client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        assert "/profile" in response.headers["Location"], (
            "Valid POST /expenses/add must redirect to /profile"
        )

    def test_valid_post_shows_success_flash(self, client):
        user_id, email, password = _make_test_user("happy_flash")
        _login(client, email, password)
        response = client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=True)
        assert b"Expense added successfully." in response.data, (
            "Success flash 'Expense added successfully.' must appear after valid POST"
        )

    def test_valid_post_inserts_one_row(self, client):
        user_id, email, password = _make_test_user("happy_db")
        _login(client, email, password)
        before = _count_expenses_for_user(user_id)
        client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        after = _count_expenses_for_user(user_id)
        assert after == before + 1, (
            "Valid POST must insert exactly one row into the expenses table"
        )

    def test_valid_post_stores_correct_amount(self, client):
        user_id, email, password = _make_test_user("happy_amount")
        _login(client, email, password)
        client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        expenses = _get_expenses_for_user(user_id)
        assert len(expenses) == 1
        assert abs(expenses[0]["amount"] - 42.50) < 0.001, (
            f"Stored amount must be 42.50, got {expenses[0]['amount']}"
        )

    def test_valid_post_stores_correct_category(self, client):
        user_id, email, password = _make_test_user("happy_category")
        _login(client, email, password)
        client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        expenses = _get_expenses_for_user(user_id)
        assert expenses[0]["category"] == "Food", (
            f"Stored category must be 'Food', got '{expenses[0]['category']}'"
        )

    def test_valid_post_stores_correct_date(self, client):
        user_id, email, password = _make_test_user("happy_date")
        _login(client, email, password)
        client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        expenses = _get_expenses_for_user(user_id)
        assert expenses[0]["date"] == "2026-06-01", (
            f"Stored date must be '2026-06-01', got '{expenses[0]['date']}'"
        )

    def test_valid_post_stores_correct_description(self, client):
        user_id, email, password = _make_test_user("happy_descr")
        _login(client, email, password)
        client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        expenses = _get_expenses_for_user(user_id)
        assert expenses[0]["description"] == "Weekly groceries", (
            f"Stored description must be 'Weekly groceries', got '{expenses[0]['description']}'"
        )

    def test_valid_post_stores_correct_user_id(self, client):
        user_id, email, password = _make_test_user("happy_uid")
        _login(client, email, password)
        client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        expenses = _get_expenses_for_user(user_id)
        assert expenses[0]["user_id"] == user_id, (
            f"Stored user_id must be {user_id}, got {expenses[0]['user_id']}"
        )

    def test_valid_post_without_description_succeeds(self, client):
        """Description is optional — an empty description must not trigger an error."""
        user_id, email, password = _make_test_user("happy_nodesc")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "description": ""}
        response = client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 302, (
            "POST with empty description must succeed (302 redirect)"
        )
        expenses = _get_expenses_for_user(user_id)
        assert len(expenses) == 1, "One expense row must be inserted even with empty description"

    def test_valid_post_description_empty_stored_as_null_or_empty(self, client):
        """Description column allows NULL; an empty submit must not raise an error."""
        user_id, email, password = _make_test_user("happy_nulldesc")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "description": ""}
        client.post("/expenses/add", data=payload, follow_redirects=False)
        expenses = _get_expenses_for_user(user_id)
        # description should be None (NULL) or empty string — either is acceptable
        assert expenses[0]["description"] in (None, ""), (
            f"Empty description must be stored as NULL or empty, got '{expenses[0]['description']}'"
        )

    def test_expense_appears_in_get_recent_transactions(self, client):
        """The newly inserted expense must be retrievable via get_recent_transactions."""
        user_id, email, password = _make_test_user("happy_query")
        _login(client, email, password)
        client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        txns = get_recent_transactions(user_id)
        assert len(txns) == 1, (
            f"get_recent_transactions must return 1 row for the new user, got {len(txns)}"
        )
        assert txns[0]["category"] == "Food"
        assert abs(txns[0]["amount"] - 42.50) < 0.001

    @pytest.mark.parametrize("category", ALL_VALID_CATEGORIES)
    def test_all_valid_categories_accepted(self, client, category):
        user_id, email, password = _make_test_user(f"cat_{category.lower()}")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "category": category}
        response = client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 302, (
            f"Category '{category}' must be accepted and produce a 302 redirect"
        )
        expenses = _get_expenses_for_user(user_id)
        assert len(expenses) == 1, f"Exactly one row must be inserted for category '{category}'"
        assert expenses[0]["category"] == category

    def test_amount_as_integer_string_accepted(self, client):
        """An amount like '100' (no decimal) must be accepted as a valid positive float."""
        user_id, email, password = _make_test_user("int_amount")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "amount": "100"}
        response = client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 302, (
            "Integer-string amount '100' must be accepted"
        )

    def test_sql_injection_in_description_stored_safely(self, client):
        """A SQL injection attempt in description must be stored as plain text, not executed."""
        user_id, email, password = _make_test_user("sql_inject")
        _login(client, email, password)
        malicious_desc = "'; DROP TABLE expenses; --"
        payload = {**VALID_PAYLOAD, "description": malicious_desc}
        response = client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 302, (
            "SQL injection in description must not crash the route"
        )
        # Expenses table must still be intact
        expenses = _get_expenses_for_user(user_id)
        assert len(expenses) == 1, "expenses table must survive a SQL injection attempt"
        assert expenses[0]["description"] == malicious_desc, (
            "Injected string must be stored verbatim, not interpreted as SQL"
        )


# ==================================================================== #
# Section 4 — POST validation errors: amount                           #
# ==================================================================== #


class TestAmountValidation:
    """Invalid amount values must re-render the form with an error flash."""

    @pytest.mark.parametrize("bad_amount", [
        "0",
        "0.0",
        "-1",
        "-0.01",
        "-999.99",
    ])
    def test_zero_or_negative_amount_rejected(self, client, bad_amount):
        user_id, email, password = _make_test_user(f"amt_neg_{bad_amount.replace('-', 'n').replace('.', 'd')}")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "amount": bad_amount}
        response = client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 200, (
            f"Amount '{bad_amount}' must re-render the form (200), not redirect"
        )

    @pytest.mark.parametrize("bad_amount", ["0", "-1", "-0.01", "-999.99"])
    def test_zero_or_negative_shows_error_flash(self, client, bad_amount):
        user_id, email, password = _make_test_user(f"amt_flash_{bad_amount.replace('-', 'n').replace('.', 'd')}")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "amount": bad_amount}
        response = client.post("/expenses/add", data=payload, follow_redirects=True)
        assert b"Amount must be a positive number." in response.data, (
            f"Error flash must appear for amount '{bad_amount}'"
        )

    @pytest.mark.parametrize("bad_amount", [
        "",
        "abc",
        "one hundred",
        "12.34.56",
        "  ",
        "1e999",  # effectively inf — should be rejected or accepted; spec says positive float
    ])
    def test_non_numeric_amount_rejected(self, client, bad_amount):
        user_id, email, password = _make_test_user(f"amt_nn_{abs(hash(bad_amount)) % 9999}")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "amount": bad_amount}
        response = client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 200, (
            f"Non-numeric amount '{bad_amount!r}' must re-render the form (200)"
        )

    def test_non_numeric_amount_shows_error_flash(self, client):
        user_id, email, password = _make_test_user("amt_nn_flash")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "amount": "not-a-number"}
        response = client.post("/expenses/add", data=payload, follow_redirects=True)
        assert b"Amount must be a positive number." in response.data, (
            "Error flash 'Amount must be a positive number.' must appear for non-numeric amount"
        )

    def test_invalid_amount_does_not_insert_row(self, client):
        user_id, email, password = _make_test_user("amt_nodb")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "amount": "0"}
        before = _count_expenses_for_user(user_id)
        client.post("/expenses/add", data=payload, follow_redirects=False)
        after = _count_expenses_for_user(user_id)
        assert after == before, (
            "Validation failure (bad amount) must not insert any expense row"
        )


# ==================================================================== #
# Section 5 — POST validation errors: category                         #
# ==================================================================== #


class TestCategoryValidation:
    """Invalid category values must re-render the form with an error flash."""

    @pytest.mark.parametrize("bad_category", [
        "",
        "food",          # wrong case
        "FOOD",          # all caps
        "Groceries",     # not in the list
        "Unknown",
        "'; DROP TABLE expenses; --",
    ])
    def test_invalid_category_rejected(self, client, bad_category):
        user_id, email, password = _make_test_user(f"cat_bad_{abs(hash(bad_category)) % 9999}")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "category": bad_category}
        response = client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 200, (
            f"Invalid category '{bad_category!r}' must re-render the form (200)"
        )

    def test_invalid_category_shows_error_flash(self, client):
        user_id, email, password = _make_test_user("cat_flash")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "category": "Groceries"}
        response = client.post("/expenses/add", data=payload, follow_redirects=True)
        assert b"Please select a valid category." in response.data, (
            "Error flash 'Please select a valid category.' must appear for an invalid category"
        )

    def test_invalid_category_does_not_insert_row(self, client):
        user_id, email, password = _make_test_user("cat_nodb")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "category": "InvalidCat"}
        before = _count_expenses_for_user(user_id)
        client.post("/expenses/add", data=payload, follow_redirects=False)
        after = _count_expenses_for_user(user_id)
        assert after == before, (
            "Validation failure (bad category) must not insert any expense row"
        )


# ==================================================================== #
# Section 6 — POST validation errors: date                             #
# ==================================================================== #


class TestDateValidation:
    """Invalid date strings must re-render the form with an error flash."""

    @pytest.mark.parametrize("bad_date", [
        "",
        "01/06/2026",        # DD/MM/YYYY — wrong format
        "06-01-2026",        # MM-DD-YYYY — wrong format
        "2026/06/01",        # slashes instead of dashes
        "not-a-date",
        "2026-13-01",        # month 13 doesn't exist
        "2026-00-01",        # month 0 doesn't exist
        "2026-06-32",        # day 32 doesn't exist
        "20260601",          # missing separators
    ])
    def test_invalid_date_rejected(self, client, bad_date):
        user_id, email, password = _make_test_user(f"dt_bad_{abs(hash(bad_date)) % 9999}")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "date": bad_date}
        response = client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 200, (
            f"Invalid date '{bad_date!r}' must re-render the form (200)"
        )

    def test_invalid_date_shows_error_flash(self, client):
        user_id, email, password = _make_test_user("dt_flash")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "date": "not-a-date"}
        response = client.post("/expenses/add", data=payload, follow_redirects=True)
        assert b"Date must be a valid YYYY-MM-DD date." in response.data, (
            "Error flash 'Date must be a valid YYYY-MM-DD date.' must appear for a malformed date"
        )

    def test_invalid_date_does_not_insert_row(self, client):
        user_id, email, password = _make_test_user("dt_nodb")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "date": "bad-date"}
        before = _count_expenses_for_user(user_id)
        client.post("/expenses/add", data=payload, follow_redirects=False)
        after = _count_expenses_for_user(user_id)
        assert after == before, (
            "Validation failure (bad date) must not insert any expense row"
        )


# ==================================================================== #
# Section 7 — POST validation errors: description length               #
# ==================================================================== #


class TestDescriptionValidation:
    """Description longer than 300 characters must be rejected."""

    def test_description_301_chars_rejected(self, client):
        user_id, email, password = _make_test_user("desc_long")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "description": "x" * 301}
        response = client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 200, (
            "A 301-character description must re-render the form (200)"
        )

    def test_description_301_chars_shows_error_flash(self, client):
        user_id, email, password = _make_test_user("desc_long_flash")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "description": "y" * 301}
        response = client.post("/expenses/add", data=payload, follow_redirects=True)
        assert b"Description must be 300 characters or fewer." in response.data, (
            "Error flash for oversized description must appear"
        )

    def test_description_300_chars_accepted(self, client):
        """Exactly 300 characters must not trigger a validation error."""
        user_id, email, password = _make_test_user("desc_max")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "description": "z" * 300}
        response = client.post("/expenses/add", data=payload, follow_redirects=False)
        assert response.status_code == 302, (
            "A 300-character description (at the boundary) must be accepted"
        )

    def test_description_over_limit_does_not_insert_row(self, client):
        user_id, email, password = _make_test_user("desc_nodb")
        _login(client, email, password)
        payload = {**VALID_PAYLOAD, "description": "a" * 301}
        before = _count_expenses_for_user(user_id)
        client.post("/expenses/add", data=payload, follow_redirects=False)
        after = _count_expenses_for_user(user_id)
        assert after == before, (
            "Validation failure (description too long) must not insert any expense row"
        )


# ==================================================================== #
# Section 8 — Form value preservation on validation error              #
# ==================================================================== #


class TestFormValuePreservation:
    """After a validation failure the form must re-render with the user's input intact."""

    def test_amount_preserved_after_invalid_category(self, client):
        user_id, email, password = _make_test_user("pres_amount")
        _login(client, email, password)
        payload = {
            "amount": "99.99",
            "category": "InvalidCat",
            "date": "2026-06-15",
            "description": "Test description",
        }
        html = client.post("/expenses/add", data=payload, follow_redirects=False).data.decode()
        assert "99.99" in html, (
            "The submitted amount must be preserved in the re-rendered form"
        )

    def test_date_preserved_after_invalid_category(self, client):
        user_id, email, password = _make_test_user("pres_date")
        _login(client, email, password)
        payload = {
            "amount": "99.99",
            "category": "InvalidCat",
            "date": "2026-06-15",
            "description": "Test description",
        }
        html = client.post("/expenses/add", data=payload, follow_redirects=False).data.decode()
        assert "2026-06-15" in html, (
            "The submitted date must be preserved in the re-rendered form"
        )

    def test_description_preserved_after_invalid_amount(self, client):
        user_id, email, password = _make_test_user("pres_desc")
        _login(client, email, password)
        payload = {
            "amount": "-5",
            "category": "Food",
            "date": "2026-06-15",
            "description": "My preserved description",
        }
        html = client.post("/expenses/add", data=payload, follow_redirects=False).data.decode()
        assert "My preserved description" in html, (
            "The submitted description must be preserved in the re-rendered form"
        )

    def test_category_preserved_after_invalid_date(self, client):
        user_id, email, password = _make_test_user("pres_cat")
        _login(client, email, password)
        payload = {
            "amount": "50.00",
            "category": "Transport",
            "date": "not-a-date",
            "description": "",
        }
        html = client.post("/expenses/add", data=payload, follow_redirects=False).data.decode()
        # The selected category must appear as selected/value in the re-rendered form
        assert "Transport" in html, (
            "The submitted category must be preserved in the re-rendered form"
        )

    def test_amount_preserved_after_invalid_date(self, client):
        user_id, email, password = _make_test_user("pres_amt_dt")
        _login(client, email, password)
        payload = {
            "amount": "123.45",
            "category": "Bills",
            "date": "INVALID",
            "description": "Electricity",
        }
        html = client.post("/expenses/add", data=payload, follow_redirects=False).data.decode()
        assert "123.45" in html, (
            "Amount must be preserved when re-rendering after a date validation error"
        )

    def test_multiple_errors_all_flashed(self, client):
        """When both amount and date are invalid, both error messages must be shown."""
        user_id, email, password = _make_test_user("multi_error")
        _login(client, email, password)
        payload = {
            "amount": "-5",
            "category": "Food",
            "date": "not-a-date",
            "description": "",
        }
        response = client.post("/expenses/add", data=payload, follow_redirects=True)
        html = response.data.decode()
        assert "Amount must be a positive number." in html, (
            "Amount error flash must appear when both amount and date are invalid"
        )
        assert "Date must be a valid YYYY-MM-DD date." in html, (
            "Date error flash must appear when both amount and date are invalid"
        )


# ==================================================================== #
# Section 9 — User isolation                                           #
# ==================================================================== #


class TestUserIsolation:
    """Expenses must be associated with the correct user and not visible to others."""

    def test_expense_not_visible_to_another_user(self, client):
        """User A's expense must not appear in User B's transaction list."""
        user_a_id, email_a, pass_a = _make_test_user("iso_a")
        user_b_id, email_b, pass_b = _make_test_user("iso_b")

        # Log in as User A and add an expense
        _login(client, email_a, pass_a)
        client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        client.get("/logout")  # log out

        # User B must not see User A's expense
        txns_b = get_recent_transactions(user_b_id)
        assert len(txns_b) == 0, (
            "User B must not have any expenses after User A adds one"
        )

    def test_expense_belongs_to_logged_in_user_only(self, client):
        user_a_id, email_a, pass_a = _make_test_user("iso_own_a")
        user_b_id, email_b, pass_b = _make_test_user("iso_own_b")

        # Add expense as User A
        _login(client, email_a, pass_a)
        client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)
        client.get("/logout")

        # Add a different expense as User B
        _login(client, email_b, pass_b)
        payload_b = {**VALID_PAYLOAD, "amount": "77.77", "category": "Transport"}
        client.post("/expenses/add", data=payload_b, follow_redirects=False)

        # Each user must have exactly their own expense
        expenses_a = _get_expenses_for_user(user_a_id)
        expenses_b = _get_expenses_for_user(user_b_id)

        assert len(expenses_a) == 1
        assert expenses_a[0]["user_id"] == user_a_id

        assert len(expenses_b) == 1
        assert expenses_b[0]["user_id"] == user_b_id
        assert abs(expenses_b[0]["amount"] - 77.77) < 0.001
