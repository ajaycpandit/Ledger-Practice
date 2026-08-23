"""
Pure calculation helpers that derive reports from a company's ledgers and
vouchers. Nothing here touches files — everything is computed from the DB
and handed to templates as plain data structures.
"""

# Groups that make up the P&L (Income - Expenses)
INCOME_GROUPS = {"Sales Accounts", "Direct Income", "Indirect Income"}
EXPENSE_GROUPS = {"Purchase Accounts", "Direct Expenses", "Indirect Expenses"}

# Everything else (assets/liabilities/capital/duties) sits on the Balance Sheet
ASSET_GROUPS = {"Bank Accounts", "Cash-in-Hand", "Sundry Debtors", "Fixed Assets", "Current Assets"}
LIABILITY_GROUPS = {
    "Capital Account",
    "Sundry Creditors",
    "Loans (Liability)",
    "Current Liabilities",
    "Duties & Taxes",
}


def ledger_balance(ledger, as_of=None):
    """
    Returns (balance, side) where side is 'debit' or 'credit'.
    Positive opening_balance is treated as an opening debit; negative as opening credit.
    """
    debit_total = ledger.opening_balance if ledger.opening_balance > 0 else 0.0
    credit_total = abs(ledger.opening_balance) if ledger.opening_balance < 0 else 0.0

    for entry in ledger.entries:
        voucher = entry.voucher
        if as_of and voucher.date > as_of:
            continue
        if entry.entry_type == "debit":
            debit_total += entry.amount
        else:
            credit_total += entry.amount

    net = debit_total - credit_total
    if net >= 0:
        return round(net, 2), "debit"
    return round(abs(net), 2), "credit"


def trial_balance(company, as_of=None):
    rows = []
    total_debit = 0.0
    total_credit = 0.0
    for ledger in sorted(company.ledgers, key=lambda l: l.name):
        balance, side = ledger_balance(ledger, as_of=as_of)
        if balance == 0:
            continue
        rows.append({"ledger": ledger, "balance": balance, "side": side})
        if side == "debit":
            total_debit += balance
        else:
            total_credit += balance
    return {
        "rows": rows,
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "balanced": round(total_debit, 2) == round(total_credit, 2),
    }


def profit_and_loss(company, as_of=None):
    income_rows = []
    expense_rows = []
    total_income = 0.0
    total_expense = 0.0

    for ledger in sorted(company.ledgers, key=lambda l: l.name):
        balance, side = ledger_balance(ledger, as_of=as_of)
        if balance == 0:
            continue
        if ledger.group in INCOME_GROUPS:
            # Income normally sits on the credit side
            income_rows.append({"ledger": ledger, "balance": balance})
            total_income += balance if side == "credit" else -balance
        elif ledger.group in EXPENSE_GROUPS:
            expense_rows.append({"ledger": ledger, "balance": balance})
            total_expense += balance if side == "debit" else -balance

    net_profit = round(total_income - total_expense, 2)
    return {
        "income_rows": income_rows,
        "expense_rows": expense_rows,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "net_profit": net_profit,
    }


def balance_sheet(company, as_of=None):
    asset_rows = []
    liability_rows = []
    total_assets = 0.0
    total_liabilities = 0.0

    for ledger in sorted(company.ledgers, key=lambda l: l.name):
        balance, side = ledger_balance(ledger, as_of=as_of)
        if balance == 0:
            continue
        if ledger.group in ASSET_GROUPS:
            asset_rows.append({"ledger": ledger, "balance": balance})
            total_assets += balance if side == "debit" else -balance
        elif ledger.group in LIABILITY_GROUPS:
            liability_rows.append({"ledger": ledger, "balance": balance})
            total_liabilities += balance if side == "credit" else -balance

    pnl = profit_and_loss(company, as_of=as_of)
    total_liabilities_with_pnl = round(total_liabilities + pnl["net_profit"], 2)

    return {
        "asset_rows": asset_rows,
        "liability_rows": liability_rows,
        "total_assets": round(total_assets, 2),
        "total_liabilities": total_liabilities_with_pnl,
        "net_profit_carried": pnl["net_profit"],
        "balanced": round(total_assets, 2) == total_liabilities_with_pnl,
    }


def day_book(company, as_of=None):
    vouchers = sorted(company.vouchers, key=lambda v: (v.date, v.id))
    if as_of:
        vouchers = [v for v in vouchers if v.date <= as_of]
    return vouchers
