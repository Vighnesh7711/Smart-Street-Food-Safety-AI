"""Shared FastAPI dependencies: authentication and role-based access control."""

from typing import Callable, Iterable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.crud import user as crud_user
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.token import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")

# Reported as the WWW-Authenticate scheme on 401s.
_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """Decode the bearer token and load the matching user.

    Raises 401 for any malformed, expired, or unresolvable token. (Phase 1
    returned 403 here, which is incorrect for a missing/invalid credential
    and prevented clients from knowing to re-authenticate.)
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (jwt.InvalidTokenError, ValidationError):
        raise _CREDENTIALS_EXCEPTION

    if not token_data.sub:
        raise _CREDENTIALS_EXCEPTION

    try:
        user_id = int(token_data.sub)
    except (TypeError, ValueError):
        raise _CREDENTIALS_EXCEPTION

    user = crud_user.get_user(db, user_id=user_id)
    if not user:
        raise _CREDENTIALS_EXCEPTION
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


def _role_value(role) -> str:
    """Normalise a role to its plain string value.

    Depending on how the row was loaded, `role` may arrive as a UserRole
    enum or as a bare string, so compare on `.value` defensively.
    """
    return role.value if isinstance(role, UserRole) else str(role)


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Build a dependency that admits only the given roles.

    Usage:
        @router.get("/", dependencies=[Depends(require_roles(UserRole.REVIEWER))])

    Prefer this over checking `current_user.role` inside each handler: it
    keeps the rule visible in the route signature and in the generated
    OpenAPI schema.
    """
    allowed: Iterable[str] = {r.value for r in roles}

    def _dependency(current_user: User = Depends(get_current_active_user)) -> User:
        if _role_value(current_user.role) not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return _dependency
