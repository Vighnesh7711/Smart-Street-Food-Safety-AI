"""Shared SQLAlchemy column types.

`JSONB` on PostgreSQL, plain `JSON` elsewhere. Using a variant keeps the
models portable enough to run against SQLite in tests while still getting
JSONB's indexing and storage benefits in production.
"""

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSONType = JSON().with_variant(JSONB, "postgresql")
