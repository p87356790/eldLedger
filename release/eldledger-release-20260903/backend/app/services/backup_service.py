from __future__ import annotations

import json
import zipfile
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import Attachment, Organization, Transaction, User
from app.models.enums import PaymentInstrumentKind, RecordStatus, TransactionType
from app.repositories.account_repository import AccountRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.import_repository import ImportRepository
from app.repositories.tag_repository import TagRepository
from app.schemas.accounting import TransactionCreate, TransactionItemCreate
from app.schemas.backup import (
    LEDGER_FORMAT,
    LEDGER_VERSION,
    LedgerAttachment,
    LedgerBundle,
    LedgerCategory,
    LedgerImportResult,
    LedgerItem,
    LedgerRule,
    LedgerTag,
    LedgerTransaction,
    LedgerWallet,
)
from app.schemas.categories import CategoryCreate, CategoryUpdate, TagCreate
from app.schemas.imports import AutoCategoryRuleCreate
from app.schemas.wallets import WalletAccountCreate, WalletAccountUpdate, WalletBalanceAdjust
from app.services.account_service import AccountService
from app.services.accounting_service import AccountingError
from app.services.audit_service import AuditService
from app.services.category_service import CategoryService
from app.services.csv_import_service import CsvImportService
from app.services.tag_service import TagService
from app.services.transaction_service import TransactionService

MAX_BACKUP_BYTES = 50 * 1024 * 1024
CARD_KIND = PaymentInstrumentKind.CREDIT_CARD


class LedgerConflictError(Exception):
    """Import refused because this user already has records."""


