from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard" if current_user.is_admin() else "learner.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(name=name).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("admin.dashboard" if user.is_admin() else "learner.dashboard"))
        flash("Invalid name or password.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/")
def index():
    return redirect(url_for("auth.login"))
