from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import PaymentInstrumentKind


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WalletAccountCreate(BaseModel):
    organization_id: int
    name: str = Field(..., min_length=1, max_length=100)
    instrument_kind: PaymentInstrumentKind
    currency: str = Field(default="KRW", min_length=3, max_length=3)
    opening_balance: int = Field(default=0, ge=0)
    opening_on: date | None = None
    institution: str | None = Field(default=None, max_length=100)
    card_payment_day: int | None = Field(default=None, ge=1, le=28)
    settlement_account_id: int | None = None
    sort_order: int = 0

    @model_validator(mode="after")
    def validate_card_fields(self) -> "WalletAccountCreate":
        if self.instrument_kind == PaymentInstrumentKind.CREDIT_CARD:
            if self.card_payment_day is None:
                raise ValueError("카드는 결제일을 입력해 주세요.")
            if self.settlement_account_id is None:
                raise ValueError("카드는 결제 계좌를 선택해 주세요.")
        else:
            if self.card_payment_day is not None or self.settlement_account_id is not None:
                raise ValueError("결제일과 결제 계좌는 신용카드만 설정할 수 있습니다.")
        return self


class WalletAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    institution: str | None = Field(default=None, max_length=100)
    card_payment_day: int | None = Field(default=None, ge=1, le=28)
    settlement_account_id: int | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class WalletBalanceAdjust(BaseModel):
    actual_balance: int = Field(..., ge=0)
    occurred_on: date
    memo: str | None = Field(default=None, max_length=255)


class WalletAccountRead(ORMModel):
    id: int
    organization_id: int
    name: str
    instrument_kind: PaymentInstrumentKind
    currency: str
    opening_balance: int
    chart_code: str
    sort_order: int
    is_active: bool
    is_system: bool
    institution: str | None
    card_payment_day: int | None
    settlement_account_id: int | None
    current_balance: int
