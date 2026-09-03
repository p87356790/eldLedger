from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, account_id: int) -> Account | None:
        return self._session.get(Account, account_id)

    def get_by_code(self, organization_id: int, code: str) -> Account | None:
        return self._session.scalar(
            select(Account).where(Account.organization_id == organization_id, Account.code == code)
        )

    def list_wallets(
        self,
        organization_id: int,
        *,
        include_hidden: bool = False,
    ) -> list[Account]:
        stmt = (
            select(Account)
            .where(
                Account.organization_id == organization_id,
                Account.instrument_kind.is_not(None),
            )
            .order_by(Account.sort_order, Account.code)
        )
        if not include_hidden:
            stmt = stmt.where(Account.is_active.is_(True))
        return list(self._session.scalars(stmt).all())

    def list_codes(self, organization_id: int) -> set[str]:
        return set(
            self._session.scalars(select(Account.code).where(Account.organization_id == organization_id)).all()
        )

    def referenced_as_settlement(self, account_id: int) -> bool:
        return (
            self._session.scalar(
                select(Account.id).where(
                    Account.settlement_account_id == account_id,
                    Account.is_active.is_(True),
                )
            )
            is not None
        )
