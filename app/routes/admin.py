from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from app import db
from app.models import User, Company, Packet, PacketReview, Submission
from app.accounting import trial_balance, profit_and_loss, balance_sheet, day_book

admin_bp = Blueprint("admin", __name__)


def require_admin():
    if not current_user.is_admin():
        abort(403)


@admin_bp.route("/dashboard")
@login_required
def dashboard():
    require_admin()
    learners = User.query.filter_by(role="learner").all()
    pending_packets = (
        Packet.query.join(Submission, Packet.id == Submission.packet_id, isouter=True)
        .filter(Submission.id.isnot(None))
        .all()
    )
    # packets with a submission but no completed review
    needs_review = [p for p in pending_packets if not p.review or p.review.status == "pending"]
    return render_template("admin/dashboard.html", learners=learners, needs_review=needs_review)


@admin_bp.route("/learners/new", methods=["GET", "POST"])
@login_required
def new_learner():
    require_admin()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        company_name = request.form.get("company_name", "").strip() or f"{name}'s Company"

        if not name or not password:
            flash("Name and password are required.", "error")
            return redirect(url_for("admin.new_learner"))

        if User.query.filter_by(name=name).first():
            flash(f"A user named '{name}' already exists.", "error")
            return redirect(url_for("admin.new_learner"))

        user = User(name=name, role="learner", password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.flush()  # get user.id before commit

        company = Company(user_id=user.id, name=company_name)
        db.session.add(company)
        db.session.commit()

        flash(f"Learner '{name}' created with company '{company_name}'.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/new_learner.html")


@admin_bp.route("/learners/<int:user_id>")
@login_required
def view_learner(user_id):
    require_admin()
    learner = User.query.get_or_404(user_id)
    if learner.role != "learner":
        abort(404)
    packets = Packet.query.filter_by(user_id=user_id).order_by(Packet.due_date.desc()).all()

    as_of = request.args.get("as_of")
    as_of_date = None
    if as_of:
        try:
            as_of_date = datetime.strptime(as_of, "%Y-%m-%d").date()
        except ValueError:
            pass

    tb = trial_balance(learner.company, as_of=as_of_date) if learner.company else None
    pnl = profit_and_loss(learner.company, as_of=as_of_date) if learner.company else None
    bs = balance_sheet(learner.company, as_of=as_of_date) if learner.company else None

    return render_template(
        "admin/view_learner.html",
        learner=learner,
        packets=packets,
        tb=tb,
        pnl=pnl,
        bs=bs,
        as_of=as_of_date,
    )


@admin_bp.route("/learners/<int:user_id>/packets/new", methods=["GET", "POST"])
@login_required
def new_packet(user_id):
    require_admin()
    learner = User.query.get_or_404(user_id)
    if learner.role != "learner":
        abort(404)

    if request.method == "POST":
        month_label = request.form.get("month_label", "").strip()
        title = request.form.get("title", "").strip()
        instructions_html = request.form.get("instructions_html", "")
        due_date_str = request.form.get("due_date")
        expected_answer_html = request.form.get("expected_answer_html", "")

        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            flash("Valid due date is required.", "error")
            return redirect(url_for("admin.new_packet", user_id=user_id))

        if not month_label or not title:
            flash("Month label and title are required.", "error")
            return redirect(url_for("admin.new_packet", user_id=user_id))

        packet = Packet(
            user_id=user_id,
            month_label=month_label,
            title=title,
            instructions_html=instructions_html,
            due_date=due_date,
            expected_answer_html=expected_answer_html,
            show_answer_to_learner=False,
        )
        db.session.add(packet)
        db.session.commit()
        flash("Packet created.", "success")
        return redirect(url_for("admin.view_learner", user_id=user_id))

    return render_template("admin/new_packet.html", learner=learner)


@admin_bp.route("/packets/<int:packet_id>/review", methods=["GET", "POST"])
@login_required
def review_packet(packet_id):
    require_admin()
    packet = Packet.query.get_or_404(packet_id)
    learner = User.query.get_or_404(packet.user_id)

    if request.method == "POST":
        feedback_text = request.form.get("feedback_text", "")
        status = request.form.get("status", "reviewed")
        show_answer = request.form.get("show_answer_to_learner") == "on"

        if packet.review:
            packet.review.feedback_text = feedback_text
            packet.review.status = status
            packet.review.reviewed_at = datetime.utcnow()
        else:
            review = PacketReview(
                packet_id=packet.id,
                status=status,
                feedback_text=feedback_text,
                reviewed_at=datetime.utcnow(),
            )
            db.session.add(review)

        packet.show_answer_to_learner = show_answer
        db.session.commit()
        flash("Review saved.", "success")
        return redirect(url_for("admin.view_learner", user_id=learner.id))

    tb = trial_balance(learner.company, as_of=packet.due_date) if learner.company else None
    pnl = profit_and_loss(learner.company, as_of=packet.due_date) if learner.company else None
    bs = balance_sheet(learner.company, as_of=packet.due_date) if learner.company else None

    return render_template(
        "admin/review_packet.html", packet=packet, learner=learner, tb=tb, pnl=pnl, bs=bs
    )
