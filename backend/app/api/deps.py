from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models import Organization, ApiKey
from app.db import crud
from jose import jwt, JWTError
# pyrefly: ignore [missing-import]
from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets
import hashlib

SECRET_KEY = "dummy-secret-key-for-hackathon-only"  # Replace with env var in prod
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_org(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        org_id: str = payload.get("sub")
        if org_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    org = await crud.get_organization_by_id(db, org_id)
    if org is None:
        raise credentials_exception
    return org

def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()

async def verify_api_key(api_key_header: str = Depends(api_key_header), db: AsyncSession = Depends(get_db)):
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key",
        )
    
    # Expect "Bearer <API_KEY>"
    parts = api_key_header.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key format")
    
    raw_key = parts[1]
    key_hash = hash_api_key(raw_key)
    
    api_key_record = await crud.get_api_key_by_hash(db, key_hash)
    if not api_key_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
        
    return api_key_record
