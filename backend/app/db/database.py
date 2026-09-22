from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
import os
from app.logging_config import get_logger

logger = get_logger("db")

# Determine database URL with SQLite fallback
_db_url = settings.database_url

def _build_engine():
    """Create async engine, falling back to SQLite if PostgreSQL is unavailable."""
    try:
        connect_args = {"statement_cache_size": 0} if "postgresql" in _db_url else {}
        engine = create_async_engine(_db_url, connect_args=connect_args)
        logger.info("Using PostgreSQL: %s…", _db_url[:50])
        return engine, "postgresql"
    except Exception as e:
        logger.warning("PostgreSQL connection failed: %s", e)

    # Fallback to SQLite
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "voiceguard.db")
    sqlite_url = f"sqlite+aiosqlite:///{sqlite_path}"
    _db_url = sqlite_url
    logger.info("Falling back to SQLite: %s", sqlite_path)
    engine = create_async_engine(sqlite_url)
    return engine, "sqlite"


# Detect if the configured URL is PostgreSQL or SQLite
_is_sqlite = "sqlite" in _db_url.lower()

if _is_sqlite:
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "voiceguard.db")
    _db_url = f"sqlite+aiosqlite:///{sqlite_path}"
    engine = create_async_engine(_db_url)
    db_dialect = "sqlite"
    logger.info("Using SQLite: %s", sqlite_path)
else:
    try:
        # Supabase and pgbouncer transaction poolers require statement_cache_size=0 for asyncpg
        engine = create_async_engine(
            _db_url,
            connect_args={"statement_cache_size": 0}
        )
        db_dialect = "postgresql"
        logger.info("Using PostgreSQL: %s…", _db_url[:60])
    except Exception as e:
        logger.warning("PostgreSQL engine creation failed (%s), falling back to SQLite", e)
        sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "voiceguard.db")
        _db_url = f"sqlite+aiosqlite:///{sqlite_path}"
        engine = create_async_engine(_db_url)
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
