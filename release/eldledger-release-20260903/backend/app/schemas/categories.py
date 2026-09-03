from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import AccountType, CategoryDefaultScope, TransactionType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    organization_id: int
    parent_id: int | None = None
    account_id: int
    name: str = Field(..., min_length=1, max_length=100)
    transaction_type: TransactionType
    default_scope: CategoryDefaultScope = CategoryDefaultScope.COMMON
    icon: str | None = Field(default=None, max_length=32)
    sort_order: int = 0

    @field_validator("transaction_type")
    @classmethod
    def income_or_expense(cls, value: TransactionType) -> TransactionType:
        if value not in {TransactionType.INCOME, TransactionType.EXPENSE}:
            raise ValueError("분류는 수입 또는 지출만 지정할 수 있습니다.")
        return value

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if stripped == "":
            raise ValueError("분류 이름을 입력해 주세요.")
        return stripped


class CategoryUpdate(BaseModel):
    parent_id: int | None = None
    clear_parent: bool = False
    account_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    default_scope: CategoryDefaultScope | None = None
    icon: str | None = Field(default=None, max_length=32)
    sort_order: int | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if stripped == "":
            raise ValueError("분류 이름을 입력해 주세요.")
        return stripped


class CategoryRead(ORMModel):
    id: int
    organization_id: int
    parent_id: int | None
    account_id: int
    name: str
    transaction_type: TransactionType
    default_scope: CategoryDefaultScope
    icon: str | None
    is_system: bool
    is_active: bool
    sort_order: int
    chart_code: str | None = None
    chart_name: str | None = None


class CategoryReorderItem(BaseModel):
    id: int
    parent_id: int | None = None
    sort_order: int


class CategoryReorderRequest(BaseModel):
    organization_id: int
    items: list[CategoryReorderItem] = Field(..., min_length=1)


class ChartAccountOption(ORMModel):
    id: int
    code: str
    name: str
    account_type: AccountType


class TagCreate(BaseModel):
    organization_id: int
    name: str = Field(..., min_length=1, max_length=50)


class TagUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class TagRead(ORMModel):
    id: int
    organization_id: int
    name: str


class TransactionTagsUpdate(BaseModel):
    tag_ids: list[int] = Field(default_factory=list)
