# Spec: Delete Expense

## Overview
This feature replaces the stub `GET /expenses/<id>/delete` route with a safe, two-step delete flow. On GET, the user sees a confirmation page showing the expense details before they commit. On POST, ownership is verified, the expense is deleted from the database, and the user is redirected to their profile with a flash message. Ownership is always enforced — users cannot delete another user's expense (404 if not found, 403 if not theirs).

## Depends on
- Step 01 — database setup (`expenses` table exists)
- Step 03 — login/logout (session management)
- Step 04/05 — profile page (redirect target after delete)
- Step 08 — edit expense (introduces `get_expense_by_id()` and the ownership-check pattern to reuse)

## Routes
- `GET  /expenses/<int:id>/delete` — render confirmation page showing expense details — logged-in only
- `POST /expenses/<int:id>/delete` — verify ownership, delete the row, redirect to profile — logged-in only

## Database changes
No new tables or columns. One new DB helper added to `database/db.py`:

- `delete_expense(expense_id)` — deletes the expense row with the given id from the `expenses` table

## Templates
- **Create:** `templates/delete_expense.html` — confirmation page showing expense details (amount, category, date, description) with a "Yes, delete" submit button and a "Cancel" link back to the profile
- **Modify:** none

## Files to change
- `app.py` — replace the `delete_expense` stub with GET+POST implementation; add auth guard and ownership check; import new `delete_expense` DB helper from `database.db`
- `database/db.py` — add `delete_expense(expense_id)` helper function

## Files to create
- `templates/delete_expense.html` — confirmation page extending `base.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — `?` placeholders, never f-strings in SQL
- Auth guard: redirect unauthenticated users to `/login`
- Ownership check: fetch the expense first with `get_expense_by_id()`; call `abort(404)` if not found; call `abort(403)` if `expense["user_id"] != session["user_id"]`
- `user_id` for the ownership check must come from `session["user_id"]` — never trust a URL or form field for this
- The confirmation page must use a `<form method="POST">` — never delete on GET
- On successful POST: flash a success message and redirect to `url_for("profile")`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Import `delete_expense` from `database.db` in `app.py` (alongside the existing `get_expense_by_id` import)

## Definition of done
- [ ] `GET /expenses/<id>/delete` renders a confirmation page with the expense's amount, category, and date visible
- [ ] `GET /expenses/<id>/delete` redirects to `/login` when no session exists
- [ ] `GET /expenses/<id>/delete` returns 404 when the expense ID does not exist
- [ ] `GET /expenses/<id>/delete` returns 403 when the expense belongs to a different user
- [ ] Submitting the confirmation form (POST) removes the expense row from the database
- [ ] After successful deletion the user is redirected to `/profile`
- [ ] A success flash message appears on the profile page after deletion
- [ ] The deleted expense no longer appears in the profile page transaction list
- [ ] The "Cancel" link on the confirmation page returns the user to `/profile` without deleting anything
- [ ] `POST /expenses/<id>/delete` with a valid session but wrong owner returns 403 (ownership enforced on POST too)
