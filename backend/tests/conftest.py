"""Shared test fixtures and configuration."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone


class FakeSession:
    """A fake DB session that returns mock data without connecting to PostgreSQL."""

    def __init__(self):
        self._committed = False

    async def commit(self):
        self._committed = True

    async def rollback(self):
        pass

    async def close(self):
        pass

    async def refresh(self, obj):
        pass

    def add(self, obj):
        pass

    async def delete(self, obj):
        pass

    async def execute(self, stmt):
        # Return an empty result set by default
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        return mock_result


async def override_get_db():
    session = FakeSession()
    yield session


@pytest.fixture
def fake_db():
    return FakeSession()
