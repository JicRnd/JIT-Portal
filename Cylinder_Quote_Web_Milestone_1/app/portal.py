from __future__ import annotations
from flask import render_template, request, redirect, url_for, flash
from datetime import datetime
from functools import wraps
from os import name
from pathlib import Path

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from . import ai_usage_service
from .db import get_session
from .models_db import Customer, Quote, User
from .part_family_service import (
    FamilyError,
    assign_parts,
    create_family,
    list_families,
    preview_family,
    save_family_image,
    update_family,
)
from .pricing_catalog_service import (
    PriceUpdateError,
    apply_bulk_price_update,
    apply_workbook_price_update,
    build_price_template_workbook,
    catalog_page_data,
    create_catalog_part,
    get_catalog_part,
    get_conflict_details,
    parse_price_workbook,
    preview_bulk_price_update,
    recent_price_changes,
    resolve_conflict,
    restore_price_change,
    update_catalog_part,
    update_catalog_inventory_bulk,
    update_pricing_amount,
)
from .quote_service import quote_to_json


portal_bp = Blueprint("portal", __name__)


def signed_in_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    with get_session() as db:
        user = db.get(User, int(user_id))

        if not user or not user.is_active:
            session.clear()
            return None

        return user


def _customer_names(user) -> list[str]:
    """Names a saved quote could be filed under for this customer account."""
    return [n for n in (user.company_name, user.display_name) if n]


def _customer_quote_filter(user):
    """Match quotes the customer created themselves or an employee created for them.

    Employee-created quotes have no customer user id on file, so association is
    made via the customer_name presentation field (the same field the customer's
    own quote entry prefills from their account), matched case-insensitively.
    """
    names = _customer_names(user)
    conditions = [Quote.created_by_user_id == user.id]
    if names:
        conditions.append(func.lower(Quote.customer_name).in_([n.lower() for n in names]))
    return or_(*conditions)


def _customer_owns_quote(user, quote) -> bool:
    if quote.created_by_user_id == user.id:
        return True
    names = {n.lower() for n in _customer_names(user)}
    return bool(quote.customer_name) and quote.customer_name.lower() in names


