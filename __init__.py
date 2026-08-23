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
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", f"sqlite:///{db_path}"
    )
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
        """Create an admin user interactively. Run with: flask create-admin"""
        import getpass
        from werkzeug.security import generate_password_hash

        name = input("Admin name: ")
        password = getpass.getpass("Admin password: ")
        user = User(name=name, role="admin", password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        print(f"Admin user '{name}' created.")

    return app
