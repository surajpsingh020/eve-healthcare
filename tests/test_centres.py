from decimal import Decimal

from tests.conftest import auth_header
from app.models.centre import DiagnosticCentre
from app.models.test import DiagnosticTest
from app.models.centre_test import CentreTest


def _create_centre(db):
    centre = DiagnosticCentre(name="Test Centre", location="Test City")
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre


def _create_test(db):
    test = DiagnosticTest(name="CBC", description="Blood test")
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


def test_list_centres(client, db):
    _create_centre(db)
    resp = client.get("/api/v1/centres")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


def test_get_centre(client, db):
    centre = _create_centre(db)
    resp = client.get(f"/api/v1/centres/{centre.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Centre"


def test_get_centre_not_found(client):
    resp = client.get("/api/v1/centres/999")
    assert resp.status_code == 404


def test_create_centre_admin(client, admin_token):
    resp = client.post("/api/v1/centres", json={
        "name": "New Centre",
        "location": "New City",
    }, headers=auth_header(admin_token))
    assert resp.status_code == 201
    assert resp.json()["name"] == "New Centre"


def test_create_centre_non_admin(client, user_token):
    resp = client.post("/api/v1/centres", json={
        "name": "New Centre",
        "location": "New City",
    }, headers=auth_header(user_token))
    assert resp.status_code == 403


def test_create_centre_unauthenticated(client):
    resp = client.post("/api/v1/centres", json={
        "name": "New Centre",
        "location": "New City",
    })
    assert resp.status_code == 401


def test_update_centre_admin(client, db, admin_token):
    centre = _create_centre(db)
    resp = client.patch(f"/api/v1/centres/{centre.id}", json={
        "name": "Updated Centre",
    }, headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Centre"


def test_delete_centre_admin(client, db, admin_token):
    centre = _create_centre(db)
    resp = client.delete(f"/api/v1/centres/{centre.id}", headers=auth_header(admin_token))
    assert resp.status_code == 204


def test_add_centre_test(client, db, admin_token):
    centre = _create_centre(db)
    test = _create_test(db)
    resp = client.post(f"/api/v1/centres/{centre.id}/tests", json={
        "test_id": test.id,
        "price": "500.00",
    }, headers=auth_header(admin_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["test_id"] == test.id
    assert Decimal(str(data["price"])) == Decimal("500.00")


def test_add_duplicate_centre_test(client, db, admin_token):
    centre = _create_centre(db)
    test = _create_test(db)
    ct = CentreTest(centre_id=centre.id, test_id=test.id, price=Decimal("500.00"))
    db.add(ct)
    db.commit()
    resp = client.post(f"/api/v1/centres/{centre.id}/tests", json={
        "test_id": test.id,
        "price": "600.00",
    }, headers=auth_header(admin_token))
    assert resp.status_code == 409


def test_update_centre_test_price(client, db, admin_token):
    centre = _create_centre(db)
    test = _create_test(db)
    ct = CentreTest(centre_id=centre.id, test_id=test.id, price=Decimal("500.00"))
    db.add(ct)
    db.commit()
    resp = client.patch(f"/api/v1/centres/{centre.id}/tests/{test.id}", json={
        "price": "750.00",
    }, headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert Decimal(str(resp.json()["price"])) == Decimal("750.00")


def test_delete_centre_test(client, db, admin_token):
    centre = _create_centre(db)
    test = _create_test(db)
    ct = CentreTest(centre_id=centre.id, test_id=test.id, price=Decimal("500.00"))
    db.add(ct)
    db.commit()
    resp = client.delete(f"/api/v1/centres/{centre.id}/tests/{test.id}", headers=auth_header(admin_token))
    assert resp.status_code == 204


def test_centre_detail_shows_tests(client, db):
    centre = _create_centre(db)
    test = _create_test(db)
    ct = CentreTest(centre_id=centre.id, test_id=test.id, price=Decimal("500.00"))
    db.add(ct)
    db.commit()
    db.expire_all()
    resp = client.get(f"/api/v1/centres/{centre.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tests"]) == 1
    assert data["tests"][0]["test_name"] == "CBC"
