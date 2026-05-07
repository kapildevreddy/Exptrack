# Spec: Login and Logout

## Overview

Implement credential-based login and session-managed logout so registered users can authenticate into Spendly. This step adds a `POST /login` handler to the existing stub route, verifies the submitted password against the stored hash, and stores the authenticated user's ID in Flask's server-side session. The `GET /logout` stub is replaced with a real handler that clears the session and redirects to the login page. After this step users can sign in, stay signed in across requests, and explicitly sign out. No protected routes are enforced yet — that comes in a later step.

---

## Depends on

- Step 1 — Database Setup (`get_db()`, `users` table must exist)
- Step 2 — Registration (`create_user()` must exist; `app.secret_key` must be set)

---

## Routes

- `GET /login` — already implemented, renders `login.html` — **public**
- `POST /login` — new; validates credentials, sets session, redirects to `/profile` — **public**
- `GET /logout` — currently a stub; clear session and redirect to `/login` — **logged-in**

---

## Database changes

No new tables or columns.

New helper function in `database/db.py`:
- `get_user_by_email(email)` — queries the `users` table by email and returns the matching row as a `sqlite3.Row`, or `None` if not found.

---

## Templates

**Modify:**
- `templates/login.html` — add a POST form with `email` and `password` fields; render flashed error/success messages
- `templates/base.html` — add session-aware navigation: show a "Logout" link when `session.user_id` is set, otherwise show "Login" and "Register" links

---

## Files to change

- `app.py` — add `POST /login` handler; implement `GET /logout`; import `session` and `check_password_hash`
- `database/db.py` — add `get_user_by_email(email)` helper
- `templates/login.html` — add form markup and flash message display
- `templates/base.html` — add session-aware nav links

---

## Files to create

None.

---

## New dependencies

No new dependencies. `werkzeug.security.check_password_hash` is already available via the installed `werkzeug` package.

---

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — never f-strings in SQL
- Password verification with `werkzeug.security.check_password_hash` — never compare plain text
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Session key must be `user_id` — store the integer primary key from `users.id`
- `GET /login` route must accept both GET and POST methods — convert the existing stub to `methods=["GET", "POST"]`
- On invalid credentials (wrong email or wrong password): flash a single generic error ("Invalid email or password.") — do not distinguish which field was wrong
- On success: `flash()` a welcome message, set `session["user_id"]`, then `redirect(url_for("profile"))`
- `GET /logout`: call `session.clear()`, flash a sign-out confirmation, then `redirect(url_for("login"))`
- DB logic (`get_user_by_email`) belongs in `database/db.py`, not in the route
- Route must call `abort(500)` if an unexpected DB error occurs — never return a raw error string
- `app.secret_key` is already set — do not change it

---

## Definition of done

- [ ] Visiting `/login` renders a form with email and password fields
- [ ] Submitting valid credentials sets `session["user_id"]` and redirects to `/profile`
- [ ] Submitting an unknown email shows "Invalid email or password." and does not set a session
- [ ] Submitting a correct email with a wrong password shows "Invalid email or password." and does not set a session
- [ ] After login, `session["user_id"]` equals the matching user's `id` in the database
- [ ] Visiting `/logout` clears the session and redirects to `/login`
- [ ] After logout, `session["user_id"]` is no longer present
- [ ] `base.html` nav shows "Logout" when a session is active, and "Login"/"Register" when it is not
- [ ] The email field is re-populated after a failed login attempt; the password field is not
- [ ] App starts without errors after this change
