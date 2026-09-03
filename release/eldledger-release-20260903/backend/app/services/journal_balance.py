from collections.abc import Sequence


class UnbalancedJournalError(ValueError):
    def __init__(self, debit_total: int, credit_total: int) -> None:
        self.debit_total = debit_total
        self.credit_total = credit_total
        super().__init__(
            f"분개 차변 합계({debit_total})와 대변 합계({credit_total})가 일치하지 않습니다."
        )


class InvalidJournalLineError(ValueError):
    """A journal line must carry a non-negative debit XOR credit in integer KRW."""


def collect_line_amounts(lines: Sequence[object]) -> list[tuple[int, int]]:
    amounts: list[tuple[int, int]] = []
    for line in lines:
        debit = int(getattr(line, "debit_amount"))
        credit = int(getattr(line, "credit_amount"))
        amounts.append((debit, credit))
    return amounts


def assert_journal_balanced(lines: Sequence[tuple[int, int]]) -> None:
    if not lines:
        raise UnbalancedJournalError(0, 0)

    debit_total = 0
    credit_total = 0
    for debit_amount, credit_amount in lines:
        if debit_amount < 0 or credit_amount < 0:
            raise InvalidJournalLineError("차변과 대변 금액은 0 이상 정수여야 합니다.")
        if (debit_amount > 0 and credit_amount > 0) or (debit_amount == 0 and credit_amount == 0):
            raise InvalidJournalLineError("각 분개 라인은 차변 또는 대변 중 하나만 금액을 가져야 합니다.")
        debit_total += debit_amount
        credit_total += credit_amount

    if debit_total != credit_total:
        raise UnbalancedJournalError(debit_total, credit_total)
    if debit_total == 0:
        raise UnbalancedJournalError(0, 0)
