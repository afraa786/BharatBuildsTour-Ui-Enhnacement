from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.owner_auth import CurrentUser, issue_token
from app.db.session import get_db
from app.modules.identity.owner_models import User

router = APIRouter(tags=["owner-auth"])


class LoginIn(BaseModel):
    phone_number: str = Field(min_length=6, max_length=32)


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 7 * 24 * 60 * 60


class MeOut(BaseModel):
    id: str
    name: str
    phone_number: str
    business_id: str


@router.post("/auth/login", response_model=LoginOut)
def login(body: LoginIn, db: Annotated[Session, Depends(get_db)]) -> LoginOut:
    # TODO: add OTP verification before production.
    user = db.scalar(select(User).where(User.phone_number == body.phone_number.strip()))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Phone number is not registered")
    return LoginOut(access_token=issue_token(user))


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser) -> MeOut:
    return MeOut(
        id=str(user.id),
        name=user.name,
        phone_number=user.phone_number,
        business_id=str(user.business_id),
    )
