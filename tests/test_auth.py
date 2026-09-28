from tests.conftest import auth_header


def test_signup(client):
    resp = client.post("/api/v1/auth/signup", json={
        "email": "new@test.com",
        "password": "secret123",
        "full_name": "New User",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new@test.com"
    assert data["full_name"] == "New User"
    assert data["is_admin"] is False
    assert "password" not in data
    assert "password_hash" not in data


def test_signup_duplicate_email(client, regular_user):
    resp = client.post("/api/v1/auth/signup", json={
        "email": "user@test.com",
        "password": "secret123",
        "full_name": "Duplicate",
    })
    assert resp.status_code == 409


def test_signup_invalid_email(client):
    resp = client.post("/api/v1/auth/signup", json={
        "email": "not-an-email",
        "password": "secret123",
        "full_name": "Bad Email",
    })
    assert resp.status_code == 422


def test_signup_short_password(client):
    resp = client.post("/api/v1/auth/signup", json={
        "email": "new@test.com",
        "password": "123",
        "full_name": "Short",
    })
    assert resp.status_code == 422


def test_login(client, regular_user):
    resp = client.post("/api/v1/auth/login", json={
        "email": "user@test.com",
        "password": "user123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, regular_user):
    resp = client.post("/api/v1/auth/login", json={
        "email": "user@test.com",
        "password": "wrong",
    })
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post("/api/v1/auth/login", json={
        "email": "ghost@test.com",
        "password": "whatever",
    })
    assert resp.status_code == 401


def test_me(client, regular_user, user_token):
    resp = client.get("/api/v1/auth/me", headers=auth_header(user_token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@test.com"


def test_me_no_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_bad_token(client):
    resp = client.get("/api/v1/auth/me", headers=auth_header("invalid.token.here"))
    assert resp.status_code == 401
