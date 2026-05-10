import sqlite3
import calendar
from datetime import date as date_cls, datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort, session
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
from database.queries import get_user_by_id, get_summary_stats, get_recent_transactions, get_category_breakdown

app = Flask(__name__)
app.secret_key = "dev-secret-change-in-prod"

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


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
