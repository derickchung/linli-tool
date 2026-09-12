from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import DisputeCreateRequest, DisputeResponse, DisputeResolveRequest
from .auth import get_current_user, get_validated_user
from ..services import dispute_service

router = APIRouter(prefix="/api/v1/disputes", tags=["Disputes (爭議申訴工單)"])


@router.post(
    "/",
    response_model=DisputeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="發起損壞比對爭議申訴",
)
def create_dispute(
    req: DisputeCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_validated_user),
):
    """
    租借雙方若對 AI 差分判定結果不服，可發起爭議申訴工單。
    - 訂單自動轉為 DISPUTED，款項撥付自動鎖定凍結。
    """
    ticket = dispute_service.create_dispute(db, current_user, req)
    return dispute_service.to_dispute_response(ticket)


@router.get(
    "/{dispute_id}",
    response_model=DisputeResponse,
    summary="查詢爭議工單進度與結果",
)
def get_dispute(
    dispute_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = dispute_service.get_dispute(db, current_user, dispute_id)
    return dispute_service.to_dispute_response(ticket)


@router.patch(
    "/{dispute_id}/resolve",
    response_model=DisputeResponse,
    summary="審理結案爭議工單 (管理覆核)",
)
def resolve_dispute(
    dispute_id: int,
    req: DisputeResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_validated_user),
):
    """
    管委會或平台人工客服覆核審理爭議，標記為 RESOLVED 或 REJECTED。
    """
    ticket = dispute_service.resolve_dispute(
        db,
        dispute_id=dispute_id,
        resolution_status=req.status,
        notes=req.resolution_notes,
    )
    return dispute_service.to_dispute_response(ticket)
