from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Account, AutoCategoryRule, Category, ImportProfile, Organization, Transaction, User
from app.models.enums import CategoryDefaultScope, CsvAmountMode, RecordStatus, Scope, TransactionType
from app.repositories.import_repository import ImportRepository
from app.schemas.accounting import TransactionCreate, TransactionItemCreate
from app.schemas.categories import TagRead
from app.schemas.imports import (
    AutoCategoryRuleCreate,
    AutoCategoryRuleRead,
    AutoCategoryRuleUpdate,
    ImportCommitFailure,
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportProfileRead,
)
from app.services.accounting_service import AccountingError
from app.services.audit_service import AuditService
from app.services.transaction_service import TransactionService

MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_CSV_ROWS = 2000
ENCODINGS = ("utf-8-sig", "utf-8", "cp949", "euc-kr")
DATE_FORMATS = ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y%m%d", "%y-%m-%d", "%y.%m.%d", "%m/%d/%Y")

PRESET_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "preset_key": "generic",
        "name": "일반 CSV",
        "date_column": "날짜",
        "merchant_column": "가맹점",
        "memo_column": "메모",
        "amount_column": "금액",
        "outflow_column": None,
        "inflow_column": None,
        "type_column": "구분",
        "amount_mode": CsvAmountMode.SIGNED,
    },
    {
        "preset_key": "card_kr",
        "name": "카드 이용내역",
        "date_column": "이용일자",
        "merchant_column": "가맹점명",
        "memo_column": None,
        "amount_column": "이용금액",
        "outflow_column": None,
        "inflow_column": None,
        "type_column": None,
        "amount_mode": CsvAmountMode.UNSIGNED_EXPENSE,
    },
    {
        "preset_key": "bank_kr",
        "name": "은행 거래내역",
        "date_column": "거래일자",
        "merchant_column": "적요",
        "memo_column": None,
        "amount_column": None,
        "outflow_column": "출금",
        "inflow_column": "입금",
        "type_column": None,
        "amount_mode": CsvAmountMode.SPLIT,
    },
    {
        "preset_key": "cashbook",
        "name": "가계부 표",
        "date_column": "언제인가요?",
        "merchant_column": "사용처",
        "memo_column": "메모",
        "amount_column": "얼마인가요?",
        "outflow_column": None,
        "inflow_column": None,
        "type_column": None,
        "amount_mode": CsvAmountMode.UNSIGNED_EXPENSE,
    },
)

HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("언제인가요?", "언제인가요", "날짜", "거래일", "거래일자", "이용일자", "사용일", "전표일자", "date"),
    "merchant": ("사용처", "가맹점", "가맹점명", "적요", "내용", "거래내용", "merchant"),
    "memo": ("메모", "비고", "적요2", "memo"),
    "amount": ("얼마인가요?", "얼마인가요", "금액", "이용금액", "거래금액", "승인금액", "amount"),
    "outflow": ("출금", "출금액", "지급", "출금금액"),
    "inflow": ("입금", "입금액", "수취", "입금금액"),
    "type": ("구분", "거래구분", "입출금", "유형"),
    "payment": ("어떻게 냈나요?", "어떻게 냈나요", "결제수단", "카드", "계좌"),
    "category": ("어디에 사용했나요?", "어디에 사용했나요", "분류", "카테고리"),
}


@dataclass(frozen=True)
class ParsedAmount:
    value: int
    transaction_type: TransactionType


