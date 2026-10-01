
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.entities import (
    Booking,
    Payment,
    PaymentIdempotencyKey,
    User,
)
from app.payment_schemas import PaymentCreate, PaymentResponse


router = APIRouter(prefix="/payments", tags=["Payments"])

def  payment_for_key(
     db:Session,
     record: PaymentIdempotencyKey,
     booking_id: int   
) -> Payment:
    if record.booking_id != booking_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key already used for a different booking",
        )

    payment = db.get(Payment, record.payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Idempotency key points to a non-existent payment",
        )

    return payment


@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mock_payment(
    request: PaymentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[
        UUID,
        Header(alias="Idempotency-Key"),
    ],
) -> Payment:
    key = str(idempotency_key)

    booking =  db.scalar(
        select(Booking)
        .where(
            Booking.id == request.booking_id,
            Booking.user_id == current_user.id,
        )
        .with_for_update()
    )

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    # Check the key BEFORE checking the booking's current status. A retry
    # must still work after a webhook has confirmed the booking.

    existing_key = db.scalar(
        select(PaymentIdempotencyKey).where(
            PaymentIdempotencyKey.user_id == current_user.id,
            PaymentIdempotencyKey.key == key,
        )
    )

    if existing_key is not None:
        return payment_for_key(db, existing_key, request.booking_id)

    if booking.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Booking is not eligible for payment",
        )

    existing_payment = db.scalar(
        select(Payment).where(Payment.booking_id == booking.id)
    )

    if existing_payment is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A payment is already in progress for this booking",
        )

    payment = Payment(
        booking_id=booking.id,
        amount=booking.amount,
        status="PENDING",
    )
    db.add(payment)
    db.flush()  # Obtain payment.id inside this transaction.

    db.add(
        PaymentIdempotencyKey(
            user_id=current_user.id,
            booking_id=booking.id,
            payment_id=payment.id,
            key=key,
        )
    )

    try:
        db.commit()
    except IntegrityError:
        # Another request may have committed the same user/key while this
        # request was in progress, possibly for another booking.
        db.rollback()

        winning_key = db.scalar(
            select(PaymentIdempotencyKey).where(
                PaymentIdempotencyKey.user_id == current_user.id,
                PaymentIdempotencyKey.key == key,
            )
        )
        if winning_key is None:
            raise

        return payment_for_key(db, winning_key, booking.id)

    db.refresh(payment)
    return payment