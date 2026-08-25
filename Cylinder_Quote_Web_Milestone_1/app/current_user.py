from __future__ import annotations

import os
from typing import Any

import flask
from flask import request as flask_request, session as flask_session
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .db import get_session
from .models_db import User

DEFAULT_USER_NAME = os.environ.get("DEFAULT_USER_NAME", "dev")


def _normalize_display_name(name: str | None) -> str:
    if not name:
        return DEFAULT_USER_NAME
    cleaned = str(name).strip()
    return cleaned if cleaned else DEFAULT_USER_NAME


def _extract_display_name(request_obj: Any) -> str:
    """Resolve display name from request header or JSON payload."""
    display_name = request_obj.headers.get("X-User-Name")
    if display_name:
        return display_name
    if getattr(request_obj, "is_json", False):
        payload = request_obj.get_json(silent=True) or {}
        candidate = payload.get("current_user")
        if candidate:
            return candidate
    return DEFAULT_USER_NAME


def _get_or_create_user(session, display_name: str) -> User:
    """Lookup or create a user by case-insensitive display_name.

    Handles the small race where two requests arrive for the same new name
    at the same time.
    """
    lower_name = display_name.lower()
    user = session.execute(
        select(User).where(func.lower(User.display_name) == lower_name)
    ).scalar_one_or_none()

    if user is None:
        user = User(display_name=display_name, is_active=True)
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            user = session.execute(
                select(User).where(func.lower(User.display_name) == lower_name)
            ).scalar_one()

    return user


def get_or_create_current_user(
    request_obj: Any | None = None,
    *,
    display_name: str | None = None,
) -> User:
    """Return the current User for this request, creating the row if needed.

    Resolution order:
        1. ``display_name`` keyword argument if provided.
        2. ``X-User-Name`` request header.
        3. ``current_user`` field in a JSON request body.
        4. ``DEFAULT_USER_NAME`` environment variable (default: ``dev``).

    The helper opens its own short database transaction so callers can use the
    returned ``User`` in a larger transaction without worrying about user-row
    creation races.
    """
    # A real portal login takes priority over the former local dev user.
    if display_name is None:
        user_id = flask.has_request_context() and flask_session.get("user_id")
        if user_id:
            with get_session() as session:
                logged_in = session.get(User, int(user_id))
                if logged_in and logged_in.is_active:
                    return logged_in
        request_obj = request_obj or flask_request
        display_name = _extract_display_name(request_obj)

    display_name = _normalize_display_name(display_name)

    with get_session() as session:
        return _get_or_create_user(session, display_name)
