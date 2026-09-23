from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Account, Attachment, Category, Organization, Transaction, TransactionItem, TransactionTag
from app.models.enums import RecordStatus, Scope, TransactionType
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.accounting import DuplicateCheckRequest, TransactionCreate, TransactionItemCreate, TransactionUpdate
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


def attachment_relative_path(occurred_on: date, stored_name: str) -> Path:
    return Path("uploads") / occurred_on.strftime("%Y-%m") / stored_name


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
            merchant=_clean_optional_text(payload.merchant),
            memo=_clean_optional_text(payload.memo),
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
        created_by_user_id: int | None = None,
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
            created_by_user_id=created_by_user_id,
            include_reversed=include_reversed,
            offset=offset,
            limit=limit,
        )
        return total, list(rows)

    def find_duplicates(
        self,
        payload: DuplicateCheckRequest,
        *,
        created_by_user_id: int | None = None,
    ) -> list[Transaction]:
        self._require_organization(payload.organization_id)
        candidates = self._repo.find_same_day_candidates(
            organization_id=payload.organization_id,
            occurred_on=payload.occurred_on,
            amount=payload.amount,
            transaction_type=payload.transaction_type,
            payment_account_id=payload.payment_account_id,
            created_by_user_id=created_by_user_id,
            exclude_id=payload.exclude_id,
        )
        incoming_merchant = _merchant_key(payload.merchant)
        incoming_items = _item_signature(payload.items)
        matches: list[Transaction] = []
        for row in candidates:
            if payload.transaction_type == TransactionType.TRANSFER:
                if row.transfer_account_id == payload.transfer_account_id:
                    matches.append(row)
                continue
            if incoming_merchant != "":
                if _merchant_key(row.merchant) == incoming_merchant:
                    matches.append(row)
                continue
            if _merchant_key(row.merchant) == "" and _item_signature(row.items) == incoming_items:
                matches.append(row)
        return matches

    def update(self, transaction_id: int, payload: TransactionUpdate) -> Transaction:
        transaction = self.get(transaction_id)
        if transaction.status == RecordStatus.REVERSED:
            raise AccountingError("취소된 거래는 수정할 수 없습니다.")
        transaction.occurred_on = payload.occurred_on
        transaction.transaction_type = payload.transaction_type
        transaction.scope = payload.scope
        transaction.amount = payload.amount
        transaction.merchant = _clean_optional_text(payload.merchant)
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

    def list_accounts(self, organization_id: int, *, owner_user_id: int | None = None) -> list[Account]:
        stmt = select(Account).where(Account.organization_id == organization_id, Account.is_active.is_(True))
        if owner_user_id is not None:
            stmt = stmt.where(
                or_(
                    Account.owner_user_id == owner_user_id,
                    Account.owner_user_id.is_(None) & Account.instrument_kind.is_(None),
                )
            )
        return list(self._session.scalars(stmt.order_by(Account.sort_order, Account.code)))

    def list_categories(self, organization_id: int, *, owner_user_id: int | None = None) -> list[Category]:
        from app.repositories.category_repository import CategoryRepository

        return CategoryRepository(self._session).list_categories(organization_id, owner_user_id=owner_user_id)

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
        relative_path = attachment_relative_path(transaction.occurred_on, stored_name)
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
        self._session.expire(transaction, ["attachments"])
        return attachment

    def get_attachment_file(self, transaction_id: int, attachment_id: int) -> tuple[Attachment, Path]:
        transaction = self.get(transaction_id)
        attachment = next((item for item in transaction.attachments if item.id == attachment_id), None)
        if attachment is None:
            raise LookupError("영수증을 찾을 수 없습니다.")
        return attachment, self._resolve_attachment_path(attachment)

    def _resolve_attachment_path(self, attachment: Attachment) -> Path:
        data_root = Path(settings.data_dir).resolve()
        stored = Path(attachment.stored_path)
        if stored.is_absolute() or ".." in stored.parts:
            raise LookupError("영수증을 찾을 수 없습니다.")
        path = (data_root / stored).resolve()
        if not path.is_relative_to(data_root) or not path.is_file():
            raise LookupError("영수증을 찾을 수 없습니다.")
        return path

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


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _merchant_key(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split()).casefold()


def _item_signature(items: list[TransactionItemCreate] | list[TransactionItem]) -> tuple[tuple[int | None, int, str], ...]:
    rows: list[tuple[int | None, int, str]] = []
    for item in items:
        scope = item.scope.value if isinstance(item.scope, Scope) else str(item.scope)
        rows.append((item.category_id, int(item.amount), scope))
    return tuple(sorted(rows))
