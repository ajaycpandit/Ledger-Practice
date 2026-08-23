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

## Deploying on Render

This repo includes a `render.yaml` blueprint that provisions a free
Postgres database and a web service together.

**Important:** don't use the default SQLite file in production on
Render — its filesystem is ephemeral, so a redeploy can wipe the
learner's books. Use the included Postgres database instead (the
blueprint wires this up automatically via `DATABASE_URL`).

1. Push this repo to GitHub.
2. In Render, choose **New > Blueprint** and point it at the repo.
   Render will read `render.yaml` and create both the web service and
   the database.
3. Before the first deploy, set two environment variables on the web
   service (Render will prompt for these since they're marked
   `sync: false` in the blueprint): `ADMIN_NAME` and `ADMIN_PASSWORD`
   — this becomes your admin login. You can remove these env vars
   after the first successful deploy if you'd rather not leave the
   password sitting in Render's dashboard.
4. Deploy. The blueprint's `preDeployCommand` runs `flask init-db`
   (creates tables) and `flask create-admin` (creates your admin user
   from the env vars, or skips it if that user already exists) on
   every deploy — safe to leave in place long-term.
5. Log in at your Render URL with the admin name/password you set,
   and create the learner from the dashboard as usual.

If your Render plan doesn't support `preDeployCommand`, run the same
two commands once from Render's **Shell** tab instead:
```bash
flask init-db
flask create-admin
```

## Deploying elsewhere

This is a standard Flask app — deployable to any host that runs
Python (Railway, PythonAnywhere, a VPS with gunicorn + nginx, etc.).
For production generally:

- Set a real `SECRET_KEY` env var
- Set `DATABASE_URL` to a real database (Postgres, not SQLite) if the
  host's filesystem isn't persistent
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
