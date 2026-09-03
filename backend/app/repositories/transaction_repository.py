from collections.abc import Sequence
from datetime import date

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Transaction, TransactionItem, TransactionTag
from app.models.enums import RecordStatus, Scope, TransactionType


class TransactionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, transaction_id: int) -> Transaction | None:
        return self._session.scalar(
            select(Transaction)
            .options(
                selectinload(Transaction.items),
                selectinload(Transaction.transaction_tags).selectinload(TransactionTag.tag),
                selectinload(Transaction.attachments),
            )
            .where(Transaction.id == transaction_id)
        )

    def list(
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
    ) -> tuple[int, Sequence[Transaction]]:
        stmt = (
            select(Transaction)
            .options(
                selectinload(Transaction.items),
                selectinload(Transaction.transaction_tags).selectinload(TransactionTag.tag),
                selectinload(Transaction.attachments),
            )
            .where(Transaction.organization_id == organization_id)
        )
        stmt = self._apply_filters(
            stmt,
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
        )
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = int(self._session.scalar(count_stmt) or 0)
        rows = self._session.scalars(
            stmt.order_by(Transaction.occurred_on.desc(), Transaction.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return total, rows

    def list_for_dashboard(
        self,
        *,
        organization_id: int,
        created_by_user_id: int,
        date_from: date,
        date_to: date,
        account_id: int | None = None,
    ) -> Sequence[Transaction]:
        stmt = (
            select(Transaction)
            .options(
                selectinload(Transaction.items).selectinload(TransactionItem.category),
                selectinload(Transaction.payment_account),
                selectinload(Transaction.transfer_account),
                selectinload(Transaction.attachments),
            )
            .where(Transaction.organization_id == organization_id)
            .where(Transaction.created_by_user_id == created_by_user_id)
            .where(Transaction.status != RecordStatus.REVERSED)
            .where(Transaction.occurred_on >= date_from)
            .where(Transaction.occurred_on <= date_to)
        )
        if account_id is not None:
            stmt = stmt.where(
                or_(
                    Transaction.payment_account_id == account_id,
                    Transaction.transfer_account_id == account_id,
                )
            )
        return self._session.scalars(
            stmt.order_by(Transaction.occurred_on.desc(), Transaction.id.desc())
        ).all()


    def _apply_filters(
        self,
        stmt: Select[tuple[Transaction]],
        *,
        transaction_type: TransactionType | None,
        scope: Scope | None,
        date_from: date | None,
        date_to: date | None,
        amount_min: int | None,
        amount_max: int | None,
        payment_account_id: int | None,
        category_id: int | None,
        tag_id: int | None,
        memo: str | None,
        created_by_user_id: int | None,
        include_reversed: bool,
    ) -> Select[tuple[Transaction]]:
        if not include_reversed:
            stmt = stmt.where(Transaction.status != RecordStatus.REVERSED)
        if transaction_type is not None:
            stmt = stmt.where(Transaction.transaction_type == transaction_type)
        if scope is not None:
            stmt = stmt.where(Transaction.scope == scope)
        if date_from is not None:
            stmt = stmt.where(Transaction.occurred_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(Transaction.occurred_on <= date_to)
        if amount_min is not None:
            stmt = stmt.where(Transaction.amount >= amount_min)
        if amount_max is not None:
            stmt = stmt.where(Transaction.amount <= amount_max)
        if payment_account_id is not None:
            stmt = stmt.where(
                or_(
                    Transaction.payment_account_id == payment_account_id,
                    Transaction.transfer_account_id == payment_account_id,
                )
            )
        if memo:
            stmt = stmt.where(Transaction.memo.ilike(f"%{memo}%"))
        if created_by_user_id is not None:
            stmt = stmt.where(Transaction.created_by_user_id == created_by_user_id)
        if category_id is not None:
            stmt = stmt.join(Transaction.items).where(TransactionItem.category_id == category_id).distinct()
        if tag_id is not None:
            stmt = stmt.join(Transaction.transaction_tags).where(TransactionTag.tag_id == tag_id).distinct()
        return stmt
