from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Boolean,
    Text,
    UniqueConstraint,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

class Centre(Base):
    __tablename__ = "centres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(Text , nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DiagnosticTest(Base):
    __tablename__ = "diagnostic_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class CentreTestOffering(Base):
    __tablename__ = "centre_test_offerings"
    __table_args__ = (
        UniqueConstraint("centre_id", "test_id", name="uq_offering_centre_test"),
        CheckConstraint("price >= 0", name="ck_offering_price_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    centre_id: Mapped[int] = mapped_column(
        ForeignKey("centres.id", ondelete="CASCADE"), nullable=False
    )
    test_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_tests.id", ondelete="CASCADE"), nullable=False
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10,2), nullable=False)
    is_active: Mapped[bool] = mapped_column( default=True, nullable=False)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_booking_amount_nonnegative"),
        CheckConstraint(
             "status IN ('PENDING', 'CONFIRMED', 'FAILED')",
             name="ck_booking_status"
        ),
        Index("ix_booking_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    offering_id: Mapped[int] = mapped_column(
        ForeignKey("centre_test_offerings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    appointment_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

class Payment(Base):
      __tablename__ = "payments"
      __table_args__ = (
          CheckConstraint("amount >= 0", name="ck_payment_amount_nonnegative"),
          CheckConstraint(
              "status IN ('PENDING', 'SUCCESS', 'FAILED')",
              name="ck_payment_status",
          ),
          Index("ix_payment_booking_id", "booking_id"),
      )

      id: Mapped[int] = mapped_column(primary_key=True)
      booking_id: Mapped[int] = mapped_column(
          ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
      )
      amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
      status: Mapped[str] = mapped_column(
           String(20), default="PENDING", nullable=False
      )
      created_at: Mapped[datetime] = mapped_column(
           DateTime(timezone=True), server_default=func.now(), nullable=False
      )

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        Index("ix_webhook_events_payment_id", "payment_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )