from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.conftest import auth_header
from app.core.config import settings
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.test import DiagnosticTest
from app.models.user import User
from app.core.security import hash_password


def _webhook_headers():
    return {"X-Webhook-Secret": settings.WEBHOOK_SECRET}


def _create_pending_payment(db):
    """Create a user, booking, and PENDING payment for webhook tests."""
    user = User(email="wh@test.com", password_hash=hash_password("pass123"), full_name="WH User")
    db.add(user)
    db.flush()

    centre = DiagnosticCentre(name="Lab", location="City")
    test = DiagnosticTest(name="Test", description="Desc")
    db.add_all([centre, test])
    db.flush()
    db.add(CentreTest(centre_id=centre.id, test_id=test.id, price=Decimal("500.00")))
    db.flush()

    booking = Booking(
        user_id=user.id,
        centre_id=centre.id,
        test_id=test.id,
        appointment_at=datetime.now(timezone.utc) + timedelta(days=1),
        amount=Decimal("500.00"),
        status=BookingStatus.PENDING,
    )
    db.add(booking)
    db.flush()

    payment = Payment(
        booking_id=booking.id,
        provider_payment_id=f"prov_{booking.id}",
        amount=Decimal("500.00"),
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    db.refresh(booking)
    return payment, booking


def test_webhook_success(client, db):
    payment, booking = _create_pending_payment(db)
    resp = client.post("/api/v1/payments/webhook", json={
        "event_id": "evt_001",
        "event_type": "payment.success",
        "payment_id": payment.id,
        "status": "SUCCESS",
    }, headers=_webhook_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    db.refresh(payment)
    db.refresh(booking)
    assert payment.status == PaymentStatus.SUCCESS
    assert booking.status == BookingStatus.CONFIRMED


def test_webhook_failed(client, db):
    payment, booking = _create_pending_payment(db)
    resp = client.post("/api/v1/payments/webhook", json={
        "event_id": "evt_002",
        "event_type": "payment.failed",
        "payment_id": payment.id,
        "status": "FAILED",
    }, headers=_webhook_headers())
    assert resp.status_code == 200

    db.refresh(payment)
    db.refresh(booking)
    assert payment.status == PaymentStatus.FAILED
    assert booking.status == BookingStatus.FAILED


def test_webhook_duplicate_event(client, db):
    """Same event_id sent twice — second should be safely ignored."""
    payment, booking = _create_pending_payment(db)
    payload = {
        "event_id": "evt_dup",
        "event_type": "payment.success",
        "payment_id": payment.id,
        "status": "SUCCESS",
    }
    resp1 = client.post("/api/v1/payments/webhook", json=payload, headers=_webhook_headers())
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "processed"

    resp2 = client.post("/api/v1/payments/webhook", json=payload, headers=_webhook_headers())
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "already_processed"

    # Payment and booking should still be in correct state
    db.refresh(payment)
    db.refresh(booking)
    assert payment.status == PaymentStatus.SUCCESS
    assert booking.status == BookingStatus.CONFIRMED


def test_webhook_contradictory_after_terminal(client, db):
    """After SUCCESS, a FAILED webhook should not corrupt the state."""
    payment, booking = _create_pending_payment(db)
    # First: SUCCESS
    client.post("/api/v1/payments/webhook", json={
        "event_id": "evt_first",
        "event_type": "payment.success",
        "payment_id": payment.id,
        "status": "SUCCESS",
    }, headers=_webhook_headers())

    # Second: contradictory FAILED with different event_id
    resp = client.post("/api/v1/payments/webhook", json={
        "event_id": "evt_second",
        "event_type": "payment.failed",
        "payment_id": payment.id,
        "status": "FAILED",
    }, headers=_webhook_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "already_processed"

    db.refresh(payment)
    db.refresh(booking)
    assert payment.status == PaymentStatus.SUCCESS
    assert booking.status == BookingStatus.CONFIRMED


def test_webhook_bad_secret(client):
    resp = client.post("/api/v1/payments/webhook", json={
        "event_id": "evt_bad",
        "event_type": "payment.success",
        "payment_id": 1,
        "status": "SUCCESS",
    }, headers={"X-Webhook-Secret": "wrong-secret"})
    assert resp.status_code == 401


def test_webhook_missing_secret(client):
    resp = client.post("/api/v1/payments/webhook", json={
        "event_id": "evt_nosec",
        "event_type": "payment.success",
        "payment_id": 1,
        "status": "SUCCESS",
    })
    assert resp.status_code == 401


def test_webhook_unknown_payment(client, db):
    resp = client.post("/api/v1/payments/webhook", json={
        "event_id": "evt_unknown",
        "event_type": "payment.success",
        "payment_id": 9999,
        "status": "SUCCESS",
    }, headers=_webhook_headers())
    assert resp.status_code == 404


def test_webhook_malformed_payload(client):
    resp = client.post("/api/v1/payments/webhook", json={
        "bad_field": "data",
    }, headers=_webhook_headers())
    assert resp.status_code == 422


def test_webhook_invalid_event_type(client):
    resp = client.post("/api/v1/payments/webhook", json={
        "event_id": "evt_bad_type",
        "event_type": "payment.refunded",
        "payment_id": 1,
        "status": "SUCCESS",
    }, headers=_webhook_headers())
    assert resp.status_code == 422
