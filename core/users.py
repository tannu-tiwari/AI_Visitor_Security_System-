from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .database import app_scope, commit_session, db
from .models import VALID_ROLES, User


def list_users():
    with app_scope():
        users = db.session.execute(
            db.select(User).order_by(
                db.func.lower(User.full_name),
                User.id,
            )
        ).scalars().all()
        return [user.to_dict() for user in users]


def _text(value):
    return "" if value is None else str(value).strip()


def _normalize_user_fields(
    username=None,
    full_name=None,
    email=None,
    role=None,
    department=None,
):
    return {
        "username": _text(username),
        "full_name": _text(full_name),
        "email": _text(email) or None,
        "role": _text(role).lower(),
        "department": _text(department) or None,
    }


def _validate_fields(fields, require_password=False, password=""):
    if not fields["username"]:
        return "Username is required."
    if not fields["full_name"]:
        return "Full name is required."
    if fields["role"] not in VALID_ROLES:
        return "Role must be one of: " + ", ".join(VALID_ROLES) + "."
    if fields["role"] == "host" and not fields["department"]:
        return "Host accounts require a department."
    if require_password and not _text(password):
        return "Password is required."
    if password and not isinstance(password, str):
        return "Password must be text."
    if isinstance(password, str) and password and not password.strip():
        return "Password cannot be blank."
    return None


def _email_in_use(email, exclude_user_id=None):
    if not email:
        return False

    query = db.select(User.id).where(User.email == email)
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    return db.session.execute(query).first() is not None


def create_user_account(
    username,
    full_name,
    email,
    role,
    department,
    password,
):
    fields = _normalize_user_fields(
        username=username,
        full_name=full_name,
        email=email,
        role=role,
        department=department,
    )
    error = _validate_fields(
        fields,
        require_password=True,
        password=password,
    )
    if error:
        return False, error, None

    with app_scope():
        username_exists = db.session.execute(
            db.select(User.id).where(User.username == fields["username"])
        ).first()
        if username_exists is not None:
            return False, "That username is already taken.", None

        if _email_in_use(fields["email"]):
            return False, "That email address is already in use.", None

        user = User(**fields, is_active=True)
        user.set_password(password)

        try:
            db.session.add(user)
            commit_session()
            created = user.to_dict()
        except IntegrityError:
            db.session.rollback()
            return False, "Username or email already exists.", None
        except SQLAlchemyError:
            db.session.rollback()
            return False, "Could not create the user.", None

    return True, "User created.", created


def update_user_account(user_id, changes, acting_user_id):
    if not isinstance(changes, dict):
        return False, "Invalid user update.", None

    with app_scope():
        user = db.session.get(User, user_id)
        if user is None:
            return False, "User not found.", None

        role = changes.get("role", user.role)
        full_name = changes.get("full_name", user.full_name)
        email = changes.get("email", user.email)
        department = changes.get("department", user.department)
        password = changes.get("password", "")
        is_active = changes.get("is_active", user.is_active)

        fields = _normalize_user_fields(
            username=user.username,
            full_name=full_name,
            email=email,
            role=role,
            department=department,
        )
        error = _validate_fields(fields, password=password)
        if error:
            return False, error, None

        if not isinstance(is_active, bool):
            return False, "Active status must be true or false.", None

        if user.id == acting_user_id:
            if fields["role"] != "admin":
                return False, "You cannot remove your own admin role.", None
            if not is_active:
                return False, "You cannot deactivate your own account.", None

        if _email_in_use(fields["email"], exclude_user_id=user.id):
            return False, "That email address is already in use.", None

        user.full_name = fields["full_name"]
        user.email = fields["email"]
        user.role = fields["role"]
        user.department = fields["department"]
        user.is_active = is_active

        if password:
            if not isinstance(password, str):
                return False, "Password must be text.", None
            user.set_password(password)

        try:
            commit_session()
            updated = user.to_dict()
        except IntegrityError:
            db.session.rollback()
            return False, "Username or email already exists.", None
        except SQLAlchemyError:
            db.session.rollback()
            return False, "Could not update the user.", None

    return True, "User updated.", updated
