# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

# CSRF
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf

app = Flask(__name__)
app.config.from_object('config')  # make sure config.SECRET_KEY is set

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from .models import User
    return User.query.get(int(user_id))

# ---- CSRF setup -------------------------------------------------------------
csrf = CSRFProtect()
csrf.init_app(app)

# Expose {{ csrf_token() }} for templates (e.g., <meta name="csrf-token" ...>)
@app.context_processor
def inject_csrf():
    return dict(csrf_token=generate_csrf)

# Put a fresh CSRF token in a cookie so JS can send it in headers
@app.after_request
def set_csrf_cookie(response):
    # Set secure=True if you’re HTTPS-only everywhere
    response.set_cookie(
        "csrf_token",
        generate_csrf(),
        samesite="Lax",
        secure=False
    )
    return response
# ---------------------------------------------------------------------------

# (your logging setup here...)

from app import views, models  # noqa: E402
