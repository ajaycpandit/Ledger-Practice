# Ledger Practice

A simplified, Tally-style web app for giving someone with accounting
experience ongoing simulated bookkeeping work: ledgers, voucher entry
(Payment/Receipt/Sales/Purchase/Journal/Contra), and auto-generated
reports (Day Book, Trial Balance, P&L, Balance Sheet).

Fully web-based — no file upload or download anywhere. An admin posts
monthly "packets" (instructions + a hidden expected answer) to a
learner; the learner enters vouchers into their own continuous
company; the admin reviews their live books against the answer key
and can choose to reveal it.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export FLASK_APP=run.py
flask init-db
flask create-admin   # follow the prompts to set your admin login
flask run
```

Then visit http://localhost:5000, log in as admin, and create a
learner from the dashboard (this also provisions their company/books
automatically).

## Deploying

This is a standard Flask app — deployable to any host that runs
Python (Render, Railway, PythonAnywhere, a VPS with gunicorn +
nginx, etc.). For production:

- Set a real `SECRET_KEY` env var
- Set `DATABASE_URL` if you're not using the default local SQLite file
  (e.g. Postgres in production)
- Run via `gunicorn run:app` behind a reverse proxy instead of the
  Flask dev server

## Structure

```
app/
  __init__.py       # app factory, CLI commands (init-db, create-admin)
  models.py         # User, Company, Ledger, Voucher, VoucherEntry, Packet, Submission, PacketReview
  accounting.py      # trial balance / P&L / balance sheet / day book calculations
  routes/
    auth.py         # login/logout
    learner.py       # dashboard, ledgers, vouchers, reports, packet view+submit
    admin.py         # learner management, packet creation, review + answer reveal
  templates/
  static/css/
run.py
requirements.txt
```

## Notes on the model

- Each learner has exactly one `Company` that persists indefinitely —
  balances carry forward, there's no monthly reset, same as a real job.
- A "month" is really just a `Packet`: a set of instructions with a
  due date. The learner's actual work is entering vouchers into their
  ongoing books by that date.
- `Packet.expected_answer_html` is never shown to the learner unless
  `Packet.show_answer_to_learner` is explicitly turned on by the admin
  from the review page — there's no visible "check answer" control in
  the learner UI until that flag is set, so its existence isn't
  discoverable beforehand.
- All reports are computed live from the database (see
  `app/accounting.py`) — nothing is ever written to or read from a file.
