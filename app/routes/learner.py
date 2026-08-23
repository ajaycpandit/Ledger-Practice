from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app import db
from app.models import Ledger, Voucher, VoucherEntry, Packet, Submission, LEDGER_GROUPS, VOUCHER_TYPES
from app.accounting import trial_balance, profit_and_loss, balance_sheet, day_book

learner_bp = Blueprint("learner", __name__, url_prefix="/app")


def require_learner():
    if current_user.is_admin():
        abort(403)
    if current_user.company is None:
        abort(500, "No company provisioned for this learner. Contact admin.")


@learner_bp.route("/dashboard")
@login_required
def dashboard():
    require_learner()
    packets = (
        Packet.query.filter_by(user_id=current_user.id)
        .order_by(Packet.due_date.desc())
        .all()
    )
    today = date.today()
    return render_template("learner/dashboard.html", packets=packets, today=today)


@learner_bp.route("/packet/<int:packet_id>")
@login_required
def packet_detail(packet_id):
    require_learner()
    packet = Packet.query.get_or_404(packet_id)
    if packet.user_id != current_user.id:
        abort(403)
    return render_template("learner/packet_detail.html", packet=packet)


@learner_bp.route("/packet/<int:packet_id>/submit", methods=["POST"])
@login_required
def submit_packet(packet_id):
    require_learner()
    packet = Packet.query.get_or_404(packet_id)
    if packet.user_id != current_user.id:
        abort(403)

    if packet.submission:
        packet.submission.submitted_at = datetime.utcnow()
        packet.submission.note = request.form.get("note", "")
    else:
        sub = Submission(
            packet_id=packet.id,
            user_id=current_user.id,
            note=request.form.get("note", ""),
        )
        db.session.add(sub)
    db.session.commit()
    flash("Marked as submitted for review.", "success")
    return redirect(url_for("learner.packet_detail", packet_id=packet.id))


@learner_bp.route("/ledgers")
@login_required
def ledgers():
    require_learner()
    company_ledgers = sorted(current_user.company.ledgers, key=lambda l: l.name)
    return render_template("learner/ledgers.html", ledgers=company_ledgers, groups=LEDGER_GROUPS)


@learner_bp.route("/ledgers/new", methods=["POST"])
@login_required
def new_ledger():
    require_learner()
    name = request.form.get("name", "").strip()
    group = request.form.get("group", "")
    opening_balance = request.form.get("opening_balance", "0") or "0"
    gstin = request.form.get("gstin", "").strip() or None

    if not name or group not in LEDGER_GROUPS:
        flash("Ledger name and a valid group are required.", "error")
        return redirect(url_for("learner.ledgers"))

    existing = Ledger.query.filter_by(company_id=current_user.company.id, name=name).first()
    if existing:
        flash(f"A ledger named '{name}' already exists.", "error")
        return redirect(url_for("learner.ledgers"))

    ledger = Ledger(
        company_id=current_user.company.id,
        name=name,
        group=group,
        opening_balance=float(opening_balance),
        gstin=gstin,
    )
    db.session.add(ledger)
    db.session.commit()
    flash(f"Ledger '{name}' created.", "success")
    return redirect(url_for("learner.ledgers"))


@learner_bp.route("/vouchers")
@login_required
def vouchers():
    require_learner()
    all_vouchers = sorted(current_user.company.vouchers, key=lambda v: (v.date, v.id), reverse=True)
    return render_template("learner/vouchers.html", vouchers=all_vouchers)


@learner_bp.route("/vouchers/new", methods=["GET", "POST"])
@login_required
def new_voucher():
    require_learner()
    company_ledgers = sorted(current_user.company.ledgers, key=lambda l: l.name)

    if request.method == "POST":
        v_type = request.form.get("voucher_type")
        v_date_str = request.form.get("date")
        narration = request.form.get("narration", "")

        if v_type not in VOUCHER_TYPES:
            flash("Invalid voucher type.", "error")
            return redirect(url_for("learner.new_voucher"))

        try:
            v_date = datetime.strptime(v_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            flash("Invalid date.", "error")
            return redirect(url_for("learner.new_voucher"))

        debit_ledger_ids = request.form.getlist("debit_ledger_id")
        debit_amounts = request.form.getlist("debit_amount")
        credit_ledger_ids = request.form.getlist("credit_ledger_id")
        credit_amounts = request.form.getlist("credit_amount")

        entries = []
        total_debit = 0.0
        total_credit = 0.0

        for lid, amt in zip(debit_ledger_ids, debit_amounts):
            if lid and amt:
                amt_f = float(amt)
                entries.append(VoucherEntry(ledger_id=int(lid), entry_type="debit", amount=amt_f))
                total_debit += amt_f

        for lid, amt in zip(credit_ledger_ids, credit_amounts):
            if lid and amt:
                amt_f = float(amt)
                entries.append(VoucherEntry(ledger_id=int(lid), entry_type="credit", amount=amt_f))
                total_credit += amt_f

        if not entries:
            flash("Add at least one debit and one credit line.", "error")
            return redirect(url_for("learner.new_voucher"))

        if round(total_debit, 2) != round(total_credit, 2):
            flash(
                f"Voucher does not balance: Debit {total_debit:.2f} vs Credit {total_credit:.2f}. "
                "Not saved.",
                "error",
            )
            return render_template(
                "learner/voucher_form.html",
                ledgers=company_ledgers,
                voucher_types=VOUCHER_TYPES,
                form=request.form,
            )

        voucher = Voucher(
            company_id=current_user.company.id,
            voucher_type=v_type,
            date=v_date,
            narration=narration,
        )

        if v_type in ("Sales", "Purchase"):
            voucher.party_gstin = request.form.get("party_gstin") or None
            voucher.hsn_code = request.form.get("hsn_code") or None
            taxable_value = request.form.get("taxable_value")
            voucher.taxable_value = float(taxable_value) if taxable_value else None
            for field in ("cgst_rate", "sgst_rate", "igst_rate"):
                val = request.form.get(field)
                setattr(voucher, field, float(val) if val else None)

        voucher.entries = entries
        db.session.add(voucher)
        db.session.commit()
        flash("Voucher saved.", "success")
        return redirect(url_for("learner.vouchers"))

    return render_template(
        "learner/voucher_form.html", ledgers=company_ledgers, voucher_types=VOUCHER_TYPES, form={}
    )


@learner_bp.route("/reports/trial-balance")
@login_required
def report_trial_balance():
    require_learner()
    as_of = _parse_as_of()
    tb = trial_balance(current_user.company, as_of=as_of)
    return render_template("learner/report_trial_balance.html", tb=tb, as_of=as_of)


@learner_bp.route("/reports/pnl")
@login_required
def report_pnl():
    require_learner()
    as_of = _parse_as_of()
    pnl = profit_and_loss(current_user.company, as_of=as_of)
    return render_template("learner/report_pnl.html", pnl=pnl, as_of=as_of)


@learner_bp.route("/reports/balance-sheet")
@login_required
def report_balance_sheet():
    require_learner()
    as_of = _parse_as_of()
    bs = balance_sheet(current_user.company, as_of=as_of)
    return render_template("learner/report_balance_sheet.html", bs=bs, as_of=as_of)


@learner_bp.route("/reports/day-book")
@login_required
def report_day_book():
    require_learner()
    as_of = _parse_as_of()
    vouchers = day_book(current_user.company, as_of=as_of)
    return render_template("learner/report_day_book.html", vouchers=vouchers, as_of=as_of)


def _parse_as_of():
    as_of_str = request.args.get("as_of")
    if as_of_str:
        try:
            return datetime.strptime(as_of_str, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None
