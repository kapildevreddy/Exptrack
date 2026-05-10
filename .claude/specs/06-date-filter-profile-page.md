# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter to the profile page so users can slice their
expense data by time period. Currently the profile page shows lifetime totals and
all transactions. This step introduces a filter bar with preset shortcuts
("This Month", "Last Month", "All Time") and optional custom from/to date inputs.
The active filter is passed as query-string parameters (`?from=YYYY-MM-DD&to=YYYY-MM-DD`)
so filtered views are bookmarkable and shareable. Summary stats, transaction list,
and category breakdown all respect the active filter; the user-info card does not.

## Depends on
- Step 1: Database setup (`expenses` table exists with a `date` column)
- Step 4: Profile page design (template structure in place)
- Step 5: Backend connection (query helpers in `database/queries.py` exist and return live data)

## Routes
`GET /profile` — enhanced, not replaced — logged-in only
- Accepts optional query parameters: `from` and `to` (ISO date strings, `YYYY-MM-DD`)
- If both are absent, defaults to the current calendar month
- Invalid / unparseable date values are silently ignored and replaced with the default range

## Database changes
No new tables or columns. The `expenses.date` column (`TEXT NOT NULL`, stored as
`YYYY-MM-DD`) already supports `BETWEEN` filtering.

## Templates
- **Modify**: `templates/profile.html`
  - Add a filter bar above the stats section with:
    - Three preset buttons: "This Month", "Last Month", "All Time"
    - A custom date range form (two `<input type="date">` fields + Apply button)
  - Visually mark the active preset button (add/remove a CSS class)
  - Pass `from_date` and `to_date` back to the template so the filter bar can
    pre-populate the custom inputs and highlight the matching preset

## Files to change
- `app.py` — update the `profile()` view to:
  - Read `from_date` and `to_date` from `request.args`
  - Validate and parse them (use `datetime.strptime`; fall back to current month on error)
  - Pass the parsed dates to all three query helpers
  - Pass `from_date`, `to_date`, and `active_preset` strings back to the template
- `database/queries.py` — add optional `from_date` / `to_date` parameters to:
  - `get_summary_stats(user_id, from_date=None, to_date=None)`
  - `get_recent_transactions(user_id, limit=10, from_date=None, to_date=None)`
  - `get_category_breakdown(user_id, from_date=None, to_date=None)`
  - When both are provided, append `AND date BETWEEN ? AND ?` to the WHERE clause
  - When absent, no date filter is applied (All Time behaviour)
- `templates/profile.html` — add filter bar markup (see Templates section)

## Files to create
- `static/css/filter.css` — styles for the filter bar, preset buttons, and date inputs

## New dependencies
No new dependencies. `datetime` is already in the Python standard library.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline `<style>` tags — all filter styles go in `static/css/filter.css`
- Date validation in the route must use `try/except` around `datetime.strptime`; do not crash on bad input
- Default date range (when no params are supplied) must be the first and last day of the current calendar month
- `active_preset` must be one of `"this_month"`, `"last_month"`, `"all_time"`, or `"custom"`; the template uses it to apply an `active` CSS class to the matching preset button
- The custom date range form must submit via `GET` to `/profile` — no JS required; plain HTML form with `method="get"`
- Preset buttons must be anchor tags (`<a href="...">`) that construct the correct `?from=&to=` query string — no JS required
- The filter bar must be fully functional without JavaScript; JS may be used for progressive enhancement only

## Definition of done
- [ ] Visiting `/profile` with no query params shows the current calendar month's data by default, with "This Month" preset highlighted
- [ ] Clicking "Last Month" loads the previous calendar month's expenses with correct stats
- [ ] Clicking "All Time" shows lifetime totals matching the pre-filter totals from Step 5
- [ ] Entering a custom `from` and `to` date and clicking Apply filters all three sections to that range
- [ ] Summary stats (total spent, transaction count, top category) update correctly for every filter selection
- [ ] The transaction list shows only expenses within the active date range, ordered newest-first
- [ ] The category breakdown shows only categories that have expenses in the active date range
- [ ] A date range with no matching expenses shows ₹0.00 total, 0 transactions, and an empty category breakdown — no errors
- [ ] The filter bar renders and functions on mobile-width viewports (no horizontal overflow)
- [ ] Invalid query-string dates (e.g. `?from=notadate`) do not crash the app — the page loads with the default month range
