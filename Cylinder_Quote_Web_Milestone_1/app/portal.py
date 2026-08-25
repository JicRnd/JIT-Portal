from __future__ import annotations
from flask import render_template, request, redirect, url_for, flash
from datetime import datetime
from functools import wraps
from os import name

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_session
from .models_db import Customer, Quote, User
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

    if value == "approved":
        return "Approved"

    return "Approval Pending"


def safe_next(default_endpoint):
    target = (
        request.args.get("next")
        or request.form.get("next")
        or ""
    ).strip()

    if target.startswith("/") and not target.startswith("//"):
        return target

    return url_for(default_endpoint)


@portal_bp.get("/")
def landing():
    return render_template("portal_landing.html")


@portal_bp.route("/customer/login", methods=["GET", "POST"])
def customer_login():
    return login("customer")


@portal_bp.route("/employee/login", methods=["GET", "POST"])
def employee_login():
    return login("employee")

@portal_bp.post("/approve-user/<int:user_id>")
@require_role("employee")
def approve_user(user_id: int):
    with get_session() as db:
        user = db.get(User, user_id)
        if user:
            user.is_active = True
            db.commit()

    return redirect(url_for("portal.employee_dashboard"))

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
                    endpoint = "portal.customer_history"
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

            # Helper for form extraction and whitespace stripping
            def get_form_field(key):
                val = request.form.get(key, "").strip()
                return val if val else None

            account_active = True if acting_employee else False

            user = User(
                display_name=display_name,
                username=email,
                email=email or None,
                password_hash=generate_password_hash(password),
                role=role,
                company_name=get_form_field("company_name"),
                phone=get_form_field("phone"),
                phone_extension=get_form_field("phone_extension"),
                is_active=account_active,
            )

            db.add(user)

            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                error = "That username or email is already in use."
            else:
                if user and check_password_hash(user.password_hash, password):
                    if not user.is_active:
                        error = "Your account is pending approval by an employee. Please check back later."
                    
                    else:
                        session.clear()
                    session["user_id"] = user.id
                    session["role"] = user.role

                if return_to:
                    return redirect(return_to)

                endpoint = (
                    "portal.customer_history" if role == "customer" else "portal.employee_dashboard"
                )
                return redirect(url_for("portal.login"))

        
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
def forgot_access():
    return render_template(
        "portal_message.html",
        title="Account Recovery",
        message=(
            "Email recovery will be connected later. "
            "Please contact JIT for access for now."
        ),
    )


@portal_bp.get("/customer/history")
@require_role("customer")
def customer_history():
    user = signed_in_user()

    with get_session() as db:
        quotes = db.execute(
            select(Quote)
            .where(
                Quote.created_by_user_id == user.id
            )
            .order_by(Quote.created_at.desc())
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
        "customer_history.html",
        user=user,
        rows=rows,
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
        # Fetch inactive user accounts awaiting approval
        pending_users = db.execute(
            select(User)
            .where(User.is_active == True)
            .order_by(User.id.desc())
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

        # Pending-approval queue for quotes
        pending_quotes = db.execute(
            select(Quote)
            .where(
                Quote.status == "pending_approval",
                or_(
                    Quote.assigned_employee_user_id.is_(None),
                    Quote.assigned_employee_user_id == user.id,
                ),
            )
            .order_by(Quote.created_at.asc())
            .limit(50)
        ).scalars().all()
        pending_queue = [
            {
                "id": quote.id,
                "quote_id": quote.quote_number,
                "model_code": quote.model_code,
                "customer_name": quote.customer_name,
                "created_at": quote.created_at,
                "claimed_by_me": quote.assigned_employee_user_id == user.id,
            }
            for quote in pending_quotes
        ]

        updated_quotes = db.execute(
            select(Quote)
            .where(
                Quote.assigned_employee_user_id == user.id,
                Quote.customer_update_pending.is_(True),
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

    return render_template(
        "employee_dashboard.html",
        user=user,
        rows=rows,
        query=query,
        customer_rows=customer_rows,
        quotes_this_month=quotes_this_month,
        approved_orders_count_this_month=approved_orders_count_this_month,
        pending_queue=pending_queue,
        updated_queue=updated_queue,
        pending_users=pending_users,
    )

@portal_bp.post("/employee/quotes/<int:quote_id>/accept")
@require_role("employee")
def accept_pending_quote(quote_id: int):
    """Race-safe claim of an unassigned pending-approval quote."""
    user = signed_in_user()

    with get_session() as db:
        result = db.execute(
            update(Quote)
            .where(
                Quote.id == quote_id,
                Quote.status == "pending_approval",
                Quote.assigned_employee_user_id.is_(None),
            )
            .values(
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


@portal_bp.get("/employee/history")
@require_role("employee")
def employee_history():
    user = signed_in_user()
    query = (request.args.get("q") or "").strip()

    with get_session() as db:
        stmt = select(Quote).where(Quote.created_by_user_id == user.id)
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

        quotes = db.execute(
            stmt.order_by(Quote.created_at.desc())
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
        stmt = select(Quote)
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
        quotes = db.execute(
            stmt.order_by(Quote.created_at.desc()).limit(200)
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
    # A quote_id (opening a saved quote) or draft flag (from the "Quote" button)
    # goes straight to the dedicated Quote Form page instead of the calculator.
    if request.args.get("quote_id") or request.args.get("draft"):
        return render_template(
            "quote_form_customer.html",
            current_user_name=user.display_name if user else "",
            prefill_customer_name=user.company_name or user.display_name or "",
            prefill_customer_address=user.billing_address or user.shipping_address or "",
        )
    return render_template(
        "index.html",
        portal_mode="customer",
        current_user_name=user.display_name if user else "",
        prefill_customer_name=user.company_name or user.display_name or "",
        prefill_customer_address=user.billing_address or user.shipping_address or "",
        assigned_promo_code=user.assigned_promo_code or "",
        assigned_discount_percent=user.assigned_discount_percent,
    )


@portal_bp.get("/employee/quote-entry")
@require_role("employee")
def employee_quote_entry():
    user = signed_in_user()
    # A quote_id (opening a saved quote) or draft flag (from the "Quote" button)
    # goes straight to the dedicated Quote Form page instead of the calculator.
    if request.args.get("quote_id") or request.args.get("draft"):
        return render_template(
            "quote_form_employee.html",
            current_user_name=user.display_name if user else "",
        )
    return render_template(
        "index.html",
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
            and quote.created_by_user_id != user.id
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
        # Fetch all approved, active users
        approved_users = db.scalars(
            select(User)
            .where(User.is_active == True)
            .order_by(User.display_name.asc())
        ).all()
        
    return render_template("manage_users.html", user=user, users=approved_users)


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
                return redirect(url_for("portal.manage_users"))
                
            db.delete(target_user)
            db.commit()
            flash(f"User account for '{target_user.display_name}' was permanently deleted.", "success")
            
    # Redirect back to caller (either dashboard or manage users page)
    return_to = request.referrer or url_for("portal.manage_users")
    return redirect(return_to)