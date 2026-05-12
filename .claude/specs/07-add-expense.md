# Spec: Add Expense

## Overview
This feature replaces the stub `GET /expenses/add` route with a fully functional expense creation form. Logged-in users can submit a new expense with an amount, category, date, and optional description. On success the expense is saved to the `expenses` table and the user is redirected to their profile page with a confirmation flash message. This is the first write path for the expenses table and unlocks real data for the profile stats and transaction list.

## Depends on
- Step 01 — database setup (`expenses` table exists)
- Step 03 — login/logout (session management)
- Step 04/05 — profile page (redirect target after save)

## Routes
- `GET  /expenses/add` — render blank add-expense form — logged-in only
- `POST /expenses/add` — validate and save new expense, redirect to profile — logged-in only

## Database changes
No new tables or columns. The `expenses` table is already created in `init_db()` with:
- `id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`

A new DB helper `add_expense(user_id, amount, category, date, description)` must be added to `database/db.py`.

## Templates
- **Create:** `templates/add_expense.html` — form with fields: amount, category (dropdown), date, description (optional)
- **Modify:** none

## Files to change
- `app.py` — replace the `add_expense` stub with GET+POST implementation; add auth guard
- `database/db.py` — add `add_expense()` helper function

## Files to create
- `templates/add_expense.html` — expense creation form extending `base.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — `?` placeholders, never f-strings in SQL
- Auth guard: redirect unauthenticated users to `/login`
- `user_id` must come from `session["user_id"]` — never trust a form field for this
- Amount validation: must be a positive number; reject zero or negative values
- Date validation: must be a valid `YYYY-MM-DD` string; reject malformed input
- Category must be one of the fixed allowed values: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- On validation failure: re-render the form with the user's input pre-filled and a flash error
- On success: flash a success message and redirect to `url_for("profile")`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Import `add_expense` from `database.db` in `app.py`

## Definition of done
- [ ] `GET /expenses/add` renders the form for a logged-in user
- [ ] `GET /expenses/add` redirects to `/login` when no session exists
- [ ] Submitting valid data saves a row to the `expenses` table and redirects to `/profile`
- [ ] A success flash message appears on the profile page after saving
- [ ] Submitting a negative or zero amount re-renders the form with an error flash
- [ ] Submitting an invalid date re-renders the form with an error flash
- [ ] Submitting an invalid category re-renders the form with an error flash
- [ ] All previously entered form values are preserved when the form is re-rendered after a validation error
- [ ] The new expense appears in the profile page transaction list immediately after submission
