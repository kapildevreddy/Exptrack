import os
import math
import sqlite3
import calendar
from datetime import date as date_cls, datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort, session
from werkzeug.security import check_password_hash
from database.db import (
    get_db, init_db, seed_db, create_user,
    get_user_by_email, add_expense as db_add_expense,
    get_expense_by_id, update_expense, delete_expense,
)
from database.queries import get_user_by_id, get_summary_stats, get_recent_transactions, get_category_breakdown, get_monthly_trend

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name             = request.form.get("name", "").strip()
        email            = request.form.get("email", "").strip()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "error")
            return render_template("register.html", name=name, email=email)

        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "error")
            return render_template("register.html", name=name, email=email)
        except Exception:
            abort(500)

        flash("Account created! Please sign in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html", email=email)

        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


def _preset_date_ranges(today):
    first_this = today.replace(day=1)
    last_this = today.replace(day=calendar.monthrange(today.year, today.month)[1])

    lm_year = today.year if today.month > 1 else today.year - 1
    lm_month = today.month - 1 if today.month > 1 else 12
    first_last = date_cls(lm_year, lm_month, 1)
    last_last = date_cls(lm_year, lm_month, calendar.monthrange(lm_year, lm_month)[1])

    m3_ago = today.month - 3
    y3_ago = today.year
    if m3_ago <= 0:
        m3_ago += 12
        y3_ago -= 1
    first_3m = date_cls(y3_ago, m3_ago, 1)

    return first_this, last_this, first_last, last_last, first_3m


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    today = date_cls.today()
    first_this, last_this, first_last, last_last, first_3m = _preset_date_ranges(today)

    preset_urls = {
        "this_month":    url_for("profile", **{"from": first_this.isoformat(), "to": last_this.isoformat()}),
        "last_month":    url_for("profile", **{"from": first_last.isoformat(), "to": last_last.isoformat()}),
        "last_3_months": url_for("profile", **{"from": first_3m.isoformat(),   "to": last_last.isoformat()}),
        "all_time":      url_for("profile", **{"from": "", "to": ""}),
    }

    raw_from = request.args.get("from", "")
    raw_to = request.args.get("to", "")

    if "from" not in request.args:
        from_date = first_this.isoformat()
        to_date = last_this.isoformat()
        active_preset = "this_month"
    elif raw_from == "" and raw_to == "":
        from_date = None
        to_date = None
        active_preset = "all_time"
    else:
        try:
            parsed_from = datetime.strptime(raw_from, "%Y-%m-%d").date()
            parsed_to = datetime.strptime(raw_to, "%Y-%m-%d").date()
            if parsed_from > parsed_to:
                raise ValueError("from must not be after to")
            from_date = raw_from
            to_date = raw_to
            if parsed_from == first_this and parsed_to == last_this:
                active_preset = "this_month"
            elif parsed_from == first_last and parsed_to == last_last:
                active_preset = "last_month"
            elif parsed_from == first_3m and parsed_to == last_last:
                active_preset = "last_3_months"
            else:
                active_preset = "custom"
        except ValueError:
            from_date = first_this.isoformat()
            to_date = last_this.isoformat()
            active_preset = "this_month"

    user = get_user_by_id(session["user_id"])
    if user is None:
        abort(404)
    user["initials"] = "".join(w[0] for w in user["name"].split()[:2]).upper()

    stats        = get_summary_stats(session["user_id"], from_date=from_date, to_date=to_date)
    transactions = get_recent_transactions(session["user_id"], from_date=from_date, to_date=to_date)
    categories   = get_category_breakdown(session["user_id"], from_date=from_date, to_date=to_date)

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        from_date=from_date or "",
        to_date=to_date or "",
        active_preset=active_preset,
        preset_urls=preset_urls,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    today = date_cls.today()
    first_this, last_this, first_last, last_last, first_3m = _preset_date_ranges(today)

    preset_urls = {
        "this_month":  url_for("analytics", **{"from": first_this.isoformat(), "to": last_this.isoformat()}),
        "last_month":  url_for("analytics", **{"from": first_last.isoformat(), "to": last_last.isoformat()}),
        "all_time":    url_for("analytics", **{"from": "", "to": ""}),
    }

    raw_from = request.args.get("from", "")
    raw_to   = request.args.get("to", "")

    if "from" not in request.args:
        from_date    = first_this.isoformat()
        to_date      = last_this.isoformat()
        active_preset = "this_month"
    elif raw_from == "" and raw_to == "":
        from_date    = None
        to_date      = None
        active_preset = "all_time"
    else:
        try:
            parsed_from = datetime.strptime(raw_from, "%Y-%m-%d").date()
            parsed_to   = datetime.strptime(raw_to,   "%Y-%m-%d").date()
            if parsed_from > parsed_to:
                raise ValueError("from must not be after to")
            from_date = raw_from
            to_date   = raw_to
            if parsed_from == first_this and parsed_to == last_this:
                active_preset = "this_month"
            elif parsed_from == first_last and parsed_to == last_last:
                active_preset = "last_month"
            else:
                active_preset = "custom"
        except ValueError:
            from_date    = first_this.isoformat()
            to_date      = last_this.isoformat()
            active_preset = "this_month"

    stats         = get_summary_stats(session["user_id"], from_date=from_date, to_date=to_date)
    categories    = get_category_breakdown(session["user_id"], from_date=from_date, to_date=to_date)
    monthly_trend = get_monthly_trend(session["user_id"], from_date=from_date, to_date=to_date)

    return render_template(
        "analytics.html",
        stats=stats,
        categories=categories,
        monthly_trend=monthly_trend,
        from_date=from_date or "",
        to_date=to_date or "",
        active_preset=active_preset,
        preset_urls=preset_urls,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":
        amount_raw   = request.form.get("amount", "").strip()
        category     = request.form.get("category", "").strip()
        expense_date = request.form.get("date", "").strip()
        description  = request.form.get("description", "").strip()

        errors = []

        try:
            amount = float(amount_raw)
            if not math.isfinite(amount) or amount <= 0:
                raise ValueError
        except ValueError:
            errors.append("Amount must be a positive number.")

        if category not in CATEGORIES:
            errors.append("Please select a valid category.")

        try:
            datetime.strptime(expense_date, "%Y-%m-%d")
        except ValueError:
            errors.append("Date must be a valid YYYY-MM-DD date.")

        if len(description) > 300:
            errors.append("Description must be 300 characters or fewer.")

        if errors:
            for msg in errors:
                flash(msg, "error")
            return render_template("add_expense.html", categories=CATEGORIES,
                                   amount=amount_raw, category=category,
                                   date=expense_date, description=description)

        db_add_expense(session["user_id"], amount, category, expense_date, description)
        flash("Expense added successfully.", "success")
        return redirect(url_for("profile"))

    return render_template("add_expense.html", categories=CATEGORIES,
                           amount="", category="", date=date_cls.today().isoformat(), description="")


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    expense = get_expense_by_id(id)
    if expense is None:
        abort(404)
    if expense["user_id"] != session["user_id"]:
        abort(403)

    if request.method == "POST":
        amount_raw   = request.form.get("amount", "").strip()
        category     = request.form.get("category", "").strip()
        expense_date = request.form.get("date", "").strip()
        description  = request.form.get("description", "").strip()

        errors = []

        try:
            amount = float(amount_raw)
            if not math.isfinite(amount) or amount <= 0:
                raise ValueError
        except ValueError:
            errors.append("Amount must be a positive number.")

        if category not in CATEGORIES:
            errors.append("Please select a valid category.")

        try:
            datetime.strptime(expense_date, "%Y-%m-%d")
        except ValueError:
            errors.append("Date must be a valid YYYY-MM-DD date.")

        if len(description) > 300:
            errors.append("Description must be 300 characters or fewer.")

        if errors:
            for msg in errors:
                flash(msg, "error")
            return render_template(
                "edit_expense.html", categories=CATEGORIES,
                expense=expense,
                amount=amount_raw, category=category,
                date=expense_date, description=description,
            )

        update_expense(id, amount, category, expense_date, description)
        flash("Expense updated successfully.", "success")
        return redirect(url_for("profile"))

    return render_template(
        "edit_expense.html", categories=CATEGORIES,
        expense=expense,
        amount=expense["amount"], category=expense["category"],
        date=expense["date"], description=expense["description"] or "",
    )


@app.route("/expenses/<int:id>/delete", methods=["GET", "POST"])
def delete_expense_view(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    expense = get_expense_by_id(id)
    if expense is None:
        abort(404)
    if expense["user_id"] != session["user_id"]:
        abort(403)

    if request.method == "POST":
        delete_expense(id)
        flash("Expense deleted.", "success")
        return redirect(url_for("profile"))

    return render_template("delete_expense.html", expense=expense)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", port=5001)
