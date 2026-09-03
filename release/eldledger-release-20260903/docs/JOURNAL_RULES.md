# eldLedger 분개 규칙 명세서

이 문서는 사용자 거래(`Transaction`)를 복식부기 분개(`JournalEntry` / `JournalLine`)로 바꾸는 **유일한 규칙 집합**이다. 화면의 수입·지출·이체 입력은 이 규칙을 숨긴 채로 호출하고, 시산표·분개장·총계정원장은 이 규칙으로 만들어진 분개만 읽는다.

구현 위치:

| 역할 | 위치 |
| --- | --- |
| 자동분개·역분개·자본조정 | `backend/app/services/accounting_service.py` |
| 차변=대변 불변식 | `backend/app/services/journal_balance.py` |
| flush 직전 재검증 | `backend/app/models/journal.py` (`before_flush`) |
| 단위 테스트 | `backend/tests/test_accounting.py`, `test_journal_balance.py`, `test_wallets.py` |

금액 단위는 항상 **원(KRW) 정수**이다. float를 쓰지 않는다.

---

## 1. 설계 원칙

### 1.1 사용자 입력과 분개를 분리한다

`Transaction` / `TransactionItem`은 가계부 입력이다. `JournalEntry` / `JournalLine`은 회계 기록이다. 같은 테이블에 두지 않는다.

```text
Transaction  "국민카드로 사무용품 50,000원"
        │
        ▼  자동분개
JournalEntry
  JournalLine  차변 사무용품비     50,000
  JournalLine  대변 카드미지급금   50,000
```

사용자 기본 화면에는 차변·대변·분개·원장 용어를 노출하지 않는다. 이 문서는 내부 규칙이므로 회계 용어를 그대로 쓴다.

### 1.2 모든 분개는 균형이어야 한다

확정(`CONFIRMED`)되는 모든 `JournalEntry`는 다음을 만족해야 한다.

```text
SUM(debit_amount) == SUM(credit_amount)
SUM(debit_amount) > 0
```

불균형 분개는 서비스 단계에서 거부하고, SQLAlchemy `before_flush`와 DB CHECK로 한 번 더 막는다.

### 1.3 확정 분개는 고치지 않는다

확정된 `JournalEntry`와 `JournalLine`은 in-place UPDATE/DELETE하지 않는다. 수정·취소는 **역분개 후 필요하면 새 분개**로만 한다.

### 1.4 태그와 개인/사업 구분은 분개 계정을 바꾸지 않는다

- `Tag`는 검색·표시용이다. 분개 라인에 반영하지 않는다.
- `scope`(PERSONAL / BUSINESS / MIXED)는 보고·추출용이다. 분개 계정은 **분류가 가리키는 계정과목**(또는 항목에 직접 지정한 계정)으로 정한다.
- MIXED는 항목마다 PERSONAL 또는 BUSINESS를 강제하지만, 차변 계정 자체는 그 항목의 분류/계정으로 결정된다.

---

## 2. 불변식

분개를 저장하기 전에 아래를 모두 통과해야 한다. 하나라도 실패하면 `AccountingError` 또는 `UnbalancedJournalError` / `InvalidJournalLineError`로 거부한다.

| ID | 규칙 |
| --- | --- |
| J1 | 라인은 1개 이상이어야 한다. |
| J2 | 각 라인의 `debit_amount`, `credit_amount`는 0 이상 정수이다. |
| J3 | 각 라인은 차변 XOR 대변이다. `(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)` |
| J4 | 엔트리 전체 `sum(debit) == sum(credit)` 이고, 합계는 0이 아니다. |
| J5 | 분개에 쓰는 계정은 `is_postable = true` 이고 `is_active = true` 이다. 상위 집계 계정(예: 1000 자산)은 금지. |
| J6 | 거래 금액 `amount`는 0보다 큰 정수이다. |
| J7 | 수입/지출 항목 금액 합계는 거래 `amount`와 같다. |
| J8 | MIXED 거래는 항목이 1개 이상이어야 하고, 각 항목 `scope`는 PERSONAL 또는 BUSINESS만 허용한다. 항목에 MIXED를 두지 않는다. |
| J9 | 이체는 `payment_account_id`(출금)와 `transfer_account_id`(입금)가 모두 필요하고, 서로 달라야 한다. |
| J10 | 이미 활성(CONFIRMED) 분개가 있는 거래에 `post_transaction`을 다시 호출하면 거부한다. 수정은 `correct_transaction`만 사용한다. |

