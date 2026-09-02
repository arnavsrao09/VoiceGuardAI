from typing import AsyncGenerator
from app.db.database import get_db_session

async def get_db() -> AsyncGenerator:
    async for session in get_db_session():
        yield session
