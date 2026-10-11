from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import BillStatus, Scope


class BillWrite(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    amount: int = Field(..., gt=0)
    category_id: int = Field(..., ge=1)
    scope: Scope
    billed_on: date
    pay_on: date | None = None
    memo: str | None = None
    payment_account_id: int | None = Field(default=None, ge=1)
    repeats_monthly: bool = False

    @model_validator(mode="after")
    def personal_or_business_only(self) -> "BillWrite":
        if self.scope == Scope.MIXED:
            raise ValueError("청구는 개인 또는 사업 중 하나로 적어 주세요.")
        title = self.title.strip()
        if title == "":
            raise ValueError("내용을 적어 주세요.")
        self.title = title
        if self.memo is not None:
            memo = self.memo.strip()
            self.memo = memo if memo != "" else None
        return self


class BillCreate(BillWrite):
    organization_id: int = Field(..., ge=1)


class BillUpdate(BillWrite):
    pass


class BillPay(BaseModel):
    occurred_on: date
    payment_account_id: int = Field(..., ge=1)


class BillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_by_user_id: int | None
    title: str
    amount: int
    category_id: int
    scope: Scope
    billed_on: date
    pay_on: date | None
    memo: str | None
    payment_account_id: int | None
    repeats_monthly: bool
    status: BillStatus
    paid_on: date | None
    transaction_id: int | None
