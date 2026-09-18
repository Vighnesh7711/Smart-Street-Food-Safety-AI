from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserCreateOAuth


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_provider(db: Session, auth_provider: str, provider_id: str) -> Optional[User]:
    return db.query(User).filter(User.auth_provider == auth_provider, User.provider_id == provider_id).first()


def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, user_in: UserCreate) -> User:
    db_obj = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        # `user_in.role` is Optional, so an explicit JSON null would otherwise
        # write NULL and violate the NOT NULL constraint.
        role=user_in.role or UserRole.VENDOR,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def create_user_oauth(db: Session, user_in: UserCreateOAuth) -> User:
    db_obj = User(
        email=user_in.email,
        full_name=user_in.full_name,
        role=user_in.role or UserRole.VENDOR,
        auth_provider=user_in.auth_provider,
        provider_id=user_in.provider_id,
        hashed_password=None,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_user(db: Session, *, user: User, user_in: UserUpdate) -> User:
    data = user_in.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    for field, value in data.items():
        if value is not None:
            setattr(user, field, value)
    if password:
        user.hashed_password = get_password_hash(password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
