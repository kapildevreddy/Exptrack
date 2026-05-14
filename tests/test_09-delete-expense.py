"""
Tests for Step 09 — Delete Expense Feature
============================================

Spec: routes GET /expenses/<id>/delete and POST /expenses/<id>/delete

Covers:
- Auth guard: unauthenticated GET and POST redirect to /login
- GET 200: confirmation page renders with amount, category, date visible
- GET 404: non-existent expense ID returns 404
- GET 403: expense belonging to a different user returns 403
- POST happy path: expense row is removed from the DB
- POST happy path: redirect to /profile after deletion
- POST happy path: success flash message appears on profile page
- POST 403: non-owner POST is refused, row is not deleted
- After deletion: expense absent from profile transaction list
- Cancel link: /profile link present on confirmation page
- Unauthenticated POST: row count unchanged

Setup:
  Uses the real spendly.db (same as all other test files in this project).
  Each test creates fresh users via create_user() with uuid-suffixed emails
  so tests never collide.  Expenses are created via add_expense().
"""

import uuid
import pytest
from database.db import create_user, add_expense, get_expense_by_id, get_db


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _unique_user(tag: str = "del") -> tuple[int, str, str]:
    """Create a fresh user and return (user_id, email, password)."""
    suffix = uuid.uuid4().hex[:8]
    email = f"delexp_{tag}_{suffix}@spendly.test"
    password = "testpass123"
    user_id = create_user(f"DelExp {tag} {suffix}", email, password)
    return user_id, email, password


def _make_expense(user_id: int) -> int:
    """Insert a sample expense for the given user and return its id."""
    return add_expense(
        user_id,
        amount=55.00,
        category="Food",
        date="2026-04-10",
        description="Test expense for delete",
    )


def _login(client, email: str, password: str):
    """POST to /login and return the response (no redirect follow)."""
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _expense_exists(expense_id: int) -> bool:
    """Return True if the expense row still exists in the DB."""
    return get_expense_by_id(expense_id) is not None


