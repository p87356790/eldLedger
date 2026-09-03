from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.init_db import seed_standard_data
from app.models import Account, Category, Organization, Tag, TransactionTag
from app.models.enums import CategoryDefaultScope, TransactionType
from app.schemas.categories import CategoryCreate
from app.services.accounting_service import AccountingError
from app.services.category_service import CategoryService

def _seed(db_session: Session) -> Organization:
    organization = seed_standard_data(db_session)
    db_session.flush()
    return organization


def test_seeded_tree_and_scopes(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    response = client.get(f"/api/v1/categories?organization_id={organization.id}")
    assert response.status_code == 200
    by_name = {item["name"]: item for item in response.json()}
    assert by_name["식비"]["parent_id"] == by_name["생활비"]["id"]
    assert by_name["식비"]["default_scope"] == "PERSONAL"
    assert by_name["사무용품"]["default_scope"] == "BUSINESS"
    assert by_name["사업매출"]["transaction_type"] == "INCOME"
    assert by_name["사무용품"]["chart_name"] == "사무용품비"


def test_create_child_category(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    supplies = db_session.scalar(select(Account).where(Account.code == "5100"))
    living = db_session.scalar(select(Category).where(Category.name == "생활비"))
    assert supplies is not None
    assert living is not None
    response = client.post(
        "/api/v1/categories",
        json={
            "organization_id": organization.id,
            "parent_id": living.id,
            "account_id": supplies.id,
            "name": "커피",
            "transaction_type": "EXPENSE",
            "default_scope": "PERSONAL",
            "icon": "local_cafe",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["parent_id"] == living.id
    assert body["default_scope"] == "PERSONAL"
    assert body["is_system"] is False


def test_rejects_grandchild_category(db_session: Session) -> None:
    organization = _seed(db_session)
    food = db_session.scalar(select(Category).where(Category.name == "식비"))
    supplies = db_session.scalar(select(Account).where(Account.code == "5100"))
    assert food is not None
    assert supplies is not None
    service = CategoryService(db_session)
    with pytest.raises(AccountingError, match="두 단계"):
        service.create_category(
            CategoryCreate(
                organization_id=organization.id,
                parent_id=food.id,
                account_id=supplies.id,
                name="분식",
                transaction_type=TransactionType.EXPENSE,
                default_scope=CategoryDefaultScope.PERSONAL,
            )
        )


def test_tag_crud_and_transaction_mapping(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    listed = client.get(f"/api/v1/tags?organization_id={organization.id}")
    assert listed.status_code == 200
    names = {item["name"] for item in listed.json()}
    assert "출장" in names

    created = client.post(
        "/api/v1/tags",
        json={"organization_id": organization.id, "name": "#신규거래처"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "신규거래처"

    accounts = {account.code: account for account in db_session.scalars(select(Account))}
    categories = {category.name: category for category in db_session.scalars(select(Category))}
    tags = {tag.name: tag for tag in db_session.scalars(select(Tag))}
    txn = client.post(
        "/api/transactions",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-01",
            "transaction_type": "EXPENSE",
            "scope": "BUSINESS",
            "amount": 12_000,
            "memo": "태그 연결",
            "payment_account_id": accounts["2100"].id,
            "tag_ids": [tags["사무실"].id],
            "items": [
                {
                    "category_id": categories["사무용품"].id,
                    "amount": 12_000,
                    "scope": "BUSINESS",
                    "line_no": 1,
                }
            ],
        },
    )
    assert txn.status_code == 201, txn.text
    mapped = client.put(
        f"/api/v1/transactions/{txn.json()['id']}/tags",
        json={"tag_ids": [tags["출장"].id, tags["거래처"].id]},
    )
    assert mapped.status_code == 200, mapped.text
    mapped_names = {item["name"] for item in mapped.json()["tags"]}
    assert mapped_names == {"출장", "거래처"}
    links = list(db_session.scalars(select(TransactionTag).where(TransactionTag.transaction_id == txn.json()["id"])))
    assert len(links) == 2


def test_hide_system_category(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    listed = client.get(f"/api/v1/categories?organization_id={organization.id}")
    supplies = next(item for item in listed.json() if item["name"] == "사무용품")
    hidden = client.post(f"/api/v1/categories/{supplies['id']}/deactivate")
    assert hidden.status_code == 200
    visible = client.get(f"/api/v1/categories?organization_id={organization.id}")
    assert all(item["name"] != "사무용품" for item in visible.json())
    including = client.get(f"/api/v1/categories?organization_id={organization.id}&include_hidden=true")
    assert any(item["id"] == supplies["id"] and item["is_active"] is False for item in including.json())
    deleted = client.delete(f"/api/v1/categories/{supplies['id']}")
    assert deleted.status_code == 400
