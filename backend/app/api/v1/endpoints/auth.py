"""Authentication: token issue, registration, and current-user lookup."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user
from app.core import security
from app.core.config import settings
from app.crud import user as crud_user
from app.crud import vendor as crud_vendor
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import MeResponse, UserCreate, UserRead

router = APIRouter()


@router.post("/login/access-token", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Token:
    """OAuth2 password flow. Returns a bearer token valid for
    ACCESS_TOKEN_EXPIRE_MINUTES."""
    user = crud_user.get_user_by_email(db, email=form_data.username)
    if not user or not security.verify_password(
        form_data.password, user.hashed_password
    ):
        # Deliberately identical for unknown-email and wrong-password so the
        # endpoint does not confirm which emails are registered.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        token_type="bearer",
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
) -> User:
    """Public self-registration.

    Phase 1 passed `user_in.role` straight through to the database, so anyone
    could POST `{"role": "reviewer"}` (or "admin") and be granted dashboard
    access. Privileged roles are now rejected here; they must be provisioned
    out-of-band against the database.
    """
    requested = user_in.role or UserRole.VENDOR
    if requested not in UserRole.self_assignable():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Role '{requested.value}' cannot be self-assigned. "
                "Allowed: "
                + ", ".join(sorted(r.value for r in UserRole.self_assignable()))
            ),
        )

    if crud_user.get_user_by_email(db, email=user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )

    return crud_user.create_user(db, user_in=user_in)


@router.get("/me", response_model=MeResponse)
def read_current_user(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    """The caller's identity plus their vendor profile, if they have one.

    The mobile client uses this on load to decide between the onboarding
    form and the scan tab without a second request.
    """
    vendor = crud_vendor.get_vendor_by_user_id(db, user_id=current_user.id)
    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        vendor_id=vendor.id if vendor else None,
        preferred_language=vendor.preferred_language if vendor else None,
    )
