from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
import os

# Determine database URL with SQLite fallback
_db_url = settings.database_url

def _build_engine():
    """Create async engine, falling back to SQLite if PostgreSQL is unavailable."""
    global _db_url
    try:
        # Attempt PostgreSQL connection
        engine = create_async_engine(_db_url, echo=settings.debug)
        print(f"[DB] Using PostgreSQL: {_db_url[:50]}…")
        return engine, "postgresql"
    except Exception as e:
        print(f"[DB] PostgreSQL connection failed: {e}")

    # Fallback to SQLite
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "voiceguard.db")
    sqlite_url = f"sqlite+aiosqlite:///{sqlite_path}"
    _db_url = sqlite_url
    print(f"[DB] Falling back to SQLite: {sqlite_path}")
    engine = create_async_engine(sqlite_url, echo=settings.debug)
    return engine, "sqlite"


# Detect if the configured URL is PostgreSQL or SQLite
_is_sqlite = "sqlite" in _db_url.lower()

if _is_sqlite:
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "voiceguard.db")
    _db_url = f"sqlite+aiosqlite:///{sqlite_path}"
    engine = create_async_engine(_db_url, echo=settings.debug)
    db_dialect = "sqlite"
    print(f"[DB] Using SQLite: {sqlite_path}")
else:
    try:
        engine = create_async_engine(_db_url, echo=settings.debug)
        db_dialect = "postgresql"
        print(f"[DB] Using PostgreSQL: {_db_url[:60]}…")
    except Exception as e:
        print(f"[DB] PostgreSQL engine creation failed ({e}), falling back to SQLite")
        sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "voiceguard.db")
        _db_url = f"sqlite+aiosqlite:///{sqlite_path}"
        engine = create_async_engine(_db_url, echo=settings.debug)
        db_dialect = "sqlite"

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()

# Dependency for FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
