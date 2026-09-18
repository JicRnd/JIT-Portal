from __future__ import annotations

from functools import wraps
import re

from pathlib import Path

from flask import (
	Blueprint,
	make_response,
	jsonify,
	redirect,
	render_template,
	request,
	send_from_directory,
	session,
)
from sqlalchemy import select

from ..db import get_session
from ..models_db import Order, Quote, User, utc_now


employee_order_history_bp = Blueprint("employee_order_history", __name__)
employee_order_history_directory = Path(__file__).resolve().parent
_IGNORED_ORDER_SEARCH_KEYS = {
	"assigned_to",
	"assigned_to_user",
	"assigned_to_user_id",
	"assigned_employee",
	"assigned_employee_user_id",
	"ordered_by",
	"quoted_by",
	"quoted_by_user",
	"quoted_by_user_id",
	"created_by",
	"created_by_user",
	"created_by_user_id",
	"text_nodes",
}


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


def _iter_order_values(value):
	"""Yield every scalar value stored in an order or its snapshot."""
	if isinstance(value, dict):
		for key, nested_value in value.items():
			normalized_key = re.sub(r"[^a-z0-9]+", "_", str(key).casefold()).strip("_")
			if normalized_key in _IGNORED_ORDER_SEARCH_KEYS:
				continue
			yield key
			yield from _iter_order_values(nested_value)
	elif isinstance(value, (list, tuple, set)):
		for nested_value in value:
			yield from _iter_order_values(nested_value)
	else:
		yield value


def _order_search_text(order: Order) -> str:
	values = (
		order.id,
		order.quote_id,
		order.quote_number,
		order.status,
		order.created_at,
		order.updated_at,
		order.order_form_snapshot,
	)
	return " ".join(
		str(value).casefold()
		for value in _iter_order_values(values)
		if value is not None
	)


def search_orders(
	db,
	query: str,
	limit: int | None = None,
	include_deleted: bool = False,
) -> list[Order]:
	"""Search every stored value in every order from Order.db."""
	query = (query or "").strip().casefold()
	quote_ids = set(db.execute(
		select(Quote.id).where(
			Quote.deleted_at.is_not(None) if include_deleted else Quote.deleted_at.is_(None)
		)
	).scalars())
	orders = db.execute(
		select(Order).where(
			Order.deleted_at.is_not(None) if include_deleted else Order.deleted_at.is_(None)
		).order_by(Order.created_at.desc())
	).scalars().all()
	orders = [order for order in orders if order.quote_id in quote_ids]

	if query:
		orders = [
			order for order in orders
			if query in _order_search_text(order)
		]

	return orders if limit is None else orders[:limit]


def order_search_results(db, query: str, limit: int | None = None) -> list[dict[str, str]]:
	"""Format Order.db matches for the employee history results popup."""
	if len((query or "").strip()) < 2:
		return []

	results = []
	for order in search_orders(db, query, limit):
		snapshot = order.order_form_snapshot or {}
		quote_form_inputs = (snapshot.get("quote_form_edits") or {}).get("inputs") or {}
		results.append({
			"order_number": snapshot.get("order_number") or order.quote_number or "",
			"customer": (
				snapshot.get("ship_to_1")
				or snapshot.get("bill_to_1")
				or quote_form_inputs.get("pv_customer_name")
				or ""
			),
			"model_code": snapshot.get("model_code") or "",
		})
	return results


@employee_order_history_bp.get("/employee_order_history/employee_order_history.html")
@require_employee
def employee_order_history_page():
	user = signed_in_employee()
	query = (request.args.get("q") or "").strip()
	show_all = request.args.get("all") == "1"
	trash = request.args.get("trash") == "1"

	with get_session() as db:
		rows = search_orders(db, query, include_deleted=trash)

	response = make_response(render_template(
		"employee_order_history.html",
		user=user,
		rows=rows,
		query=query,
		show_all=show_all,
		trash=trash,
	))
	response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
	response.headers["Pragma"] = "no-cache"
	return response


@employee_order_history_bp.get("/employee/order-history-search")
@require_employee
def employee_order_history_search():
	query = (request.args.get("q") or "").strip()
	with get_session() as db:
		return jsonify({"ok": True, "results": order_search_results(db, query)})


@employee_order_history_bp.post("/employee/order-history/<int:order_id>/delete")
@require_employee
def delete_employee_order(order_id: int):
	user = signed_in_employee()

	with get_session() as db:
		order = db.get(Order, order_id)
		if order is None:
			return jsonify({"ok": False, "error": "Order not found"}), 404

		order.deleted_status = order.status
		order.status = "canceled"
		order.deleted_by_user_id = user.id
		order.deleted_at = utc_now()
		quote = db.get(Quote, order.quote_id)
		if quote is not None:
			quote.deleted_status = quote.status
			quote.status = "canceled"
			quote.deleted_by_user_id = user.id
			quote.deleted_at = order.deleted_at
			db.add(quote)
		db.add(order)
		db.commit()

	return redirect("/employee_order_history/employee_order_history.html")


@employee_order_history_bp.post("/employee/order-history/<int:order_id>/restore")
@require_employee
def restore_employee_order(order_id: int):
	with get_session() as db:
		order = db.get(Order, order_id)
		if order is None or order.deleted_at is None:
			return jsonify({"ok": False, "error": "Deleted order not found"}), 404

		order.status = order.deleted_status or "pending_approval"
		order.deleted_status = None
		order.deleted_by_user_id = None
		order.deleted_at = None
		quote = db.get(Quote, order.quote_id)
		if quote is not None:
			quote.status = order.status
			quote.deleted_status = None
			quote.deleted_by_user_id = None
			quote.deleted_at = None
			db.add(quote)
		db.add(order)
		db.commit()

	return redirect("/employee_order_history/employee_order_history.html")


@employee_order_history_bp.get("/employee/order-history.css")
def employee_order_history_css():
	return send_from_directory(
		employee_order_history_directory,
		"employee_order_history.css",
	)


@employee_order_history_bp.get("/employee/order-history.js")
def employee_order_history_js():
	return send_from_directory(
		employee_order_history_directory,
		"employee_order_history.js",
	)
