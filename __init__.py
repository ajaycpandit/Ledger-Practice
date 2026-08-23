import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-this-in-production")

    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, "..", "instance", "ledger.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    database_url = os.environ.get("DATABASE_URL", f"sqlite:///{db_path}")
    # Render (and Heroku-style providers) hand out "postgres://", but
    # SQLAlchemy 2.x / psycopg2 require "postgresql://".
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.learner import learner_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(learner_bp)

    @app.cli.command("init-db")
    def init_db():
        """Create all tables. Run with: flask init-db"""
        db.create_all()
        print("Database initialized.")

    @app.cli.command("create-admin")
    def create_admin():
        """
        Create an admin user. Run with: flask create-admin

        Non-interactive (for Render's build/release step): set ADMIN_NAME
        and ADMIN_PASSWORD env vars and this will use those instead of
        prompting. Safe to run on every deploy — it skips creation if a
        user with that name already exists.
        """
        import getpass
        from werkzeug.security import generate_password_hash

        name = os.environ.get("ADMIN_NAME")
        password = os.environ.get("ADMIN_PASSWORD")

        if not name:
            name = input("Admin name: ")
        if not password:
            password = getpass.getpass("Admin password: ")

        if User.query.filter_by(name=name).first():
            print(f"User '{name}' already exists, skipping.")
            return

        user = User(name=name, role="admin", password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        print(f"Admin user '{name}' created.")

    return app