class BackupService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._accounts = AccountService(session)
        self._account_repo = AccountRepository(session)
        self._categories = CategoryService(session)
        self._category_repo = CategoryRepository(session)
        self._tags = TagService(session)
        self._tag_repo = TagRepository(session)
        self._imports = CsvImportService(session)
        self._import_repo = ImportRepository(session)
        self._transactions = TransactionService(session)
        self._audit = AuditService(session)

    def export_zip(self, user: User) -> bytes:
        bundle = self._build_bundle(user)
        files = self._attachment_bytes(bundle)
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "ledger.json",
                json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2),
            )
            for path, content in files.items():
                archive.writestr(path, content)
        self._audit.record(
            action="LEDGER_EXPORT",
            user_id=user.id,
            entity_type="backup",
            details=f"거래 {len(bundle.transactions)}건",
        )
        return buffer.getvalue()

    def import_zip(self, user: User, payload: bytes, *, replace: bool = False) -> LedgerImportResult:
        if len(payload) > MAX_BACKUP_BYTES:
            raise AccountingError("백업 파일은 50MB를 넘을 수 없어요.")
        bundle, files = _read_bundle(payload)
        existing = self._active_transactions(user)
        replaced = 0
        if existing:
            if not replace:
                raise LedgerConflictError("이미 거래가 있어요. 덮어쓰기를 선택한 뒤에 가져올 수 있어요.")
            for transaction in existing:
                self._transactions.cancel(transaction.id)
                replaced += 1
        result = self._restore_bundle(user, bundle, files)
        result.replaced_transactions = replaced
        self._audit.record(
            action="LEDGER_IMPORT",
            user_id=user.id,
            entity_type="backup",
            details=f"거래 {result.transactions_created}건 복원",
        )
        return result

    def _build_bundle(self, user: User) -> LedgerBundle:
        organization = self._session.get(Organization, user.organization_id)
        wallets = self._account_repo.list_wallets(user.organization_id, owner_user_id=user.id, include_hidden=True)
        categories = self._category_repo.list_categories(
            user.organization_id,
            owner_user_id=user.id,
            include_hidden=True,
        )
        tags = self._tag_repo.list_tags(user.organization_id, owner_user_id=user.id)
        rules = self._import_repo.list_rules(user.organization_id, owner_user_id=user.id)
        transactions = self._active_transactions(user)
        return LedgerBundle(
            format=LEDGER_FORMAT,
            version=LEDGER_VERSION,
            exported_at=datetime.now(timezone.utc),
            organization_name=organization.name if organization is not None else None,
            wallets=[
                LedgerWallet(
                    id=wallet.id,
                    name=wallet.name,
                    instrument_kind=wallet.instrument_kind or PaymentInstrumentKind.OTHER_ASSET,
                    currency=wallet.currency,
                    opening_balance=int(wallet.opening_balance),
                    institution=wallet.institution,
                    card_payment_day=wallet.card_payment_day,
                    settlement_account_id=wallet.settlement_account_id,
                    sort_order=wallet.sort_order,
                    is_active=wallet.is_active,
                )
                for wallet in wallets
            ],
            categories=[
                LedgerCategory(
                    id=category.id,
                    parent_id=category.parent_id,
                    name=category.name,
                    transaction_type=category.transaction_type,
                    default_scope=category.default_scope,
                    icon=category.icon,
                    chart_code=category.chart_code or "",
                    sort_order=category.sort_order,
                    is_active=category.is_active,
                )
                for category in categories
            ],
            tags=[LedgerTag(id=tag.id, name=tag.name) for tag in tags],
            rules=[
                LedgerRule(
                    name=rule.name,
                    merchant_keyword=rule.merchant_keyword,
                    payment_account_id=rule.payment_account_id,
                    category_id=rule.category_id,
                    scope=rule.scope,
                    tag_ids=[link.tag_id for link in rule.rule_tags],
                    sort_order=rule.sort_order,
                    is_active=rule.is_active,
                )
                for rule in rules
            ],
            transactions=[self._transaction_row(row) for row in transactions],
        )

    def _transaction_row(self, transaction: Transaction) -> LedgerTransaction:
        attachments: list[LedgerAttachment] = []
        for attachment in transaction.attachments:
            safe_name = Path(attachment.original_filename).name or "receipt.bin"
            attachments.append(
                LedgerAttachment(
                    original_filename=attachment.original_filename,
                    content_type=attachment.content_type,
                    file_size=int(attachment.file_size),
                    path=f"attachments/{transaction.id}/{safe_name}",
                )
            )
        return LedgerTransaction(
            id=transaction.id,
            occurred_on=transaction.occurred_on,
            transaction_type=transaction.transaction_type,
            scope=transaction.scope,
            amount=int(transaction.amount),
            memo=transaction.memo,
            payment_account_id=transaction.payment_account_id,
            transfer_account_id=transaction.transfer_account_id,
            tag_ids=[link.tag_id for link in transaction.transaction_tags],
            items=[
                LedgerItem(
                    category_id=item.category_id,
                    amount=int(item.amount),
                    scope=item.scope,
                    memo=item.memo,
                    line_no=item.line_no,
                )
                for item in transaction.items
            ],
            attachments=attachments,
        )

    def _attachment_bytes(self, bundle: LedgerBundle) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        ids = [row.id for row in bundle.transactions]
        if not ids:
            return files
        loaded_rows = self._session.scalars(
            select(Transaction).options(selectinload(Transaction.attachments)).where(Transaction.id.in_(ids))
        ).all()
        by_id = {row.id: row for row in loaded_rows}
        for row in bundle.transactions:
            loaded = by_id.get(row.id)
            if loaded is None:
                continue
            for attachment, spec in zip(loaded.attachments, row.attachments, strict=False):
                source = Path(settings.data_dir) / attachment.stored_path
                if source.is_file():
                    files[spec.path] = source.read_bytes()
        return files

    def _restore_bundle(
        self,
        user: User,
        bundle: LedgerBundle,
        files: dict[str, bytes],
    ) -> LedgerImportResult:
        wallet_map = self._restore_wallets(user, bundle.wallets)
        category_map = self._restore_categories(user, bundle.categories)
        tag_map = self._restore_tags(user, bundle.tags)
        rules_created = self._restore_rules(user, bundle.rules, wallet_map, category_map, tag_map)
        created_txs, created_files = self._restore_transactions(
            user,
            bundle.transactions,
            wallet_map,
            category_map,
            tag_map,
            files,
        )
        return LedgerImportResult(
            wallets_created=wallet_map.created,
            wallets_matched=wallet_map.matched,
            categories_created=category_map.created,
            categories_matched=category_map.matched,
            tags_created=tag_map.created,
            rules_created=rules_created,
            transactions_created=created_txs,
            attachments_created=created_files,
            replaced_transactions=0,
        )

    def _restore_wallets(self, user: User, rows: list[LedgerWallet]) -> "_IdMap":
        existing = self._account_repo.list_wallets(user.organization_id, owner_user_id=user.id, include_hidden=True)
        unused = list(existing)
        mapping: dict[int, int] = {}
        created = 0
        matched = 0
        opening_on = date.today()
        ordered = sorted(rows, key=lambda row: (1 if row.instrument_kind == CARD_KIND else 0, row.sort_order, row.id))
        for row in ordered:
            found = next(
                (
                    wallet
                    for wallet in unused
                    if wallet.instrument_kind == row.instrument_kind and wallet.name == row.name
                ),
                None,
            )
            if found is not None:
                unused.remove(found)
                mapping[row.id] = found.id
                matched += 1
                if row.settlement_account_id is not None and row.instrument_kind == CARD_KIND:
                    settlement = mapping.get(row.settlement_account_id)
                    if settlement is not None:
                        self._accounts.update_wallet(
                            found.id,
                            WalletAccountUpdate(settlement_account_id=settlement, card_payment_day=row.card_payment_day),
                            owner_user_id=user.id,
                        )
                if not row.is_active and found.is_active:
                    self._accounts.update_wallet(found.id, WalletAccountUpdate(is_active=False), owner_user_id=user.id)
                self._align_opening(found.id, row.opening_balance, opening_on, user.id)
                continue
            settlement_id = None
            if row.instrument_kind == CARD_KIND:
                if row.settlement_account_id is None or row.settlement_account_id not in mapping:
                    raise AccountingError(f"카드 '{row.name}'의 결제 계좌를 백업에서 찾지 못했어요.")
                settlement_id = mapping[row.settlement_account_id]
            created_wallet = self._accounts.create_wallet(
                WalletAccountCreate(
                    organization_id=user.organization_id,
                    name=row.name,
                    instrument_kind=row.instrument_kind,
                    currency=row.currency or "KRW",
                    opening_balance=row.opening_balance,
                    opening_on=opening_on,
                    institution=row.institution,
                    card_payment_day=row.card_payment_day,
                    settlement_account_id=settlement_id,
                    sort_order=row.sort_order,
                ),
                owner_user_id=user.id,
            )
            if not row.is_active:
                self._accounts.update_wallet(
                    created_wallet.id,
                    WalletAccountUpdate(is_active=False),
                    owner_user_id=user.id,
                )
            mapping[row.id] = created_wallet.id
            created += 1
        return _IdMap(ids=mapping, created=created, matched=matched)

    def _align_opening(self, wallet_id: int, opening_balance: int, occurred_on: date, owner_user_id: int) -> None:
        current = self._accounts.get_wallet(wallet_id, owner_user_id=owner_user_id).current_balance
        if current == opening_balance:
            return
        if opening_balance < 0:
            raise AccountingError("시작 잔액은 0원 이상이어야 해요.")
        try:
            self._accounts.adjust_balance(
                wallet_id,
                WalletBalanceAdjust(
                    actual_balance=opening_balance,
                    occurred_on=occurred_on,
                    memo="백업 시작 잔액",
                ),
                owner_user_id=owner_user_id,
            )
        except AccountingError:
            if current != opening_balance:
                raise

    def _restore_categories(self, user: User, rows: list[LedgerCategory]) -> "_IdMap":
        existing = self._category_repo.list_categories(user.organization_id, owner_user_id=user.id, include_hidden=True)
        unused = list(existing)
        mapping: dict[int, int] = {}
        created = 0
        matched = 0
        for row in _order_categories(rows):
            found = next((item for item in unused if item.name == row.name), None)
            if found is not None:
                unused.remove(found)
                mapping[row.id] = found.id
                matched += 1
                parent_id = mapping.get(row.parent_id) if row.parent_id is not None else None
                self._categories.update_category(
                    found.id,
                    CategoryUpdate(
                        parent_id=parent_id,
                        clear_parent=row.parent_id is None,
                        default_scope=row.default_scope,
                        icon=row.icon,
                        sort_order=row.sort_order,
                        is_active=row.is_active,
                    ),
                    owner_user_id=user.id,
                )
                continue
            chart = self._account_repo.get_by_code(user.organization_id, row.chart_code)
            if chart is None:
                raise AccountingError(f"분류 '{row.name}'에 연결된 계정과목({row.chart_code})이 없어요.")
            parent_id = mapping.get(row.parent_id) if row.parent_id is not None else None
            created_category = self._categories.create_category(
                CategoryCreate(
                    organization_id=user.organization_id,
                    parent_id=parent_id,
                    account_id=chart.id,
                    name=row.name,
                    transaction_type=row.transaction_type,
                    default_scope=row.default_scope,
                    icon=row.icon,
                    sort_order=row.sort_order,
                ),
                owner_user_id=user.id,
            )
            if not row.is_active:
                self._categories.update_category(
                    created_category.id,
                    CategoryUpdate(is_active=False),
                    owner_user_id=user.id,
                )
            mapping[row.id] = created_category.id
            created += 1
        return _IdMap(ids=mapping, created=created, matched=matched)

    def _restore_tags(self, user: User, rows: list[LedgerTag]) -> "_IdMap":
        existing = self._tag_repo.list_tags(user.organization_id, owner_user_id=user.id)
        unused = list(existing)
        mapping: dict[int, int] = {}
        created = 0
        matched = 0
        for row in rows:
            found = next((item for item in unused if item.name == row.name), None)
            if found is not None:
                unused.remove(found)
                mapping[row.id] = found.id
                matched += 1
                continue
            created_tag = self._tags.create_tag(
                TagCreate(organization_id=user.organization_id, name=row.name),
                owner_user_id=user.id,
            )
            mapping[row.id] = created_tag.id
            created += 1
        return _IdMap(ids=mapping, created=created, matched=matched)

    def _restore_rules(
        self,
        user: User,
        rows: list[LedgerRule],
        wallets: "_IdMap",
        categories: "_IdMap",
        tags: "_IdMap",
    ) -> int:
        existing = {(rule.merchant_keyword, rule.category_id) for rule in self._import_repo.list_rules(user.organization_id, owner_user_id=user.id)}
        created = 0
        for row in rows:
            category_id = categories.ids.get(row.category_id)
            if category_id is None:
                continue
            payment_id = wallets.ids.get(row.payment_account_id) if row.payment_account_id is not None else None
            key = (row.merchant_keyword, category_id)
            if key in existing:
                continue
            self._imports.create_rule(
                user,
                AutoCategoryRuleCreate(
                    name=row.name,
                    merchant_keyword=row.merchant_keyword,
                    payment_account_id=payment_id,
                    category_id=category_id,
                    scope=row.scope,
                    tag_ids=[tags.ids[tag_id] for tag_id in row.tag_ids if tag_id in tags.ids],
                    sort_order=row.sort_order,
                    is_active=row.is_active,
                ),
            )
            existing.add(key)
            created += 1
        return created

    def _restore_transactions(
        self,
        user: User,
        rows: list[LedgerTransaction],
        wallets: "_IdMap",
        categories: "_IdMap",
        tags: "_IdMap",
        files: dict[str, bytes],
    ) -> tuple[int, int]:
        created = 0
        attachments = 0
        for row in sorted(rows, key=lambda item: (item.occurred_on, item.id)):
            payment_id = wallets.ids.get(row.payment_account_id)
            if payment_id is None:
                raise AccountingError("거래에 쓰인 결제수단을 백업에서 찾지 못했어요.")
            transfer_id = None
            if row.transfer_account_id is not None:
                transfer_id = wallets.ids.get(row.transfer_account_id)
                if transfer_id is None:
                    raise AccountingError("이체 상대 계좌를 백업에서 찾지 못했어요.")
            items = []
            if row.transaction_type != TransactionType.TRANSFER:
                for item in row.items:
                    category_id = categories.ids.get(item.category_id) if item.category_id is not None else None
                    if category_id is None:
                        raise AccountingError("거래 분류를 백업에서 찾지 못했어요.")
                    items.append(
                        TransactionItemCreate(
                            category_id=category_id,
                            amount=item.amount,
                            scope=item.scope,
                            memo=item.memo,
                            line_no=item.line_no,
                        )
                    )
            saved = self._transactions.create(
                TransactionCreate(
                    organization_id=user.organization_id,
                    occurred_on=row.occurred_on,
                    transaction_type=row.transaction_type,
                    scope=row.scope,
                    amount=row.amount,
                    memo=row.memo,
                    payment_account_id=payment_id,
                    transfer_account_id=transfer_id,
                    items=items,
                    tag_ids=[tags.ids[tag_id] for tag_id in row.tag_ids if tag_id in tags.ids],
                ),
                created_by_user_id=user.id,
            )
            created += 1
            for spec in row.attachments:
                content = files.get(spec.path)
                if content is None:
                    continue
                self._transactions.add_attachment(
                    saved.id,
                    original_filename=spec.original_filename,
                    content=content,
                    content_type=spec.content_type,
                )
                attachments += 1
        return created, attachments

    def _active_transactions(self, user: User) -> list[Transaction]:
        return list(
            self._session.scalars(
                select(Transaction)
                .options(
                    selectinload(Transaction.items),
                    selectinload(Transaction.transaction_tags),
                    selectinload(Transaction.attachments),
                )
                .where(Transaction.organization_id == user.organization_id)
                .where(Transaction.created_by_user_id == user.id)
                .where(Transaction.status != RecordStatus.REVERSED)
                .order_by(Transaction.occurred_on.asc(), Transaction.id.asc())
            )
        )


