from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Account, Attachment, Category, Organization, Transaction, TransactionItem, TransactionTag
from app.models.enums import RecordStatus, Scope, TransactionType
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.accounting import TransactionCreate, TransactionItemCreate, TransactionUpdate
from app.services.accounting_service import AccountingError, AccountingService

ALLOWED_ATTACHMENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "application/pdf",
}
ALLOWED_ATTACHMENT_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".pdf"}
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


class TransactionService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = TransactionRepository(session)
        self._accounting = AccountingService(session)

    def create(self, payload: TransactionCreate, *, created_by_user_id: int | None = None) -> Transaction:
        self._require_organization(payload.organization_id)
        transaction = Transaction(
            organization_id=payload.organization_id,
            created_by_user_id=created_by_user_id,
            occurred_on=payload.occurred_on,
            transaction_type=payload.transaction_type,
            scope=payload.scope,
            amount=payload.amount,
            memo=payload.memo,
            payment_account_id=payload.payment_account_id,
            transfer_account_id=payload.transfer_account_id,
            items=[_item_from_payload(item) for item in payload.items],
        )
        self._accounting.post_transaction(transaction)
        self.replace_tags(transaction, payload.tag_ids)
        self._session.flush()
        loaded = self._repo.get(transaction.id) if transaction.id is not None else None
        if loaded is None:
            raise AccountingError("거래를 저장하지 못했습니다.")
        return loaded

    def get(self, transaction_id: int) -> Transaction:
        transaction = self._repo.get(transaction_id)
        if transaction is None:
            raise LookupError("거래를 찾을 수 없습니다.")
        return transaction

    def list_transactions(
        self,
        *,
        organization_id: int,
        transaction_type: TransactionType | None = None,
        scope: Scope | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        amount_min: int | None = None,
        amount_max: int | None = None,
        payment_account_id: int | None = None,
        category_id: int | None = None,
        tag_id: int | None = None,
        memo: str | None = None,
        include_reversed: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[int, list[Transaction]]:
        total, rows = self._repo.list(
            organization_id=organization_id,
            transaction_type=transaction_type,
            scope=scope,
            date_from=date_from,
            date_to=date_to,
            amount_min=amount_min,
            amount_max=amount_max,
            payment_account_id=payment_account_id,
            category_id=category_id,
            tag_id=tag_id,
            memo=memo,
            include_reversed=include_reversed,
            offset=offset,
            limit=limit,
        )
        return total, list(rows)

    def update(self, transaction_id: int, payload: TransactionUpdate) -> Transaction:
        transaction = self.get(transaction_id)
        if transaction.status == RecordStatus.REVERSED:
            raise AccountingError("취소된 거래는 수정할 수 없습니다.")
        transaction.occurred_on = payload.occurred_on
        transaction.transaction_type = payload.transaction_type
        transaction.scope = payload.scope
        transaction.amount = payload.amount
        transaction.memo = payload.memo
        transaction.payment_account_id = payload.payment_account_id
        transaction.transfer_account_id = payload.transfer_account_id
        transaction.items.clear()
        for item in payload.items:
            transaction.items.append(_item_from_payload(item))
        self.replace_tags(transaction, payload.tag_ids)
        self._session.flush()
        self._accounting.correct_transaction(transaction)
        loaded = self._repo.get(transaction_id)
        if loaded is None:
            raise LookupError("거래를 찾을 수 없습니다.")
        return loaded

    def cancel(self, transaction_id: int) -> Transaction:
        transaction = self.get(transaction_id)
        self._accounting.cancel_transaction(transaction)
        return transaction

    def list_accounts(self, organization_id: int) -> list[Account]:
        return list(
            self._session.scalars(
                select(Account)
                .where(Account.organization_id == organization_id, Account.is_active.is_(True))
                .order_by(Account.sort_order, Account.code)
            )
        )

    def list_categories(self, organization_id: int) -> list[Category]:
        from app.repositories.category_repository import CategoryRepository

        return CategoryRepository(self._session).list_categories(organization_id)

    def add_attachment(
        self,
        transaction_id: int,
        *,
        original_filename: str,
        content: bytes,
        content_type: str,
    ) -> Attachment:
        transaction = self.get(transaction_id)
        suffix = Path(original_filename).suffix.lower()
        if suffix not in ALLOWED_ATTACHMENT_SUFFIXES:
            raise AccountingError("영수증은 JPG, PNG, WEBP, HEIC, PDF만 올릴 수 있습니다.")
        normalized_type = content_type.split(";")[0].strip().lower() or "application/octet-stream"
        if normalized_type not in ALLOWED_ATTACHMENT_TYPES and suffix not in ALLOWED_ATTACHMENT_SUFFIXES:
            raise AccountingError("지원하지 않는 파일 형식입니다.")
        if len(content) == 0:
            raise AccountingError("빈 파일은 올릴 수 없습니다.")
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise AccountingError("파일 크기는 10MB 이하여야 합니다.")

        stored_name = f"{uuid4().hex}{suffix}"
        relative_path = Path("uploads") / str(transaction.id) / stored_name
        destination = Path(settings.data_dir) / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

        attachment = Attachment(
            transaction_id=transaction.id,
            original_filename=original_filename[:255],
            stored_path=relative_path.as_posix(),
            content_type=normalized_type,
            file_size=len(content),
        )
        self._session.add(attachment)
        self._session.flush()
        return attachment

    def replace_tags(self, transaction: Transaction, tag_ids: list[int]) -> None:
        transaction.transaction_tags.clear()
        for tag_id in tag_ids:
            transaction.transaction_tags.append(TransactionTag(tag_id=tag_id))

    def _require_organization(self, organization_id: int) -> None:
        organization = self._session.get(Organization, organization_id)
        if organization is None:
            raise LookupError("조직을 찾을 수 없습니다.")


def _item_from_payload(item: TransactionItemCreate) -> TransactionItem:
    return TransactionItem(
        category_id=item.category_id,
        account_id=item.account_id,
        amount=item.amount,
        scope=item.scope,
        memo=item.memo,
        line_no=item.line_no,
    )
