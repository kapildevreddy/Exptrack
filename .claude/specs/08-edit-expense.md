# Spec: Edit Expense

## Overview
This feature replaces the stub `GET /expenses/<id>/edit` route with a fully functional edit form. Logged-in users can update the amount, category, date, and description of any expense they own. On GET the form is pre-filled with the existing values; on POST, validated changes are persisted and the user is redirected to their profile with a confirmation flash. Ownership is enforced — users cannot edit another user's expense (404 if not found, 403 if not theirs).

## Depends on
- Step 01 — database setup (`expenses` table exists)
- Step 03 — login/logout (session management)
- Step 04/05 — profile page (redirect target after save)
- Step 07 — add expense (introduces `CATEGORIES` list and validation patterns to reuse)

## Routes
- `GET  /expenses/<int:id>/edit` — render edit form pre-filled with the expense — logged-in only
- `POST /expenses/<int:id>/edit` — validate and save changes, redirect to profile — logged-in only

## Database changes
No new tables or columns. Two new DB helpers added to `database/db.py`:

- `get_expense_by_id(expense_id)` — returns a single expense row as a dict, or `None` if not found
- `update_expense(expense_id, amount, category, date, description)` — updates all editable fields for the given expense

## Templates
- **Create:** `templates/edit_expense.html` — pre-filled form with fields: amount, category (dropdown), date, description (optional)
- **Modify:** none

## Files to change
- `app.py` — replace the `edit_expense` stub with GET+POST implementation; add auth guard and ownership check; import new DB helpers
- `database/db.py` — add `get_expense_by_id()` and `update_expense()` helper functions

## Files to create
- `templates/edit_expense.html` — expense edit form extending `base.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — `?` placeholders, never f-strings in SQL
- Auth guard: redirect unauthenticated users to `/login`
- Ownership check: after fetching the expense, verify `expense["user_id"] == session["user_id"]`; call `abort(403)` if it does not match; call `abort(404)` if the expense does not exist
- `user_id` for the ownership check must come from `session["user_id"]` — never trust a URL or form field for this
- Amount validation: must be a positive number; reject zero or negative values
- Date validation: must be a valid `YYYY-MM-DD` string; reject malformed input
- Category must be one of the fixed allowed values defined in `CATEGORIES` in `app.py`
- On validation failure: re-render the form with the user's submitted input pre-filled and a flash error
- On success: flash a success message and redirect to `url_for("profile")`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Import `get_expense_by_id` and `update_expense` from `database.db` in `app.py`

## Definition of done
- [ ] `GET /expenses/<id>/edit` renders a pre-filled form for the expense owner
- [ ] `GET /expenses/<id>/edit` redirects to `/login` when no session exists
- [ ] `GET /expenses/<id>/edit` returns 404 when the expense ID does not exist
- [ ] `GET /expenses/<id>/edit` returns 403 when the expense belongs to a different user
- [ ] Submitting valid data updates the row in the `expenses` table and redirects to `/profile`
- [ ] A success flash message appears on the profile page after saving
- [ ] Submitting a negative or zero amount re-renders the form with an error flash and preserves other field values
- [ ] Submitting an invalid date re-renders the form with an error flash and preserves other field values
- [ ] Submitting an invalid category re-renders the form with an error flash and preserves other field values
- [ ] The updated expense is reflected immediately in the profile page transaction list
