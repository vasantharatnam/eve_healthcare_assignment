from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.entities import Booking, Payment, User
from app.payment_schemas import PaymentCreate, PaymentResponse


router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mock_payment(
    request: PaymentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Payment:
    # Lock this booking until commit. Concurrent payment requests for the
    # same booking will run one after the other.
    booking = db.scalar(
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

    if booking.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Booking is not eligible for payment",
        )

    payment = Payment(
        booking_id=booking.id,
        amount=booking.amount,
        status=request.outcome,
    )
    db.add(payment)

    booking.status = (
        "CONFIRMED" if request.outcome == "SUCCESS" else "FAILED"
    )

    db.commit()
    db.refresh(payment)
    return payment