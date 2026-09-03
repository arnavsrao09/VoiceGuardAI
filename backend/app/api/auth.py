from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db import crud
from pydantic import BaseModel, EmailStr
from app.api.deps import get_password_hash, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta
import uuid

router = APIRouter()

class OrgCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str

    model_config = {"from_attributes": True}

@router.post("/register", response_model=OrgResponse)
async def register(org_data: OrgCreate, db: AsyncSession = Depends(get_db)):
    db_org = await crud.get_organization_by_email(db, email=org_data.email)
    if db_org:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(org_data.password)
    new_org = await crud.create_organization(
        db, name=org_data.name, email=org_data.email, hashed_password=hashed_password
    )
    return new_org

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    org = await crud.get_organization_by_email(db, email=form_data.username)
    if not org or not verify_password(form_data.password, org.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(org.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
