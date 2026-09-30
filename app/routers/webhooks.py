from hmac import compare_digest
from typing import Annotated


from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.models.entities import Booking, Payment, WebhookEvent
from app.webhook_schemas import (
    PaymentWebhookRequest,
    PaymentWebhookResponse,
)


router = APIRouter(prefix="/payments", tags=["Payment webhooks"])

def duplicate_response(
    event: WebhookEvent,
    payload: dict,
) -> PaymentWebhookResponse: 

    if event.payload != payload:
        raise HTTPException(
            status_code= status.HTTP_409_CONFLICT,
            detail = "Event ID was already used with different content.",
        )
    
    return PaymentWebhookResponse(
        event_id=event.event_id,
        payment_id=event.payment_id,
        status=payload["status"],
        already_processed=True,
    )


@router.post(
    "/webhook/",
    response_model = PaymentWebhookResponse,
)
def process_payment_webhook(
    request: PaymentWebhookRequest,
    db: Annotated[Session, Depends(get_db)],
    webhook_secret : Annotated[
        str | None,
        Header(alias="X-Webhook-Secret"),
    ] = None,
) -> PaymentWebhookResponse :
    configured_secret = get_settings().webhook_secret

    if webhook_secret is None or not compare_digest(
        webhook_secret, configured_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )

    payload = request.model_dump()

    # Lock the payment before checking the event. Deliveries concerning
    # the same payment are serialized until this transaction finishes.

    payment = db.scalar(
        select(Payment)
        .where(Payment.id == request.payment_id)
        .with_for_update()
    )

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    existing_event = db.scalar(
        select(WebhookEvent).where(
            WebhookEvent.event_id == request.event_id
        )
    )

    if existing_event is not None:
        return duplicate_response(existing_event, payload)

    booking = db.scalar(
        select(Booking)
        .where(Booking.id == payment.booking_id)
        .with_for_update()
    )

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment has no valid booking",
        )

    expected_booking_status = (
        "CONFIRMED" if request.status == "SUCCESS" else "FAILED"
    )

    if payment.status == "PENDING":
        if booking.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Booking and payment states conflict",
            )

        payment.status = request.status
        booking.status = expected_booking_status

    elif (
        payment.status != request.status
        or booking.status != expected_booking_status
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Webhook conflicts with the recorded payment",
        )

    db.add(
        WebhookEvent(
            event_id=request.event_id,
            payment_id=payment.id,
            payload=payload,
        )
    )

    try:
        db.commit()
    except IntegrityError:
        # A concurrent request for a different payment may have inserted
        # this same event_id first. The unique DB constraint decides.
        db.rollback()
        existing_event = db.scalar(
            select(WebhookEvent).where(
                WebhookEvent.event_id == request.event_id
            )
        )
        if existing_event is None:
            raise

        return duplicate_response(existing_event, payload)

    return PaymentWebhookResponse(
        event_id=request.event_id,
        payment_id=payment.id,
        status=request.status,
        already_processed=False,
    )