def _count_all_expenses() -> int:
    """Return total number of rows in the expenses table."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    conn.close()
    return count


# ------------------------------------------------------------------ #
# Fixtures (mirror conftest.py style used by this project)           #
# ------------------------------------------------------------------ #
# conftest.py already provides `app` and `client` fixtures.
# We rely on those — no re-definition needed.
# ------------------------------------------------------------------ #


# ==================================================================== #
# Section 1 — Auth guard                                               #
# ==================================================================== #


class TestAuthGuard:
    """Unauthenticated requests must be redirected to /login."""

    def test_get_unauthenticated_returns_302(self, client):
        user_id, _, _ = _unique_user("ag_get")
        expense_id = _make_expense(user_id)
        response = client.get(f"/expenses/{expense_id}/delete")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/<id>/delete must return 302"
        )

    def test_get_unauthenticated_redirects_to_login(self, client):
        user_id, _, _ = _unique_user("ag_get_loc")
        expense_id = _make_expense(user_id)
        response = client.get(f"/expenses/{expense_id}/delete")
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET /expenses/<id>/delete must redirect to /login"
        )

    def test_post_unauthenticated_returns_302(self, client):
        user_id, _, _ = _unique_user("ag_post")
        expense_id = _make_expense(user_id)
        response = client.post(f"/expenses/{expense_id}/delete")
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/<id>/delete must return 302"
        )

    def test_post_unauthenticated_redirects_to_login(self, client):
        user_id, _, _ = _unique_user("ag_post_loc")
        expense_id = _make_expense(user_id)
        response = client.post(f"/expenses/{expense_id}/delete")
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST /expenses/<id>/delete must redirect to /login"
        )

    def test_post_unauthenticated_does_not_delete_row(self, client):
        """An unauthenticated POST must not remove the expense from the DB."""
        user_id, _, _ = _unique_user("ag_nodel")
        expense_id = _make_expense(user_id)
        client.post(f"/expenses/{expense_id}/delete")
        assert _expense_exists(expense_id), (
            "Unauthenticated POST must not delete the expense row"
        )


# ==================================================================== #
# Section 2 — GET /expenses/<id>/delete (authenticated owner)          #
# ==================================================================== #


class TestGetDeleteConfirmation:
    """Authenticated owner should see a confirmation page with expense details."""

    def test_get_returns_200_for_owner(self, client):
        user_id, email, password = _unique_user("get200")
        expense_id = _make_expense(user_id)
        _login(client, email, password)
        response = client.get(f"/expenses/{expense_id}/delete")
        assert response.status_code == 200, (
            "Authenticated owner GET /expenses/<id>/delete must return 200"
        )

    def test_get_shows_amount_on_confirmation_page(self, client):
        user_id, email, password = _unique_user("get_amt")
        expense_id = add_expense(user_id, 99.99, "Food", "2026-04-10", "Lunch")
        _login(client, email, password)
        html = client.get(f"/expenses/{expense_id}/delete").data.decode()
        assert "99.99" in html, (
            "Confirmation page must display the expense amount (99.99)"
        )

    def test_get_shows_category_on_confirmation_page(self, client):
        user_id, email, password = _unique_user("get_cat")
        expense_id = add_expense(user_id, 30.00, "Transport", "2026-04-10", "Bus")
        _login(client, email, password)
        html = client.get(f"/expenses/{expense_id}/delete").data.decode()
        assert "Transport" in html, (
            "Confirmation page must display the expense category (Transport)"
        )

    def test_get_shows_date_on_confirmation_page(self, client):
        user_id, email, password = _unique_user("get_date")
        expense_id = add_expense(user_id, 15.00, "Bills", "2026-03-22", "Electricity")
        _login(client, email, password)
        html = client.get(f"/expenses/{expense_id}/delete").data.decode()
        assert "2026-03-22" in html, (
            "Confirmation page must display the expense date (2026-03-22)"
        )

    def test_get_confirmation_page_contains_post_form(self, client):
        """The confirmation page must use a POST form — never delete on GET."""
        user_id, email, password = _unique_user("get_form")
        expense_id = _make_expense(user_id)
        _login(client, email, password)
        html = client.get(f"/expenses/{expense_id}/delete").data.decode()
        assert 'method="post"' in html.lower(), (
            "Confirmation page must contain a form with method='post'"
        )

    def test_get_confirmation_page_has_cancel_link_to_profile(self, client):
        """The Cancel link must point back to /profile."""
        user_id, email, password = _unique_user("get_cancel")
        expense_id = _make_expense(user_id)
        _login(client, email, password)
        html = client.get(f"/expenses/{expense_id}/delete").data.decode()
        assert "/profile" in html, (
            "Confirmation page must contain a Cancel link pointing to /profile"
        )

    def test_get_confirmation_page_extends_base_template(self, client):
        """The page must extend base.html — check for a landmark from base.html."""
        user_id, email, password = _unique_user("get_base")
        expense_id = _make_expense(user_id)
        _login(client, email, password)
        html = client.get(f"/expenses/{expense_id}/delete").data.decode()
        # base.html renders the nav; check for "Spendly" which appears in brand/logo
        assert "Spendly" in html, (
            "Page must extend base.html (expected 'Spendly' from base template)"
        )

    def test_get_confirmation_page_has_submit_button(self, client):
        """There must be a submit button on the confirmation form."""
        user_id, email, password = _unique_user("get_submit")
        expense_id = _make_expense(user_id)
        _login(client, email, password)
        html = client.get(f"/expenses/{expense_id}/delete").data.decode()
        assert 'type="submit"' in html.lower(), (
            "Confirmation page must contain a submit button"
        )

    def test_get_does_not_delete_the_expense(self, client):
        """A GET request must never delete the expense — delete only happens on POST."""
        user_id, email, password = _unique_user("get_nodel")
        expense_id = _make_expense(user_id)
        _login(client, email, password)
        client.get(f"/expenses/{expense_id}/delete")
        assert _expense_exists(expense_id), (
            "GET /expenses/<id>/delete must not delete the expense row"
        )


# ==================================================================== #
# Section 3 — Not-found and ownership errors on GET                    #
# ==================================================================== #


class TestGetOwnershipAndNotFound:
    """GET must enforce 404 for missing expenses and 403 for wrong owner."""

    def test_get_nonexistent_expense_returns_404(self, client):
        user_id, email, password = _unique_user("get404")
        _login(client, email, password)
        response = client.get("/expenses/999999/delete")
        assert response.status_code == 404, (
            "GET /expenses/<id>/delete with non-existent id must return 404"
        )

    def test_get_wrong_owner_returns_403(self, client):
        owner_id, _, _ = _unique_user("get403_owner")
        other_id, other_email, other_pass = _unique_user("get403_other")
        expense_id = _make_expense(owner_id)

        # Log in as the OTHER user (not the owner)
        _login(client, other_email, other_pass)
        response = client.get(f"/expenses/{expense_id}/delete")
        assert response.status_code == 403, (
            "GET /expenses/<id>/delete must return 403 when the expense belongs to a different user"
        )

    def test_get_404_beats_403_when_expense_missing(self, client):
        """A request for a missing ID should always be 404, not 403."""
        _, email, password = _unique_user("get404_not403")
        _login(client, email, password)
        response = client.get("/expenses/888888/delete")
        assert response.status_code == 404, (
            "A missing expense ID must yield 404 regardless of the requester's identity"
        )


# ==================================================================== #
# Section 4 — POST /expenses/<id>/delete happy path                    #
# ==================================================================== #


class TestPostDeleteHappyPath:
    """Valid POST by the owner must delete the row and redirect to /profile."""

    def test_post_returns_302(self, client):
        user_id, email, password = _unique_user("post302")
        expense_id = _make_expense(user_id)
        _login(client, email, password)
        response = client.post(
            f"/expenses/{expense_id}/delete", follow_redirects=False
        )
        assert response.status_code == 302, (
            "Valid POST /expenses/<id>/delete must return 302"
        )

    def test_post_redirects_to_profile(self, client):
        user_id, email, password = _unique_user("post_loc")
        expense_id = _make_expense(user_id)
        _login(client, email, password)
        response = client.post(
            f"/expenses/{expense_id}/delete", follow_redirects=False
        )
        assert "/profile" in response.headers["Location"], (
            "POST /expenses/<id>/delete must redirect to /profile"
        )

    def test_post_deletes_expense_from_db(self, client):
        user_id, email, password = _unique_user("post_db")
        expense_id = _make_expense(user_id)
        assert _expense_exists(expense_id), "Expense must exist before deletion"
        _login(client, email, password)
        client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)
        assert not _expense_exists(expense_id), (
            "POST /expenses/<id>/delete must remove the expense row from the DB"
        )

    def test_post_shows_success_flash_on_profile(self, client):
        user_id, email, password = _unique_user("post_flash")
        expense_id = _make_expense(user_id)
        _login(client, email, password)
        response = client.post(
            f"/expenses/{expense_id}/delete", follow_redirects=True
        )
        assert response.status_code == 200, (
            "Following the redirect after deletion must land on a 200 page"
        )
        html = response.data.decode()
        # The spec says flash a success message; check for keywords present in the flash
        assert "deleted" in html.lower() or "success" in html.lower(), (
            "A success flash message must appear on the profile page after deletion"
        )

    def test_post_deletes_only_target_expense(self, client):
        """Deleting one expense must not affect other expenses for the same user."""
        user_id, email, password = _unique_user("post_only")
        expense_id_1 = _make_expense(user_id)
        expense_id_2 = _make_expense(user_id)
        _login(client, email, password)
        client.post(f"/expenses/{expense_id_1}/delete", follow_redirects=False)
        assert not _expense_exists(expense_id_1), (
            "The targeted expense must be deleted"
        )
        assert _expense_exists(expense_id_2), (
            "Other expenses for the same user must not be deleted"
        )

    def test_deleted_expense_absent_from_profile_transaction_list(self, client):
        """After deletion the expense must not appear in the profile transaction list."""
        user_id, email, password = _unique_user("post_profile")
        expense_id = add_expense(
            user_id,
            amount=77.77,
            category="Shopping",
            date="2026-04-15",
            description="Unique item for delete test",
        )
        _login(client, email, password)
        # Delete via POST
        client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)
        # Fetch profile with all-time filter so the deleted expense would appear if present
        profile_response = client.get("/profile?from=&to=", follow_redirects=True)
        html = profile_response.data.decode()
        # The unique description must no longer appear
        assert "Unique item for delete test" not in html, (
            "Deleted expense must not appear in the profile transaction list"
        )


# ==================================================================== #
# Section 5 — Ownership check on POST                                  #
# ==================================================================== #


class TestPostOwnership:
    """POST must also enforce ownership — wrong owner gets 403, row survives."""

    def test_post_wrong_owner_returns_403(self, client):
        owner_id, _, _ = _unique_user("post403_owner")
        other_id, other_email, other_pass = _unique_user("post403_other")
        expense_id = _make_expense(owner_id)

        _login(client, other_email, other_pass)
        response = client.post(
            f"/expenses/{expense_id}/delete", follow_redirects=False
        )
        assert response.status_code == 403, (
            "POST /expenses/<id>/delete must return 403 when the expense belongs to a different user"
        )

    def test_post_wrong_owner_does_not_delete_row(self, client):
        """A 403 POST must leave the expense untouched in the DB."""
        owner_id, _, _ = _unique_user("post403_nodel_owner")
        other_id, other_email, other_pass = _unique_user("post403_nodel_other")
        expense_id = _make_expense(owner_id)

        _login(client, other_email, other_pass)
        client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)
        assert _expense_exists(expense_id), (
            "Expense row must NOT be deleted when the POST is made by a non-owner"
        )

    def test_post_nonexistent_expense_returns_404(self, client):
        """POST against a missing expense ID must return 404, not crash."""
        _, email, password = _unique_user("post404")
        _login(client, email, password)
        response = client.post("/expenses/777777/delete", follow_redirects=False)
        assert response.status_code == 404, (
            "POST /expenses/<id>/delete with a non-existent id must return 404"
        )


# ==================================================================== #
# Section 6 — User isolation                                           #
# ==================================================================== #


class TestUserIsolation:
    """Deleting an expense must only affect the target user's data."""

    def test_delete_does_not_affect_other_users_expenses(self, client):
        """Deleting User A's expense must leave User B's expenses intact."""
        user_a_id, email_a, pass_a = _unique_user("iso_a")
        user_b_id, email_b, pass_b = _unique_user("iso_b")

        expense_a_id = _make_expense(user_a_id)
        expense_b_id = _make_expense(user_b_id)

        _login(client, email_a, pass_a)
        client.post(f"/expenses/{expense_a_id}/delete", follow_redirects=False)

        assert not _expense_exists(expense_a_id), (
            "User A's expense must be deleted"
        )
        assert _expense_exists(expense_b_id), (
            "User B's expense must not be affected when User A deletes their own expense"
        )

    def test_user_cannot_delete_another_users_expense_via_url(self, client):
        """Directly hitting another user's delete URL must be blocked with 403."""
        victim_id, _, _ = _unique_user("iso_victim")
        attacker_id, attacker_email, attacker_pass = _unique_user("iso_attacker")

        victim_expense_id = add_expense(
            victim_id, 200.00, "Bills", "2026-01-01", "Victim's bill"
        )

        _login(client, attacker_email, attacker_pass)
        response = client.post(
            f"/expenses/{victim_expense_id}/delete", follow_redirects=False
        )
        assert response.status_code == 403, (
            "A user must not be able to delete another user's expense — 403 expected"
        )
        assert _expense_exists(victim_expense_id), (
            "Victim's expense must remain in the DB after an unauthorized delete attempt"
        )


# ==================================================================== #
# Section 7 — SQL injection safety                                     #
# ==================================================================== #


class TestSqlInjectionSafety:
    """The route must use parameterised queries — injection attempts must be harmless."""

    def test_get_with_injection_style_id_is_not_found(self, client):
        """Non-integer IDs are rejected at the routing level (Flask int converter)."""
        _, email, password = _unique_user("sqli_get")
        _login(client, email, password)
        # Flask's <int:id> converter rejects non-integer path segments with 404
        response = client.get("/expenses/1;DROP TABLE expenses--/delete")
        assert response.status_code == 404, (
            "A non-integer expense ID in the URL must result in 404 (Flask type converter)"
        )

    def test_post_with_injection_style_id_is_not_found(self, client):
        """Flask's int converter must reject non-integer path segments on POST too."""
        _, email, password = _unique_user("sqli_post")
        _login(client, email, password)
        response = client.post("/expenses/1;DROP TABLE expenses--/delete")
        assert response.status_code == 404, (
            "A non-integer expense ID in the POST URL must result in 404"
        )