class _IdMap:
    def __init__(self, *, ids: dict[int, int], created: int, matched: int) -> None:
        self.ids = ids
        self.created = created
        self.matched = matched


def _order_categories(rows: list[LedgerCategory]) -> list[LedgerCategory]:
    remaining = {row.id: row for row in rows}
    ordered: list[LedgerCategory] = []
    while remaining:
        progressed = False
        for row_id, row in list(remaining.items()):
            if row.parent_id is None or row.parent_id not in remaining:
                ordered.append(row)
                del remaining[row_id]
                progressed = True
        if not progressed:
            ordered.extend(remaining.values())
            break
    return ordered


def _read_bundle(payload: bytes) -> tuple[LedgerBundle, dict[str, bytes]]:
    if len(payload) >= 4 and payload[:2] == b"PK":
        try:
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                names = archive.namelist()
                if "ledger.json" not in names:
                    raise AccountingError("백업 파일에 ledger.json 이 없어요.")
                bundle = LedgerBundle.model_validate_json(archive.read("ledger.json"))
                files = {
                    name: archive.read(name)
                    for name in names
                    if name.startswith("attachments/") and not name.endswith("/")
                }
        except zipfile.BadZipFile as error:
            raise AccountingError("백업 ZIP 파일을 읽지 못했어요.") from error
    else:
        try:
            bundle = LedgerBundle.model_validate_json(payload)
        except ValueError as error:
            raise AccountingError("백업 파일 형식이 올바르지 않아요.") from error
        files = {}
    if bundle.format != LEDGER_FORMAT:
        raise AccountingError("eldLedger 백업 파일이 아니에요.")
    if bundle.version != LEDGER_VERSION:
        raise AccountingError("이 버전의 백업은 아직 가져올 수 없어요.")
    return bundle, files
