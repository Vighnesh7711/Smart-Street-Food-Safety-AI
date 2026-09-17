from sqlalchemy import Column, Enum, Integer, String

from app.db.base_class import Base
from app.models.enums import UserRole

__all__ = ["User", "UserRole"]


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    # values_callable makes Postgres store the enum *values* ("vendor",
    # "reviewer", ...) rather than SQLAlchemy's default of the member
    # *names* ("VENDOR"). The lowercase form matches the JSON API contract
    # and keeps raw SQL reads legible.
    role = Column(
        Enum(
            UserRole,
            name="userrole",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        default=UserRole.VENDOR,
        nullable=False,
    )
    full_name = Column(String, nullable=True)
