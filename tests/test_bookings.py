from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.conftest import auth_header
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest


def _seed_catalogue(db):
    """Create a centre, test, and offering for booking tests."""
    centre = DiagnosticCentre(name="Lab A", location="City X")
    test = DiagnosticTest(name="CBC", description="Blood count")
    db.add_all([centre, test])
    db.flush()
    ct = CentreTest(centre_id=centre.id, test_id=test.id, price=Decimal("500.00"))
    db.add(ct)
    db.commit()
    db.refresh(centre)
    db.refresh(test)
    return centre, test


def _future_time():
    return (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()


def test_create_booking(client, db, user_token, regular_user):
    centre, test = _seed_catalogue(db)
    resp = client.post("/api/v1/bookings", json={
        "centre_id": centre.id,
        "test_id": test.id,
        "appointment_at": _future_time(),
    }, headers=auth_header(user_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "PENDING"
    assert Decimal(str(data["amount"])) == Decimal("500.00")
    assert data["centre_id"] == centre.id
    assert data["test_id"] == test.id


def test_booking_captures_price_snapshot(client, db, user_token, regular_user):
    """If price changes after booking, the booking amount stays the same."""
    centre, test = _seed_catalogue(db)
    resp = client.post("/api/v1/bookings", json={
        "centre_id": centre.id,
        "test_id": test.id,
        "appointment_at": _future_time(),
    }, headers=auth_header(user_token))
    assert resp.status_code == 201
    booking_amount = Decimal(str(resp.json()["amount"]))
    assert booking_amount == Decimal("500.00")

    # Now change the price
    ct = db.query(CentreTest).filter(
        CentreTest.centre_id == centre.id,
        CentreTest.test_id == test.id,
    ).first()
    ct.price = Decimal("700.00")
    db.commit()

    # Original booking still shows ₹500
    booking_id = resp.json()["id"]
    resp2 = client.get(f"/api/v1/bookings/{booking_id}", headers=auth_header(user_token))
    assert Decimal(str(resp2.json()["amount"])) == Decimal("500.00")


def test_booking_invalid_centre(client, db, user_token, regular_user):
    centre, test = _seed_catalogue(db)
    resp = client.post("/api/v1/bookings", json={
        "centre_id": 999,
        "test_id": test.id,
        "appointment_at": _future_time(),
    }, headers=auth_header(user_token))
    assert resp.status_code == 404


def test_booking_invalid_test(client, db, user_token, regular_user):
    centre, test = _seed_catalogue(db)
    resp = client.post("/api/v1/bookings", json={
        "centre_id": centre.id,
        "test_id": 999,
        "appointment_at": _future_time(),
    }, headers=auth_header(user_token))
    assert resp.status_code == 404


def test_booking_test_not_offered(client, db, user_token, regular_user):
    centre, _test = _seed_catalogue(db)
    other_test = DiagnosticTest(name="MRI", description="Imaging")
    db.add(other_test)
    db.commit()
    db.refresh(other_test)
    resp = client.post("/api/v1/bookings", json={
        "centre_id": centre.id,
        "test_id": other_test.id,
        "appointment_at": _future_time(),
    }, headers=auth_header(user_token))
    assert resp.status_code == 400


def test_booking_past_appointment(client, db, user_token, regular_user):
    centre, test = _seed_catalogue(db)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = client.post("/api/v1/bookings", json={
        "centre_id": centre.id,
        "test_id": test.id,
        "appointment_at": past,
    }, headers=auth_header(user_token))
    assert resp.status_code == 400


def test_booking_naive_datetime_future(client, db, user_token, regular_user):
    centre, test = _seed_catalogue(db)
    # Naive future datetime (without +00:00)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None).isoformat()
    resp = client.post("/api/v1/bookings", json={
        "centre_id": centre.id,
        "test_id": test.id,
        "appointment_at": future,
    }, headers=auth_header(user_token))
    assert resp.status_code == 201


def test_booking_naive_datetime_past(client, db, user_token, regular_user):
    centre, test = _seed_catalogue(db)
    # Naive past datetime
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None).isoformat()
    resp = client.post("/api/v1/bookings", json={
        "centre_id": centre.id,
        "test_id": test.id,
        "appointment_at": past,
    }, headers=auth_header(user_token))
    assert resp.status_code == 400


def test_list_own_bookings(client, db, user_token, regular_user):
    centre, test = _seed_catalogue(db)
    client.post("/api/v1/bookings", json={
        "centre_id": centre.id,
        "test_id": test.id,
        "appointment_at": _future_time(),
    }, headers=auth_header(user_token))
    resp = client.get("/api/v1/bookings", headers=auth_header(user_token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_cannot_see_other_users_booking(client, db, user_token, admin_token, regular_user, admin_user):
    centre, test = _seed_catalogue(db)
    # Create booking as regular user
    resp = client.post("/api/v1/bookings", json={
        "centre_id": centre.id,
        "test_id": test.id,
        "appointment_at": _future_time(),
    }, headers=auth_header(user_token))
    booking_id = resp.json()["id"]
    # Admin tries to access it
    resp2 = client.get(f"/api/v1/bookings/{booking_id}", headers=auth_header(admin_token))
    assert resp2.status_code == 403


def test_cancel_booking(client, db, user_token, regular_user):
    centre, test = _seed_catalogue(db)
    resp = client.post("/api/v1/bookings", json={
        "centre_id": centre.id,
        "test_id": test.id,
        "appointment_at": _future_time(),
    }, headers=auth_header(user_token))
    booking_id = resp.json()["id"]
    resp2 = client.post(f"/api/v1/bookings/{booking_id}/cancel", headers=auth_header(user_token))
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "CANCELLED"


def test_cancel_already_cancelled(client, db, user_token, regular_user):
    centre, test = _seed_catalogue(db)
    resp = client.post("/api/v1/bookings", json={
        "centre_id": centre.id,
        "test_id": test.id,
        "appointment_at": _future_time(),
    }, headers=auth_header(user_token))
    booking_id = resp.json()["id"]
    client.post(f"/api/v1/bookings/{booking_id}/cancel", headers=auth_header(user_token))
    resp2 = client.post(f"/api/v1/bookings/{booking_id}/cancel", headers=auth_header(user_token))
    assert resp2.status_code == 409


def test_booking_unauthenticated(client):
    resp = client.post("/api/v1/bookings", json={
        "centre_id": 1,
        "test_id": 1,
        "appointment_at": _future_time(),
    })
    assert resp.status_code == 401