class CsvImportService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = ImportRepository(session)
        self._transactions = TransactionService(session)
        self._audit = AuditService(session)

    def list_profiles(self, user: User) -> list[ImportProfileRead]:
        self._ensure_presets(user.organization_id)
        return [ImportProfileRead.model_validate(item) for item in self._repo.list_profiles(user.organization_id)]

    def preview(
        self,
        user: User,
        *,
        file_bytes: bytes,
        filename: str,
        account_id: int | None,
        organization_id: int | None,
        profile_id: int | None,
    ) -> ImportPreviewResponse:
        organization_id = organization_id or user.organization_id
        self._require_org(user, organization_id)
        fallback_account = (
            self._require_payment_account(user, organization_id, account_id) if account_id is not None else None
        )
        if not filename.lower().endswith((".csv", ".txt", ".tsv")):
            raise AccountingError("CSV 또는 표 텍스트만 가져올 수 있어요.")
        if len(file_bytes) == 0:
            raise AccountingError("빈 파일이에요.")
        if len(file_bytes) > MAX_CSV_BYTES:
            raise AccountingError("CSV는 5MB 이하여야 해요.")

        encoding = detect_encoding(file_bytes)
        text = file_bytes.decode(encoding)
        delimiter, headers, records = parse_csv_table(text)
        if len(records) > MAX_CSV_ROWS:
            raise AccountingError(f"한 번에 {MAX_CSV_ROWS}행까지만 가져올 수 있어요.")

        self._ensure_presets(organization_id)
        profile = self._resolve_profile(organization_id, profile_id, headers)
        fingerprints = self._existing_fingerprints(organization_id)
        rules = self._repo.list_rules(organization_id, owner_user_id=user.id, active_only=True)
        wallets = self._list_payment_accounts(user, organization_id)
        categories = self._list_user_categories(user, organization_id)
        seen: set[str] = set()
        rows: list[ImportPreviewRow] = []
        for index, record in enumerate(records, start=2):
            parsed = self._parse_record(record, profile)
            duplicate = False
            skip = False
            if parsed.fingerprint is not None and parsed.error is None:
                duplicate = parsed.fingerprint in fingerprints or parsed.fingerprint in seen
                skip = duplicate
                seen.add(parsed.fingerprint)
            wallet = match_wallet(parsed.payment_label, wallets)
            if wallet is None and parsed.payment_label.strip() == "":
                wallet = fallback_account
            category = None
            if parsed.error is None and parsed.transaction_type is not None:
                category = match_category(parsed.category_label, categories, parsed.transaction_type)
            suggestion = None
            if category is None and parsed.error is None:
                suggestion = self._suggest(
                    parsed,
                    rules,
                    wallet.id if wallet is not None else (fallback_account.id if fallback_account is not None else 0),
                )
            if category is not None:
                category_id = category.id
                category_name = category.name
                scope = _scope_from_category(category)
                tag_ids: list[int] = []
                suggested = True
            elif suggestion is not None:
                category_id = suggestion.category_id
                category_name = suggestion.category_name
                scope = suggestion.scope
                tag_ids = suggestion.tag_ids
                suggested = True
            else:
                category_id = None
                category_name = None
                scope = Scope.PERSONAL
                tag_ids = []
                suggested = False
            rows.append(
                ImportPreviewRow(
                    row_no=index,
                    occurred_on=parsed.occurred_on,
                    amount=parsed.amount,
                    merchant=parsed.merchant,
                    memo=parsed.extra_memo,
                    transaction_type=parsed.transaction_type,
                    scope=scope,
                    category_id=category_id,
                    category_name=category_name,
                    payment_account_id=wallet.id if wallet is not None else None,
                    payment_account_name=(
                        wallet.name
                        if wallet is not None
                        else (parsed.payment_label.strip() or None)
                    ),
                    tag_ids=tag_ids,
                    suggested=suggested,
                    duplicate=duplicate,
                    skip=skip,
                    fingerprint=parsed.fingerprint,
                    error=parsed.error,
                )
            )
        return ImportPreviewResponse(
            encoding=encoding.replace("-sig", ""),
            delimiter="tab" if delimiter == "\t" else delimiter,
            headers=headers,
            profile=ImportProfileRead.model_validate(profile),
            rows=rows,
            total_rows=len(rows),
            duplicate_count=sum(1 for row in rows if row.duplicate),
            uncategorized_count=sum(1 for row in rows if row.error is None and row.category_id is None),
            error_count=sum(1 for row in rows if row.error is not None),
        )

    def commit(self, user: User, payload: ImportCommitRequest) -> ImportCommitResponse:
        self._require_org(user, payload.organization_id)
        if payload.payment_account_id is not None:
            self._require_payment_account(user, payload.organization_id, payload.payment_account_id)
        created = 0
        skipped = 0
        failed: list[ImportCommitFailure] = []
        for row in payload.rows:
            if row.skip:
                skipped += 1
                continue
            if row.transaction_type == TransactionType.TRANSFER:
                failed.append(ImportCommitFailure(merchant=row.merchant, error="이체는 CSV로 가져올 수 없어요."))
                continue
            merchant = row.merchant.strip() if row.merchant.strip() else None
            extra_memo = row.memo.strip() if row.memo is not None and row.memo.strip() else None
            payment_account_id = row.payment_account_id or payload.payment_account_id
            if payment_account_id is None:
                failed.append(
                    ImportCommitFailure(
                        merchant=row.merchant,
                        error="어떻게 냈나요?에 적은 자산 이름을 목록에서 찾지 못했어요.",
                    )
                )
                continue
            try:
                self._require_payment_account(user, payload.organization_id, payment_account_id)
                self._transactions.create(
                    TransactionCreate(
                        organization_id=payload.organization_id,
                        occurred_on=row.occurred_on,
                        transaction_type=row.transaction_type,
                        scope=row.scope,
                        amount=row.amount,
                        merchant=merchant,
                        memo=extra_memo,
                        payment_account_id=payment_account_id,
                        items=[
                            TransactionItemCreate(
                                category_id=row.category_id,
                                amount=row.amount,
                                scope=row.scope,
                                memo=None,
                                line_no=1,
                            )
                        ],
                        tag_ids=row.tag_ids,
                    ),
                    created_by_user_id=user.id,
                )
                created += 1
            except (AccountingError, LookupError, ValueError) as error:
                failed.append(ImportCommitFailure(merchant=row.merchant, error=str(error)))
        self._audit.record(
            action="IMPORT_COMMIT",
            user_id=user.id,
            entity_type="import",
            details=f"{created}건 등록, {skipped}건 건너뜀, {len(failed)}건 실패",
        )
        self._session.flush()
        return ImportCommitResponse(created=created, skipped=skipped, failed=failed)

    def list_rules(self, user: User) -> list[AutoCategoryRuleRead]:
        return [_rule_read(rule) for rule in self._repo.list_rules(user.organization_id, owner_user_id=user.id)]

    def create_rule(self, user: User, payload: AutoCategoryRuleCreate) -> AutoCategoryRuleRead:
        self._validate_rule_refs(user, payload.category_id, payload.payment_account_id, payload.scope)
        rule = AutoCategoryRule(
            organization_id=user.organization_id,
            owner_user_id=user.id,
            name=payload.name.strip(),
            merchant_keyword=payload.merchant_keyword.strip(),
            payment_account_id=payload.payment_account_id,
            category_id=payload.category_id,
            scope=payload.scope,
            sort_order=payload.sort_order,
            is_active=payload.is_active,
        )
        self._session.add(rule)
        self._session.flush()
        self._repo.replace_rule_tags(rule, payload.tag_ids)
        self._session.flush()
        loaded = self._repo.get_rule(rule.id)
        assert loaded is not None
        return _rule_read(loaded)

    def update_rule(self, user: User, rule_id: int, payload: AutoCategoryRuleUpdate) -> AutoCategoryRuleRead:
        rule = self._require_rule(user, rule_id)
        if payload.name is not None:
            rule.name = payload.name.strip()
        if payload.merchant_keyword is not None:
            rule.merchant_keyword = payload.merchant_keyword.strip()
        if payload.clear_payment_account:
            rule.payment_account_id = None
        elif payload.payment_account_id is not None:
            rule.payment_account_id = payload.payment_account_id
        if payload.category_id is not None:
            rule.category_id = payload.category_id
        if payload.scope is not None:
            rule.scope = payload.scope
        if payload.sort_order is not None:
            rule.sort_order = payload.sort_order
        if payload.is_active is not None:
            rule.is_active = payload.is_active
        self._validate_rule_refs(user, rule.category_id, rule.payment_account_id, rule.scope)
        if payload.tag_ids is not None:
            self._repo.replace_rule_tags(rule, payload.tag_ids)
        self._session.flush()
        loaded = self._repo.get_rule(rule.id)
        assert loaded is not None
        return _rule_read(loaded)

    def delete_rule(self, user: User, rule_id: int) -> None:
        rule = self._require_rule(user, rule_id)
        self._session.delete(rule)
        self._session.flush()

    def _ensure_presets(self, organization_id: int) -> None:
        organization = self._session.get(Organization, organization_id)
        if organization is None:
            raise LookupError("장부를 찾을 수 없어요.")
        for preset in PRESET_DEFINITIONS:
            existing = self._repo.get_profile_by_preset(organization_id, str(preset["preset_key"]))
            if existing is not None:
                if existing.preset_key == "cashbook" and not existing.memo_column:
                    existing.memo_column = "메모"
                continue
            self._session.add(
                ImportProfile(
                    organization_id=organization_id,
                    name=str(preset["name"]),
                    preset_key=str(preset["preset_key"]),
                    date_column=str(preset["date_column"]),
                    merchant_column=str(preset["merchant_column"]),
                    memo_column=preset["memo_column"],
                    amount_column=preset["amount_column"],
                    outflow_column=preset["outflow_column"],
                    inflow_column=preset["inflow_column"],
                    type_column=preset["type_column"],
                    amount_mode=preset["amount_mode"],
                    is_preset=True,
                    is_active=True,
                )
            )
        self._session.flush()

    def _resolve_profile(
        self,
        organization_id: int,
        profile_id: int | None,
        headers: list[str],
    ) -> ImportProfile:
        if profile_id is not None:
            profile = self._repo.get_profile(profile_id)
            if profile is None or profile.organization_id != organization_id:
                raise AccountingError("열 매핑 프로필을 찾을 수 없어요.")
            return profile
        header_set = {_norm_header(header) for header in headers}
        for preset in PRESET_DEFINITIONS:
            needed = {_norm_header(str(preset["date_column"])), _norm_header(str(preset["merchant_column"]))}
            if preset["amount_mode"] == CsvAmountMode.SPLIT:
                needed.update({_norm_header(str(preset["outflow_column"])), _norm_header(str(preset["inflow_column"]))})
            else:
                needed.add(_norm_header(str(preset["amount_column"])))
            if needed.issubset(header_set):
                found = self._repo.get_profile_by_preset(organization_id, str(preset["preset_key"]))
                if found is not None:
                    return found
        generic = self._repo.get_profile_by_preset(organization_id, "generic")
        if generic is None:
            raise AccountingError("열 매핑 프로필을 준비하지 못했어요.")
        return generic

    def _parse_record(self, record: dict[str, str], profile: ImportProfile) -> "_RowParse":
        occurred_on = parse_date(_cell(record, profile.date_column, *HEADER_ALIASES["date"]))
        merchant = " ".join(_cell(record, profile.merchant_column, *HEADER_ALIASES["merchant"]).split())
        extra_memo = " ".join(_cell(record, profile.memo_column, *HEADER_ALIASES["memo"]).split()) or None
        payment_label = _cell(record, None, *HEADER_ALIASES["payment"])
        category_label = _cell(record, None, *HEADER_ALIASES["category"])
        try:
            parsed_amount = self._parse_amount(record, profile)
        except AccountingError as error:
            return _RowParse(None, None, merchant, extra_memo, payment_label, category_label, None, None, str(error))
        if occurred_on is None:
            return _RowParse(
                None,
                parsed_amount.value,
                merchant,
                extra_memo,
                payment_label,
                category_label,
                parsed_amount.transaction_type,
                None,
                "날짜를 읽지 못했어요.",
            )
        if not merchant:
            return _RowParse(
                occurred_on,
                parsed_amount.value,
                "",
                extra_memo,
                payment_label,
                category_label,
                parsed_amount.transaction_type,
                None,
                "사용처가 비어 있어요.",
            )
        if parsed_amount.value <= 0:
            return _RowParse(
                occurred_on,
                parsed_amount.value,
                merchant,
                extra_memo,
                payment_label,
                category_label,
                parsed_amount.transaction_type,
                None,
                "금액은 0보다 커야 해요.",
            )
        fingerprint = import_fingerprint(occurred_on, parsed_amount.value, merchant)
        return _RowParse(
            occurred_on,
            parsed_amount.value,
            merchant,
            extra_memo,
            payment_label,
            category_label,
            parsed_amount.transaction_type,
            fingerprint,
            None,
        )

    def _parse_amount(self, record: dict[str, str], profile: ImportProfile) -> ParsedAmount:
        type_hint = classify_type_label(_cell(record, profile.type_column, *HEADER_ALIASES["type"]))
        if profile.amount_mode == CsvAmountMode.SPLIT:
            outflow = abs(parse_krw(_cell(record, profile.outflow_column, *HEADER_ALIASES["outflow"]) or "0"))
            inflow = abs(parse_krw(_cell(record, profile.inflow_column, *HEADER_ALIASES["inflow"]) or "0"))
            if outflow > 0 and inflow > 0:
                raise AccountingError("출금과 입금이 한 행에 같이 있어요.")
            if outflow > 0:
                return ParsedAmount(outflow, TransactionType.EXPENSE)
            if inflow > 0:
                return ParsedAmount(inflow, TransactionType.INCOME)
            raise AccountingError("금액이 없어요.")
        raw = _cell(record, profile.amount_column, *HEADER_ALIASES["amount"])
        signed = parse_krw(raw)
        if profile.amount_mode == CsvAmountMode.UNSIGNED_EXPENSE:
            amount = abs(signed)
            return ParsedAmount(amount, type_hint or TransactionType.EXPENSE)
        if signed < 0:
            return ParsedAmount(abs(signed), TransactionType.EXPENSE)
        if signed > 0:
            return ParsedAmount(signed, type_hint or TransactionType.INCOME)
        raise AccountingError("금액이 없어요.")

    def _suggest(
        self,
        parsed: "_RowParse",
        rules: Sequence[AutoCategoryRule],
        account_id: int,
    ) -> "_Suggestion | None":
        if parsed.transaction_type is None:
            return None
        merchant = parsed.merchant.casefold()
        for rule in rules:
            if rule.scope == Scope.MIXED:
                continue
            if rule.payment_account_id is not None and rule.payment_account_id != account_id:
                continue
            if rule.merchant_keyword.strip().casefold() not in merchant:
                continue
            category = rule.category
            if category is None or not category.is_active:
                continue
            if category.transaction_type != parsed.transaction_type:
                continue
            return _Suggestion(
                category_id=category.id,
                category_name=category.name,
                scope=rule.scope,
                tag_ids=[tag.id for tag in rule.tags],
            )
        return None

    def _existing_fingerprints(self, organization_id: int) -> set[str]:
        rows = self._session.execute(
            select(Transaction.occurred_on, Transaction.amount, Transaction.merchant, Transaction.memo).where(
                Transaction.organization_id == organization_id,
                Transaction.status == RecordStatus.CONFIRMED,
            )
        ).all()
        fingerprints: set[str] = set()
        for occurred_on, amount, merchant_value, memo in rows:
            if merchant_value:
                merchant = normalize_merchant(merchant_value)
            else:
                # 예전 데이터: 가맹점이 memo 앞부분에 붙어 있음
                merchant = normalize_merchant((memo or "").split(" · ", 1)[0])
            if merchant:
                fingerprints.add(import_fingerprint(occurred_on, int(amount), merchant))
        return fingerprints

    def _require_org(self, user: User, organization_id: int) -> None:
        if user.organization_id != organization_id:
            raise AccountingError("다른 장부에는 가져올 수 없어요.")

    def _require_payment_account(self, user: User, organization_id: int, account_id: int) -> Account:
        account = self._session.get(Account, account_id)
        if account is None or account.organization_id != organization_id:
            raise LookupError("결제수단을 찾을 수 없어요.")
        if account.owner_user_id is not None and account.owner_user_id != user.id:
            raise LookupError("결제수단을 찾을 수 없어요.")
        if not account.is_postable or not account.is_active or not account.is_payment_method:
            raise AccountingError("이 계좌로는 가져올 수 없어요.")
        return account

    def _require_rule(self, user: User, rule_id: int) -> AutoCategoryRule:
        rule = self._repo.get_rule(rule_id)
        if rule is None or rule.organization_id != user.organization_id or rule.owner_user_id != user.id:
            raise LookupError("규칙을 찾을 수 없어요.")
        return rule

    def _validate_rule_refs(
        self,
        user: User,
        category_id: int,
        payment_account_id: int | None,
        scope: Scope,
    ) -> None:
        if scope == Scope.MIXED:
            raise AccountingError("자동 분류 구분은 개인 또는 사업만 가능해요.")
        category = self._session.get(Category, category_id)
        if (
            category is None
            or category.organization_id != user.organization_id
            or category.owner_user_id != user.id
            or not category.is_active
        ):
            raise AccountingError("분류를 확인해주세요.")
        if payment_account_id is not None:
            self._require_payment_account(user, user.organization_id, payment_account_id)

    def _list_payment_accounts(self, user: User, organization_id: int) -> list[Account]:
        return list(
            self._session.scalars(
                select(Account).where(
                    Account.organization_id == organization_id,
                    Account.is_payment_method.is_(True),
                    Account.is_active.is_(True),
                    Account.is_postable.is_(True),
                    or_(Account.owner_user_id.is_(None), Account.owner_user_id == user.id),
                )
            ).all()
        )

    def _list_user_categories(self, user: User, organization_id: int) -> list[Category]:
        return list(
            self._session.scalars(
                select(Category).where(
                    Category.organization_id == organization_id,
                    Category.is_active.is_(True),
                    or_(Category.owner_user_id.is_(None), Category.owner_user_id == user.id),
                )
            ).all()
        )


