from collections.abc import Sequence
from typing import Any

from app.models.enums import TransactionItemKind, TransactionType


class ItemAmountError(ValueError):
    """Raised when cashbook item amounts do not match the stored transaction amount."""


def line_kind_of(item: Any) -> TransactionItemKind:
    raw = getattr(item, "line_kind", None)
    if raw is None:
        return TransactionItemKind.STANDARD
    if isinstance(raw, TransactionItemKind):
        return raw
    return TransactionItemKind(str(raw))


def is_deduction_item(item: Any) -> bool:
    return line_kind_of(item) == TransactionItemKind.DEDUCTION


def partition_items(items: Sequence[Any]) -> tuple[list[Any], list[Any]]:
    standard: list[Any] = []
    deductions: list[Any] = []
    for item in items:
        if is_deduction_item(item):
            deductions.append(item)
        else:
            standard.append(item)
    return standard, deductions


def validate_item_amounts(
    *,
    transaction_type: TransactionType,
    amount: int,
    items: Sequence[Any],
) -> None:
    if not items:
        return
    standard, deductions = partition_items(items)
    if deductions:
        if transaction_type != TransactionType.INCOME:
            raise ItemAmountError("공제는 수입 기록에만 넣을 수 있습니다.")
        if not standard:
            raise ItemAmountError("공제 있는 수입은 세전 분류가 필요합니다.")
        gross = sum(int(item.amount) for item in standard)
        withheld = sum(int(item.amount) for item in deductions)
        if withheld >= gross:
            raise ItemAmountError("공제 합계가 세전 금액보다 작아야 합니다.")
        if gross - withheld != amount:
            raise ItemAmountError("실수령은 세전에서 공제를 뺀 금액이어야 합니다.")
        return
    item_total = sum(int(item.amount) for item in items)
    if item_total != amount:
        raise ItemAmountError("항목 금액 합계가 거래 금액과 일치해야 합니다.")
