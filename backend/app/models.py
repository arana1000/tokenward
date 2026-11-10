import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, MetaData, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint names, so future migrations can find and change them.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ApiKey(Base):
    """A client's API key. Only a hash of the key is stored, never the key itself."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    key_prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RequestLog(Base):
    """One row per authenticated chat request, successful or not."""

    __tablename__ = "request_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # Keys are revoked, never deleted, in normal use. CASCADE only matters for test cleanup.
    api_key_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_keys.id", ondelete="CASCADE"), index=True
    )
    model: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str | None] = mapped_column(String(50))
    status_code: Mapped[int]
    outcome: Mapped[str] = mapped_column(String(20))
    error_type: Mapped[str | None] = mapped_column(String(50))
    latency_ms: Mapped[int | None]
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 8))