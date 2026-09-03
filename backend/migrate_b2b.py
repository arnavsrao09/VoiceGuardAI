"""
Migration script to add B2B multi-tenant columns to existing PostgreSQL tables.
Run once: uv run python migrate_b2b.py
"""
import asyncio
import asyncpg
import os
from urllib.parse import unquote

# Read DATABASE_URL from .env
db_url = None
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line.startswith("DATABASE_URL=") and not line.startswith("#"):
            db_url = line.split("=", 1)[1].strip().strip('"')
            break

if not db_url:
    raise RuntimeError("DATABASE_URL not found in .env")

# Convert SQLAlchemy URL to raw asyncpg URL
DATABASE_URL = db_url.replace("postgresql+asyncpg://", "postgresql://")

MIGRATIONS = [
    # 1. Create organizations table
    """
    CREATE TABLE IF NOT EXISTS organizations (
        id UUID PRIMARY KEY,
        name VARCHAR,
        email VARCHAR UNIQUE,
        hashed_password VARCHAR,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """,
    # 2. Create api_keys table
    """
    CREATE TABLE IF NOT EXISTS api_keys (
        id UUID PRIMARY KEY,
        organization_id UUID REFERENCES organizations(id),
        key_hash VARCHAR UNIQUE,
        prefix VARCHAR,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """,
    # 3. Add organization_id to detection_sessions
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='detection_sessions' AND column_name='organization_id'
        ) THEN
            ALTER TABLE detection_sessions ADD COLUMN organization_id UUID REFERENCES organizations(id);
        END IF;
    END $$;
    """,
    # 4. Add api_key_id to detection_sessions
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='detection_sessions' AND column_name='api_key_id'
        ) THEN
            ALTER TABLE detection_sessions ADD COLUMN api_key_id UUID REFERENCES api_keys(id);
        END IF;
    END $$;
    """,
    # 5. Add organization_id to voice_profiles
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='voice_profiles' AND column_name='organization_id'
        ) THEN
            ALTER TABLE voice_profiles ADD COLUMN organization_id UUID REFERENCES organizations(id);
        END IF;
    END $$;
    """,
    # 6. Rename user_id to external_user_id in voice_profiles (if user_id exists)
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='voice_profiles' AND column_name='user_id'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='voice_profiles' AND column_name='external_user_id'
        ) THEN
            ALTER TABLE voice_profiles RENAME COLUMN user_id TO external_user_id;
        END IF;
    END $$;
    """,
    # 7. Add external_user_id if neither user_id nor external_user_id exists
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='voice_profiles' AND column_name='external_user_id'
        ) THEN
            ALTER TABLE voice_profiles ADD COLUMN external_user_id VARCHAR;
        END IF;
    END $$;
    """,
    # 8. Add organization_id to alerts
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='alerts' AND column_name='organization_id'
        ) THEN
            ALTER TABLE alerts ADD COLUMN organization_id UUID REFERENCES organizations(id);
        END IF;
    END $$;
    """,
    # 9. Create indexes
    """
    CREATE INDEX IF NOT EXISTS idx_detection_sessions_org ON detection_sessions(organization_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_voice_profiles_org ON voice_profiles(organization_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_voice_profiles_ext_user ON voice_profiles(external_user_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_alerts_org ON alerts(organization_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_api_keys_org ON api_keys(organization_id);
    """,
]

async def run_migrations():
    conn = await asyncpg.connect(DATABASE_URL)
    print("Connected to PostgreSQL. Running B2B migrations...\n")
    
    for i, sql in enumerate(MIGRATIONS, 1):
        try:
            await conn.execute(sql)
            print(f"  [{i}/{len(MIGRATIONS)}] OK")
        except Exception as e:
            print(f"  [{i}/{len(MIGRATIONS)}] WARN: {e}")
    
    await conn.close()
    print("\nAll migrations applied successfully!")

if __name__ == "__main__":
    asyncio.run(run_migrations())
