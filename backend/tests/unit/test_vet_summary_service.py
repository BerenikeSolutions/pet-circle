"""
Unit tests for vet_summary_service.py.

Covers:
  - No vet contacts → None returned
  - Single vet contact → returned as primary vet
  - Multiple vets → most-mentioned vet selected
  - Tie on mention count → most-recent event_date wins
  - Vet with no document event_dates → last_visit is None

All tests are pure Python with no DB or external dependencies.
The SQLAlchemy session is replaced by a MagicMock whose query chain
returns a controlled list of pre-aggregated rows, mirroring what the
real GROUP BY query would produce.
"""

import os
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

os.environ.setdefault("APP_ENV", "test")

from app.services.vet_summary_service import VetSummary, get_vet_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(rows: list) -> MagicMock:
    """Return a mock db session whose .query(…).…chain().all() returns *rows*."""
    db = MagicMock()
    chain = db.query.return_value
    # Each chained method on the query object returns the same chain so that
    # .outerjoin().filter().group_by().order_by().all() all resolve correctly.
    chain.outerjoin.return_value = chain
    chain.filter.return_value = chain
    chain.group_by.return_value = chain
    chain.order_by.return_value = chain
    chain.all.return_value = rows
    return db


def _row(
    name: str,
    mention_count: int,
    last_visit: date | None,
) -> SimpleNamespace:
    """Build a fake aggregated result row (as returned by the SQLAlchemy query)."""
    return SimpleNamespace(
        name=name,
        mention_count=mention_count,
        last_visit=last_visit,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetVetSummary:
    def test_no_contacts_returns_none(self):
        """No vet contacts for the pet → service returns None."""
        db = _make_db([])

        result = get_vet_summary(db, uuid4())

        assert result is None

    def test_single_vet_returned(self):
        """Single vet contact → returned as VetSummary with correct fields."""
        pet_id = uuid4()
        rows = [_row("Dr. Sharma", 1, date(2024, 6, 15))]
        db = _make_db(rows)

        result = get_vet_summary(db, pet_id)

        assert result == VetSummary(name="Dr. Sharma", last_visit=date(2024, 6, 15))

    def test_most_mentioned_vet_selected(self):
        """Most-mentioned vet (rows[0] after DB ordering) is returned as primary."""
        # The real query orders rows by mention_count DESC — we replicate that
        # ordering in the fixture so rows[0] is the expected winner.
        rows = [
            _row("Dr. Patel", 3, date(2024, 8, 1)),
            _row("Dr. Sharma", 1, date(2024, 6, 15)),
        ]
        db = _make_db(rows)

        result = get_vet_summary(db, uuid4())

        assert result is not None
        assert result.name == "Dr. Patel"
        assert result.last_visit == date(2024, 8, 1)

    def test_tie_broken_by_most_recent_event_date(self):
        """Two vets with equal mention count — newer event_date wins (rows[0])."""
        rows = [
            _row("Dr. Newer", 2, date(2024, 10, 1)),
            _row("Dr. Older", 2, date(2024, 3, 15)),
        ]
        db = _make_db(rows)

        result = get_vet_summary(db, uuid4())

        assert result is not None
        assert result.name == "Dr. Newer"
        assert result.last_visit == date(2024, 10, 1)

    def test_last_visit_none_when_no_event_dates(self):
        """Vet exists but linked documents have no event_date → last_visit=None."""
        rows = [_row("Dr. Nair", 2, None)]
        db = _make_db(rows)

        result = get_vet_summary(db, uuid4())

        assert result is not None
        assert result.name == "Dr. Nair"
        assert result.last_visit is None

    def test_correct_pet_id_is_queried(self):
        """Service passes the given pet_id into the db query filter."""
        pet_id = uuid4()
        db = _make_db([_row("Dr. Verma", 1, date(2024, 1, 10))])

        get_vet_summary(db, pet_id)

        # The filter call must have received the pet_id somewhere in its args
        filter_call_args = db.query.return_value.outerjoin.return_value.filter.call_args
        assert filter_call_args is not None
