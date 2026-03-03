"""
Admin Authentication Service
- Email + Password login
- JWT tokens
- Password hashing with bcrypt
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
import jwt
import hashlib
import secrets
import structlog
from sqlalchemy.orm import Session
from app.models import AdminUser
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()

# JWT settings
JWT_ALGORITHM  = "HS256"
JWT_EXPIRES_HRS = 24


# ─── Password helpers ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Simple SHA-256 + salt hashing (no bcrypt dependency needed)."""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}{settings.secret_key}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hashed = stored_hash.split(":", 1)
        check = hashlib.sha256(f"{salt}{password}{settings.secret_key}".encode()).hexdigest()
        return check == hashed
    except Exception:
        return False


# ─── JWT helpers ──────────────────────────────────────────────────────────────

def create_token(admin_id: str, email: str) -> str:
    payload = {
        "sub":   admin_id,
        "email": email,
        "role":  "admin",
        "exp":   datetime.utcnow() + timedelta(hours=JWT_EXPIRES_HRS),
        "iat":   datetime.utcnow(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        log.warning("auth.token_expired")
        return None
    except jwt.InvalidTokenError:
        log.warning("auth.token_invalid")
        return None


# ─── DB operations ────────────────────────────────────────────────────────────

def create_admin(db: Session, email: str, password: str, name: str = "Admin") -> AdminUser:
    admin = AdminUser(
        email=email,
        password_hash=hash_password(password),
        name=name,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    log.info("auth.admin_created", email=email)
    return admin


def get_admin_by_email(db: Session, email: str) -> Optional[AdminUser]:
    return db.query(AdminUser).filter(AdminUser.email == email).first()


def authenticate_admin(db: Session, email: str, password: str) -> Optional[AdminUser]:
    admin = get_admin_by_email(db, email)
    if not admin:
        log.warning("auth.email_not_found", email=email)
        return None
    if not admin.is_active:
        log.warning("auth.admin_inactive", email=email)
        return None
    if not verify_password(password, admin.password_hash):
        log.warning("auth.wrong_password", email=email)
        return None
    # Update last login
    admin.last_login = datetime.utcnow()
    db.commit()
    log.info("auth.login_success", email=email)
    return admin
