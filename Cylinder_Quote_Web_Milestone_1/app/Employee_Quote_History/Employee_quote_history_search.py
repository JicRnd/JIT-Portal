from __future__ import annotations

from functools import wraps
from pathlib import Path
import re

from flask import Blueprint, jsonify, make_response, redirect, render_template, request, send_from_directory, session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..db import get_session
from ..models_db import Order, Quote, QuoteLineItem, User, utc_now
from ..quote_service import sync_order_status


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


_IGNORED_QUOTE_SEARCH_KEYS = {
    "assigned_to",
    "assigned_to_user",
    "assigned_to_user_id",
    "assigned_employee",
    "assigned_employee_user_id",
    "quoted_by",
    "quoted_by_user",
    "quoted_by_user_id",
    "ordered_by",
    "ordered_by_user",
    "ordered_by_user_id",
    "created_by",
    "created_by_user",
    "created_by_user_id",
    "edited_by",
    "edited_by_user",
    "edited_by_user_id",
    "approved_by",
    "approved_by_user",
    "approved_by_user_id",
    "text_nodes",
    "textnodes",
}


def _iter_quote_values(value):
    """Yield searchable scalar values while skipping attribution metadata."""
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = re.sub(r"[^a-z0-9]+", "_", str(key).casefold()).strip("_")
            if normalized_key in _IGNORED_QUOTE_SEARCH_KEYS:
                continue
            yield key
            yield from _iter_quote_values(nested_value)
    elif isinstance(value, (list, tuple, set)):
        for nested_value in value:
            yield from _iter_quote_values(nested_value)
    else:
        yield value


def _quote_search_text(quote: Quote) -> str:
    values = (
        quote.id,
        quote.quote_number,
        quote.status,
        quote.customer_name,
        quote.customer_address,
        quote.person_of_contact,
        quote.customer_contact,
        quote.customer_reference,
        quote.comments,
        quote.special_instructions,
        quote.pricing_version,
        quote.revision,
        quote.quantity,
        quote.discount,
        quote.model_code,
        quote.created_at,
        quote.edited_at,
        quote.emailed_at,
        quote.approved_at,
        quote.deleted_at,
        quote.assigned_at,
        quote.customer_update_pending,
        quote.order_form_snapshot,
        quote.cylinder_inputs_snapshot,
        quote.price_breakdown_snapshot,
        [
            (
                line_item.reference_part_number,
                line_item.description,
                line_item.quantity,
                line_item.unit_price,
                line_item.extended_price,
                line_item.internal_note,
                line_item.show_on_customer_quote,
            )
            for line_item in quote.line_items
        ],
    )
    return " ".join(
        str(value).casefold()
        for value in _iter_quote_values(values)
        if value is not None
    )


def search_quotes(
    db,
    query: str,
    limit: int | None = None,
    include_deleted: bool = False,
) -> list[Quote]:
    """Search every stored quote and line item in Quote.db."""
    query = (query or "").strip().casefold()
    quotes = db.execute(
        select(Quote).where(
            Quote.deleted_at.is_not(None) if include_deleted else Quote.deleted_at.is_(None)
        )
        .options(selectinload(Quote.line_items))
        .order_by(Quote.created_at.desc())
    ).scalars().all()

    if query:
        quotes = [
            quote for quote in quotes
            if query in _quote_search_text(quote)
        ]

    return quotes if limit is None else quotes[:limit]


@employee_quote_history_bp.get("/employee_quote_history/employee_quote_history.html")
@require_employee
def employee_quote_history_page():
    user = signed_in_employee()
    query = (request.args.get("q") or "").strip()
    show_all = request.args.get("all") == "1"
    trash = request.args.get("trash") == "1"

    with get_session() as db:
        rows = [
            (quote, total_for(quote), status_label(quote.status))
            for quote in search_quotes(db, query, include_deleted=trash)
        ]
        status_order = {
            "accepted": 0,
            "pending_approval": 0,
            "pending": 0,
            "approved": 1,
        }
        def history_timestamp(row):
            quote = row[0]
            return (
                quote.approved_at
                if quote.status == "approved" and quote.approved_at
                else quote.created_at
            )

        rows.sort(
            key=lambda row: (
                status_order.get(row[0].status, 2),
                -(history_timestamp(row).timestamp() if history_timestamp(row) else 0),
            )
        )

    response = make_response(render_template(
        "employee_quote_history.html",
        user=user,
        rows=rows,
        query=query,
        show_all=show_all,
        trash=trash,
    ))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@employee_quote_history_bp.get("/employee_quote_history_search")
@require_employee
def employee_quote_history_search():
    query = (request.args.get("q") or "").strip()
    with get_session() as db:
        return jsonify({
            "ok": True,
            "results": [
                {
                    "id": quote.id,
                    "quote_number": quote.quote_number or "",
                    "customer": quote.customer_name or "",
                    "model_code": quote.model_code or "",
                }
                for quote in search_quotes(db, query)
            ] if len(query) >= 2 else [],
        })


@employee_quote_history_bp.post("/employee_quote_history/<int:quote_id>/delete")
@require_employee
def delete_employee_quote(quote_id: int):
    user = signed_in_employee()

    with get_session() as db:
        quote = db.get(Quote, quote_id)
        if quote is None:
            return jsonify({"ok": False, "error": "Quote not found"}), 404

        quote.deleted_status = quote.status
        quote.status = "canceled"
        quote.deleted_by_user_id = user.id
        quote.deleted_at = utc_now()
        quote.edited_by_user_id = user.id
        quote.edited_at = utc_now()
        sync_order_status(db, quote.id, "canceled")
        order = db.execute(
            select(Order).where(Order.quote_id == quote.id)
        ).scalar_one_or_none()
        if order is not None:
            order.deleted_status = order.status
            order.status = "canceled"
            order.deleted_by_user_id = user.id
            order.deleted_at = quote.deleted_at
            db.add(order)
        db.add(quote)
        db.commit()

    return redirect("/employee_quote_history/employee_quote_history.html")


@employee_quote_history_bp.post("/employee_quote_history/<int:quote_id>/restore")
@require_employee
def restore_employee_quote(quote_id: int):
    with get_session() as db:
        quote = db.get(Quote, quote_id)
        if quote is None or quote.deleted_at is None:
            return jsonify({"ok": False, "error": "Deleted quote not found"}), 404

        quote.status = quote.deleted_status or "draft"
        quote.deleted_status = None
        quote.deleted_by_user_id = None
        quote.deleted_at = None
        sync_order_status(db, quote.id, quote.status)
        order = db.execute(
            select(Order).where(Order.quote_id == quote.id)
        ).scalar_one_or_none()
        if order is not None:
            order.status = quote.status
            order.deleted_status = None
            order.deleted_by_user_id = None
            order.deleted_at = None
            db.add(order)
        db.add(quote)
        db.commit()

    return redirect("/employee_quote_history/employee_quote_history.html")


@employee_quote_history_bp.get("/employee_quote_history.css")
def employee_quote_history_css():
    return send_from_directory(
        employee_quote_history_directory,
        "employee_quote_history.css",
    )


@employee_quote_history_bp.get("/employee_quote_history.js")
def employee_quote_history_js():
    return send_from_directory(
        employee_quote_history_directory,
        "employee_quote_history.js",
    )
