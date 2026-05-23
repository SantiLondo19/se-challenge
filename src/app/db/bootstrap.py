"""Idempotent admin bootstrap.

On startup, if no admin user exists, create one from `BOOTSTRAP_ADMIN_*` settings.
Safe to run on every boot: a single SELECT plus an INSERT only when zero admins.
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

_logger = get_logger("app.bootstrap")


async def ensure_admin() -> None:
    """Create the bootstrap admin if no admin exists yet."""
    async with AsyncSessionLocal() as session:
        repo = UserRepository(session)
        existing_admins = await repo.count_by_role(UserRole.ADMIN)
        if existing_admins > 0:
            _logger.info("bootstrap_admin_skipped", existing_admins=existing_admins)
            return

        username = settings.bootstrap_admin_username
        email = settings.bootstrap_admin_email

        if await repo.exists_by_email_or_username(email=email, username=username):
            _logger.warning(
                "bootstrap_admin_conflict",
                username=username,
                email=email,
                detail="Non-admin user with bootstrap identity exists; skipping seed",
            )
            return

        admin = User(
            username=username,
            email=email,
            first_name="Bootstrap",
            last_name="Admin",
            role=UserRole.ADMIN,
            active=True,
            password_hash=hash_password(
                settings.bootstrap_admin_password.get_secret_value()
            ),
        )
        await repo.add(admin)
        await session.commit()
        _logger.info("bootstrap_admin_created", username=username, email=email)
