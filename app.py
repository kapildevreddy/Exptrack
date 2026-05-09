import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, abort, session
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email

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


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": "January 2026",
        "initials": "DU",
    }

    stats = {
        "total_spent": 356.24,
        "transaction_count": 8,
        "top_category": "Bills",
    }

    transactions = [
        {"date": "2026-05-15", "description": "Restaurant lunch",  "category": "Food",          "amount": 18.75},
        {"date": "2026-05-10", "description": "Clothes",           "category": "Shopping",      "amount": 89.99},
        {"date": "2026-05-08", "description": "Movie tickets",     "category": "Entertainment", "amount": 25.00},
        {"date": "2026-05-05", "description": "Pharmacy",          "category": "Health",        "amount": 35.00},
        {"date": "2026-05-03", "description": "Electricity bill",  "category": "Bills",         "amount": 120.00},
        {"date": "2026-05-02", "description": "Bus pass top-up",   "category": "Transport",     "amount": 15.00},
        {"date": "2026-05-01", "description": "Groceries",         "category": "Food",          "amount": 42.50},
    ]

    categories = [
        {"name": "Bills",         "amount": 120.00, "percent": 34},
        {"name": "Shopping",      "amount": 89.99,  "percent": 25},
        {"name": "Food",          "amount": 61.25,  "percent": 17},
        {"name": "Health",        "amount": 35.00,  "percent": 10},
        {"name": "Entertainment", "amount": 25.00,  "percent": 7},
        {"name": "Transport",     "amount": 15.00,  "percent": 4},
        {"name": "Other",         "amount": 10.00,  "percent": 3},
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
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
