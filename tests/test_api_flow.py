from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.entities import User

from app.core.config import get_settings
from app.models.entities import (
    Booking,
    Centre,
    CentreTestOffering,
    DiagnosticTest,
    Payment,
    WebhookEvent,
)


def signup_and_login(client: TestClient, email: str) -> dict[str, str]:
    password = "test-password-123"

    signup = client.post(
        "/auth/signup",
        json={"email": email, "password": password},
    )
    assert signup.status_code == 201, signup.text

    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text

    return {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


def add_offering(db: Session) -> CentreTestOffering:
    suffix = uuid4().hex[:8]

    centre = Centre(
        name=f"Test Centre {suffix}",
        address="Test address",
    )
    diagnostic_test = DiagnosticTest(
        name=f"Test {suffix}",
        description="Test description",
    )

    db.add_all([centre, diagnostic_test])
    db.flush()

    offering = CentreTestOffering(
        centre_id=centre.id,
        test_id=diagnostic_test.id,
        price=Decimal("450.00"),
        is_active=True,
    )
    db.add(offering)
    db.flush()

    return offering


def create_booking(
    client: TestClient,
    headers: dict[str, str],
    offering_id: int,
):
    appointment = datetime.now(timezone.utc) + timedelta(days=7)

    return client.post(
        "/bookings",
        headers=headers,
        json={
            "offering_id": offering_id,
            "appointment_at": appointment.isoformat(),
        },
    )


def webhook_headers() -> dict[str, str]:
    return {
        "X-Webhook-Secret": get_settings().webhook_secret
    }


def test_authentication_and_duplicate_signup(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401

    headers = signup_and_login(client, "alice@example.com")

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"

    duplicate = client.post(
        "/auth/signup",
        json={
            "email": "alice@example.com",
            "password": "another-password",
        },
    )
    assert duplicate.status_code == 409

    wrong_password = client.post(
        "/auth/login",
        json={
            "email": "alice@example.com",
            "password": "incorrect-password",
        },
    )
    assert wrong_password.status_code == 401


def test_catalogue_and_booking_price_snapshot(
    client: TestClient,
    db_session: Session,
) -> None:
    offering = add_offering(db_session)
    headers = signup_and_login(client, "buyer@example.com")

    centres = client.get("/centres")
    assert centres.status_code == 200
    assert any(
        centre["id"] == offering.centre_id
        for centre in centres.json()
    )

    tests = client.get(f"/centres/{offering.centre_id}/tests")
    assert tests.status_code == 200
    assert any(
        item["offering_id"] == offering.id
        for item in tests.json()
    )

    created = create_booking(client, headers, offering.id)
    assert created.status_code == 201, created.text
    booking = created.json()
    assert booking["status"] == "PENDING"
    assert Decimal(str(booking["amount"])) == Decimal("450.00")

    offering.price = Decimal("600.00")
    db_session.commit()

    fetched = client.get(
        f"/bookings/{booking['id']}",
        headers=headers,
    )
    assert fetched.status_code == 200
    assert Decimal(str(fetched.json()["amount"])) == Decimal("450.00")


def test_booking_validation_and_ownership(
    client: TestClient,
    db_session: Session,
) -> None:
    offering = add_offering(db_session)
    owner = signup_and_login(client, "owner@example.com")
    other_user = signup_and_login(client, "other@example.com")

    assert client.post(
        "/bookings",
        json={
            "offering_id": offering.id,
            "appointment_at": (
                datetime.now(timezone.utc) + timedelta(days=7)
            ).isoformat(),
        },
    ).status_code == 401

    created = create_booking(client, owner, offering.id)
    assert created.status_code == 201, created.text
    booking_id = created.json()["id"]

    assert client.get(
        f"/bookings/{booking_id}",
        headers=other_user,
    ).status_code == 404

    assert client.get(
        "/bookings",
        headers=other_user,
    ).json() == []

    past = client.post(
        "/bookings",
        headers=owner,
        json={
            "offering_id": offering.id,
            "appointment_at": (
                datetime.now(timezone.utc) - timedelta(days=1)
            ).isoformat(),
        },
    )
    assert past.status_code == 422

    unknown = create_booking(client, owner, 999999)
    assert unknown.status_code == 404


def test_payment_and_webhook_retries(
    client: TestClient,
    db_session: Session,
) -> None:
    offering = add_offering(db_session)
    headers = signup_and_login(client, "payer@example.com")

    created = create_booking(client, headers, offering.id)
    assert created.status_code == 201, created.text
    booking_id = created.json()["id"]

    paid = client.post(
        "/payments/",
        headers=headers,
        json={"booking_id": booking_id},
    )
    assert paid.status_code == 201, paid.text
    payment_id = paid.json()["id"]
    assert paid.json()["status"] == "PENDING"

    db_session.expire_all()
    assert db_session.get(Payment, payment_id).status == "PENDING"
    assert db_session.get(Booking, booking_id).status == "PENDING"

    second_payment = client.post(
        "/payments/",
        headers=headers,
        json={"booking_id": booking_id},
    )
    assert second_payment.status_code == 409

    event = {
        "event_id": f"evt-{uuid4().hex}",
        "payment_id": payment_id,
        "status": "SUCCESS",
    }

    first = client.post(
        "/payments/webhook/",
        headers=webhook_headers(),
        json=event,
    )
    assert first.status_code == 200, first.text
    assert first.json()["already_processed"] is False

    db_session.expire_all()
    assert db_session.get(Payment, payment_id).status == "SUCCESS"
    assert db_session.get(Booking, booking_id).status == "CONFIRMED"
    
    replay = client.post(
        "/payments/webhook/",
        headers=webhook_headers(),
        json=event,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["already_processed"] is True

    conflicting_reuse = client.post(
        "/payments/webhook/",
        headers=webhook_headers(),
        json={**event, "status": "FAILED"},
    )
    assert conflicting_reuse.status_code == 409

    conflicting_new_event = client.post(
        "/payments/webhook/",
        headers=webhook_headers(),
        json={**event, "event_id": f"evt-{uuid4().hex}", "status": "FAILED"},
    )
    assert conflicting_new_event.status_code == 409

    assert (
        db_session.query(WebhookEvent)
        .filter(WebhookEvent.payment_id == payment_id)
        .count()
        == 1
    )
    


def test_failed_payment_and_invalid_webhook_secret(
    client: TestClient,
    db_session: Session,
) -> None:
    offering = add_offering(db_session)
    headers = signup_and_login(client, "failure@example.com")

    created = create_booking(client, headers, offering.id)
    assert created.status_code == 201, created.text
    booking_id = created.json()["id"]

    payment_response = client.post(
        "/payments/",
        headers=headers,
        json={"booking_id": booking_id},
    )
    assert payment_response.status_code == 201, payment_response.text
    payment_id = payment_response.json()["id"]
    assert payment_response.json()["status"] == "PENDING"

    event = {
        "event_id": f"evt-{uuid4().hex}",
        "payment_id": payment_id,
        "status": "FAILED",
    }

    denied = client.post(
        "/payments/webhook/",
        headers={"X-Webhook-Secret": "wrong-secret"},
        json=event,
    )
    assert denied.status_code == 401

    db_session.expire_all()
    assert db_session.get(Payment, payment_id).status == "PENDING"
    assert db_session.get(Booking, booking_id).status == "PENDING"

    accepted = client.post(
        "/payments/webhook/",
        headers=webhook_headers(),
        json=event,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["already_processed"] is False

    db_session.expire_all()
    assert db_session.get(Payment, payment_id).status == "FAILED"
    assert db_session.get(Booking, booking_id).status == "FAILED"


def test_admin_catalogue_management(
    client: TestClient,
    db_session: Session,
) -> None:
    admin_headers = signup_and_login(client, "admin-test@example.com")
    normal_headers = signup_and_login(client, "normal-test@example.com")

    body = {
        "name": f"Admin Centre {uuid4().hex[:8]}",
        "address": "Bengaluru",
    }

    # Authentication and authorization are separate checks.
    assert client.post("/centres", json=body).status_code == 401
    assert client.post(
        "/centres",
        headers=normal_headers,
        json=body,
    ).status_code == 403

    admin = db_session.scalar(
        select(User).where(User.email == "admin-test@example.com")
    )
    assert admin is not None
    admin.is_admin = True
    db_session.commit()

    created_centre = client.post(
        "/centres",
        headers=admin_headers,
        json=body,
    )
    assert created_centre.status_code == 201, created_centre.text
    centre_id = created_centre.json()["id"]

    updated_centre = client.patch(
        f"/centres/{centre_id}",
        headers=admin_headers,
        json={"address": "Whitefield, Bengaluru"},
    )
    assert updated_centre.status_code == 200, updated_centre.text
    assert updated_centre.json()["address"] == "Whitefield, Bengaluru"

    test_name = f"Vitamin D {uuid4().hex[:8]}"
    created_test = client.post(
        "/tests",
        headers=admin_headers,
        json={
            "name": test_name,
            "description": "Vitamin D test",
        },
    )
    assert created_test.status_code == 201, created_test.text
    test_id = created_test.json()["id"]

    created_offering = client.post(
        f"/centres/{centre_id}/tests",
        headers=admin_headers,
        json={"test_id": test_id, "price": "700.00"},
    )
    assert created_offering.status_code == 201, created_offering.text
    offering_id = created_offering.json()["offering_id"]

    # The public catalogue shows the new offering.
    public_list = client.get(f"/centres/{centre_id}/tests")
    assert public_list.status_code == 200
    assert any(
        item["offering_id"] == offering_id
        for item in public_list.json()
    )

    # The centre/test pair is unique.
    duplicate = client.post(
        f"/centres/{centre_id}/tests",
        headers=admin_headers,
        json={"test_id": test_id, "price": "700.00"},
    )
    assert duplicate.status_code == 409

    # An admin can deactivate it; public listing then hides it.
    deactivated = client.patch(
        f"/offerings/{offering_id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text

    public_list = client.get(f"/centres/{centre_id}/tests")
    assert all(
        item["offering_id"] != offering_id
        for item in public_list.json()
    )

    # A normal user still cannot modify it.
    assert client.patch(
        f"/offerings/{offering_id}",
        headers=normal_headers,
        json={"price": "1.00"},
    ).status_code == 403