def require_role(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = signed_in_user()

            if not user or user.role != role:
                return redirect(url_for(f"portal.{role}_login"))

            return view(*args, **kwargs)

        return wrapped

    return decorator


def require_admin(view):
    """Restrict a portal page to an employee with the existing admin access level."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = signed_in_user()
        if not user or user.role != "employee" or user.access_level != "admin":
            return redirect(url_for("portal.employee_login"))
        return view(*args, **kwargs)

    return wrapped


def total_for(quote):
    data = quote.price_breakdown_snapshot or {}

    for key in (
        "quote_net_each",
        "working_net_each",
        "net_each",
        "total",
    ):
        if data.get(key) not in (None, ""):
            try:
                return float(data[key])
            except (TypeError, ValueError):
                pass

    return 0.0


def status_label(value):
    value = (value or "pending_approval").lower().replace("-", "_")

    labels = {
        "pending_approval": "Pending Approval",
        "approved": "Approved",
        "denied": "Denied",
        "canceled": "Canceled",
    }
    if value in labels:
        return labels[value]

    return value.replace("_", " ").title()


def customer_status_label(value):
    """Collapse internal quote states into the four customer-facing labels."""
    value = (value or "pending_approval").lower().replace("-", "_")

    if value == "approved":
        return "Approved"
    if value == "denied":
        return "Denied"
    if value == "canceled":
        return "Canceled"
    return "Pending Approval"


def safe_next(default_endpoint):
    target = (
        request.args.get("next")
        or request.form.get("next")
        or ""
    ).strip()

    if target.startswith("/") and not target.startswith("//"):
        return target

    return url_for(default_endpoint)


def account_directory_redirect():
    endpoint = request.form.get("return_to")
    if endpoint == "customer_accounts":
        return url_for("portal.customer_accounts")
    return url_for("portal.manage_users")


@portal_bp.get("/")
def landing():
    return render_template("portal_landing.html")


@portal_bp.route("/customer/login", methods=["GET", "POST"])
def customer_login():
    return login("customer")


@portal_bp.route("/employee/login", methods=["GET", "POST"])
def employee_login():
    return login("employee")

@portal_bp.post("/approve-user/<int:user_id>/<decision>")
@require_role("employee")
def approve_user(user_id: int, decision: str):
    statuses = {"approve": "approved", "hold": "hold", "deny": "denied"}
    normalized = (decision or "").lower()
    reviewer = signed_in_user()

    with get_session() as db:
        user = db.get(User, user_id)
        if user and normalized in statuses:
            user.approval_status = statuses[normalized]
            user.is_active = normalized == "approve"
            user.approval_decided_at = datetime.now()
            user.approval_decided_by_user_id = reviewer.id if reviewer else None
            db.commit()

    return redirect(url_for("portal.employee_dashboard"))


def pending_quote_requires_accept(db, quote_id: str | None, user: User | None) -> bool:
    if not quote_id or not quote_id.isdigit() or not user:
        return False

    quote = db.get(Quote, int(quote_id))
    return bool(
        quote
        and quote.status == "pending_approval"
        and quote.assigned_employee_user_id != user.id
    )


def login(role):
    error = None

    if request.method == "POST":
        identity = (
            request.form.get("identity") or ""
        ).strip().lower()

        password = request.form.get("password") or ""

        with get_session() as db:
            user = db.execute(
                select(User).where(
                    User.role == role,
                    User.is_active.is_(True),
                    or_(
                        func.lower(User.username) == identity,
                        func.lower(User.email) == identity,
                    ),
                )
            ).scalar_one_or_none()

            if (
                user
                and user.password_hash
                and check_password_hash(
                    user.password_hash,
                    password,
                )
            ):
                session.clear()
                session["user_id"] = user.id
                session["role"] = user.role

                if role == "customer":
                    endpoint = "portal.customer_dashboard"
                else:
                    endpoint = "portal.employee_dashboard"

                return redirect(safe_next(endpoint))

        error = "The username/email or password did not match."

    return render_template(
        "portal_login.html",
        role=role,
        error=error,
    )


@portal_bp.route(
    "/customer/signup",
    methods=["GET", "POST"],
)
def customer_signup():
    return signup("customer")


@portal_bp.route(
    "/employee/signup",
    methods=["GET", "POST"],
)
def employee_signup():
    return signup("employee")


def signup(role):
    # Set the template early so it is always accessible for GET or POST error paths
    template_file = "customer_signup.html" if role == "customer" else "employee_signup.html"

    error = None

    return_to = (
        request.form.get("return_to")
        if request.method == "POST"
        else request.args.get("return_to")
    ) or ""
    acting_employee = session.get("role") == "employee"

    if request.method == "POST":
        name = (
            request.form.get("display_name") or ""
        ).strip()

        email = (
            request.form.get("email") or ""
        ).strip().lower()

        password = request.form.get("password") or ""
        address = (
            request.form.get("shipping_address") or ""
        ).strip()

        shipping_same_as_billing = None
        same_flag = request.form.get("shipping_same_as_billing")
        if same_flag == "true":
            shipping_same_as_billing = True
        elif same_flag == "false":
            shipping_same_as_billing = False

        def get_form_field(key):
            val = request.form.get(key, "").strip()
            return val if val else None

        if not name or not email or not password:
            error = (
                "Name, email and password are required."
            )
        else:
            with get_session() as db:
                conditions = [
                    func.lower(User.username) == email
                ]

                if email:
                    conditions.append(
                        func.lower(User.email) == email
                    )

                duplicate = db.execute(
                    select(User).where(or_(*conditions))
                ).scalar_one_or_none()

                if duplicate:
                    if duplicate.role == role and not duplicate.is_active:
                        duplicate.display_name = duplicate.display_name or name
                        duplicate.username = email
                        duplicate.email = email or None
                        duplicate.password_hash = generate_password_hash(password)
                        duplicate.company_name = get_form_field("company_name")
                        duplicate.phone = get_form_field("phone")
                        duplicate.phone_extension = get_form_field("phone_extension")
                        duplicate.approval_status = "pending"
                        db.commit()

                        if return_to:
                            return redirect(return_to)

                        return redirect(url_for(f"portal.{role}_login"))
                    error = "That username or email is already in use."
                else:
                    display_name = name

                    # Check for existing display name collisions
                    existing_name = db.execute(
                        select(User).where(
                            func.lower(User.display_name) == name.lower()
                        )
                    ).scalar_one_or_none()

                    if existing_name:
                        display_name = f"{name} ({email})"

                    account_active = True if acting_employee else False

                    user = User(
                        display_name=display_name,
                        username=email,
                        email=email or None,
                        password_hash=generate_password_hash(password),
                        role=role,
                        access_level="standard",
                        company_name=get_form_field("company_name"),
                        phone=get_form_field("phone"),
                        phone_extension=get_form_field("phone_extension"),
                        approval_status="approved" if account_active else "pending",
                        is_active=account_active,
                    )

                    db.add(user)

                    try:
                        db.commit()
                    except IntegrityError:
                        db.rollback()
                        error = "That username or email is already in use."
                    else:
                        if return_to:
                            return redirect(return_to)

                        return redirect(url_for(f"portal.{role}_login"))

        
    return render_template(
        template_file,
        role=role,
        error=error,
        return_to=return_to or request.referrer or "",
        prefill_name=request.args.get("name", "") if request.method == "GET" else "",
        prefill_address=request.args.get("address", "") if request.method == "GET" else "",
        prefill_phone=request.args.get("phone", "") if request.method == "GET" else "",
        prefill_email=request.args.get("email", "") if request.method == "GET" else "",
    )


@portal_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("portal.landing"))


@portal_bp.get("/forgot-access")
@portal_bp.post("/forgot-access")
def forgot_access():
    error = None
    message = None

    if request.method == "POST":
        identity = (request.form.get("identity") or "").strip().lower()
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not identity or not new_password or not confirm_password:
            error = "Username/email, new password and confirmation are required."
        elif new_password != confirm_password:
            error = "The new passwords did not match."
        else:
            with get_session() as db:
                user = db.execute(
                    select(User).where(
                        or_(
                            func.lower(User.username) == identity,
                            func.lower(User.email) == identity,
                        )
                    )
                ).scalar_one_or_none()

                if user:
                    user.password_hash = generate_password_hash(new_password)
                    if not user.is_active and user.approval_status in (None, "approved"):
                        user.approval_status = "pending"
                    db.commit()

            message = (
                "If that account exists, the password has been updated. "
                "Pending accounts still need employee approval before login."
            )

    return render_template(
        "forgot_access.html",
        error=error,
        message=message,
    )


@portal_bp.get("/customer/dashboard")
@require_role("customer")
def customer_dashboard():
    user = signed_in_user()

    with get_session() as db:
        quotes = db.execute(
            select(Quote)
            .where(_customer_quote_filter(user))
            .order_by(
                case((Quote.status == "canceled", 1), else_=0),
                Quote.created_at.desc(),
            )
        ).scalars().all()

        rows = [
            (
                quote,
                total_for(quote),
                customer_status_label(quote.status),
            )
            for quote in quotes
        ]

    return render_template(
        "customer_dashboard.html",
        user=user,
        rows=rows,
    )


@portal_bp.get("/customer/dashboard.css")
def customer_dashboard_css():
    return send_from_directory(
        Path(__file__).resolve().parent / "customer dashboard",
        "customer_dashboard.css",
    )


@portal_bp.get("/customer/quote-form.css")
def customer_quote_css():
    return send_from_directory(
        Path(__file__).resolve().parent / "customer_quote_form",
        "customer_quote_form.css",
    )


@portal_bp.get("/customer/quote-form.js")
def customer_quote_form_js():
    return send_from_directory(
        Path(__file__).resolve().parent / "customer_quote_form",
        "customer_quote_form.js",
    )


@portal_bp.get("/employee/dashboard.css")
def employee_dashboard_css():
    return send_from_directory(
        Path(__file__).resolve().parent / "Employee_dashboard",
        "Employees_dashboard.css",
    )


@portal_bp.get("/employee/dashboard")
@require_role("employee")
def employee_dashboard():
    user = signed_in_user()
    query = (
        request.args.get("q") or ""
    ).strip()

    rows = []
    pending_queue = []
    customer_rows = []

    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)

    with get_session() as db:
        # Fetch new account requests that are awaiting employee approval (not yet assigned to any employee)
        new_accept_users = db.execute(
            select(User)
            .where(
                User.role.in_(["customer", "employee"]),
                User.is_active.is_(False),
                User.approval_decided_at.is_(None),
            )
            .order_by(User.created_at.desc())
            .limit(25)
        ).scalars().all()

        quotes_this_month = db.execute(
            select(func.count(Quote.id)).where(
                Quote.created_by_user_id == user.id,
                Quote.created_at >= month_start,
            )
        ).scalar() or 0

        approved_quotes_this_month = db.execute(
            select(Quote).where(
                Quote.created_by_user_id == user.id,
                Quote.status == "approved",
                Quote.approved_at.is_not(None),
                Quote.approved_at >= month_start,
            )
        ).scalars().all()
        approved_orders_count_this_month = len(approved_quotes_this_month)

        # New accept requests - quotes that are pending approval but not yet assigned to any employee
        new_accept_quotes = db.execute(
            select(Quote)
            .where(
                Quote.status.in_(["new", "pending_approval"]),
                Quote.assigned_employee_user_id.is_(None),
            )
            .order_by(Quote.created_at.asc())
            .limit(25)
        ).scalars().all()
        new_accept_queue = [
            {
                "id": quote.id,
                "quote_id": quote.quote_number,
                "model_code": quote.model_code,
                "customer_name": quote.customer_name,
                "created_at": quote.created_at,
                "status": quote.status,
            }
            for quote in new_accept_quotes
        ]

        # Pending-approval queue for quotes already accepted by the current user.
        # Unassigned quotes belong only in the New Accept Request section.
        pending_quotes = db.execute(
            select(Quote)
            .where(
                Quote.status.in_(["accepted", "pending_approval"]),
                Quote.assigned_employee_user_id == user.id,
            )
            .order_by(Quote.created_at.asc())
            .limit(25)
        ).scalars().all()
        pending_queue = [
            {
                "id": quote.id,
                "quote_id": quote.quote_number,
                "model_code": quote.model_code,
                "customer_name": quote.customer_name,
                "created_at": quote.created_at,
                "status": quote.status,
            }
            for quote in pending_quotes
        ]

        updated_quotes = db.execute(
            select(Quote)
            .where(
                Quote.assigned_employee_user_id == user.id,
                Quote.customer_update_pending.is_(True),
                Quote.status != "canceled",
            )
            .order_by(Quote.edited_at.desc())
        ).scalars().all()
        updated_queue = [
            {
                "id": quote.id,
                "quote_id": quote.quote_number,
                "model_code": quote.model_code,
                "customer_name": quote.customer_name,
                "edited_at": quote.edited_at,
            }
            for quote in updated_quotes
        ]

        if query:
            like = f"%{query}%"

            # Users live in a separate database file, so resolve matching
            # employee/customer ids first instead of a cross-database SQL join.
            matching_user_ids = db.execute(
                select(User.id).where(User.display_name.ilike(like))
            ).scalars().all()

            quotes = db.execute(
                select(Quote)
                .where(
                    or_(
                        Quote.quote_number.ilike(like),
                        Quote.model_code.ilike(like),
                        Quote.customer_name.ilike(like),
                        Quote.customer_address.ilike(like),
                        Quote.status.ilike(like),
                        Quote.created_by_user_id.in_(matching_user_ids),
                        func.json_extract(Quote.order_form_snapshot, "$.order_number").ilike(like),
                    )
                )
                .order_by(Quote.created_at.desc())
                .limit(75)
            ).scalars().all()

            rows = [
                (
                    quote,
                    total_for(quote),
                    status_label(quote.status),
                )
                for quote in quotes
            ]

            customer_rows = db.execute(
                select(Customer)
                .where(
                    or_(
                        Customer.name.ilike(like),
                        Customer.address.ilike(like),
                        Customer.city_state_zip.ilike(like),
                        Customer.phone.ilike(like),
                        Customer.email.ilike(like),
                    )
                )
                .order_by(Customer.name)
                .limit(50)
            ).scalars().all()

    dashboard_template = (
        "Admin_dashboard.html"
        if user.access_level == "admin"
        else "employee_dashboard.html"
    )

    return render_template(
        dashboard_template,
        user=user,
        rows=rows,
        query=query,
        customer_rows=customer_rows,
        quotes_this_month=quotes_this_month,
        approved_orders_count_this_month=approved_orders_count_this_month,
        current_month_label=month_start.strftime("%B"),
        new_accept_users=new_accept_users,
        new_accept_queue=new_accept_queue,
        pending_queue=pending_queue,
        updated_queue=updated_queue,
    )

@portal_bp.post("/employee/quotes/<int:quote_id>/accept")
@require_role("employee")
def accept_pending_quote(quote_id: int):
    """Race-safe acceptance of an unassigned new quote."""
    user = signed_in_user()

    with get_session() as db:
        result = db.execute(
            update(Quote)
            .where(
                Quote.id == quote_id,
                Quote.status.in_(["new", "pending_approval"]),
                Quote.assigned_employee_user_id.is_(None),
            )
            .values(
                status="accepted",
                assigned_employee_user_id=user.id,
                assigned_at=datetime.utcnow(),
            )
        )
        db.commit()

    if result.rowcount == 0:
        return jsonify({
            "ok": False,
            "error": "Already claimed by another employee or not available",
        }), 409

    return jsonify({"ok": True, "quote_id": quote_id}), 200


@portal_bp.post("/employee/quotes/<int:quote_id>/delete")
@require_role("employee")
def delete_pending_quote(quote_id: int):
    """Delete a pending-approval quote that the current employee has claimed."""
    user = signed_in_user()

    with get_session() as db:
        quote = db.get(Quote, quote_id)
        if (
            quote is None
            or quote.status != "pending_approval"
            or quote.assigned_employee_user_id != user.id
        ):
            return jsonify({
                "ok": False,
                "error": "Quote not found or not claimed by you",
            }), 404

        db.delete(quote)
        db.commit()

    return jsonify({"ok": True, "quote_id": quote_id}), 200


@portal_bp.get("/employee/history")
@require_role("employee")
def employee_history():
    user = signed_in_user()
    query = (request.args.get("q") or "").strip()

    with get_session() as db:
        stmt = (
            select(Quote)
            .where(
                or_(
                    Quote.created_by_user_id == user.id,
                    Quote.assigned_employee_user_id == user.id,
                )
            )
            .where(Quote.status.notin_(["accepted", "pending_approval", "canceled"]))
        )
        if query:
            like = f"%{query}%"
            # Users live in a separate database file, so resolve matching
            # employee/customer ids first instead of a cross-database SQL join.
            matching_user_ids = db.execute(
                select(User.id).where(User.display_name.ilike(like))
            ).scalars().all()
            stmt = stmt.where(
                or_(
                    Quote.quote_number.ilike(like),
                    Quote.model_code.ilike(like),
                    Quote.customer_name.ilike(like),
                    Quote.customer_address.ilike(like),
                    Quote.status.ilike(like),
                    Quote.created_by_user_id.in_(matching_user_ids),
                    Quote.assigned_employee_user_id.in_(matching_user_ids),
                    func.json_extract(Quote.order_form_snapshot, "$.order_number").ilike(like),
                )
            )

        order_number = func.json_extract(Quote.order_form_snapshot, "$.order_number")
        order_submission_priority = case(
            (func.coalesce(order_number, "") == "", 0),
            else_=1,
        )
        quotes = db.execute(
            stmt.order_by(
                case((Quote.status == "denied", 1), else_=0),
                order_submission_priority,
                Quote.created_at.desc(),
            ).limit(25)
        ).scalars().all()

        rows = [
            (
                quote,
                total_for(quote),
                status_label(quote.status),
            )
            for quote in quotes
        ]

    return render_template(
        "employee_history.html",
        user=user,
        rows=rows,
        query=query,
    )


@portal_bp.get("/employee/quote-history")
@require_role("employee")
def employee_quote_history():
    user = signed_in_user()
    query = (request.args.get("q") or "").strip()

    with get_session() as db:
        stmt = select(Quote).where(Quote.status != "canceled")
        if query:
            like = f"%{query}%"
            # Users live in a separate database file, so resolve matching
            # employee/customer ids first instead of a cross-database SQL join.
            matching_user_ids = db.execute(
                select(User.id).where(User.display_name.ilike(like))
            ).scalars().all()
            stmt = stmt.where(
                or_(
                    Quote.quote_number.ilike(like),
                    Quote.model_code.ilike(like),
                    Quote.customer_name.ilike(like),
                    Quote.customer_address.ilike(like),
                    Quote.status.ilike(like),
                    Quote.created_by_user_id.in_(matching_user_ids),
                    func.json_extract(Quote.order_form_snapshot, "$.order_number").ilike(like),
                )
            )
        quote_action_priority = case(
            (
                or_(
                    Quote.status != "pending_approval",
                    Quote.assigned_employee_user_id == user.id,
                ),
                0,
            ),
            else_=1,
        )
        quotes = db.execute(
            stmt.order_by(
                case((Quote.status == "denied", 1), else_=0),
                quote_action_priority,
                Quote.created_at.desc(),
            ).limit(25)
        ).scalars().all()

        rows = [
            (quote, total_for(quote), status_label(quote.status))
            for quote in quotes
        ]

    return render_template(
        "employee_quote_history.html",
        user=user,
        rows=rows,
        query=query,
    )


@portal_bp.get("/customer/quote-entry")
@require_role("customer")
def customer_quote_entry():
    user = signed_in_user()
    # Customer quote entry is the calculator only. The dedicated customer
    # quote-form route is the sole route that renders the canonical form.
    return render_template(
        "customer_calculator.html",
        portal_mode="customer",
        current_user_name=user.display_name if user else "",
        prefill_customer_name=user.company_name or user.display_name or "",
        prefill_customer_address=user.billing_address or user.shipping_address or "",
        assigned_promo_code=user.assigned_promo_code or "",
        assigned_discount_percent=user.assigned_discount_percent,
    )


@portal_bp.get("/customer/quote-form")
@require_role("customer")
def customer_quote_form():
    user = signed_in_user()
    return render_template(
        "customer_quote_form/customer_quote_form.html",
        current_user_name=user.display_name if user else "",
        prefill_customer_name=user.company_name or user.display_name or "",
        prefill_customer_address=user.billing_address or user.shipping_address or "",
        is_existing_quote=bool(request.args.get("quote_id") or request.args.get("quote_number")) and request.args.get("new") != "1",
    )


@portal_bp.get("/quote_form_customer")
def legacy_customer_quote_form():
    return redirect(url_for("portal.customer_quote_form", **request.args.to_dict(flat=True)))


@portal_bp.get("/employee/quote-entry")
@require_role("employee")
def employee_quote_entry():
    user = signed_in_user()
    # A quote_id (opening a saved quote) or draft flag (from the "Quote" button)
    # goes straight to the dedicated Quote Form page instead of the calculator.
    quote_id = request.args.get("quote_id")
    if quote_id:
        with get_session() as db:
            if pending_quote_requires_accept(db, quote_id, user):
                flash("Accept the pending quote before opening it.", "error")
                return redirect(url_for("portal.employee_dashboard"))

    if quote_id or request.args.get("draft"):
        return render_template(
            "employee_quote_forms.html",
            current_user_name=user.display_name if user else "",
        )
    return render_template(
        "employee_calculator.html",
        portal_mode="employee",
        current_user_name=user.display_name if user else "",
    )


@portal_bp.get("/metric-coming-soon")
def metric_coming_soon():
    return render_template(
        "portal_message.html",
        title="Metric Calculator",
        message="Metric Calculator Coming Soon",
    )


@portal_bp.get("/portal/api/search")
@require_role("employee")
def search_suggestions():
    query = (
        request.args.get("q") or ""
    ).strip()

    if len(query) < 2:
        return jsonify({
            "ok": True,
            "results": [],
        })

    like = f"%{query}%"

    with get_session() as db:
        quotes = db.execute(
            select(Quote)
            .where(
                or_(
                    Quote.quote_number.ilike(like),
                    Quote.model_code.ilike(like),
                    Quote.customer_name.ilike(like),
                    Quote.customer_address.ilike(like),
                    func.json_extract(Quote.order_form_snapshot, "$.order_number").ilike(like),
                )
            )
            .order_by(Quote.created_at.desc())
            .limit(10)
        ).scalars().all()

        customers = db.execute(
            select(Customer)
            .where(
                or_(
                    Customer.name.ilike(like),
                    Customer.address.ilike(like),
                    Customer.city_state_zip.ilike(like),
                    Customer.phone.ilike(like),
                    Customer.email.ilike(like),
                )
            )
            .order_by(Customer.name)
            .limit(5)
        ).scalars().all()

        results = [
            {
                "type": "quote",
                "id": quote.id,
                "quote_number": quote.quote_number,
                "customer": quote.customer_name or "",
                "model_code": quote.model_code or "",
            }
            for quote in quotes
        ]

        results.extend([
            {
                "type": "customer",
                "id": customer.id,
                "name": customer.name,
                "address": customer.address or "",
                "phone": customer.phone or "",
            }
            for customer in customers
        ])

    return jsonify({
        "ok": True,
        "results": results,
    })


@portal_bp.get(
    "/portal/api/quotes/<int:quote_id>"
)
def portal_quote(quote_id):
    user = signed_in_user()

    if not user:
        return jsonify({
            "ok": False,
            "error": "Login required",
        }), 401

    with get_session() as db:
        quote = db.get(Quote, quote_id)

        if not quote:
            return jsonify({
                "ok": False,
                "error": "Quote not found",
            }), 404

        if (
            user.role == "customer"
            and not _customer_owns_quote(user, quote)
        ):
            return jsonify({
                "ok": False,
                "error": "Quote not found",
            }), 404

        data = quote_to_json(quote)

        if user.role == "customer":
            data.pop(
                "price_breakdown_snapshot",
                None,
            )

            data["manual_line_items"] = [
                {
                    key: value
                    for key, value in item.items()
                    if key != "internal_note"
                }
                for item in data.get(
                    "manual_line_items",
                    [],
                )
                if item.get(
                    "show_on_customer_quote",
                    True,
                )
            ]

    return jsonify({
        "ok": True,
        "quote": data,
    })


@portal_bp.get("/manage-users")
@require_role("employee")
def manage_users():
    user = signed_in_user()
    with get_session() as db:
        # Employee management stays separate from customer account management.
        approved_users = db.scalars(
            select(User)
            .where(User.is_active == True, User.role == "employee")
            .order_by(User.display_name.asc())
        ).all()

    return render_template(
        "manage_users.html",
        user=user,
        users=approved_users,
        directory_type="employee",
    )


@portal_bp.get("/customer-accounts")
@require_role("employee")
def customer_accounts():
    user = signed_in_user()
    with get_session() as db:
        customer_users = db.scalars(
            select(User)
            .where(User.is_active == True, User.role == "customer")
            .order_by(User.display_name.asc())
        ).all()

    return render_template(
        "customer_accounts.html",
        user=user,
        users=customer_users,
        directory_type="customer",
    )


@portal_bp.get("/parts-catalog")
@require_admin
def parts_catalog():
    user = signed_in_user()
    return render_template(
        "parts_catalog.html",
        user=user,
        **catalog_page_data(),
    )


@portal_bp.post("/parts-catalog/price")
@require_admin
def update_parts_catalog_price():
    payload = request.get_json(silent=True) or {}
    try:
        result = update_pricing_amount(
            payload.get("table"),
            payload.get("id"),
            payload.get("field"),
            payload.get("value"),
            actor=signed_in_user(),
        )
    except PriceUpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.post("/parts-catalog/bulk-price/preview")
@require_admin
def preview_parts_catalog_bulk_price():
    payload = request.get_json(silent=True) or {}
    try:
        result = preview_bulk_price_update(
            payload.get("table"),
            payload.get("field"),
            payload.get("ids") or [],
            payload.get("method"),
            payload.get("amount"),
        )
    except PriceUpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.post("/parts-catalog/bulk-price/apply")
@require_admin
def apply_parts_catalog_bulk_price():
    payload = request.get_json(silent=True) or {}
    try:
        result = apply_bulk_price_update(
            payload.get("table"),
            payload.get("field"),
            payload.get("ids") or [],
            payload.get("method"),
            payload.get("amount"),
            actor=signed_in_user(),
            context=(payload.get("context") or "")[:120],
        )
    except PriceUpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.post("/parts-catalog/bulk-price/workbook-preview")
@require_admin
def preview_parts_catalog_workbook():
    try:
        result = parse_price_workbook(
            request.files.get("workbook"),
            (request.form.get("field") or "sell_price").strip(),
        )
    except PriceUpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.post("/parts-catalog/bulk-price/workbook-apply")
@require_admin
def apply_parts_catalog_workbook():
    payload = request.get_json(silent=True) or {}
    try:
        field = (payload.get("field") or "sell_price").strip()
        result = apply_workbook_price_update(
            field,
            payload.get("updates") or [],
            actor=signed_in_user(),
            source_name=(payload.get("source_name") or "")[:120],
        )
    except PriceUpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.get("/parts-catalog/price-template.xlsx")
@require_admin
def download_parts_catalog_price_template():
    return send_file(
        build_price_template_workbook(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="jit_price_update_template.xlsx",
    )


@portal_bp.get("/parts-catalog/price-history")
@require_admin
def parts_catalog_price_history():
    return jsonify({"ok": True, "changes": recent_price_changes(request.args.get("limit", type=int) or 50)})


@portal_bp.post("/parts-catalog/price-history/<int:change_id>/restore")
@require_admin
def restore_parts_catalog_price(change_id: int):
    try:
        result = restore_price_change(change_id, actor=signed_in_user())
    except PriceUpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.get("/parts-catalog/conflict/<int:row_id>")
@require_admin
def parts_catalog_conflict(row_id: int):
    field = request.args.get("field") or "sell_price"
    try:
        result = get_conflict_details(row_id, field)
    except PriceUpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.post("/parts-catalog/conflict/<int:row_id>/resolve")
@require_admin
def resolve_parts_catalog_conflict(row_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        result = resolve_conflict(
            row_id,
            payload.get("field") or "sell_price",
            payload.get("resolution"),
            payload.get("source_name"),
            payload.get("value"),
            actor=signed_in_user(),
        )
    except PriceUpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.post("/parts-catalog/parts")
@require_admin
def create_parts_catalog_part():
    payload = request.get_json(silent=True) or {}
    try:
        result = create_catalog_part(payload, actor=signed_in_user())
    except PriceUpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.get("/parts-catalog/parts/<int:row_id>")
@require_admin
def get_parts_catalog_part(row_id: int):
    try:
        result = get_catalog_part(row_id)
    except PriceUpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, "part": result})


@portal_bp.post("/parts-catalog/parts/<int:row_id>")
@require_admin
def update_parts_catalog_part(row_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        result = update_catalog_part(row_id, payload, actor=signed_in_user())
    except PriceUpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.post("/parts-catalog/inventory/bulk")
@require_admin
def update_parts_catalog_inventory_bulk():
    payload = request.get_json(silent=True) or {}
    try:
        result = update_catalog_inventory_bulk(
            payload.get("ids") or [],
            payload.get("inventory"),
            actor=signed_in_user(),
        )
    except PriceUpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.get("/parts-catalog/families")
@require_admin
def parts_catalog_families():
    return jsonify({"ok": True, "families": list_families()})


@portal_bp.post("/parts-catalog/families")
@require_admin
def create_parts_catalog_family():
    try:
        result = create_family(request.get_json(silent=True) or {})
    except FamilyError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, "family": result})


@portal_bp.post("/parts-catalog/families/<int:family_id>")
@require_admin
def update_parts_catalog_family(family_id: int):
    try:
        result = update_family(family_id, request.get_json(silent=True) or {})
    except FamilyError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, "family": result})


@portal_bp.get("/parts-catalog/families/<int:family_id>/preview")
@require_admin
def preview_parts_catalog_family(family_id: int):
    try:
        result = preview_family(family_id)
    except FamilyError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.post("/parts-catalog/families/<int:family_id>/image")
@require_admin
def upload_parts_catalog_family_image(family_id: int):
    try:
        result = save_family_image(family_id, request.files.get("image"))
    except FamilyError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, "family": result})


@portal_bp.post("/parts-catalog/families/assign")
@require_admin
def assign_parts_catalog_family():
    payload = request.get_json(silent=True) or {}
    try:
        result = assign_parts(payload.get("family_code"), payload.get("ids") or [])
    except FamilyError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    return jsonify({"ok": True, **result})


@portal_bp.route("/employee/admin/ai-usage-dashboard", methods=["GET", "POST"])
@require_admin
def ai_usage_dashboard():
    user = signed_in_user()

    def _parse_filter_date(raw_value: str | None):
        if not raw_value:
            return None
        try:
            return datetime.strptime(raw_value, "%Y-%m-%d").date()
        except ValueError:
            return None

    start_date = _parse_filter_date(request.args.get("start_date"))
    end_date = _parse_filter_date(request.args.get("end_date"))

    if request.method == "POST":
        try:
            ai_usage_service.add_credit_entry(
                (request.form.get("entry_date") or "").strip(),
                (request.form.get("credits_used") or "").strip(),
                (request.form.get("credits_remaining") or "").strip(),
                request.form.get("note"),
            )
            flash("Credit entry saved.", "success")
        except ai_usage_service.CreditEntryError as exc:
            flash(str(exc), "error")
        return redirect(url_for("portal.ai_usage_dashboard", **request.args.to_dict(flat=True)))

    return render_template(
        "ai_usage_dashboard_simplified.html",
        user=user,
        data=ai_usage_service.get_dashboard_data(start_date, end_date),
    )


@portal_bp.post("/manage-users/<int:user_id>/password")
@require_role("employee")
def update_user_password(user_id: int):
    new_password = (request.form.get("new_password") or "").strip()

    if not new_password:
        flash("Enter a new password before saving.", "error")
        return redirect(account_directory_redirect())

    with get_session() as db:
        target_user = db.get(User, user_id)
        if target_user:
            target_user.password_hash = generate_password_hash(new_password)
            db.commit()
            flash(f"Password updated for '{target_user.display_name}'.", "success")

    return redirect(account_directory_redirect())


@portal_bp.post("/manage-users/<int:user_id>/access-level")
@require_role("employee")
def update_user_access_level(user_id: int):
    access_level = (request.form.get("access_level") or "standard").strip().lower()
    allowed_levels = {"standard", "admin"}

    if access_level not in allowed_levels:
        flash("Choose a valid access level.", "error")
        return redirect(account_directory_redirect())

    with get_session() as db:
        target_user = db.get(User, user_id)
        if target_user and target_user.role == "employee":
            target_user.access_level = access_level
            db.commit()
            flash(f"Access level updated for '{target_user.display_name}'.", "success")

    return redirect(account_directory_redirect())


@portal_bp.post("/delete-user/<int:user_id>")
@require_role("employee")
def delete_user(user_id: int):
    current_user = signed_in_user()
    
    with get_session() as db:
        target_user = db.get(User, user_id)
        if target_user:
            # Prevent an employee from deleting their own active account
            if current_user and current_user.id == target_user.id:
                flash("You cannot delete your own active account.", "error")
                return redirect(account_directory_redirect())
                
            db.delete(target_user)
            db.commit()
            flash(f"User account for '{target_user.display_name}' was permanently deleted.", "success")
            
    # Redirect back to caller (either dashboard or manage users page)
    return redirect(account_directory_redirect())