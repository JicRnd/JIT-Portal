from __future__ import annotations

import csv
import io
import logging
import os
from datetime import datetime, time
from pathlib import Path

try:
    import openpyxl
except ModuleNotFoundError:  # pragma: no cover - optional until requirements installed
    openpyxl = None

try:
    from flask import (
        Flask,
        jsonify,
        render_template,
        request,
        send_file,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - developer environment may not have Flask installed
    raise RuntimeError("Flask is required for the web layer. Install with: pip install -r requirements.txt") from exc

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from .catalog import build_catalog
from .current_user import get_or_create_current_user
from .data1_service import (
    approval_submission_to_json,
    is_data1_configured,
    submit_approval,
)
from .db import get_session, init_db
from .email_service import (
    email_log_to_json,
    send_order_approval_email,
    send_quote_email,
    validate_recipients,
)
from .models_db import ApprovalSubmission, Customer, Order, Quote, QuoteDocument, User, utc_now
from .pdf_service import (
    PdfEngineUnavailableError,
    generate_and_store_pdf,
    quote_pdf_absolute_path,
)
from .quote_service import (
    create_quote_snapshot,
    duplicate_quote,
    get_quote,
    quote_to_json,
    update_quote_edits,
    upsert_customer,
)
from .service import build_quote_draft, calculate_payload, make_engine

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    # JIT portal session key. Set SECRET_KEY in .env before public deployment.
    app.secret_key = os.environ.get(
        "SECRET_KEY",
        "jit-local-portal-change-before-public",
    )
    app.json.sort_keys = False  # preserve catalog dropdown display order (series/mount/seal)
    init_db()
    root = Path(__file__).resolve().parents[1]
    engine = make_engine(root)
    catalog = build_catalog(engine.data)

    # JIT portal pages are kept separate from the pricing engine routes.
    from .portal import portal_bp
    app.register_blueprint(portal_bp)

    @app.get("/quote-entry")
    def index():
        current_user = get_or_create_current_user(request)
        return render_template(
            "index.html",
            portal_mode="employee",
            current_user_name=getattr(current_user, "display_name", "") or "",
        )

    @app.get("/order-approval")
    @app.get("/order-form")
    def order_approval():
        return render_template(
            "order_form.html",
            quote_id=(request.args.get("quote_id") or "").strip(),
        )

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "engine": "Pricing Engine v1.2"})

    @app.get("/api/catalog")
    def get_catalog():
        return jsonify(catalog)

    def _customer_status(session, customer: Customer) -> str:
        """Return 'Member' if a customer-role user shares this customer's email."""
        if not customer.email or not customer.email.strip():
            return "Visitor"
        user = session.execute(
            select(User).where(
                User.role == "customer",
                User.email.is_not(None),
                func.lower(User.email) == customer.email.lower(),
            )
        ).scalar_one_or_none()
        return "Member" if user is not None else "Visitor"

    @app.get("/api/customers/search")
    def search_customers():
        query = (request.args.get("q") or "").strip()
        if not query:
            return jsonify({"ok": True, "customers": []})
        with get_session() as session:
            matches = session.execute(
                select(Customer)
                .where(
                    or_(
                        Customer.name.ilike(f"%{query}%"),
                        Customer.address.ilike(f"%{query}%"),
                        Customer.city_state_zip.ilike(f"%{query}%"),
                        Customer.phone.ilike(f"%{query}%"),
                        Customer.email.ilike(f"%{query}%"),
                    )
                )
                .order_by(Customer.name)
                .limit(10)
            ).scalars().all()
            return jsonify({
                "ok": True,
                "customers": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "address": c.address or "",
                        "city_state_zip": c.city_state_zip or "",
                        "phone": c.phone or "",
                        "email": c.email or "",
                        "status": _customer_status(session, c),
                    }
                    for c in matches
                ],
            })

    @app.get("/api/customers/all")
    def list_all_customers():
        with get_session() as session:
            customers = session.execute(
                select(Customer).order_by(Customer.name)
            ).scalars().all()
            return jsonify({
                "ok": True,
                "customers": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "address": c.address or "",
                        "city_state_zip": c.city_state_zip or "",
                        "phone": c.phone or "",
                        "email": c.email or "",
                        "status": _customer_status(session, c),
                    }
                    for c in customers
                ],
            })

    @app.patch("/api/customers/<int:customer_id>")
    def update_customer(customer_id: int):
        current_user = get_or_create_current_user(request)
        if getattr(current_user, "role", "employee") != "employee":
            return jsonify({"ok": False, "error": "Employees only"}), 403

        payload = request.get_json(silent=True) or {}
        if "name" in payload and not str(payload["name"]).strip():
            return jsonify({"ok": False, "error": "Name cannot be blank"}), 400

        with get_session() as session:
            customer = session.get(Customer, customer_id)
            if customer is None:
                return jsonify({"ok": False, "error": "Customer not found"}), 404

            if "name" in payload:
                customer.name = str(payload["name"]).strip()
            for field in ("address", "city_state_zip", "phone", "email"):
                if field in payload:
                    value = payload[field]
                    setattr(
                        customer,
                        field,
                        None if value is None or str(value).strip() == "" else str(value).strip(),
                    )

            session.commit()
            return jsonify({
                "ok": True,
                "customer": {
                    "id": customer.id,
                    "name": customer.name,
                    "address": customer.address or "",
                    "city_state_zip": customer.city_state_zip or "",
                    "phone": customer.phone or "",
                    "email": customer.email or "",
                    "status": _customer_status(session, customer),
                },
            })

    @app.delete("/api/customers/<int:customer_id>")
    def delete_customer(customer_id: int):
        current_user = get_or_create_current_user(request)
        if getattr(current_user, "role", "employee") != "employee":
            return jsonify({"ok": False, "error": "Employees only"}), 403

        with get_session() as session:
            customer = session.get(Customer, customer_id)
            if customer is None:
                return jsonify({"ok": False, "error": "Customer not found"}), 404
            session.delete(customer)
            session.commit()
            return jsonify({"ok": True})

    @app.post("/api/customers/bulk-import")
    def bulk_import_customers():
        current_user = get_or_create_current_user(request)
        if getattr(current_user, "role", "employee") != "employee":
            return jsonify({"ok": False, "error": "Employees only"}), 403

        uploaded = request.files.get("file")
        if not uploaded or uploaded.filename == "":
            return jsonify({"ok": False, "error": "No file provided"}), 400

        filename = uploaded.filename.lower()
        stream = io.BytesIO(uploaded.read())

        if filename.endswith((".xlsx", ".xls")):
            if openpyxl is None:
                return jsonify({"ok": False, "error": "Excel parsing is not available"}), 503
            try:
                workbook = openpyxl.load_workbook(stream, data_only=True)
                worksheet = workbook.active
                rows = [[str(cell) if cell is not None else "" for cell in row] for row in worksheet.iter_rows(values_only=True)]
            except Exception as exc:
                logger.warning("Failed to parse uploaded Excel file: %s", exc)
                return jsonify({"ok": False, "error": "Could not parse Excel file"}), 400
        elif filename.endswith(".csv"):
            try:
                text = stream.read().decode("utf-8-sig")
                rows = list(csv.reader(io.StringIO(text)))
            except Exception as exc:
                logger.warning("Failed to parse uploaded CSV file: %s", exc)
                return jsonify({"ok": False, "error": "Could not parse CSV file"}), 400
        else:
            return jsonify({"ok": False, "error": "Unsupported file type. Use .xlsx, .xls, or .csv"}), 400

        # Detect header row.
        start_index = 0
        if rows:
            first_cell = (rows[0][0] or "").strip().lower()
            if first_cell in {"company", "contact", "name", "company or contact"}:
                start_index = 1

        imported = 0
        skipped = 0

        with get_session() as session:
            for row in rows[start_index:]:
                cells = list(row) + ["", "", "", "", ""]
                name, address, city_state_zip, phone, email = [str(cell).strip() for cell in cells[:5]]

                if not any((name, address, city_state_zip, phone, email)):
                    continue

                try:
                    upsert_customer(
                        session,
                        name=name or "",
                        address=address or None,
                        phone=phone or None,
                        email=email or None,
                        city_state_zip=city_state_zip or None,
                    )
                    imported += 1
                except Exception as exc:
                    logger.warning("Skipping customer import row %s: %s", row, exc)
                    skipped += 1

            session.commit()

        return jsonify({"ok": True, "imported": imported, "skipped": skipped})

    @app.post("/api/calculate")
    def calculate():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"ok": False, "error": "Expected application/json request body"}), 400
        try:
            result = calculate_payload(engine, payload)
        except (ValueError, LookupError, KeyError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "result": result})

    @app.post("/api/quote/draft")
    def quote_draft():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"ok": False, "error": "Expected application/json request body"}), 400
        try:
            result = build_quote_draft(engine, payload)
        except (ValueError, LookupError, KeyError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "draft": result})

    @app.post("/api/quotes")
    def create_quote():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"ok": False, "error": "Expected application/json request body"}), 400

        current_user = get_or_create_current_user(request)

        with get_session() as session:
            try:
                quote = create_quote_snapshot(session, payload, current_user, engine=engine)
                session.commit()
            except (ValueError, LookupError, KeyError) as exc:
                session.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400
            result = quote_to_json(quote)

        return jsonify({"ok": True, "quote": result})

    @app.get("/api/quotes")
    def list_quotes():
        quote_number = request.args.get("quote_number", "").strip()
        customer_name = request.args.get("customer_name", "").strip()
        model_code = request.args.get("model_code", "").strip()
        status = request.args.get("status", "").strip()
        created_by = request.args.get("created_by", "").strip()
        date_from = request.args.get("date_from", "").strip()
        date_to = request.args.get("date_to", "").strip()

        page_raw = request.args.get("page", "1").strip()
        page_size_raw = request.args.get("page_size", "25").strip()
        try:
            page = int(page_raw)
            if page < 1:
                page = 1
        except ValueError:
            page = 1
        try:
            page_size = int(page_size_raw)
            if page_size < 1:
                page_size = 25
            elif page_size > 100:
                page_size = 100
        except ValueError:
            page_size = 25

        filters = []
        if quote_number:
            filters.append(Quote.quote_number.ilike(f"%{quote_number}%"))
        if customer_name:
            filters.append(Quote.customer_name.ilike(f"%{customer_name}%"))
        if model_code:
            filters.append(Quote.model_code.ilike(f"%{model_code}%"))
        if status:
            filters.append(Quote.status == status)

        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                filters.append(Quote.created_at >= datetime.combine(from_date, time.min))
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                filters.append(Quote.created_at <= datetime.combine(to_date, time.max))
            except ValueError:
                pass

        with get_session() as session:
            # Users live in a separate database file, so resolve matching
            # employee/customer ids first instead of a cross-database SQL join.
            if created_by:
                matching_user_ids = session.execute(
                    select(User.id).where(
                        func.lower(User.display_name).like(func.lower(f"%{created_by}%"))
                    )
                ).scalars().all()
                filters.append(Quote.created_by_user_id.in_(matching_user_ids))

            base_stmt = select(Quote)
            count_stmt = select(func.count(Quote.id))
            for filt in filters:
                base_stmt = base_stmt.where(filt)
                count_stmt = count_stmt.where(filt)

            total = session.execute(count_stmt).scalar() or 0

            quotes = session.execute(
                base_stmt
                .order_by(Quote.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .options(selectinload(Quote.created_by))
            ).scalars().all()

            results = []
            for quote in quotes:
                breakdown = quote.price_breakdown_snapshot or {}
                results.append(
                    {
                        "id": quote.id,
                        "quote_number": quote.quote_number,
                        "status": quote.status,
                        "model_code": quote.model_code,
                        "customer_name": quote.customer_name,
                        "created_by": quote.created_by.display_name if quote.created_by else None,
                        "created_at": quote.created_at.isoformat() if quote.created_at else None,
                        "revision": quote.revision,
                        "quote_net_each": breakdown.get("quote_net_each"),
                    }
                )

        return jsonify(
            {
                "ok": True,
                "results": results,
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        )

    @app.get("/api/quotes/<int:quote_id>")
    def get_quote_route(quote_id: int):
        current_user = get_or_create_current_user(request)

        with get_session() as session:
            quote = get_quote(session, quote_id)
            if quote is None:
                return jsonify({"ok": False, "error": "Quote not found"}), 404
            if (
                quote.customer_update_pending
                and getattr(current_user, "role", "employee") == "employee"
                and quote.assigned_employee_user_id == current_user.id
            ):
                quote.customer_update_pending = False
                session.commit()
            result = quote_to_json(quote)

        return jsonify({"ok": True, "quote": result})

    @app.post("/api/quotes/<int:quote_id>/duplicate")
    def duplicate_quote_route(quote_id: int):
        current_user = get_or_create_current_user(request)

        with get_session() as session:
            source = get_quote(session, quote_id)
            if source is None:
                return jsonify({"ok": False, "error": "Quote not found"}), 404

            try:
                new_quote = duplicate_quote(session, source, current_user)
                session.commit()
            except (ValueError, LookupError, KeyError) as exc:
                session.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

            result = quote_to_json(new_quote)

        return jsonify({"ok": True, "quote": result})

    @app.patch("/api/quotes/<int:quote_id>")
    def update_quote(quote_id: int):
        payload = request.get_json(silent=True) or {}
        current_user = get_or_create_current_user(request)

        with get_session() as session:
            existing_quote = get_quote(session, quote_id)
            if existing_quote is None:
                return jsonify({"ok": False, "error": "Quote not found"}), 404
            if getattr(current_user, "role", "employee") == "customer" and existing_quote.created_by_user_id != current_user.id:
                return jsonify({"ok": False, "error": "Quote not found"}), 404
            try:
                quote = update_quote_edits(session, quote_id, payload, current_user, engine=engine)
                session.commit()
            except ValueError as exc:
                session.rollback()
                error_text = str(exc)
                status_code = 404 if error_text == "Quote not found" else 400
                return jsonify({"ok": False, "error": error_text}), status_code
            except (LookupError, KeyError) as exc:
                session.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400
            result = quote_to_json(quote)

        return jsonify({"ok": True, "quote": result})

    def _regenerate_quote_pdf(session, quote, current_user):
        try:
            document = generate_and_store_pdf(quote, current_user)
            session.add(document)
            session.commit()
            return document, None
        except PdfEngineUnavailableError as exc:
            logger.warning("PDF engine unavailable for quote %s: %s", quote.id, exc)
            return None, (
                jsonify({"ok": False, "error": "PDF generation is not available in this environment (see setup docs)"}),
                503,
            )
        except Exception as exc:  # pragma: no cover - unexpected render failure
            logger.exception("Unexpected PDF generation failure for quote %s", quote.id)
            return None, (
                jsonify({"ok": False, "error": "PDF generation failed"}),
                500,
            )

    @app.post("/api/quotes/<int:quote_id>/pdf")
    def generate_quote_pdf(quote_id: int):
        current_user = get_or_create_current_user(request)

        with get_session() as session:
            quote = get_quote(session, quote_id)
            if quote is None:
                return jsonify({"ok": False, "error": "Quote not found"}), 404

            document, error = _regenerate_quote_pdf(session, quote, current_user)
            if error:
                return error

            return jsonify({
                "ok": True,
                "document": {
                    "id": document.id,
                    "revision": document.revision,
                    "download_path": f"/api/quotes/{quote.id}/documents/{document.id}",
                },
            })

    @app.post("/api/quotes/<int:quote_id>/email")
    def email_quote(quote_id: int):
        payload = request.get_json(silent=True) or {}
        current_user = get_or_create_current_user(request)

        try:
            recipients = validate_recipients(payload.get("recipients"))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        presentation_keys = {
            "customer_name",
            "customer_address",
            "customer_contact",
            "reference_notes",
            "comments",
            "manual_line_items",
        }

        with get_session() as session:
            quote = get_quote(session, quote_id)
            if quote is None:
                return jsonify({"ok": False, "error": "Quote not found"}), 404

            if presentation_keys.intersection(payload):
                try:
                    update_quote_edits(session, quote_id, payload, current_user)
                    session.commit()
                except ValueError as exc:
                    session.rollback()
                    error_text = str(exc)
                    status_code = 404 if error_text == "Quote not found" else 400
                    return jsonify({"ok": False, "error": error_text}), status_code
                except (LookupError, KeyError) as exc:
                    session.rollback()
                    return jsonify({"ok": False, "error": str(exc)}), 400

            document, error = _regenerate_quote_pdf(session, quote, current_user)
            if error:
                return error

            try:
                email_log = send_quote_email(
                    session,
                    quote,
                    document,
                    recipients,
                    subject_override=payload.get("subject"),
                    sent_by_user=current_user,
                )
                session.add(email_log)
            except Exception as exc:  # pragma: no cover - unexpected email failure
                logger.exception("Unexpected email failure for quote %s", quote_id)
                session.rollback()
                return jsonify({"ok": False, "error": "Email failed"}), 500

            if email_log.status == "sent":
                quote.emailed_by_user_id = current_user.id
                quote.emailed_at = utc_now()
                session.add(quote)

            session.commit()

            response_body = {
                "ok": email_log.status == "sent",
                "email_log": email_log_to_json(email_log),
            }
            if email_log.status == "sent":
                return jsonify(response_body), 200
            if email_log.status == "not_configured":
                return jsonify(response_body), 503
            return jsonify(response_body), 502


    @app.post("/api/quotes/<int:quote_id>/order")
    def submit_order_for_approval(quote_id: int):
        payload = request.get_json(silent=True) or {}
        current_user = get_or_create_current_user(request)
        recipient = (os.environ.get("ORDER_APPROVAL_RECIPIENT") or "kane@jitindustries.com").strip()

        with get_session() as session:
            quote = get_quote(session, quote_id)
            if quote is None:
                return jsonify({"ok": False, "error": "Quote not found"}), 404

            order_form = payload.get("order_form")
            if order_form is not None and not isinstance(order_form, dict):
                return jsonify({"ok": False, "error": "order_form must be an object"}), 400

            # The Order ID belongs to the Order Now action, not to page loading.
            # Format: J + MMDDYYHHMM (never the customer initial).
            order_timestamp = datetime.now()
            saved_order_form = dict(quote.order_form_snapshot or {})
            if order_form:
                saved_order_form.update(order_form)

            saved_order_form["order_number"] = order_timestamp.strftime("J%m%d%y%H%M")
            saved_order_form["order_created_at"] = order_timestamp.isoformat()
            saved_order_form["order_date"] = order_timestamp.strftime("%m/%d/%Y, %I:%M %p")
            quote.order_form_snapshot = saved_order_form

            quote.status = "pending_approval"
            quote.edited_by_user_id = current_user.id
            quote.edited_at = utc_now()
            session.add(quote)
            session.flush()

            order_row = session.execute(
                select(Order).where(Order.quote_id == quote.id)
            ).scalar_one_or_none()
            if order_row is None:
                order_row = Order(quote_id=quote.id)
            order_row.quote_number = quote.quote_number
            order_row.order_form_snapshot = saved_order_form
            session.add(order_row)

            configured_base = (os.environ.get("ORDER_APPROVAL_BASE_URL") or "").strip().rstrip("/")
            base_url = configured_base or request.url_root.rstrip("/")
            approval_url = f"{base_url}/order-approval?quote_id={quote.id}"
            email_log = send_order_approval_email(
                quote, approval_url, recipient, sent_by_user=current_user
            )
            session.add(email_log)
            if email_log.status == "sent":
                quote.emailed_by_user_id = current_user.id
                quote.emailed_at = utc_now()
            session.commit()

            return jsonify({
                "ok": True,
                "quote": quote_to_json(quote),
                "approval_url": approval_url,
                "approval_recipient": recipient,
                "email_log": email_log_to_json(email_log),
            })

    @app.post("/api/quotes/<int:quote_id>/order/approve")
    def approve_internal_order(quote_id: int):
        payload = request.get_json(silent=True) or {}
        order_form = payload.get("order_form")
        if not isinstance(order_form, dict):
            return jsonify({"ok": False, "error": "order_form must be an object"}), 400

        current_user = get_or_create_current_user(request)
        with get_session() as session:
            quote = get_quote(session, quote_id)
            if quote is None:
                return jsonify({"ok": False, "error": "Quote not found"}), 404
            quote.order_form_snapshot = order_form
            quote.status = "approved"
            quote.approved_by_user_id = current_user.id
            quote.approved_at = utc_now()
            quote.edited_by_user_id = current_user.id
            quote.edited_at = utc_now()
            session.add(quote)
            session.flush()

            order_row = session.execute(
                select(Order).where(Order.quote_id == quote.id)
            ).scalar_one_or_none()
            if order_row is None:
                order_row = Order(quote_id=quote.id)
            order_row.quote_number = quote.quote_number
            order_row.order_form_snapshot = order_form
            session.add(order_row)

            session.commit()
            return jsonify({"ok": True, "quote": quote_to_json(quote)})
    @app.post("/api/quotes/<int:quote_id>/approve")
    def approve_quote(quote_id: int):
        current_user = get_or_create_current_user(request)

        with get_session() as session:
            quote = get_quote(session, quote_id)
            if quote is None:
                return jsonify({"ok": False, "error": "Quote not found"}), 404

            try:
                submission = submit_approval(session, quote, current_user)
                session.commit()
            except Exception as exc:  # pragma: no cover - unexpected failure
                logger.exception("Unexpected approval submission failure for quote %s", quote_id)
                session.rollback()
                return jsonify({"ok": False, "error": "Approval submission failed"}), 500

            if submission.success:
                quote.approved_by_user_id = current_user.id
                quote.approved_at = utc_now()
                quote.status = "approved"
                session.add(quote)
                session.commit()
                session.refresh(quote)

                result = quote_to_json(quote)
                return jsonify({
                    "ok": True,
                    "approval": approval_submission_to_json(submission),
                    "quote": result,
                }), 200

            if not is_data1_configured():
                return jsonify({
                    "ok": False,
                    "error": submission.error_message or "Data1 is not configured; approval was not transmitted.",
                    "approval": approval_submission_to_json(submission),
                }), 503

            return jsonify({
                "ok": False,
                "error": submission.error_message or "Approval was not acknowledged by Data1.",
                "approval": approval_submission_to_json(submission),
            }), 502

    @app.get("/api/quotes/<int:quote_id>/documents/<int:doc_id>")
    def download_quote_document(quote_id: int, doc_id: int):
        with get_session() as session:
            document = session.get(QuoteDocument, doc_id)
            if document is None or document.quote_id != quote_id:
                return jsonify({"ok": False, "error": "Document not found"}), 404

            absolute_path = quote_pdf_absolute_path(document.quote)
            if not absolute_path.exists():
                return jsonify({"ok": False, "error": "Document file not found"}), 404

        return send_file(
            absolute_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{document.quote.quote_number}-rev{document.revision}.pdf",
        )

    return app