@dataclass
class _RowParse:
    occurred_on: date | None
    amount: int | None
    merchant: str
    extra_memo: str | None
    payment_label: str
    category_label: str
    transaction_type: TransactionType | None
    fingerprint: str | None
    error: str | None


@dataclass
class _Suggestion:
    category_id: int
    category_name: str
    scope: Scope
    tag_ids: list[int]


def detect_encoding(data: bytes) -> str:
    for encoding in ENCODINGS:
        try:
            data.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def parse_csv_table(text: str) -> tuple[str, list[str], list[dict[str, str]]]:
    delimiter = _detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if reader.fieldnames is None:
        raise AccountingError("헤더 행이 없어요.")
    headers = [name.strip() for name in reader.fieldnames if name is not None and name.strip() != ""]
    records: list[dict[str, str]] = []
    for raw in reader:
        if all((value or "").strip() == "" for value in raw.values()):
            continue
        records.append({(key or "").strip(): (value or "").strip() for key, value in raw.items()})
    return delimiter, headers, records


def parse_krw(raw: str) -> int:
    text = raw.strip().replace("₩", "").replace("원", "").replace(",", "").replace(" ", "").replace("\u00a0", "")
    if text == "":
        return 0
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    if text.startswith("-"):
        negative = True
        text = text[1:]
    if text.startswith("+"):
        text = text[1:]
    if "." in text:
        text = text.split(".", 1)[0]
    if not text.isdigit():
        raise AccountingError("금액을 숫자로 읽지 못했어요.")
    value = int(text)
    return -value if negative else value


