from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.conftest import auth_header
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest


def _setup_and_book(client, db, user_token):
    """Create catalogue + booking, return booking_id."""
    centre = DiagnosticCentre(name="Lab A", location="City X")
    test = DiagnosticTest(name="CBC", description="Blood")
    db.add_all([centre, test])
    db.flush()
    db.add(CentreTest(centre_id=centre.id, test_id=test.id, price=Decimal("500.00")))
    db.commit()
    db.refresh(centre)
    db.refresh(test)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    resp = client.post("/api/v1/bookings", json={
        "centre_id": centre.id,
        "test_id": test.id,
        "appointment_at": future,
    }, headers=auth_header(user_token))
    return resp.json()["id"]


def test_successful_payment(client, db, user_token, regular_user):
    booking_id = _setup_and_book(client, db, user_token)
    resp = client.post("/api/v1/payments", json={
        "booking_id": booking_id,
        "simulate_result": "SUCCESS",
    }, headers=auth_header(user_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert Decimal(str(data["amount"])) == Decimal("500.00")

    # Booking should be CONFIRMED
    booking = client.get(f"/api/v1/bookings/{booking_id}", headers=auth_header(user_token))
    assert booking.json()["status"] == "CONFIRMED"


def test_failed_payment(client, db, user_token, regular_user):
    booking_id = _setup_and_book(client, db, user_token)
    resp = client.post("/api/v1/payments", json={
        "booking_id": booking_id,
        "simulate_result": "FAILED",
    }, headers=auth_header(user_token))
    assert resp.status_code == 201
    assert resp.json()["status"] == "FAILED"

    booking = client.get(f"/api/v1/bookings/{booking_id}", headers=auth_header(user_token))
    assert booking.json()["status"] == "FAILED"


def test_duplicate_payment_returns_existing(client, db, user_token, regular_user):
    """Repeated payment requests for the same booking are safe and deterministic."""
    booking_id = _setup_and_book(client, db, user_token)
    resp1 = client.post("/api/v1/payments", json={
        "booking_id": booking_id,
        "simulate_result": "SUCCESS",
    }, headers=auth_header(user_token))
    resp2 = client.post("/api/v1/payments", json={
        "booking_id": booking_id,
        "simulate_result": "SUCCESS",
    }, headers=auth_header(user_token))
    assert resp1.json()["id"] == resp2.json()["id"]
    assert resp2.json()["status"] == "SUCCESS"


def test_payment_invalid_booking(client, user_token, regular_user):
    resp = client.post("/api/v1/payments", json={
        "booking_id": 999,
        "simulate_result": "SUCCESS",
    }, headers=auth_header(user_token))
    assert resp.status_code == 404


def test_payment_cancelled_booking(client, db, user_token, regular_user):
    booking_id = _setup_and_book(client, db, user_token)
    client.post(f"/api/v1/bookings/{booking_id}/cancel", headers=auth_header(user_token))
    resp = client.post("/api/v1/payments", json={
        "booking_id": booking_id,
        "simulate_result": "SUCCESS",
    }, headers=auth_header(user_token))
    assert resp.status_code == 409


def test_payment_other_users_booking(client, db, user_token, admin_token, regular_user, admin_user):
    booking_id = _setup_and_book(client, db, user_token)
    resp = client.post("/api/v1/payments", json={
        "booking_id": booking_id,
        "simulate_result": "SUCCESS",
    }, headers=auth_header(admin_token))
    assert resp.status_code == 403


def test_payment_unauthenticated(client):
    resp = client.post("/api/v1/payments", json={
        "booking_id": 1,
        "simulate_result": "SUCCESS",
    })
    assert resp.status_code == 401


def test_invalid_simulate_result(client, db, user_token, regular_user):
    booking_id = _setup_and_book(client, db, user_token)
    resp = client.post("/api/v1/payments", json={
        "booking_id": booking_id,
        "simulate_result": "MAYBE",
    }, headers=auth_header(user_token))
    assert resp.status_code == 422
