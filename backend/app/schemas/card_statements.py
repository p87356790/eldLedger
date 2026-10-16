from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BillStatus


class CardStatementLine(BaseModel):
    transaction_id: int
    occurred_on: date
    label: str
    signed_amount: int


class CardStatementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_account_id: int
    card_name: str
    bank_account_id: int | None
    bank_name: str | None
    title: str
    period_start: date
    period_end: date
    pay_on: date
    amount: int
    book_amount: int
    amount_locked: bool
    status: BillStatus
    paid_on: date | None
    transaction_id: int | None
    lines: list[CardStatementLine] = Field(default_factory=list)


class CardStatementUpdate(BaseModel):
    amount: int = Field(..., gt=0)


class CardStatementPay(BaseModel):
    occurred_on: date
