from __future__ import annotations

import py_compile
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
TEMPLATES = APP / "templates"
STATIC = APP / "static"


def stop(message: str) -> None:
    print(f"\nERROR: {message}\n")
    raise SystemExit(1)


def write(relative: str, content: str) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    print(f"Created/updated: {relative}")


def replace_once(relative: str, old: str, new: str, marker: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")

    if marker in text:
        print(f"Already installed: {relative} ({marker})")
        return

    if old not in text:
        stop(
            f"Could not find the expected installation point in {relative}. "
            "No replacement was made in that file."
        )

    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Connected: {relative}")


def validate_project() -> None:
    required = [
        APP / "web.py",
        APP / "db.py",
        APP / "models_db.py",
        APP / "current_user.py",
        TEMPLATES / "index.html",
        STATIC / "app.js",
    ]

    missing = [str(path) for path in required if not path.exists()]

    if missing:
        stop(
            "Save BUILD_JIT_PORTAL.py inside the "
            "Cylinder_Quote_Web_Milestone_1 folder. Missing: "
            + ", ".join(missing)
        )


PORTAL_PY = r'''
from __future__ import annotations

from functools import wraps

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_session
from .models_db import Quote, User
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
    error = None

    if request.method == "POST":
        name = (
            request.form.get("display_name") or ""
        ).strip()

        username = (
            request.form.get("username") or ""
        ).strip()

        email = (
            request.form.get("email") or ""
        ).strip().lower()

        password = request.form.get("password") or ""

        if not name or not username or not password:
            error = (
                "Name, username and password are required."
            )

        elif role == "customer" and not email:
            error = "Email is required for a customer account."

        else:
            with get_session() as db:
                conditions = [
                    func.lower(User.username)
                    == username.lower()
                ]

                if email:
                    conditions.append(
                        func.lower(User.email) == email
                    )

                duplicate = db.execute(
                    select(User).where(or_(*conditions))
                ).scalar_one_or_none()

                if duplicate:
                    error = (
                        "That username or email is already in use."
                    )

                else:
                    display_name = name

                    existing_name = db.execute(
                        select(User).where(
                            func.lower(User.display_name)
                            == name.lower()
                        )
                    ).scalar_one_or_none()

                    if existing_name:
                        display_name = (
                            f"{name} ({username})"
                        )

                    user = User(
                        display_name=display_name,
                        username=username,
                        email=email or None,
                        password_hash=generate_password_hash(
                            password
                        ),
                        role=role,
                        company_name=(
                            request.form.get("company_name")
                            or ""
                        ).strip() or None,
                        phone=(
                            request.form.get("phone")
                            or ""
                        ).strip() or None,
                        phone_extension=(
                            request.form.get("phone_extension")
                            or ""
                        ).strip() or None,
                        shipping_name=(
                            request.form.get("shipping_name")
                            or ""
                        ).strip() or None,
                        shipping_address=(
                            request.form.get("shipping_address")
                            or ""
                        ).strip() or None,
                        billing_address=(
                            request.form.get("billing_address")
                            or ""
                        ).strip() or None,
                        is_active=True,
                    )

                    db.add(user)

                    try:
                        db.commit()

                    except IntegrityError:
                        db.rollback()
                        error = (
                            "That username or email "
                            "is already in use."
                        )

                    else:
                        session.clear()
                        session["user_id"] = user.id
                        session["role"] = user.role

                        if role == "customer":
                            endpoint = (
                                "portal.customer_history"
                            )
                        else:
                            endpoint = (
                                "portal.employee_dashboard"
                            )

                        return redirect(
                            url_for(endpoint)
                        )

    return render_template(
        "portal_signup.html",
        role=role,
        error=error,
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

    if query:
        like = f"%{query}%"

        with get_session() as db:
            quotes = db.execute(
                select(Quote)
                .join(
                    User,
                    Quote.created_by_user_id == User.id,
                )
                .where(
                    or_(
                        Quote.quote_number.ilike(like),
                        Quote.model_code.ilike(like),
                        Quote.customer_name.ilike(like),
                        Quote.customer_address.ilike(like),
                        Quote.status.ilike(like),
                        User.display_name.ilike(like),
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

    return render_template(
        "employee_dashboard.html",
        user=user,
        rows=rows,
        query=query,
    )


@portal_bp.get("/employee/history")
@require_role("employee")
def employee_history():
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
        "employee_history.html",
        user=user,
        rows=rows,
    )


@portal_bp.get("/customer/quote-entry")
@require_role("customer")
def customer_quote_entry():
    return render_template(
        "index.html",
        portal_mode="customer",
    )


@portal_bp.get("/employee/quote-entry")
@require_role("employee")
def employee_quote_entry():
    return render_template(
        "index.html",
        portal_mode="employee",
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
                )
            )
            .order_by(Quote.created_at.desc())
            .limit(10)
        ).scalars().all()

        results = [
            {
                "id": quote.id,
                "quote_number": quote.quote_number,
                "customer": quote.customer_name or "",
                "model_code": quote.model_code or "",
            }
            for quote in quotes
        ]

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
'''


LANDING_HTML = r'''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width,initial-scale=1"
  >
  <title>JIT Landing Page</title>
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_common.css') }}"
  >
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_landing.css') }}"
  >
</head>
<body class="landing-page">
  <header>
    <nav>
      <a href="{{ url_for('portal.customer_login') }}">
        Customer Login
      </a>
      <a href="{{ url_for('portal.employee_login') }}">
        Employee Login
      </a>
    </nav>

    <h1>JIT Landing Page</h1>
  </header>

  <main class="landing-card">
    <img
      src="{{ url_for('static', filename='quote_form_logo.png') }}"
      alt="JIT Cylinders"
    >

    <p>Quoting and order portal</p>

    <div class="landing-actions">
      <a
        class="portal-button"
        href="{{ url_for('portal.customer_login') }}"
      >
        Customer Login
      </a>

      <a
        class="portal-button light"
        href="{{ url_for('portal.employee_login') }}"
      >
        Employee Login
      </a>
    </div>
  </main>
</body>
</html>
'''


LOGIN_HTML = r'''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width,initial-scale=1"
  >
  <title>{{ role|title }} Login</title>
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_common.css') }}"
  >
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_auth.css') }}"
  >
</head>
<body class="auth-page">
  <main class="auth-card">
    <a
      class="back-link"
      href="{{ url_for('portal.landing') }}"
    >
      ← JIT Landing Page
    </a>

    <img
      src="{{ url_for('static', filename='quote_form_logo.png') }}"
      alt="JIT Cylinders"
    >

    <h1>{{ role|title }} Login</h1>

    {% if error %}
      <p class="form-error">{{ error }}</p>
    {% endif %}

    <form method="post">
      <label>
        Username or Email
        <input
          name="identity"
          autocomplete="username"
          required
          autofocus
        >
      </label>

      <label>
        Password
        <input
          name="password"
          type="password"
          autocomplete="current-password"
          required
        >
      </label>

      <button
        class="portal-button"
        type="submit"
      >
        Login
      </button>
    </form>

    <a href="{{ url_for('portal.forgot_access') }}">
      Forgot username or password?
    </a>

    <hr>

    <a
      class="portal-button secondary"
      href="{{ url_for(
        'portal.customer_signup'
        if role == 'customer'
        else 'portal.employee_signup'
      ) }}"
    >
      {{
        'New Customer Sign Up'
        if role == 'customer'
        else 'New Employee'
      }}
    </a>
  </main>
</body>
</html>
'''


SIGNUP_HTML = r'''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width,initial-scale=1"
  >
  <title>New {{ role|title }} Account</title>
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_common.css') }}"
  >
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_auth.css') }}"
  >
</head>
<body class="auth-page">
  <main class="auth-card wide">
    <a
      class="back-link"
      href="{{ url_for(
        'portal.customer_login'
        if role == 'customer'
        else 'portal.employee_login'
      ) }}"
    >
      ← Back to Login
    </a>

    <h1>New {{ role|title }} Account</h1>

    {% if error %}
      <p class="form-error">{{ error }}</p>
    {% endif %}

    <form method="post" class="signup-grid">
      <label>
        Full Name
        <input name="display_name" required>
      </label>

      <label>
        Company
        {% if role == 'employee' %}
          (optional)
        {% endif %}
        <input name="company_name">
      </label>

      <label>
        Username
        <input
          name="username"
          required
          autocomplete="username"
        >
      </label>

      <label>
        Email
        {% if role == 'employee' %}
          (optional)
        {% endif %}
        <input
          name="email"
          type="email"
          {% if role == 'customer' %}required{% endif %}
        >
      </label>

      <label>
        Password
        <input
          name="password"
          type="password"
          required
          autocomplete="new-password"
        >
      </label>

      <label>
        Phone
        <input name="phone" type="tel">
      </label>

      <label>
        Extension
        <input name="phone_extension">
      </label>

      {% if role == 'customer' %}
        <label>
          Shipping Name
          <input name="shipping_name">
        </label>

        <label class="full">
          Shipping Address
          <textarea name="shipping_address"></textarea>
        </label>

        <label class="full">
          Billing Address
          <textarea name="billing_address"></textarea>
        </label>
      {% endif %}

      <button
        class="portal-button full"
        type="submit"
      >
        Set Account and Continue
      </button>
    </form>
  </main>
</body>
</html>
'''


HISTORY_TABLE = r'''
{% if rows %}
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Order ID</th>
          <th>Model Code</th>
          <th>Customer</th>
          <th>Date</th>
          <th>Total</th>
          <th>Status</th>
          <th></th>
        </tr>
      </thead>

      <tbody>
        {% for quote, total, status in rows %}
          <tr>
            <td>{{ quote.quote_number }}</td>
            <td>{{ quote.model_code or '—' }}</td>
            <td>{{ quote.customer_name or '—' }}</td>

            <td>
              {{
                quote.created_at.strftime('%b %d, %Y')
                if quote.created_at
                else '—'
              }}
            </td>

            <td>${{ '%.2f'|format(total) }}</td>

            <td>
              <span class="status {{
                'approved'
                if status == 'Approved'
                else 'pending'
              }}">
                {{ status }}
              </span>
            </td>

            <td>
              <a
                class="small-button"
                href="{{ entry_url }}?quote_id={{ quote.id }}"
              >
                Open
              </a>
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
{% else %}
  <div class="empty-state">
    No saved quotes or orders yet.
  </div>
{% endif %}
'''


CUSTOMER_HISTORY = r'''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width,initial-scale=1"
  >
  <title>Customer History</title>
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_common.css') }}"
  >
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_history.css') }}"
  >
</head>
<body>
  <header class="portal-header">
    <div>{{ user.display_name }}</div>
    <h1>Customer History</h1>
    <a href="{{ url_for('portal.logout') }}">Log Out</a>
  </header>

  <main class="portal-shell">
    <div class="page-actions">
      <button
        class="portal-button new-quote"
        data-standard="{{ url_for('portal.customer_quote_entry') }}"
        data-metric="{{ url_for('portal.metric_coming_soon') }}"
      >
        + New Quote
      </button>
    </div>

    {% set entry_url=url_for('portal.customer_quote_entry') %}
''' + HISTORY_TABLE + r'''
  </main>

  <div class="quote-modal" hidden>
    <div>
      <h2>Select Measurement Type</h2>
      <button class="portal-button standard-choice">
        Standard
      </button>
      <button class="portal-button secondary metric-choice">
        Metric
      </button>
      <button class="text-button modal-close">
        Cancel
      </button>
    </div>
  </div>

  <script
    src="{{ url_for('static', filename='portal.js') }}"
  ></script>
</body>
</html>
'''


EMPLOYEE_HISTORY = r'''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width,initial-scale=1"
  >
  <title>Employee Order History</title>
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_common.css') }}"
  >
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_history.css') }}"
  >
</head>
<body>
  <header class="portal-header">
    <div>{{ user.display_name }}</div>
    <h1>My Order History</h1>
    <a href="{{ url_for('portal.employee_dashboard') }}">
      Dashboard
    </a>
  </header>

  <main class="portal-shell">
    <div class="page-actions">
      <a
        class="small-button"
        href="{{ url_for('portal.employee_dashboard') }}"
      >
        ← Dashboard
      </a>

      <button
        class="portal-button new-quote"
        data-standard="{{ url_for('portal.employee_quote_entry') }}"
        data-metric="{{ url_for('portal.metric_coming_soon') }}"
      >
        + New Quote
      </button>
    </div>

    {% set entry_url=url_for('portal.employee_quote_entry') %}
''' + HISTORY_TABLE + r'''
  </main>

  <div class="quote-modal" hidden>
    <div>
      <h2>Select Measurement Type</h2>

      <button class="portal-button standard-choice">
        Standard
      </button>

      <button class="portal-button secondary metric-choice">
        Metric
      </button>

      <button class="text-button modal-close">
        Cancel
      </button>
    </div>
  </div>

  <script
    src="{{ url_for('static', filename='portal.js') }}"
  ></script>
</body>
</html>
'''


EMPLOYEE_DASHBOARD = r'''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width,initial-scale=1"
  >
  <title>JIT Operations Dashboard</title>
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_common.css') }}"
  >
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_history.css') }}"
  >
</head>
<body>
  <header class="portal-header">
    <div>{{ user.display_name }} · Employee</div>
    <h1>JIT Operations Dashboard</h1>
    <a href="{{ url_for('portal.logout') }}">Log Out</a>
  </header>

  <main class="portal-shell">
    <div class="dashboard-actions">
      <button
        class="portal-button new-quote"
        data-standard="{{ url_for('portal.employee_quote_entry') }}"
        data-metric="{{ url_for('portal.metric_coming_soon') }}"
      >
        + New Quote
      </button>

      <a
        class="portal-button secondary"
        href="{{ url_for('portal.employee_history') }}"
      >
        My Order History
      </a>
    </div>

    <form class="search-form" method="get">
      <label for="globalSearch">
        Search customers, orders, addresses or model codes
      </label>

      <div>
        <input
          id="globalSearch"
          name="q"
          value="{{ query }}"
          autocomplete="off"
          placeholder="Start typing to search..."
        >

        <button class="portal-button" type="submit">
          Search
        </button>
      </div>

      <div
        id="searchSuggestions"
        class="suggestions"
        hidden
      ></div>
    </form>

    {% if query %}
      <h2>Search Results</h2>
      {% set entry_url=url_for('portal.employee_quote_entry') %}
''' + HISTORY_TABLE + r'''
    {% endif %}
  </main>

  <div class="quote-modal" hidden>
    <div>
      <h2>Select Measurement Type</h2>

      <button class="portal-button standard-choice">
        Standard
      </button>

      <button class="portal-button secondary metric-choice">
        Metric
      </button>

      <button class="text-button modal-close">
        Cancel
      </button>
    </div>
  </div>

  <script
    src="{{ url_for('static', filename='portal.js') }}"
  ></script>
</body>
</html>
'''


MESSAGE_HTML = r'''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width,initial-scale=1"
  >
  <title>{{ title }}</title>
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_common.css') }}"
  >
  <link
    rel="stylesheet"
    href="{{ url_for('static', filename='portal_auth.css') }}"
  >
</head>
<body class="auth-page">
  <main class="auth-card">
    <h1>{{ title }}</h1>
    <p>{{ message }}</p>

    <button
      class="portal-button"
      onclick="history.back()"
    >
      ← Go Back
    </button>
  </main>
</body>
</html>
'''


COMMON_CSS = r'''
:root {
  font-family: Arial, Helvetica, sans-serif;
  color: #17202a;
  background: #f3f5f7;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

a {
  color: #861313;
}

.portal-button,
.small-button {
  display: inline-block;
  border: 1px solid #781010;
  border-radius: 7px;
  background: linear-gradient(#d92727, #a80f0f);
  box-shadow: 0 3px 0 #6e0909;
  color: #fff;
  text-decoration: none;
  font-weight: 700;
  padding: 0.72rem 1rem;
  cursor: pointer;
}

.portal-button:active,
.small-button:active {
  transform: translateY(2px);
  box-shadow: 0 1px 0 #6e0909;
}

.portal-button.secondary,
.small-button {
  background: linear-gradient(#fff, #e8ebee);
  border-color: #7d858c;
  box-shadow: 0 3px 0 #737b82;
  color: #17202a;
}

.portal-button.light {
  background: linear-gradient(#fff, #eee);
  color: #8f1010;
}

.small-button {
  padding: 0.4rem 0.65rem;
}

.text-button {
  border: 0;
  background: none;
  color: #861313;
  text-decoration: underline;
  cursor: pointer;
}

.portal-header {
  min-height: 72px;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 2rem;
  background: #fff;
  border-bottom: 4px solid #a41414;
}

.portal-header h1 {
  margin: 0;
  text-align: center;
}

.portal-header > a {
  text-align: right;
}

.portal-shell {
  width: min(1200px, 96vw);
  margin: 2rem auto;
}

.page-actions,
.dashboard-actions {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.form-error {
  background: #ffe3e3;
  border: 1px solid #bd2323;
  color: #7d0808;
  padding: 0.7rem;
  border-radius: 5px;
}
'''


LANDING_CSS = r'''
.landing-page {
  min-height: 100vh;
  background: #a40e12;
  color: #fff;
}

.landing-page header {
  padding: 1rem 4vw;
}

.landing-page nav {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

.landing-page nav a {
  color: #fff;
  font-weight: 700;
}

.landing-page h1 {
  text-align: center;
  font-size: clamp(2rem, 5vw, 4rem);
  margin: 3rem 0;
}

.landing-card {
  width: min(620px, 92vw);
  margin: auto;
  padding: 3rem;
  text-align: center;
  background: #fff;
  color: #222;
  border-radius: 14px;
  box-shadow: 0 16px 40px #590000;
}

.landing-card img {
  max-width: 290px;
  width: 70%;
}

.landing-card p {
  font-size: 1.25rem;
}

.landing-actions {
  display: flex;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 2rem;
}
'''


AUTH_CSS = r'''
.auth-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 2rem;
  background: linear-gradient(135deg, #a51115, #5e0709);
}

.auth-card {
  width: min(460px, 94vw);
  background: #fff;
  padding: 2rem;
  border-radius: 12px;
  box-shadow: 0 15px 35px #450000;
}

.auth-card.wide {
  width: min(760px, 96vw);
}

.auth-card img {
  display: block;
  max-width: 220px;
  margin: 0 auto;
}

.auth-card h1 {
  text-align: center;
}

.auth-card form {
  display: grid;
  gap: 1rem;
  margin: 1.5rem 0;
}

.auth-card label {
  display: grid;
  gap: 0.35rem;
  font-weight: 700;
}

.auth-card input,
.auth-card textarea {
  width: 100%;
  font: inherit;
  padding: 0.7rem;
  border: 1px solid #899199;
  border-radius: 5px;
}

.auth-card textarea {
  min-height: 75px;
}

.auth-card hr {
  margin: 1.5rem 0;
}

.back-link {
  display: inline-block;
  margin-bottom: 1rem;
}

.signup-grid {
  grid-template-columns: 1fr 1fr;
}

.signup-grid .full {
  grid-column: 1 / -1;
}

@media (max-width: 600px) {
  .signup-grid {
    grid-template-columns: 1fr;
  }

  .signup-grid .full {
    grid-column: auto;
  }
}
'''


HISTORY_CSS = r'''
.table-wrap {
  overflow: auto;
  background: #fff;
  border: 1px solid #aab0b5;
  border-radius: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 780px;
}

th,
td {
  padding: 0.75rem;
  border-bottom: 1px solid #d5d9dc;
  text-align: left;
}

th {
  background: #e9ecef;
}

.status {
  display: inline-block;
  border-radius: 999px;
  padding: 0.3rem 0.65rem;
  font-weight: 700;
}

.status.pending {
  background: #fff1b8;
  color: #604900;
}

.status.approved {
  background: #d9f1d2;
  color: #215716;
}

.empty-state {
  padding: 4rem;
  text-align: center;
  background: #fff;
  border: 1px dashed #999;
  border-radius: 8px;
}

.search-form {
  position: relative;
  background: #fff;
  padding: 1.4rem;
  border-radius: 8px;
  border: 1px solid #bcc2c7;
}

.search-form label {
  display: block;
  font-weight: 700;
  margin-bottom: 0.5rem;
}

.search-form > div:first-of-type {
  display: flex;
  gap: 0.6rem;
}

.search-form input {
  flex: 1;
  font: inherit;
  padding: 0.8rem;
}

.suggestions {
  position: absolute;
  left: 1.4rem;
  right: 1.4rem;
  top: 92px;
  background: #fff;
  border: 1px solid #999;
  z-index: 5;
}

.suggestions a {
  display: block;
  padding: 0.65rem;
  text-decoration: none;
  border-bottom: 1px solid #ddd;
}

.quote-modal {
  position: fixed;
  inset: 0;
  background: #0009;
  display: grid;
  place-items: center;
  z-index: 50;
}

.quote-modal[hidden] {
  display: none;
}

.quote-modal > div {
  background: #fff;
  border-radius: 10px;
  padding: 2rem;
  min-width: min(420px, 90vw);
  text-align: center;
}

.quote-modal .portal-button {
  margin: 0.45rem;
}

.quote-modal .text-button {
  display: block;
  margin: 1rem auto 0;
}

@media (max-width: 650px) {
  .portal-header {
    grid-template-columns: 1fr;
    text-align: center;
  }

  .portal-header > a {
    text-align: center;
  }

  .page-actions,
  .dashboard-actions {
    flex-direction: column;
  }
}
'''


PORTAL_JS = r'''
document.querySelectorAll(".new-quote").forEach((button) => {
  button.addEventListener("click", () => {
    const modal = document.querySelector(".quote-modal");

    modal.hidden = false;

    modal.querySelector(".standard-choice").onclick = () => {
      location.href = button.dataset.standard;
    };

    modal.querySelector(".metric-choice").onclick = () => {
      location.href = button.dataset.metric;
    };
  });
});

document.querySelectorAll(".modal-close").forEach((button) => {
  button.addEventListener("click", () => {
    button.closest(".quote-modal").hidden = true;
  });
});

const search = document.getElementById("globalSearch");
const suggestions = document.getElementById("searchSuggestions");
let searchTimer;

if (search && suggestions) {
  search.addEventListener("input", () => {
    clearTimeout(searchTimer);

    const query = search.value.trim();

    if (query.length < 2) {
      suggestions.hidden = true;
      return;
    }

    searchTimer = setTimeout(async () => {
      try {
        const response = await fetch(
          "/portal/api/search?q="
          + encodeURIComponent(query)
        );

        const body = await response.json();

        suggestions.innerHTML = (
          body.results || []
        ).map((row) => `
          <a href="/employee/quote-entry?quote_id=${row.id}">
            <strong>${row.quote_number}</strong>
            · ${row.customer || "No customer"}
            · ${row.model_code || "No model code"}
          </a>
        `).join("");

        suggestions.hidden = !body.results.length;

      } catch (error) {
        suggestions.hidden = true;
      }
    }, 220);
  });
}
'''


CUSTOMER_QUOTE_CSS = r'''
body.customer-mode
.pricing-rows > label:has(#discount_pct),

body.customer-mode
.pricing-rows > label:has(#profit_display) {
  display: none !important;
}

body.customer-mode
.coupon-row label[for="coupon_code"] {
  font-size: 0;
}

body.customer-mode
.coupon-row label[for="coupon_code"]::after {
  content: "Promo Code";
  font-size: 14px;
}

body.customer-mode
#coupon_code::placeholder {
  color: transparent;
}

body.customer-mode
.qf-toolbar-meta {
  display: none;
}

body.customer-mode
#pv_repair_assembly,

body.customer-mode
#pv_repair_rod_kit,

body.customer-mode
#pv_repair_piston_kit,

body.customer-mode
#pv_repair_gland_kit {
  color: transparent !important;
}

body.customer-mode
.manual-note,

body.customer-mode
.qf-additional-items .show-cell {
  visibility: hidden;
}

body.customer-mode
#saveQuoteButton {
  min-width: 110px;
}
'''


QUOTE_BRIDGE_JS = r'''
(function () {
  const mode =
    document.body.dataset.portalMode || "employee";

  const saveButton =
    document.getElementById("saveQuoteButton");

  if (mode === "customer" && saveButton) {
    saveButton.textContent = "Save Quote";
  }

  const quoteId =
    new URLSearchParams(location.search)
      .get("quote_id");

  if (!quoteId) {
    return;
  }

  async function setSelect(name, value) {
    const element = document.getElementById(name);

    if (!element || value == null) {
      return;
    }

    element.value = String(value);

    element.dispatchEvent(
      new Event("change", {
        bubbles: true,
      })
    );

    await new Promise((resolve) => {
      setTimeout(resolve, 0);
    });
  }

  (async () => {
    try {
      if (window.jitCalculatorReady) {
        await window.jitCalculatorReady;
      }

      const response = await fetch(
        "/portal/api/quotes/"
        + encodeURIComponent(quoteId)
      );

      const body = await response.json();

      if (!response.ok || !body.ok) {
        throw new Error(
          body.error
          || "Saved quote could not be opened"
        );
      }

      const quote = body.quote;
      const inputs =
        quote.cylinder_inputs_snapshot || {};

      const customer =
        document.getElementById("customer_name");

      const address =
        document.getElementById("customer_address");

      if (customer) {
        customer.value =
          quote.customer_name || "";
      }

      if (address) {
        address.value =
          quote.customer_address || "";
      }

      await setSelect(
        "series",
        inputs.series
      );

      await setSelect(
        "mount",
        inputs.mount
      );

      await setSelect(
        "bore",
        inputs.bore
      );

      await setSelect(
        "rod_diameter",
        inputs.rod_diameter
      );

      const stroke =
        document.getElementById("stroke");

      if (stroke) {
        stroke.value = inputs.stroke || "";
      }

      await setSelect(
        "rod_style",
        inputs.rod_style
      );

      await setSelect(
        "cushion",
        inputs.cushion
      );

      await setSelect(
        "port_code",
        inputs.port_code
      );

      await setSelect(
        "seal_code",
        inputs.seal_code
      );

      if (mode === "employee") {
        const discount =
          document.getElementById("discount_pct");

        if (discount) {
          discount.value =
            Number(inputs.discount || 0) * 100;
        }
      }

      document.title =
        "Edit " + quote.quote_number;

    } catch (error) {
      alert(error.message);
    }
  })();
})();
'''


def install_model_fields() -> None:
    replace_once(
        "app/models_db.py",
        (
            "    password_hash: Mapped[str | None] = "
            "mapped_column(String(255), nullable=True)\n\n"
            "    is_active:"
        ),
        (
            "    password_hash: Mapped[str | None] = "
            "mapped_column(String(255), nullable=True)\n\n"

            "    # JIT portal account/profile fields.\n"

            "    role: Mapped[str] = mapped_column("
            "String(20), default=\"employee\", nullable=False)\n"

            "    company_name: Mapped[str | None] = "
            "mapped_column(String(255), nullable=True)\n"

            "    phone: Mapped[str | None] = "
            "mapped_column(String(60), nullable=True)\n"

            "    phone_extension: Mapped[str | None] = "
            "mapped_column(String(20), nullable=True)\n"

            "    shipping_name: Mapped[str | None] = "
            "mapped_column(String(255), nullable=True)\n"

            "    shipping_address: Mapped[str | None] = "
            "mapped_column(Text, nullable=True)\n"

            "    billing_address: Mapped[str | None] = "
            "mapped_column(Text, nullable=True)\n\n"

            "    is_active:"
        ),
        "JIT portal account/profile fields",
    )


def install_db_migration() -> None:
    replace_once(
        "app/db.py",
        (
            "        quote_columns = {row[1] for row in "
            "connection.exec_driver_sql("
            "\"PRAGMA table_info(quotes)\")}\n"
        ),
        (
            "        # JIT portal profile migration "
            "(safe for the existing SQLite database).\n"

            "        user_columns = {row[1] for row in "
            "connection.exec_driver_sql("
            "\"PRAGMA table_info(users)\")}\n"

            "        required_user_columns = {\n"

            "            \"role\": "
            "\"VARCHAR(20) NOT NULL DEFAULT 'employee'\",\n"

            "            \"company_name\": \"VARCHAR(255)\",\n"
            "            \"phone\": \"VARCHAR(60)\",\n"
            "            \"phone_extension\": \"VARCHAR(20)\",\n"
            "            \"shipping_name\": \"VARCHAR(255)\",\n"
            "            \"shipping_address\": \"TEXT\",\n"
            "            \"billing_address\": \"TEXT\",\n"

            "        }\n"

            "        for column_name, column_type "
            "in required_user_columns.items():\n"

            "            if column_name not in user_columns:\n"

            "                connection.exec_driver_sql(\n"
            "                    f\"ALTER TABLE users ADD COLUMN "
            "{column_name} {column_type}\"\n"
            "                )\n\n"

            "        quote_columns = {row[1] for row in "
            "connection.exec_driver_sql("
            "\"PRAGMA table_info(quotes)\")}\n"
        ),
        "JIT portal profile migration",
    )


def install_session_user() -> None:
    replace_once(
        "app/current_user.py",
        "from flask import request as flask_request\n",
        (
            "from flask import "
            "request as flask_request, "
            "session as flask_session\n"
        ),
        "session as flask_session",
    )

    replace_once(
        "app/current_user.py",
        (
            "    if display_name is None:\n"
            "        request_obj = request_obj or flask_request\n"
        ),
        (
            "    # A real portal login takes priority "
            "over the former local dev user.\n"

            "    if display_name is None:\n"

            "        user_id = "
            "flask_session.get(\"user_id\")\n"

            "        if user_id:\n"

            "            with get_session() as session:\n"

            "                logged_in = "
            "session.get(User, int(user_id))\n"

            "                if logged_in "
            "and logged_in.is_active:\n"

            "                    return logged_in\n"

            "        request_obj = request_obj or flask_request\n"
        ),
        "real portal login takes priority",
    )


def install_web_routes() -> None:
    replace_once(
        "app/web.py",
        (
            "    app = Flask("
            "__name__, "
            "template_folder=\"templates\", "
            "static_folder=\"static\")\n"
        ),
        (
            "    app = Flask("
            "__name__, "
            "template_folder=\"templates\", "
            "static_folder=\"static\")\n"

            "    # JIT portal session key. "
            "Set SECRET_KEY in .env "
            "before public deployment.\n"

            "    app.secret_key = os.environ.get(\n"
            "        \"SECRET_KEY\",\n"
            "        \"jit-local-portal-change-before-public\",\n"
            "    )\n"
        ),
        "JIT portal session key",
    )

    replace_once(
        "app/web.py",
        (
            "    catalog = build_catalog(engine.data)\n\n"

            "    @app.get(\"/\")\n"
            "    def index():\n"
            "        return render_template(\"index.html\")\n"
        ),
        (
            "    catalog = build_catalog(engine.data)\n\n"

            "    # JIT portal pages are kept separate "
            "from the pricing engine routes.\n"

            "    from .portal import portal_bp\n"

            "    app.register_blueprint(portal_bp)\n\n"

            "    @app.get(\"/quote-entry\")\n"
            "    def index():\n"

            "        return render_template(\n"
            "            \"index.html\",\n"
            "            portal_mode=\"employee\",\n"
            "        )\n"
        ),
        "JIT portal pages are kept separate",
    )


def install_index_mode() -> None:
    replace_once(
        "app/templates/index.html",
        (
            "  <link id=\"quoteFormStylesheet\" "
            "rel=\"stylesheet\" "
            "href=\"{{ url_for('static', "
            "filename='quote_form.css') }}\">\n"
        ),
        (
            "  <link id=\"quoteFormStylesheet\" "
            "rel=\"stylesheet\" "
            "href=\"{{ url_for('static', "
            "filename='quote_form.css') }}\">\n"

            "  {% if portal_mode|default('employee') "
            "== 'customer' %}\n"

            "  <link rel=\"stylesheet\" "
            "href=\"{{ url_for('static', "
            "filename='customer_quote.css') }}\">\n"

            "  {% endif %}\n"
        ),
        "customer_quote.css",
    )

    replace_once(
        "app/templates/index.html",
        "<body>\n",
        (
            "<body "
            "class=\"{{ portal_mode|default('employee') }}-mode\" "
            "data-portal-mode=\"{{ "
            "portal_mode|default('employee') }}\">\n"
        ),
        "data-portal-mode",
    )

    replace_once(
        "app/templates/index.html",
        (
            "  <script src=\"{{ url_for('static', "
            "filename='app.js') }}\"></script>\n"
        ),
        (
            "  <script src=\"{{ url_for('static', "
            "filename='app.js') }}\"></script>\n"

            "  <script src=\"{{ url_for('static', "
            "filename='portal_quote_bridge.js') }}\"></script>\n"
        ),
        "portal_quote_bridge.js",
    )


def install_app_mode() -> None:
    replace_once(
        "app/static/app.js",
        (
            "const $ = id => "
            "document.getElementById(id);\n"
        ),
        (
            "const $ = id => "
            "document.getElementById(id);\n"

            "const PORTAL_MODE = "
            "document.body.dataset.portalMode "
            "|| 'employee';\n"
        ),
        "const PORTAL_MODE =",
    )

    replace_once(
        "app/static/app.js",
        "init();\n",
        "window.jitCalculatorReady = init();\n",
        "window.jitCalculatorReady",
    )

    replace_once(
        "app/static/app.js",
        (
            "    currentQuote = body.quote;\n"

            "    const orderResponse = await fetch("
            "`/api/quotes/${body.quote.id}/order`, {\n"
        ),
        (
            "    currentQuote = body.quote;\n"

            "    if (PORTAL_MODE === 'customer') {\n"

            "      window.location.assign("
            "'/customer/history');\n"

            "      return;\n"
            "    }\n"

            "    const orderResponse = await fetch("
            "`/api/quotes/${body.quote.id}/order`, {\n"
        ),
        "PORTAL_MODE === 'customer'",
    )

    replace_once(
        "app/static/app.js",
        (
            "    $('saveQuoteButton').textContent "
            "= 'Order Now';\n"
        ),
        (
            "    $('saveQuoteButton').textContent = "
            "PORTAL_MODE === 'customer' "
            "? 'Save Quote' : 'Order Now';\n"
        ),
        (
            "PORTAL_MODE === 'customer' "
            "? 'Save Quote'"
        ),
    )


def main() -> None:
    validate_project()

    print("\nInstalling the JIT local portal...\n")

    write(
        "app/portal.py",
        PORTAL_PY,
    )

    write(
        "app/templates/portal_landing.html",
        LANDING_HTML,
    )

    write(
        "app/templates/portal_login.html",
        LOGIN_HTML,
    )

    write(
        "app/templates/portal_signup.html",
        SIGNUP_HTML,
    )

    write(
        "app/templates/customer_history.html",
        CUSTOMER_HISTORY,
    )

    write(
        "app/templates/employee_history.html",
        EMPLOYEE_HISTORY,
    )

    write(
        "app/templates/employee_dashboard.html",
        EMPLOYEE_DASHBOARD,
    )

    write(
        "app/templates/portal_message.html",
        MESSAGE_HTML,
    )

    write(
        "app/static/portal_common.css",
        COMMON_CSS,
    )

    write(
        "app/static/portal_landing.css",
        LANDING_CSS,
    )

    write(
        "app/static/portal_auth.css",
        AUTH_CSS,
    )

    write(
        "app/static/portal_history.css",
        HISTORY_CSS,
    )

    write(
        "app/static/portal.js",
        PORTAL_JS,
    )

    write(
        "app/static/customer_quote.css",
        CUSTOMER_QUOTE_CSS,
    )

    write(
        "app/static/portal_quote_bridge.js",
        QUOTE_BRIDGE_JS,
    )

    install_model_fields()
    install_db_migration()
    install_session_user()
    install_web_routes()
    install_index_mode()
    install_app_mode()

    python_files = (
        APP / "portal.py",
        APP / "models_db.py",
        APP / "db.py",
        APP / "current_user.py",
        APP / "web.py",
    )

    for file in python_files:
        py_compile.compile(
            str(file),
            doraise=True,
        )

    print(
        "\nJIT portal installation completed successfully."
    )

    print(
        "No backup folders were created. "
        "Email remains disabled."
    )

    print("\nNext:")
    print("  1. Start RUN_CYLINDER_QUOTE.bat")
    print("  2. Open http://127.0.0.1:5055/")
    print(
        "  3. Create a customer or employee "
        "account from the landing page\n"
    )


if __name__ == "__main__":
    main()