DB CHECK (`ck_journal_lines_debit_xor_credit` 등)는 J2·J3를 스키마 수준에서 재확인한다.

---

## 3. 계정과목과 분류 매핑

사용자는 **분류**를 고른다. 분류(`Category`)는 반드시 전기 가능한 계정과목(`Account`) 하나를 가리킨다. 분개 라인의 `account_id`는 이 계정이다.

표준 시드(`backend/app/db/init_db.py`) 기준:

### 3.1 전기 가능한 계정 (발췌)

| 코드 | 이름 | 유형 | 정상잔액 | 용도 |
| --- | --- | --- | --- | --- |
| 1100 | 현금 | ASSET | 차변 | 결제/이체 |
| 1200 | 보통예금 | ASSET | 차변 | 결제/이체 |
| 2100 | 카드미지급금 | LIABILITY | 대변 | 카드 결제 |
| 2300 | 대출금 | LIABILITY | 대변 | 대출 잔액 |
| 3100 | 개인자본 | EQUITY | 대변 | 시작잔액·잔액맞추기 상대계정 |
| 4100 | 사업매출 | REVENUE | 대변 | 수입 분류 |
| 4200 | 기타수익 | REVENUE | 대변 | 수입 분류 |
| 5100 | 사무용품비 | EXPENSE | 차변 | 지출 분류 |
| 5200 | 통신비 | EXPENSE | 차변 | 지출 분류 |
| 5300 | 교통비 | EXPENSE | 차변 | 지출 분류 |
| 5400 | 식비 | EXPENSE | 차변 | 지출 분류 |
| 5500 | 접대비 | EXPENSE | 차변 | 지출 분류 |
| 5600 | 차량유지비 | EXPENSE | 차변 | 지출 분류 |
| 5700 | 개인사용 | EXPENSE | 차변 | MIXED의 개인 몫 등 |

1000/2000/3000/4000/5000 등 상위 노드는 `is_postable = false` 이므로 분개에 쓰지 않는다.

사용자가 만든 통장·카드 지갑은 위 부모 아래에 자식 계정으로 추가되며, 결제수단/이체 계정으로 쓴다.

### 3.2 표준 분류 → 계정

| 분류(사용자) | 거래유형 | 기본 구분 | 계정코드 | 계정명 |
| --- | --- | --- | --- | --- |
| 사업매출 | INCOME | BUSINESS | 4100 | 사업매출 |
| 기타수익 | INCOME | COMMON | 4200 | 기타수익 |
| 생활비 | EXPENSE | PERSONAL | 5400 | 식비 |
| 식비 | EXPENSE | PERSONAL | 5400 | 식비 |
| 통신 | EXPENSE | PERSONAL | 5200 | 통신비 |
| 교통 | EXPENSE | PERSONAL | 5300 | 교통비 |
| 사무용품 | EXPENSE | BUSINESS | 5100 | 사무용품비 |
| 접대 | EXPENSE | BUSINESS | 5500 | 접대비 |
| 차량유지 | EXPENSE | BUSINESS | 5600 | 차량유지비 |
| 개인사용 | EXPENSE | PERSONAL | 5700 | 개인사용 |

항목에 `account_id`가 있으면 분류보다 그 계정을 우선한다. 둘 다 없으면 분개하지 않는다.

---

## 4. 거래 유형별 자동분개

저장 시 `AccountingService.post_transaction`이 거래를 확정하고 분개 1건을 만든다. 분개 `occurred_on`은 거래 날짜와 같다. 적요는 `수입` / `지출` / `이체` 이고, 거래 메모가 있으면 `지출: 프린터 용지` 형식이다.

결제수단·입출금 계정은 거래의 `payment_account_id`(이체는 추가로 `transfer_account_id`)이다.

### 4.1 지출 `EXPENSE`

항목마다 비용(또는 지정 계정)을 **차변**, 결제수단을 **대변**에 한 줄 둔다.

