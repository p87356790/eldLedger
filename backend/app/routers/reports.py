from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.reports import (
    AccountLedger,
    BusinessReportSummary,
    JournalBookEntry,
    TransactionLedgerRow,
    TrialBalanceResponse,
)
from app.services.ledger_service import LedgerService
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


def _ledger(db: Session = Depends(get_db)) -> LedgerService:
    return LedgerService(db)


def _reports(db: Session = Depends(get_db)) -> ReportService:
    return ReportService(db)


@router.get("/transaction-ledger", response_model=list[TransactionLedgerRow])
def transaction_ledger(
    organization_id: int = Query(..., ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: int | None = None,
    business_only: bool = False,
    ledger: LedgerService = Depends(_ledger),
) -> list[TransactionLedgerRow]:
    return ledger.transaction_ledger(
        organization_id=organization_id,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        business_only=business_only,
    )


@router.get("/journal-book", response_model=list[JournalBookEntry])
def journal_book(
    organization_id: int = Query(..., ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
    business_only: bool = False,
    ledger: LedgerService = Depends(_ledger),
) -> list[JournalBookEntry]:
    return ledger.journal_book(
        organization_id=organization_id,
        date_from=date_from,
        date_to=date_to,
        business_only=business_only,
    )


@router.get("/account-ledger", response_model=list[AccountLedger])
def account_ledger(
    organization_id: int = Query(..., ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: int | None = None,
    business_only: bool = False,
    ledger: LedgerService = Depends(_ledger),
) -> list[AccountLedger]:
    return ledger.account_ledgers(
        organization_id=organization_id,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        business_only=business_only,
    )


@router.get("/trial-balance", response_model=TrialBalanceResponse)
def trial_balance(
    organization_id: int = Query(..., ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
    business_only: bool = False,
    ledger: LedgerService = Depends(_ledger),
) -> TrialBalanceResponse:
    return ledger.trial_balance(
        organization_id=organization_id,
        date_from=date_from,
        date_to=date_to,
        business_only=business_only,
    )


@router.get("/business-summary", response_model=BusinessReportSummary)
def business_summary(
    organization_id: int = Query(..., ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
    reports: ReportService = Depends(_reports),
) -> BusinessReportSummary:
    return reports.build_business_summary(
        organization_id=organization_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/business-excel")
def business_excel(
    organization_id: int = Query(..., ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
    reports: ReportService = Depends(_reports),
) -> FileResponse:
    path = reports.generate_business_excel(
        organization_id=organization_id,
        date_from=date_from,
        date_to=date_to,
    )
    filename = quote(path.name)
    return FileResponse(
        path=path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
