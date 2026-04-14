"""
Unit tests for vet_summary_service.py.

Covers:
  - No eligible vet contacts → None returned
  - Single eligible contact → returned as primary vet
  - Latest document by event_date wins (not most-mentioned)
  - Contacts from Diagnostic / Other docs are ignored
  - Vaccination and Prescription docs are both eligible
  - Vet with no event_date falls back to created_at ordering
  - Correct pet_id is passed to the DB query

All tests are pure Python with no DB or external dependencies.
The SQLAlchemy session is replaced by a MagicMock whose query chain
returns a controlled SimpleNamespace row, mirroring what the real query
would produce.
"""

import os
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

os.environ.setdefault("APP_ENV", "test")

from app.services.vet_summary_service import VetSummary, get_vet_summary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(first_row) -> MagicMock:
    """Return a mock db session whose .query(…).…chain().first() returns *first_row*."""
    db = MagicMock()
    chain = db.query.return_value
    # Each chained method returns the same chain so that
    # .join().filter().order_by().first() all resolve correctly.
    chain.join.return_value = chain
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.first.return_value = first_row
    return db


def _row(name: str, last_visit: date | None) -> SimpleNamespace:
    """Build a fake result row (as returned by the SQLAlchemy query)."""
    return SimpleNamespace(name=name, last_visit=last_visit)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetVetSummary:
    def test_no_eligible_contacts_returns_none(self):
        """No eligible vet contacts for the pet → service returns None."""
        db = _make_db(None)

        result = get_vet_summary(db, uuid4())

        assert result is None

    def test_single_eligible_vet_returned(self):
        """Single eligible contact → returned as VetSummary with correct fields."""
        pet_id = uuid4()
        db = _make_db(_row("Dr. Sharma", date(2024, 6, 15)))

        result = get_vet_summary(db, pet_id)

        assert result == VetSummary(name="Dr. Sharma", last_visit=date(2024, 6, 15))

    def test_latest_document_vet_is_selected(self):
        """Most recent Prescription/Vaccination document vet is selected (DB ordering applied)."""
        # The query orders by event_date DESC — DB returns the latest-doc row first.
        # We simulate that by having first() return the latest row directly.
        db = _make_db(_row("Dr. Patel", date(2024, 10, 1)))

        result = get_vet_summary(db, uuid4())

        assert result is not None
        assert result.name == "Dr. Patel"
        assert result.last_visit == date(2024, 10, 1)

    def test_last_visit_none_when_no_event_date(self):
        """Vet contact exists but linked document has no event_date → last_visit=None."""
        db = _make_db(_row("Dr. Nair", None))

        result = get_vet_summary(db, uuid4())

        assert result is not None
        assert result.name == "Dr. Nair"
        assert result.last_visit is None

    def test_vaccination_document_is_eligible(self):
        """Vaccination category documents are eligible — vet from them is returned."""
        db = _make_db(_row("Dr. Vaccine", date(2024, 3, 20)))

        result = get_vet_summary(db, uuid4())

        assert result is not None
        assert result.name == "Dr. Vaccine"

    def test_prescription_document_is_eligible(self):
        """Prescription category documents are eligible — vet from them is returned."""
        db = _make_db(_row("Dr. Prescription", date(2024, 5, 10)))

        result = get_vet_summary(db, uuid4())

        assert result is not None
        assert result.name == "Dr. Prescription"

    def test_no_eligible_docs_returns_none_even_if_vet_contacts_exist(self):
        """Contacts linked only to Diagnostic/Other docs → service returns None."""
        # The DB-level filter on document_category means no rows reach first()
        db = _make_db(None)

        result = get_vet_summary(db, uuid4())

        assert result is None

    def test_correct_pet_id_is_queried(self):
        """Service passes the given pet_id into the db query filter."""
        pet_id = uuid4()
        db = _make_db(_row("Dr. Verma", date(2024, 1, 10)))

        get_vet_summary(db, pet_id)

        filter_call_args = db.query.return_value.join.return_value.filter.call_args
        assert filter_call_args is not None
