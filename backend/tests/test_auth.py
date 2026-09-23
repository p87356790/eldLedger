from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.init_db import seed_standard_data
from app.models.enums import UserRole


def test_setup_status_when_empty(anon_client: TestClient, db_session: Session) -> None:
    seed_standard_data(db_session)
    db_session.flush()
    response = anon_client.get("/api/v1/setup")
    assert response.status_code == 200
    assert response.json()["needs_setup"] is True


def test_first_run_setup_and_login(anon_client: TestClient, db_session: Session) -> None:
    created = anon_client.post(
        "/api/v1/setup",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "display_name": "관리자",
            "password": "secret-pass-1",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["user"]["role"] == UserRole.ADMIN.value
    assert body["user"]["username"] == "admin"
    assert body["access_token"]
    assert body["refresh_token"]

    second = anon_client.post(
        "/api/v1/setup",
        json={
            "username": "other",
            "email": "other@example.com",
            "display_name": "다른사람",
            "password": "secret-pass-1",
        },
    )
    assert second.status_code == 400

    me = anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.com"

    login = anon_client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret-pass-1"})
    assert login.status_code == 200
    refreshed = anon_client.post("/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]

    headers = {"Authorization": f"Bearer {body['access_token']}"}
    org_id = body["user"]["organization_id"]
    accounts = anon_client.get(f"/api/accounts?organization_id={org_id}", headers=headers)
    categories = anon_client.get(f"/api/v1/categories?organization_id={org_id}", headers=headers)
    assert accounts.status_code == 200, accounts.text
    assert categories.status_code == 200, categories.text
    assert any(item["code"] == "5100" for item in accounts.json())
    assert any(item["name"] == "식비" for item in categories.json())


def test_login_rejects_bad_password(anon_client: TestClient, db_session: Session) -> None:
    seed_standard_data(db_session)
    db_session.flush()
    anon_client.post(
        "/api/v1/setup",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "display_name": "관리자",
            "password": "secret-pass-1",
        },
    )
    failed = anon_client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong-pass"})
    assert failed.status_code == 401


def test_protected_api_requires_login(anon_client: TestClient, db_session: Session) -> None:
    seed_standard_data(db_session)
    db_session.flush()
    response = anon_client.get("/api/v1/accounts?organization_id=1")
    assert response.status_code == 401


def test_admin_user_crud_and_password_change(anon_client: TestClient, db_session: Session) -> None:
    setup = anon_client.post(
        "/api/v1/setup",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "display_name": "관리자",
            "password": "secret-pass-1",
        },
    )
    token = setup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = anon_client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "keeper",
            "email": "keeper@example.com",
            "display_name": "기록원",
            "password": "user-pass-1",
            "role": "USER",
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    listed = anon_client.get("/api/v1/users", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    login_user = anon_client.post("/api/v1/auth/login", json={"username": "keeper", "password": "user-pass-1"})
    user_headers = {"Authorization": f"Bearer {login_user.json()['access_token']}"}
    forbidden = anon_client.get("/api/v1/users", headers=user_headers)
    assert forbidden.status_code == 403

    changed = anon_client.post(
        "/api/v1/users/me/password",
        headers=user_headers,
        json={"current_password": "user-pass-1", "new_password": "user-pass-2"},
    )
    assert changed.status_code == 204
    old = anon_client.post("/api/v1/auth/login", json={"username": "keeper", "password": "user-pass-1"})
    assert old.status_code == 401
    new = anon_client.post("/api/v1/auth/login", json={"username": "keeper", "password": "user-pass-2"})
    assert new.status_code == 200

    hidden = anon_client.post(f"/api/v1/users/{user_id}/deactivate", headers=headers)
    assert hidden.status_code == 200
    assert hidden.json()["is_active"] is False
    blocked = anon_client.post("/api/v1/auth/login", json={"username": "keeper", "password": "user-pass-2"})
    assert blocked.status_code == 401

    history = anon_client.get("/api/v1/users/me/login-history", headers=headers)
    assert history.status_code == 200
    assert any(item["action"] == "LOGIN" for item in history.json())


def test_admin_can_set_other_user_password(anon_client: TestClient, db_session: Session) -> None:
    setup = anon_client.post(
        "/api/v1/setup",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "display_name": "관리자",
            "password": "secret-pass-1",
        },
    )
    token = setup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = anon_client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "keeper",
            "email": "keeper@example.com",
            "display_name": "기록원",
            "password": "user-pass-1",
            "role": "USER",
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]

    login_user = anon_client.post("/api/v1/auth/login", json={"username": "keeper", "password": "user-pass-1"})
    assert login_user.status_code == 200
    user_headers = {"Authorization": f"Bearer {login_user.json()['access_token']}"}
    forbidden = anon_client.post(
        f"/api/v1/users/{user_id}/password",
        headers=user_headers,
        json={"admin_password": "user-pass-1", "new_password": "user-pass-9"},
    )
    assert forbidden.status_code == 403

    wrong_admin = anon_client.post(
        f"/api/v1/users/{user_id}/password",
        headers=headers,
        json={"admin_password": "wrong-pass-1", "new_password": "user-pass-9"},
    )
    assert wrong_admin.status_code == 400

    changed = anon_client.post(
        f"/api/v1/users/{user_id}/password",
        headers=headers,
        json={"admin_password": "secret-pass-1", "new_password": "user-pass-9"},
    )
    assert changed.status_code == 204, changed.text
    old = anon_client.post("/api/v1/auth/login", json={"username": "keeper", "password": "user-pass-1"})
    assert old.status_code == 401
    new = anon_client.post("/api/v1/auth/login", json={"username": "keeper", "password": "user-pass-9"})
    assert new.status_code == 200

    missing = anon_client.post(
        "/api/v1/users/9999/password",
        headers=headers,
        json={"admin_password": "secret-pass-1", "new_password": "user-pass-8"},
    )
    assert missing.status_code == 404


