from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session


from app.booking_schemas import BookingCreate, BookingResponse
from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.entities import Booking, CentreTestOffering, User

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_booking(
        request: BookingCreate,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
) -> Booking:
    if request.appointment_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="appointment_at must be in the future",
        )


    offering = db.get(CentreTestOffering, request.offering_id)

    if offering is None or not offering.is_active:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = "Active offering is not found"
        )

    booking = Booking(
        user_id = current_user.id,
        offering_id = offering.id,
        appointment_at = request.appointment_at,
        amount = offering.price,
        status = "PENDING",
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    return booking



@router.get("", response_model = list[BookingResponse])
def list_bookings(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge = 1, le = 100)] = 20,
    offset: Annotated[int, Query(ge = 0)] = 0
) -> list[Booking]:
    return list(
        db.scalars(
            select(Booking)
            .where(Booking.user_id == current_user.id)
            .order_by(Booking.created_at.desc(), Booking.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
     booking_id : int,
     db: Annotated[Session, Depends(get_db)],
     current_user: Annotated[User, Depends(get_current_user)]
) -> Booking:
    booking = db.scalar(
        select(Booking).where(
            Booking.id == booking_id,
            Booking.user_id == current_user.id
        )
    )

    if booking is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = "Booking not found",
        )


    return booking