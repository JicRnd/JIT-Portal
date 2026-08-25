from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

from sqlalchemy import Integer, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Mapped, mapped_column, Session

from .db import Base


class QuoteNumberSequence(Base):
    """Legacy per-year counter table retained for existing databases."""

    __tablename__ = "quote_number_sequences"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


def _customer_initial(customer_name: str | None) -> str:
    """Uppercase first letter of the customer name; fallback X if missing."""
    cleaned = str(customer_name or "").strip()
    match = re.search(r"[A-Za-z]", cleaned)
    if match:
        return match.group(0).upper()
    return "X"


def generate_quote_number(
    session: Session,
    customer_name: str | None = None,
    *,
    max_retries: int = 20,
) -> str:
    """Generate a quote ID only when a quote is being created/saved.

    Format: [first letter of customer name] + MMDDYYHHMM
    Example: customer "AC Hotels" at 08/19/2026 12:15 PM -> A0819261215

    Generation happens at call time (create/save), not on page load. If two
    quotes for the same customer land in the same minute, uniqueness is kept
    by advancing one minute and retrying.
    """
    # Local import avoids circular import with models_db/quote_service.
    from .models_db import Quote

    initial = _customer_initial(customer_name)

    for attempt in range(max_retries):
        try:
            stamp = datetime.now() + timedelta(minutes=attempt)
            candidate = f"{initial}{stamp.strftime('%m%d%y%H%M')}"

            exists = session.execute(
                select(Quote.id).where(Quote.quote_number == candidate).limit(1)
            ).scalar_one_or_none()
            if exists is None:
                return candidate

            time.sleep(0.005 * (attempt + 1))
        except (IntegrityError, OperationalError):
            if attempt == max_retries - 1:
                raise
            time.sleep(0.005 * (attempt + 1))

    raise RuntimeError("Failed to generate a unique quote number")
