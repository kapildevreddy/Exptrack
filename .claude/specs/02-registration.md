# Spec: Registration

## Overview

Implement user registration so new visitors can create a Spendly account. This step wires up the `POST /register` route (the `GET` stub already exists), validates form input, hashes the password, inserts the new user into the database, and redirects to the login page on success. It also adds `app.secret_key` (required for Flask flash messages) and updates `register.html` with the real form. No session is created here — authentication is handled in Step 3.

---

## Depends on

- Step 1 — Database Setup (`get_db()`, `init_db()`, `users` table must exist)

---

## Routes

- `GET /register` — already implemented, renders `register.html` — **public**
- `POST /register` — new; validates form, creates user, redirects to `/login` — **public**

---

## Database changes

No new tables or columns. The `users` table from Step 1 is sufficient.

New helper function in `database/db.py`:
- `create_user(name, email, password)` — hashes the password and inserts a row into `users`; returns the new `user_id` on success, raises `sqlite3.IntegrityError` if the email is already taken.

---

## Templates

**Modify:**
- `templates/register.html` — add a POST form with fields: `name`, `email`, `password`, `confirm_password`; render flashed error/success messages

---

## Files to change

- `app.py` — add `POST /register` route; import `flash`, `redirect`, `request`, `url_for`; set `app.secret_key`
- `database/db.py` — add `create_user()` helper; import `generate_password_hash` at module level (already used in `seed_db`)
- `templates/register.html` — add form markup and flash message display
- `static/css/style.css` — add form field and flash message styles (reuse CSS variables only)

---

## Files to create

None.

---

## New dependencies

No new dependencies.

---

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — never f-strings in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `app.secret_key` must be set before any `flash()` call; use a hardcoded dev string for now (e.g. `"dev-secret-change-in-prod"`)
- DB logic (`create_user`) belongs in `database/db.py`, not in the route
- Route must call `abort(500)` if an unexpected DB error occurs — never return a raw error string
- On duplicate email: catch `sqlite3.IntegrityError`, flash a user-facing error, re-render the form (do **not** redirect)
- On password mismatch: flash an error and re-render the form without hitting the DB
- On success: `flash()` a success message, then `redirect(url_for("login"))`
- Do **not** create a session or log the user in — that is Step 3

---

## Definition of done

- [ ] Visiting `/register` renders a form with name, email, password, and confirm-password fields
- [ ] Submitting the form with valid data creates a new user row in `users` with a hashed password
- [ ] After successful registration the user is redirected to `/login`
- [ ] Submitting with mismatched passwords shows an inline error and does not create a user
- [ ] Submitting with an already-registered email shows an inline error and does not create a duplicate row
- [ ] All form fields are preserved (re-populated) after a validation error except the password fields
- [ ] The `password_hash` column in the DB never contains a plain-text password
- [ ] App starts without errors after this change