```text
차변: 각 항목의 분류 계정     item.amount   (라인 1..n, transaction_item_id 연결)
대변: 결제수단 계정           transaction.amount
```

단일 항목이면 Requirements §7 예시와 같다.

```text
입력: 국민카드 / 사무용품 / 사업 / 50,000원

차변: 사무용품비(5100)     50,000
대변: 카드미지급금(2100)   50,000
```

현금·통장 지출이면 대변이 1100 또는 사용자 은행 계정이다. 카드면 대변이 카드미지급금(부채 증가)이다.

### 4.2 수입 `INCOME`

입금계정을 **차변**, 항목마다 수익 계정을 **대변**에 둔다.

```text
차변: 입금계좌               transaction.amount
대변: 각 항목의 분류 계정     item.amount
```

```text
입력: 국민은행 / 사업매출 / 사업 / 1,000,000원

차변: 보통예금(1200)       1,000,000
대변: 사업매출(4100)       1,000,000
```

### 4.3 이체 `TRANSFER`

수입/지출이 아니다. 분류 항목을 쓰지 않는다. 출금 계정에서 입금 계정으로 자산(또는 지갑)만 옮긴다.

```text
차변: 입금 계정 (transfer_account_id)    amount
대변: 출금 계정 (payment_account_id)    amount
```

```text
입력: 국민은행 → 카카오뱅크(또는 현금)  500,000원

차변: 입금 계정     500,000
대변: 출금 계정     500,000
```

같은 계정으로의 이체는 거부한다.

---

## 5. 혼합 거래 `MIXED`

하나의 결제를 개인 몫과 사업 몫으로 나눈다. 거래 `scope = MIXED`이고, 항목 합계는 결제 금액과 같아야 한다.

Requirements §11 예시:

```text
입력: 카드 100,000원
  사업용품  30,000  (BUSINESS → 사무용품비 5100)
  개인생활  70,000  (PERSONAL → 개인사용 5700)

차변: 사무용품비(5100)     30,000
차변: 개인사용(5700)       70,000
대변: 카드미지급금(2100)  100,000
```

수입 MIXED도 동일하게 항목을 여러 수익 계정 대변으로 나누고, 입금계좌 차변은 거래 금액 한 줄이다.

거부 조건:

- 항목 없음
- 항목 합 ≠ 거래 금액
- 어떤 항목의 `scope`가 MIXED

---

## 6. 거래와 연결되지 않는 분개 (자본 조정)

지갑 **시작 잔액**과 **잔액 맞추기**는 `Transaction`을 만들지 않는다. `JournalEntry.transaction_id`는 NULL이다. 상대 계정은 항상 **3100 개인자본**이다.

`post_capital_adjustment(amount_delta)`:

| 지갑 정상잔액 | delta > 0 (잔액 증가) | delta < 0 (잔액 감소) |
| --- | --- | --- |
| 자산·비용형 (DEBIT) 예: 현금, 통장 | 차변 지갑 / 대변 3100 | 차변 3100 / 대변 지갑 |
| 부채·자본형 (CREDIT) 예: 카드미지급금, 대출 | 차변 3100 / 대변 지갑 | 차변 지갑 / 대변 3100 |

예시:

```text
통장 시작 잔액 1,000,000
  차변: 해당 은행계정     1,000,000
  대변: 개인자본(3100)    1,000,000

신용카드 시작 잔액(미결제) 200,000
  차변: 개인자본(3100)        200,000
  대변: 카드미지급금 지갑     200,000

현금 장부 0원 → 실제 50,000원 (잔액 맞추기)
  차변: 현금     50,000
  대변: 개인자본  50,000
```

`amount_delta == 0`이면 분개하지 않는다.

이 분개도 J1–J5를 지킨다. 거래 수정/취소 흐름에는 넣지 않는다.

---

## 7. 상태와 불변성

### 7.1 상태

| 상태 | 의미 |
| --- | --- |
| `DRAFT` | 모델 기본값. 자동분개 직후 거래·분개는 `CONFIRMED`로 올라간다. |
| `CONFIRMED` | 장부에 반영된 활성 분개. 시산표·원장이 이 상태만 집계한다. |
| `REVERSED` | 역분개로 무효가 된 원래 분개(또는 취소된 거래). |

