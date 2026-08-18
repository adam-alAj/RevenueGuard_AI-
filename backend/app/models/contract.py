"""Contract and contract-line models."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDMixin
from app.models.customer import Customer


class Contract(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """A commercial agreement governing pricing, billing, and renewal terms."""

    __tablename__ = "contracts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )
    contract_number: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Dates
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Financial
    total_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    billing_frequency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    minimum_commitment: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    discount_cap_pct: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    # Renewal
    auto_renew: Mapped[bool] = mapped_column(default=False, nullable=False)
    renewal_terms: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    customer: Mapped[Customer] = relationship(back_populates="contracts")
    lines: Mapped[list[ContractLine]] = relationship(
        back_populates="contract", lazy="selectin"
    )


class ContractLine(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """A line item within a contract (service, quantity, unit price)."""

    __tablename__ = "contract_lines"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    # Relationships
    contract: Mapped[Contract] = relationship(back_populates="lines")
