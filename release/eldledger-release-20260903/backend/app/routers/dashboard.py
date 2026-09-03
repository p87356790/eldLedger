from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.dashboard import DashboardScopeFilter, DashboardSummaryResponse
from app.security.deps import get_current_user
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


@router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: int | None = Query(default=None, ge=1),
    scope: DashboardScopeFilter = DashboardScopeFilter.ALL,
    user: User = Depends(get_current_user),
    service: DashboardService = Depends(_service),
) -> DashboardSummaryResponse:
    try:
        return service.summary(
            organization_id=user.organization_id,
            owner_user_id=user.id,
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            scope=scope,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
