# Spec: Update Analytics

## Overview
Step 10 replaces the "Coming Soon" placeholder on the `/analytics` page with a
real analytics dashboard. The page reuses the date-filtering pattern introduced in
Step 6 and the query helpers already in `database/queries.py`. It adds one new
query (`get_monthly_trend`) to power a month-by-month spending chart. The result
is a focused insights view separate from the profile page: summary stats, a
category-breakdown bar chart, and a monthly trend chart — all driven by the active
date filter. Charts are rendered with vanilla JS using the Canvas API; no third-party
charting libraries are added.

## Depends on
- Step 01 — database setup (`expenses` table with `date` and `category` columns)
- Step 03 — login/logout (session management)
- Step 05 — backend routes / profile page (`get_summary_stats`, `get_recent_transactions`, `get_category_breakdown` already exist in `database/queries.py`)
- Step 06 — date filter (query helpers already accept `from_date`/`to_date`; preset URL-building pattern established)

## Routes
- `GET /analytics` — replace stub; render full analytics dashboard — logged-in only
  - Accepts optional query parameters: `from` and `to` (ISO date strings, `YYYY-MM-DD`)
  - Default range: current calendar month (same defaulting logic as `/profile`)
  - Passes `stats`, `categories`, `monthly_trend`, `from_date`, `to_date`, `active_preset`, and `preset_urls` to the template

## Database changes
No new tables or columns. One new query helper added to `database/queries.py`:

- `get_monthly_trend(user_id, from_date=None, to_date=None)` — returns a list of
  `{"month": "YYYY-MM", "total": float}` dicts ordered by month ascending, filtered
  by the same `BETWEEN` clause used by the other helpers.
  SQL: `SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total FROM expenses WHERE user_id = ? [AND date BETWEEN ? AND ?] GROUP BY month ORDER BY month ASC`

## Templates
- **Replace:** `templates/analytics.html`
  - Remove the "Coming Soon" card entirely
  - Add a date-filter bar identical in structure to the one on `profile.html`
    (same preset buttons: "This Month", "Last Month", "All Time"; same custom date
    range inputs; same active-preset highlighting)
  - Summary stats strip (total spent, transaction count, top category) — same layout as profile
  - Category breakdown section: horizontal bar chart rendered on a `<canvas>` element
    via a small inline `<script>` block (data passed as a Jinja JSON variable)
  - Monthly trend section: vertical bar chart rendered on a second `<canvas>` element
    (data passed as a Jinja JSON variable)
  - Empty-state message ("No expenses found for this period.") shown when both datasets are empty

## Files to change
- `app.py` — replace the `analytics()` stub with a full implementation:
  - Add auth guard (redirect to `/login` if no session)
  - Parse and validate `from`/`to` query params using the same logic as `profile()`
  - Build `preset_urls` dict using `url_for("analytics", ...)`
  - Call `get_summary_stats`, `get_category_breakdown`, and `get_monthly_trend`
  - Import `get_monthly_trend` from `database.queries`
  - Render `analytics.html` with all required template variables
- `database/queries.py` — add `get_monthly_trend(user_id, from_date=None, to_date=None)`
- `templates/analytics.html` — full replacement (see Templates section)

## Files to create
- `static/css/analytics.css` — page-specific styles for the analytics layout, chart containers, and canvas elements; no inline `<style>` tags

## New dependencies
No new dependencies. Canvas API is built into all modern browsers.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()`
- Parameterised queries only — `?` placeholders, never f-strings in SQL
- Auth guard: redirect unauthenticated users to `/login`
- Use CSS variables — never hardcode hex values in CSS or JS
- All templates extend `base.html`
- Chart data must be passed to JS via `{{ categories | tojson }}` and `{{ monthly_trend | tojson }}` — never build JSON strings manually in Jinja
- Vanilla JS only — no Chart.js, no D3, no external libraries
- Canvas charts must include a text fallback inside the `<canvas>` tag for accessibility
- Date filtering logic in `app.py` must be identical to the `profile()` view — extract or duplicate the `_preset_date_ranges()` helper
- `get_monthly_trend` must reuse the `_date_filter()` helper already in `queries.py`

## Definition of done
- [ ] `GET /analytics` redirects to `/login` when no session exists
- [ ] `GET /analytics` returns 200 with the analytics page for a logged-in user
- [ ] The "Coming Soon" card is no longer visible on the analytics page
- [ ] Summary stats (total spent, transaction count, top category) are visible and match the active date range
- [ ] The category breakdown chart renders and displays at least one bar when expenses exist in the selected range
- [ ] The monthly trend chart renders and displays at least one bar when expenses exist in the selected range
- [ ] "This Month", "Last Month", and "All Time" preset buttons are present and update the displayed data when clicked
- [ ] The active preset button is visually distinguished from inactive ones
- [ ] Custom from/to date inputs apply correctly via the Apply button
- [ ] When no expenses exist in the selected range, an empty-state message is shown and no broken charts appear
- [ ] `get_monthly_trend` returns rows grouped and ordered by month with correct totals
- [ ] All chart data reflects the active date filter (not lifetime data)
- [ ] Page links in `base.html` navigation to `/analytics` use `url_for("analytics")`