def test_factory_reset_requires_admin_and_wipes_users(anon_client: TestClient, db_session: Session) -> None:
    setup = anon_client.post(
        "/api/v1/setup",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "display_name": "관리자",
            "password": "secret-pass-1",
        },
    )
    token = setup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    anon_client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "keeper",
            "email": "keeper@example.com",
            "display_name": "기록원",
            "password": "user-pass-1",
            "role": "USER",
        },
    )
    user_login = anon_client.post("/api/v1/auth/login", json={"username": "keeper", "password": "user-pass-1"})
    user_headers = {"Authorization": f"Bearer {user_login.json()['access_token']}"}
    forbidden = anon_client.post(
        "/api/v1/setup/reset",
        headers=user_headers,
        json={"password": "user-pass-1", "confirm": "초기화"},
    )
    assert forbidden.status_code == 403

    bad_confirm = anon_client.post(
        "/api/v1/setup/reset",
        headers=headers,
        json={"password": "secret-pass-1", "confirm": "지워"},
    )
    assert bad_confirm.status_code == 400

    bad_password = anon_client.post(
        "/api/v1/setup/reset",
        headers=headers,
        json={"password": "wrong-pass-1", "confirm": "초기화"},
    )
    assert bad_password.status_code == 400

    wiped = anon_client.post(
        "/api/v1/setup/reset",
        headers=headers,
        json={"password": "secret-pass-1", "confirm": "초기화"},
    )
    assert wiped.status_code == 200, wiped.text
    assert wiped.json()["needs_setup"] is True

    status = anon_client.get("/api/v1/setup")
    assert status.json()["needs_setup"] is True
    blocked = anon_client.get("/api/v1/auth/me", headers=headers)
    assert blocked.status_code == 401
    accounts = anon_client.get("/api/v1/accounts?organization_id=1")
    assert accounts.status_code == 401


def test_ledger_reset_clears_one_user_and_keeps_the_other(anon_client: TestClient, db_session: Session) -> None:
    setup = anon_client.post(
        "/api/v1/setup",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "display_name": "관리자",
            "password": "secret-pass-1",
        },
    )
    admin = setup.json()["user"]
    admin_headers = {"Authorization": f"Bearer {setup.json()['access_token']}"}
    created = anon_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "username": "keeper",
            "email": "keeper@example.com",
            "display_name": "기록원",
            "password": "user-pass-1",
            "role": "USER",
        },
    )
    assert created.status_code == 201, created.text

    wallets = anon_client.get(f"/api/v1/accounts?organization_id={admin['organization_id']}", headers=admin_headers).json()
    categories = anon_client.get(
        f"/api/v1/categories?organization_id={admin['organization_id']}",
        headers=admin_headers,
    ).json()
    cash = next(row for row in wallets if row["instrument_kind"] == "CASH")
    food = next(row for row in categories if row["name"] == "식비")
    posted = anon_client.post(
        "/api/transactions",
        headers=admin_headers,
        json={
            "organization_id": admin["organization_id"],
            "occurred_on": "2026-09-01",
            "transaction_type": "EXPENSE",
            "scope": "PERSONAL",
            "amount": 9_000,
            "payment_account_id": cash["id"],
            "items": [{"category_id": food["id"], "amount": 9_000, "scope": "PERSONAL", "line_no": 1}],
        },
    )
    assert posted.status_code == 201, posted.text

    keeper_login = anon_client.post("/api/v1/auth/login", json={"username": "keeper", "password": "user-pass-1"})
    keeper_headers = {"Authorization": f"Bearer {keeper_login.json()['access_token']}"}
    keeper_cats_before = anon_client.get(
        f"/api/v1/categories?organization_id={admin['organization_id']}",
        headers=keeper_headers,
    ).json()
    assert any(row["name"] == "식비" for row in keeper_cats_before)

    reset = anon_client.post(
        "/api/v1/setup/reset-ledger",
        headers=admin_headers,
        json={"password": "secret-pass-1", "confirm": "초기화"},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["transactions_deleted"] == 1
    assert reset.json()["user_id"] == admin["id"]

    listed = anon_client.get(
        f"/api/transactions?organization_id={admin['organization_id']}",
        headers=admin_headers,
    ).json()
    assert listed["total"] == 0
    admin_cats = anon_client.get(
        f"/api/v1/categories?organization_id={admin['organization_id']}",
        headers=admin_headers,
    ).json()
    assert any(row["name"] == "식비" for row in admin_cats)

    still_in = anon_client.get("/api/v1/users/me", headers=admin_headers)
    assert still_in.status_code == 200
    keeper_me = anon_client.get("/api/v1/users/me", headers=keeper_headers)
    assert keeper_me.status_code == 200
    keeper_cats = anon_client.get(
        f"/api/v1/categories?organization_id={admin['organization_id']}",
        headers=keeper_headers,
    ).json()
    assert any(row["name"] == "식비" for row in keeper_cats)

    other = anon_client.post(
        f"/api/v1/users/{keeper_login.json()['user']['id']}/reset-ledger",
        headers=admin_headers,
        json={"password": "secret-pass-1", "confirm": "초기화"},
    )
    assert other.status_code == 200, other.text
    assert other.json()["user_id"] == keeper_login.json()["user"]["id"]
