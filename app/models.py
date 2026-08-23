from datetime import datetime
from flask_login import UserMixin
from app import db

# Standard Tally-style account groups, used to classify ledgers
LEDGER_GROUPS = [
    "Capital Account",
    "Sundry Debtors",
    "Sundry Creditors",
    "Bank Accounts",
    "Cash-in-Hand",
    "Sales Accounts",
    "Purchase Accounts",
    "Direct Expenses",
    "Indirect Expenses",
    "Direct Income",
    "Indirect Income",
    "Duties & Taxes",
    "Fixed Assets",
    "Loans (Liability)",
    "Current Liabilities",
    "Current Assets",
]

VOUCHER_TYPES = ["Payment", "Receipt", "Sales", "Purchase", "Journal", "Contra"]


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="learner")  # 'admin' or 'learner'
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship("Company", backref="user", uselist=False)

    def is_admin(self):
        return self.role == "admin"


class Company(db.Model):
    """Each learner gets exactly one continuous company (their 'books')."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ledgers = db.relationship("Ledger", backref="company", cascade="all, delete-orphan")
    vouchers = db.relationship("Voucher", backref="company", cascade="all, delete-orphan")


class Ledger(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    group = db.Column(db.String(50), nullable=False)
    opening_balance = db.Column(db.Float, default=0.0)
    # Positive opening_balance = Debit, negative = Credit, by convention here
    gstin = db.Column(db.String(20), nullable=True)  # for party ledgers, optional
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    entries = db.relationship("VoucherEntry", backref="ledger")

    __table_args__ = (db.UniqueConstraint("company_id", "name", name="uq_ledger_company_name"),)


class Voucher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    voucher_type = db.Column(db.String(20), nullable=False)  # Payment/Receipt/Sales/Purchase/Journal/Contra
    date = db.Column(db.Date, nullable=False)
    narration = db.Column(db.String(500))

    # Optional GST fields, used on Sales/Purchase vouchers
    party_gstin = db.Column(db.String(20), nullable=True)
    hsn_code = db.Column(db.String(20), nullable=True)
    taxable_value = db.Column(db.Float, nullable=True)
    cgst_rate = db.Column(db.Float, nullable=True)
    sgst_rate = db.Column(db.Float, nullable=True)
    igst_rate = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    entries = db.relationship("VoucherEntry", backref="voucher", cascade="all, delete-orphan")

    def total_debit(self):
        return sum(e.amount for e in self.entries if e.entry_type == "debit")

    def total_credit(self):
        return sum(e.amount for e in self.entries if e.entry_type == "credit")

    def is_balanced(self):
        return round(self.total_debit(), 2) == round(self.total_credit(), 2)


class VoucherEntry(db.Model):
    """One debit or credit line within a voucher."""
    id = db.Column(db.Integer, primary_key=True)
    voucher_id = db.Column(db.Integer, db.ForeignKey("voucher.id"), nullable=False)
    ledger_id = db.Column(db.Integer, db.ForeignKey("ledger.id"), nullable=False)
    entry_type = db.Column(db.String(10), nullable=False)  # 'debit' or 'credit'
    amount = db.Column(db.Float, nullable=False)


class Packet(db.Model):
    """A monthly work packet, created by admin, assigned to one learner."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # assigned learner
    month_label = db.Column(db.String(20), nullable=False)  # e.g. "August 2026"
    title = db.Column(db.String(200), nullable=False)
    instructions_html = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.Date, nullable=False)

    expected_answer_html = db.Column(db.Text, nullable=True)
    show_answer_to_learner = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    submission = db.relationship("Submission", backref="packet", uselist=False, cascade="all, delete-orphan")
    review = db.relationship("PacketReview", backref="packet", uselist=False, cascade="all, delete-orphan")


class Submission(db.Model):
    """Learner's 'I'm done for this month' marker. Their books are live, not a file."""
    id = db.Column(db.Integer, primary_key=True)
    packet_id = db.Column(db.Integer, db.ForeignKey("packet.id"), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.Text, nullable=True)  # learner's optional comment/question


class PacketReview(db.Model):
    """Admin's feedback against a packet."""
    id = db.Column(db.Integer, primary_key=True)
    packet_id = db.Column(db.Integer, db.ForeignKey("packet.id"), nullable=False, unique=True)
    status = db.Column(db.String(20), default="pending")  # pending / reviewed / needs_revision
    feedback_text = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
