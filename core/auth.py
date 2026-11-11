import os
from datetime import timedelta
from urllib.parse import unquote, urlparse

import click
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy.exc import IntegrityError

from .database import app_scope, commit_session, db
from .models import VALID_ROLES, User

GENERIC_LOGIN_ERROR = "Invalid username or password."

login_manager = LoginManager()
auth_bp = Blueprint("auth", __name__)


def _env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@login_manager.user_loader
def load_user(user_id):
    """Load the account for Flask-Login using its database primary key."""
    try:
        user_pk = int(user_id)
    except (TypeError, ValueError):
        return None

    user = db.session.get(User, user_pk)
    if user is None or not user.is_active:
        return None

    return user


def is_safe_redirect_target(target):
    """
    Only allow local, absolute paths as post-login redirect targets.

    Rejects absolute URLs, protocol-relative URLs (`//host`), backslash
    variants and encoded tricks (`%2F%2Fhost`) that browsers may normalise
    into an external location.
    """
    if not isinstance(target, str):
        return False

    target = target.strip()

    if not target:
        return False

    decoded = unquote(target)

    if any(ord(character) < 32 or ord(character) == 127 for character in decoded):
        return False

    if "\\" in target or "\\" in decoded:
        return False

    if target.startswith("//") or decoded.startswith("//"):
        return False

    if not target.startswith("/") or not decoded.startswith("/"):
        return False

    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc


def _redirect_after_login(next_url):
    if is_safe_redirect_target(next_url):
        path = urlparse(next_url).path
        if path not in (url_for("auth.login"), url_for("auth.logout")):
            return redirect(next_url)

    return redirect(url_for("dashboard"))


def _find_user(username):
    with app_scope():
        return db.session.execute(
            db.select(User).where(User.username == username)
        ).scalar_one_or_none()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.values.get("next", "")

    if request.method == "GET" and current_user.is_authenticated:
        return _redirect_after_login(next_url)

    error = None
    username = ""

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            error = "Username and password are required."
        else:
            user = _find_user(username)

            if (
                user is not None
                and user.is_active
                and user.check_password(password)
            ):
                login_user(user)
                return _redirect_after_login(request.form.get("next", ""))

            error = GENERIC_LOGIN_ERROR

    return render_template(
        "login.html",
        error=error,
        username=username,
        next_url=next_url if is_safe_redirect_target(next_url) else "",
    )


@auth_bp.route("/logout", methods=["POST"])
def logout():
    if current_user.is_authenticated:
        logout_user()

    return redirect(url_for("auth.login"))


@auth_bp.route("/auth-test")
@login_required
def auth_test():
    """Small protected route used to verify sessions in this step."""
    return jsonify({
        "authenticated": True,
        "user": current_user.to_dict(),
    })


def init_auth(app):
    """Attach Flask-Login, the auth blueprint and user-management CLI."""
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault(
        "SESSION_COOKIE_SECURE", _env_flag("SESSION_COOKIE_SECURE")
    )
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", timedelta(hours=8))
    app.config.setdefault("REMEMBER_COOKIE_HTTPONLY", True)
    app.config.setdefault("REMEMBER_COOKIE_SAMESITE", "Lax")
    app.config.setdefault(
        "REMEMBER_COOKIE_SECURE", _env_flag("SESSION_COOKIE_SECURE")
    )

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "warning"
    login_manager.session_protection = "strong"

    app.register_blueprint(auth_bp)

    @app.cli.command("create-user")
    @click.option("--username", prompt="Username")
    @click.option("--full-name", prompt="Full name")
    @click.option("--email", default="", help="Optional unique email address.")
    @click.option(
        "--role",
        type=click.Choice(VALID_ROLES, case_sensitive=False),
        prompt="Role (admin/security/host)",
    )
    @click.option("--department", default="", help="Optional department.")
    @click.option(
        "--password",
        prompt="Password",
        hide_input=True,
        confirmation_prompt=True,
    )
    def create_user_command(username, full_name, email, role, department, password):
        """Create a login account with an explicit role."""
        username = (username or "").strip()
        full_name = (full_name or "").strip()
        email = (email or "").strip() or None
        role = (role or "").strip().lower()
        department = (department or "").strip() or None

        if not username:
            raise click.ClickException("Username is required.")
        if not full_name:
            raise click.ClickException("Full name is required.")
        if role not in VALID_ROLES:
            raise click.ClickException(
                "Role must be one of: " + ", ".join(VALID_ROLES) + "."
            )
        if not password:
            raise click.ClickException("Password is required.")

        existing = db.session.execute(
            db.select(User).where(User.username == username)
        ).scalar_one_or_none()
        if existing is not None:
            raise click.ClickException("That username is already taken.")

        if email is not None:
            email_exists = db.session.execute(
                db.select(User).where(User.email == email)
            ).scalar_one_or_none()
            if email_exists is not None:
                raise click.ClickException("That email address is already in use.")

        user = User(
            username=username,
            full_name=full_name,
            email=email,
            role=role,
            department=department,
            is_active=True,
        )
        user.set_password(password)

        try:
            db.session.add(user)
            commit_session()
        except IntegrityError:
            db.session.rollback()
            raise click.ClickException("Username or email already exists.")

        click.echo(f"Created user '{username}' with role '{role}'.")

    @app.cli.command("assign-role")
    @click.option("--username", prompt="Username")
    @click.option(
        "--role",
        type=click.Choice(VALID_ROLES, case_sensitive=False),
        prompt="Role (admin/security/host)",
    )
    @click.option("--department", default="", help="Optional department.")
    def assign_role_command(username, role, department):
        """Assign or change the role of an existing account."""
        username = (username or "").strip()
        role = (role or "").strip().lower()
        department = (department or "").strip()

        user = db.session.execute(
            db.select(User).where(User.username == username)
        ).scalar_one_or_none()
        if user is None:
            raise click.ClickException(f"No account found for '{username}'.")

        user.role = role
        if department:
            user.department = department

        try:
            commit_session()
        except IntegrityError:
            db.session.rollback()
            raise click.ClickException("Could not update the account role.")

        click.echo(f"Assigned role '{role}' to '{username}'.")