거래 하나에 CONFIRMED 분개는 최대 1건이다. 역분개 후에는 원본이 REVERSED가 되고, 수정 시 새 CONFIRMED 분개가 생긴다.

### 7.2 취소 `cancel_transaction`

1. 활성 CONFIRMED 분개를 찾는다. 없으면 거부.
2. 각 라인의 차변·대변을 뒤바꾼 역분개를 만든다. `reverses_entry_id`는 원본 ID.
3. 원본 분개와 거래를 `REVERSED`로 바꾼다.
4. 적요는 `역분개: {원래 적요}`.

```text
원본  차변 사무용품비 50,000 / 대변 카드미지급금 50,000
역분개 차변 카드미지급금 50,000 / 대변 사무용품비 50,000
```

취소된 거래는 다시 `post_transaction`할 수 없다.

### 7.3 수정 `correct_transaction`

1. 취소된 거래는 수정 불가.
2. 활성 분개가 있으면 먼저 역분개한다.
3. 바뀐 거래 내용으로 `post_transaction`하여 새 분개를 확정한다.

원본·역분개·새 분개 세 건이 남으며, 추적 가능하다.

---

## 8. 라인 연결

| 필드 | 규칙 |
| --- | --- |
| `journal_lines.transaction_item_id` | 수입/지출의 분류 항목 라인에만 설정. 결제수단 한 줄과 이체 두 줄은 NULL. |
| `journal_entries.transaction_id` | 거래에서 온 분개만 설정. 자본 조정은 NULL. |
| `journal_entries.reverses_entry_id` | 역분개만 원본을 가리킨다. |
| `line_no` | 1부터 항목 순서, 이어서 결제수단(지출) 또는 수익 항목(수입). |

증빙 파일은 `attachments`에만 두고 분개 라인에 복제하지 않는다.

---

## 9. 보고서

분개장·계정별원장·시산표는 CONFIRMED `journal_lines`만 사용한다. 화면에서 차변/대변을 다시 계산하지 않는다.

- 개인/사업 추출은 거래·항목의 `scope`로 하고, 분개 계정을 바꾸지 않는다.
- MIXED의 개인 몫은 보통 5700 개인사용으로 전기되므로, 사업 보고서에서 5100 등과 분리할 수 있다.

---

## 10. 처리 흐름

```text
사용자 저장
  → Transaction + TransactionItem 검증 (J6–J9)
  → JournalEntry 생성
  → 유형별 라인 생성 (§4, §5)
  → assert_journal_balanced (J1–J4)
  → 거래/분개 CONFIRMED
  → flush 시 모델 이벤트 재검증
  → DB CHECK
```

수정:

```text
작성 → 확정 → 수정 요청 → 역분개 → 새 분개 확정
```

---

## 11. 테스트로 고정한 시나리오

다음 시나리오는 회귀 테스트로 유지한다. 규칙을 바꾸면 테스트와 이 문서를 함께 수정한다.

| 시나리오 | 기대 |
| --- | --- |
| 카드 사무용품 50,000 사업 지출 | Dr 5100 50,000 / Cr 2100 50,000 |
| 은행 사업매출 1,000,000 | Dr 1200 1,000,000 / Cr 4100 1,000,000 |
| 보통예금 → 현금 500,000 이체 | Dr 1100 500,000 / Cr 1200 500,000 |
| MIXED 마트 100,000 (30,000+70,000) | Dr 5100 30,000 + Dr 5700 70,000 / Cr 2100 100,000 |
| MIXED 항목 합 불일치 | 거부 |
| 확정 후 재 `post_transaction` | 거부 |
| 50,000 → 55,000 수정 | 원본 역분개 + 새 분개 55,000 |
| 통장 시작 잔액 1,000,000 | Dr 지갑 / Cr 3100, `transaction_id` NULL |
| 잔액 맞추기 | 차액만 3100과 지갑에 균형 분개 |

차변=대변 불변식 자체는 `test_journal_balance.py`가 빈 분개, 한쪽만 있는 라인, 음수, 동시 차대변을 거부하는지 검증한다.
