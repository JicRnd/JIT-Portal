from __future__ import annotations

from functools import wraps
from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, send_from_directory, session
from sqlalchemy import String, cast, func, or_, select

from ..db import get_session
from ..models_db import Quote, QuoteLineItem, User


employee_quote_history_bp = Blueprint("employee_quote_history", __name__)
employee_quote_history_directory = Path(__file__).resolve().parent


def signed_in_employee():
    user_id = session.get("user_id")
    if not user_id:
        return None

    with get_session() as db:
        user = db.get(User, int(user_id))
        if not user or not user.is_active or user.role != "employee":
            session.clear()
            return None
        return user


def require_employee(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not signed_in_employee():
            return redirect("/employee/login")
        return view(*args, **kwargs)

    return wrapped


def total_for(quote: Quote) -> float:
    data = quote.price_breakdown_snapshot or {}
    for key in ("quote_net_each", "working_net_each", "net_each", "total"):
        if data.get(key) not in (None, ""):
            try:
                return float(data[key])
            except (TypeError, ValueError):
                pass
    return 0.0


def status_label(value: str | None) -> str:
    value = (value or "pending_approval").lower().replace("-", "_")
    labels = {
        "accepted": "Pending Approval",
        "pending": "Pending Approval",
        "pending_approval": "Pending Approval",
        "approved": "Approved",
        "denied": "Denied",
        "canceled": "Canceled",
    }
    return labels.get(value, value.replace("_", " ").title())


def search_quotes(db, employee_id: int, query: str, limit: int = 25) -> list[Quote]:
    """Search only quote records and line items stored in Quote.db."""
    statement = (
        select(Quote)
        .where(Quote.status != "canceled")
        .where(
            or_(
                Quote.created_by_user_id == employee_id,
                Quote.assigned_employee_user_id == employee_id,
                Quote.edited_by_user_id == employee_id,
                Quote.approved_by_user_id == employee_id,
            )
        )
    )
    query = (query or "").strip()

    if query:
        like = f"%{query}%"
        statement = statement.where(
            or_(
                Quote.quote_number.ilike(like),
                Quote.model_code.ilike(like),
                Quote.customer_name.ilike(like),
                Quote.customer_address.ilike(like),
                Quote.person_of_contact.ilike(like),
                Quote.customer_contact.ilike(like),
                Quote.customer_reference.ilike(like),
                Quote.comments.ilike(like),
                Quote.special_instructions.ilike(like),
                Quote.status.ilike(like),
                cast(Quote.order_form_snapshot, String).ilike(like),
                cast(Quote.cylinder_inputs_snapshot, String).ilike(like),
                cast(Quote.price_breakdown_snapshot, String).ilike(like),
                Quote.id.in_(
                    select(QuoteLineItem.quote_id).where(
                        or_(
                            QuoteLineItem.reference_part_number.ilike(like),
                            QuoteLineItem.description.ilike(like),
                            QuoteLineItem.internal_note.ilike(like),
                        )
                    )
                ),
            )
        )

    return db.execute(
        statement.order_by(Quote.created_at.desc()).limit(limit)
    ).scalars().all()


@employee_quote_history_bp.get("/employee_quote_history/employee_quote_history.html")
@employee_quote_history_bp.get("/employee/quote-history")
@require_employee
def employee_quote_history_page():
    user = signed_in_employee()
    query = (request.args.get("q") or "").strip()

    with get_session() as db:
        rows = [
            (quote, total_for(quote), status_label(quote.status))
            for quote in search_quotes(db, user.id, query)
        ]

    return render_template(
        "employee_quote_history.html",
        user=user,
        rows=rows,
        query=query,
    )


@employee_quote_history_bp.get("/employee/quote-history.css")
def employee_quote_history_css():
    return send_from_directory(
        employee_quote_history_directory,
        "employee_quote_history.css",
    )


@employee_quote_history_bp.get("/employee/quote-history.js")
def employee_quote_history_js():
    return send_from_directory(
        employee_quote_history_directory,
        "employee_quote_history.js",
    )
