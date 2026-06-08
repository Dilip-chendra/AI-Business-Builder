from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Order(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    business_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), index=True)
    stripe_session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(255))
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    status: Mapped[str] = mapped_column(String(60), nullable=False, default="pending")
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    business = relationship("Business", back_populates="orders")
    product = relationship("Product", back_populates="orders")