def parse_date(raw: str) -> date | None:
    text = raw.strip()
    if text == "":
        return None
    text = re.split(r"[ T]", text, maxsplit=1)[0].strip()
    matched = re.fullmatch(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", text)
    if matched is not None:
        try:
            return date(int(matched.group(1)), int(matched.group(2)), int(matched.group(3)))
        except ValueError:
            return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 8:
        try:
            return datetime.strptime(digits[:8], "%Y%m%d").date()
        except ValueError:
            return None
    return None


def normalize_merchant(value: str) -> str:
    return " ".join(value.split()).casefold()


def import_fingerprint(occurred_on: date, amount: int, merchant: str) -> str:
    payload = f"{occurred_on.isoformat()}|{amount}|{normalize_merchant(merchant)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_type_label(raw: str) -> TransactionType | None:
    label = raw.strip()
    if label == "":
        return None
    if any(token in label for token in ("출금", "지출", "지급", "카드")):
        return TransactionType.EXPENSE
    if any(token in label for token in ("입금", "수입", "수취")):
        return TransactionType.INCOME
    return None


def match_wallet(label: str, wallets: Sequence[Account]) -> Account | None:
    needle = _wallet_key(label)
    if needle == "":
        return None
    exact = [wallet for wallet in wallets if _wallet_key(wallet.name) == needle]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        owned = [wallet for wallet in exact if wallet.owner_user_id is not None]
        return owned[0] if owned else exact[0]
    compact_matches = [
        wallet
        for wallet in wallets
        if needle in _wallet_key(wallet.name) or _wallet_key(wallet.name) in needle
    ]
    if len(compact_matches) == 1:
        return compact_matches[0]
    return None


def match_category(label: str, categories: Sequence[Category], transaction_type: TransactionType) -> Category | None:
    text = " ".join(label.replace(">", "/").replace("·", "/").replace("-", "/").split())
    if text == "":
        return None
    parts = [part.strip() for part in re.split(r"\s*/\s*", text) if part.strip() != ""]
    typed = [category for category in categories if category.transaction_type == transaction_type]
    by_id = {category.id: category for category in typed}
    if len(parts) >= 2:
        parent_name, child_name = parts[0], parts[-1]
        path_matches = [
            category
            for category in typed
            if category.name.casefold() == child_name.casefold()
            and category.parent_id is not None
            and by_id.get(category.parent_id) is not None
            and by_id[category.parent_id].name.casefold() == parent_name.casefold()
        ]
        if len(path_matches) == 1:
            return path_matches[0]
        if len(path_matches) > 1:
            owned = [category for category in path_matches if category.owner_user_id is not None]
            if len(owned) == 1:
                return owned[0]
            return path_matches[0]
    name = parts[-1].casefold()
    exact = [category for category in typed if category.name.casefold() == name]
    if len(exact) == 0:
        return None
    owned = [category for category in exact if category.owner_user_id is not None]
    pool = owned if owned else exact
    leaves = [category for category in pool if category.parent_id is not None]
    if len(leaves) == 1:
        return leaves[0]
    if len(pool) == 1:
        return pool[0]
    return pool[0]


def _scope_from_category(category: Category) -> Scope:
    if category.default_scope == CategoryDefaultScope.BUSINESS:
        return Scope.BUSINESS
    return Scope.PERSONAL


def _detect_delimiter(text: str) -> str:
    first_line = next((line for line in text.splitlines() if line.strip() != ""), "")
    if first_line.count("\t") >= 2:
        return "\t"
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
    except csv.Error:
        if sample.count("\t") > sample.count(","):
            return "\t"
        return ","


def _wallet_key(value: str) -> str:
    return re.sub(r"[\s\-_.]+", "", value).casefold()


def _norm_header(value: str) -> str:
    return re.sub(r"[\s?？]+", "", value).casefold()


def _cell(record: dict[str, str], primary: str | None, *aliases: str) -> str:
    keys = [primary, *aliases] if primary else list(aliases)
    wanted = {_norm_header(key) for key in keys if key}
    for actual, value in record.items():
        if actual.strip() == "":
            continue
        if _norm_header(actual) in wanted:
            return value
    return ""


def _rule_read(rule: AutoCategoryRule) -> AutoCategoryRuleRead:
    return AutoCategoryRuleRead(
        id=rule.id,
        organization_id=rule.organization_id,
        name=rule.name,
        merchant_keyword=rule.merchant_keyword,
        payment_account_id=rule.payment_account_id,
        category_id=rule.category_id,
        category_name=rule.category.name if rule.category is not None else None,
        scope=rule.scope,
        sort_order=rule.sort_order,
        is_active=rule.is_active,
        tags=[TagRead.model_validate(tag) for tag in rule.tags],
    )
