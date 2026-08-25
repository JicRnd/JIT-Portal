from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from flask import render_template

from .models_db import Quote, QuoteDocument, utc_now

logger = logging.getLogger(__name__)

PDF_SETUP_COMMAND = "pip install playwright && playwright install chromium"


class PdfEngineUnavailableError(Exception):
    """Raised when the Playwright/Chromium PDF engine cannot be used.

    This is typically an environment/operator issue rather than a quote
    logic error, so callers should present a friendly setup message.
    """

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or (
                "PDF generation is not available. Install the engine with: "
                f"{PDF_SETUP_COMMAND}"
            )
        )


def _project_root() -> Path:
    """Return the project root (the folder containing app/)."""
    return Path(__file__).resolve().parents[1]


def _documents_root() -> Path:
    """Return the root directory where quote PDFs are stored.

    Override with the ``QUOTE_DOCUMENTS_DIR`` environment variable; otherwise
    ``<project_root>/instance/quote_documents`` is used.
    """
    env_path = os.environ.get("QUOTE_DOCUMENTS_DIR")
    if env_path:
        return Path(env_path).resolve()
    return _project_root() / "instance" / "quote_documents"


def _safe_quote_number(quote: Quote) -> str:
    """Return a filesystem-safe version of the quote number."""
    return str(quote.quote_number).replace("/", "_").replace("\\", "_")


def quote_pdf_relative_path(quote: Quote) -> str:
    """Return the project-relative storage path for a quote revision PDF.

    The path is always constructed server-side from the quote object; no
    browser-supplied path or filename is ever accepted.
    """
    safe_number = _safe_quote_number(quote)
    return f"instance/quote_documents/{safe_number}/rev{quote.revision}.pdf"


def quote_pdf_absolute_path(quote: Quote) -> Path:
    """Return the absolute filesystem path for a quote revision PDF."""
    relative = quote_pdf_relative_path(quote)
    return _project_root() / relative


def _public_customer_line_items(quote: Quote) -> list[dict[str, Any]]:
    """Return only the customer-visible manual line items, sorted."""
    return [
        {
            "reference_part_number": item.reference_part_number,
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "extended_price": item.extended_price,
        }
        for item in quote.line_items
        if item.show_on_customer_quote
    ]


def build_quote_pdf_context(quote: Quote) -> dict[str, Any]:
    """Build the Jinja context for the customer quote PDF template."""
    return {
        "quote": quote,
        "customer_line_items": _public_customer_line_items(quote),
    }


def _render_pdf_with_playwright(html: str) -> bytes:
    """Render HTML to a PDF byte stream using Playwright + Chromium.

    This helper is separated from ``render_quote_pdf`` so tests can
    monkeypatch it without needing a real browser installation.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise PdfEngineUnavailableError(
            "Playwright is not installed. Run: " + PDF_SETUP_COMMAND
        ) from exc

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            pdf = page.pdf(format="Letter", print_background=True)
            browser.close()
            return pdf
    except Exception as exc:
        message = str(exc).lower()
        if any(
            keyword in message
            for keyword in ("executable", "chromium", "browser", "browser_type")
        ):
            raise PdfEngineUnavailableError(
                "Chromium is not installed. Run: " + PDF_SETUP_COMMAND
            ) from exc
        raise


def render_quote_pdf(quote: Quote) -> bytes:
    """Render a customer-facing PDF for ``quote`` and return its bytes.

    Raises:
        PdfEngineUnavailableError: if Playwright or Chromium is missing.
    """
    context = build_quote_pdf_context(quote)
    html = render_template("quote_pdf.html", **context)
    return _render_pdf_with_playwright(html)


def generate_and_store_pdf(
    quote: Quote,
    current_user,
) -> QuoteDocument:
    """Render, store, and record a PDF for the quote's current revision.

    The returned ``QuoteDocument`` is not committed to the database; the
    caller remains responsible for committing its session.
    """
    pdf_bytes = render_quote_pdf(quote)

    absolute_path = quote_pdf_absolute_path(quote)
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(pdf_bytes)

    document = QuoteDocument(
        quote_id=quote.id,
        revision=quote.revision,
        file_path=quote_pdf_relative_path(quote),
        created_by_user_id=current_user.id,
        created_at=utc_now(),
    )
    return document
