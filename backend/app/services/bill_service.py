from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Account, Attachment, Bill, Category, User
from app.models.enums import BillStatus, TransactionType
from app.schemas.accounting import TransactionCreate, TransactionItemCreate
from app.schemas.bills import BillCreate, BillPay, BillUpdate
from app.services.accounting_service import AccountingError
from app.services.transaction_service import (
    TransactionService,
    delete_unreferenced_attachment_files,
    resolve_attachment_path,
    store_attachment_bytes,
)


def add_months(value: date, months: int) -> date:
    """Shift a calendar date by whole months, clamping the day to the target month."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    last_day = (next_first - timedelta(days=1)).day
    return date(year, month, min(value.day, last_day))


class BillService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._transactions = TransactionService(session)

    def list_bills(self, user: User) -> list[Bill]:
        rows = list(
            self._session.scalars(
                select(Bill)
                .options(selectinload(Bill.attachments))
                .where(Bill.organization_id == user.organization_id)
                .where(Bill.created_by_user_id == user.id)
            )
        )
        rows.sort(key=_sort_key)
        return rows

    def create(self, user: User, payload: BillCreate) -> Bill:
        self._require_same_org(user, payload.organization_id)
        self._require_expense_category(user, payload.category_id)
        if payload.payment_account_id is not None:
            self._require_wallet(user, payload.payment_account_id)
        bill = Bill(
            organization_id=user.organization_id,
            created_by_user_id=user.id,
            title=payload.title,
            amount=payload.amount,
            category_id=payload.category_id,
            scope=payload.scope,
            billed_on=payload.billed_on,
            pay_on=payload.pay_on,
            memo=payload.memo,
            payment_account_id=payload.payment_account_id,
            repeats_monthly=payload.repeats_monthly,
            status=BillStatus.OPEN,
        )
        self._session.add(bill)
        self._session.flush()
        return bill

    def update(self, user: User, bill_id: int, payload: BillUpdate) -> Bill:
        bill = self._require_own(user, bill_id)
        if bill.status != BillStatus.OPEN:
            raise AccountingError("이미 지불한 청구는 고칠 수 없어요.")
        self._require_expense_category(user, payload.category_id)
        if payload.payment_account_id is not None:
            self._require_wallet(user, payload.payment_account_id)
        bill.title = payload.title
        bill.amount = payload.amount
        bill.category_id = payload.category_id
        bill.scope = payload.scope
        bill.billed_on = payload.billed_on
        bill.pay_on = payload.pay_on
        bill.memo = payload.memo
        bill.payment_account_id = payload.payment_account_id
        bill.repeats_monthly = payload.repeats_monthly
        self._session.flush()
        return bill

    def delete(self, user: User, bill_id: int) -> None:
        bill = self._require_own(user, bill_id)
        if bill.status != BillStatus.OPEN:
            raise AccountingError("이미 지불한 청구는 지울 수 없어요. 기록 화면에서 그 지출을 정정하세요.")
        paths = [item.stored_path for item in list(bill.attachments)]
        self._session.delete(bill)
        self._session.flush()
        delete_unreferenced_attachment_files(self._session, paths)

    def pay(self, user: User, bill_id: int, payload: BillPay) -> Bill:
        bill = self._require_own(user, bill_id)
        if bill.status != BillStatus.OPEN:
            raise AccountingError("이미 지불한 청구예요.")
        self._require_wallet(user, payload.payment_account_id)
        self._require_expense_category(user, bill.category_id)
        transaction = self._transactions.create(
            TransactionCreate(
                organization_id=bill.organization_id,
                occurred_on=payload.occurred_on,
                transaction_type=TransactionType.EXPENSE,
                scope=bill.scope,
                amount=bill.amount,
                merchant=bill.title,
                memo=bill.memo,
                payment_account_id=payload.payment_account_id,
                items=[
                    TransactionItemCreate(
                        category_id=bill.category_id,
                        amount=bill.amount,
                        scope=bill.scope,
                        line_no=1,
                    )
                ],
            ),
            created_by_user_id=user.id,
        )
        bill.status = BillStatus.PAID
        bill.paid_on = payload.occurred_on
        bill.transaction_id = transaction.id
        bill.payment_account_id = payload.payment_account_id
        for source in list(bill.attachments):
            self._session.add(
                Attachment(
                    transaction_id=transaction.id,
                    bill_id=None,
                    original_filename=source.original_filename,
                    stored_path=source.stored_path,
                    content_type=source.content_type,
                    file_size=source.file_size,
                )
            )
        self._session.flush()
        self._session.expire(transaction, ["attachments"])
        if bill.repeats_monthly:
            self._spawn_next_month(user, bill)
        return bill

    def add_attachment(
        self,
        user: User,
        bill_id: int,
        *,
        original_filename: str,
        content: bytes,
        content_type: str,
    ) -> Attachment:
        bill = self._require_own(user, bill_id)
        if bill.status != BillStatus.OPEN:
            raise AccountingError("이미 낸 청구의 청구서는 기록 화면에서 고칠 수 있어요.")
        attachment = store_attachment_bytes(
            occurred_on=bill.billed_on,
            original_filename=original_filename,
            content=content,
            content_type=content_type,
            bill_id=bill.id,
        )
        self._session.add(attachment)
        self._session.flush()
        self._session.expire(bill, ["attachments"])
        return attachment

    def unlink_attachment(self, user: User, bill_id: int, attachment_id: int) -> None:
        """Drop the invoice from this bill and leave the file on disk."""
        bill = self._require_own(user, bill_id)
        if bill.status != BillStatus.OPEN:
            raise AccountingError("이미 낸 청구의 청구서는 기록 화면에서 고칠 수 있어요.")
        attachment = next((item for item in bill.attachments if item.id == attachment_id), None)
        if attachment is None:
            raise LookupError("청구서를 찾을 수 없습니다.")
        self._session.delete(attachment)
        self._session.flush()
        self._session.expire(bill, ["attachments"])

    def get_attachment_file(self, user: User, bill_id: int, attachment_id: int) -> tuple[Attachment, Path]:
        bill = self._require_own(user, bill_id)
        attachment = next((item for item in bill.attachments if item.id == attachment_id), None)
        if attachment is None:
            raise LookupError("청구서를 찾을 수 없습니다.")
        return attachment, resolve_attachment_path(attachment)

    def _spawn_next_month(self, user: User, paid: Bill) -> None:
        next_billed = add_months(paid.billed_on, 1)
        next_pay = add_months(paid.pay_on, 1) if paid.pay_on is not None else None
        already = self._session.scalar(
            select(Bill.id)
            .where(Bill.created_by_user_id == user.id)
            .where(Bill.status == BillStatus.OPEN)
            .where(Bill.title == paid.title)
            .where(Bill.category_id == paid.category_id)
            .where(Bill.billed_on == next_billed)
            .limit(1)
        )
        if already is not None:
            return
        self._session.add(
            Bill(
                organization_id=paid.organization_id,
                created_by_user_id=user.id,
                title=paid.title,
                amount=paid.amount,
                category_id=paid.category_id,
                scope=paid.scope,
                billed_on=next_billed,
                pay_on=next_pay,
                memo=paid.memo,
                payment_account_id=paid.payment_account_id,
                repeats_monthly=True,
                status=BillStatus.OPEN,
            )
        )
        self._session.flush()

    def _require_same_org(self, user: User, organization_id: int) -> None:
        if user.organization_id != organization_id:
            raise AccountingError("다른 장부에는 청구를 남길 수 없어요.")

    def _require_own(self, user: User, bill_id: int) -> Bill:
        bill = self._session.get(Bill, bill_id)
        if bill is None or bill.organization_id != user.organization_id or bill.created_by_user_id != user.id:
            raise LookupError("청구를 찾을 수 없습니다.")
        return bill

    def _require_expense_category(self, user: User, category_id: int) -> Category:
        category = self._session.get(Category, category_id)
        if (
            category is None
            or category.organization_id != user.organization_id
            or category.owner_user_id != user.id
        ):
            raise LookupError("분류를 찾을 수 없습니다.")
        if category.transaction_type != TransactionType.EXPENSE or not category.is_active:
            raise AccountingError("지출 분류만 고를 수 있어요.")
        return category

    def _require_wallet(self, user: User, account_id: int) -> Account:
        account = self._session.get(Account, account_id)
        if (
            account is None
            or account.organization_id != user.organization_id
            or account.owner_user_id != user.id
            or not account.is_payment_method
            or not account.is_active
        ):
            raise LookupError("결제수단을 찾을 수 없습니다.")
        return account


def _sort_key(bill: Bill) -> tuple[int, int, int]:
    if bill.status == BillStatus.OPEN:
        due = bill.pay_on or bill.billed_on
        return (0, due.toordinal(), bill.id)
    paid = bill.paid_on or bill.billed_on
    return (1, -paid.toordinal(), -bill.id)
