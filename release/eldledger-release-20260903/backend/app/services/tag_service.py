from sqlalchemy.orm import Session

from app.models import Organization, Tag
from app.repositories.tag_repository import TagRepository
from app.schemas.accounting import TransactionRead
from app.schemas.categories import TagCreate, TagRead, TagUpdate
from app.services.accounting_service import AccountingError
from app.services.transaction_service import TransactionService


def normalize_tag_name(name: str) -> str:
    stripped = name.strip()
    if stripped.startswith("#"):
        stripped = stripped[1:].strip()
    if stripped == "":
        raise AccountingError("태그 이름을 입력해 주세요.")
    return stripped[:50]


class TagService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = TagRepository(session)
        self._transactions = TransactionService(session)

    def list_tags(self, organization_id: int, *, owner_user_id: int | None = None) -> list[TagRead]:
        self._require_organization(organization_id)
        return [TagRead.model_validate(tag) for tag in self._repo.list_tags(organization_id, owner_user_id=owner_user_id)]

    def create_tag(self, payload: TagCreate, *, owner_user_id: int | None = None) -> TagRead:
        self._require_organization(payload.organization_id)
        name = normalize_tag_name(payload.name)
        if self._repo.get_by_name(payload.organization_id, name, owner_user_id=owner_user_id) is not None:
            raise AccountingError("같은 이름의 태그가 이미 있어요.")
        tag = Tag(organization_id=payload.organization_id, owner_user_id=owner_user_id, name=name)
        self._session.add(tag)
        self._session.flush()
        return TagRead.model_validate(tag)

    def update_tag(self, tag_id: int, payload: TagUpdate, *, owner_user_id: int | None = None) -> TagRead:
        tag = self._require_tag(tag_id, owner_user_id=owner_user_id)
        name = normalize_tag_name(payload.name)
        existing = self._repo.get_by_name(tag.organization_id, name, owner_user_id=owner_user_id)
        if existing is not None and existing.id != tag.id:
            raise AccountingError("같은 이름의 태그가 이미 있어요.")
        tag.name = name
        self._session.flush()
        return TagRead.model_validate(tag)

    def delete_tag(self, tag_id: int, *, owner_user_id: int | None = None) -> None:
        tag = self._require_tag(tag_id, owner_user_id=owner_user_id)
        self._session.delete(tag)
        self._session.flush()

    def set_transaction_tags(
        self,
        transaction_id: int,
        tag_ids: list[int],
        *,
        owner_user_id: int | None = None,
    ) -> TransactionRead:
        transaction = self._transactions.get(transaction_id)
        unique_ids = list(dict.fromkeys(tag_ids))
        for tag_id in unique_ids:
            tag = self._require_tag(tag_id, owner_user_id=owner_user_id)
            if tag.organization_id != transaction.organization_id:
                raise LookupError("태그를 찾을 수 없습니다.")
        self._transactions.replace_tags(transaction, unique_ids)
        self._session.flush()
        loaded = self._transactions.get(transaction_id)
        return TransactionRead.model_validate(loaded)

    def _require_tag(self, tag_id: int, *, owner_user_id: int | None = None) -> Tag:
        tag = self._repo.get(tag_id)
        if tag is None:
            raise LookupError("태그를 찾을 수 없습니다.")
        if owner_user_id is not None and tag.owner_user_id != owner_user_id:
            raise LookupError("태그를 찾을 수 없습니다.")
        return tag

    def _require_organization(self, organization_id: int) -> None:
        organization = self._session.get(Organization, organization_id)
        if organization is None:
            raise LookupError("조직을 찾을 수 없습니다.")
