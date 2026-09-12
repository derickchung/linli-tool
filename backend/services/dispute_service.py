import json
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import DisputeTicket, Order, User, DisputeStatus, OrderStatus
from ..schemas import DisputeCreateRequest, DisputeResponse


def to_dispute_response(ticket: DisputeTicket) -> DisputeResponse:
    evidence_list: List[str] = []
    if ticket.evidence_photos:
        try:
            data = json.loads(ticket.evidence_photos)
            if isinstance(data, list):
                evidence_list = [str(x) for x in data]
        except Exception:
            evidence_list = []

    return DisputeResponse(
        id=ticket.id,
        order_id=ticket.order_id,
        complainant_id=ticket.complainant_id,
        complainant_name=ticket.complainant.name if ticket.complainant else None,
        reason=ticket.reason,
        status=ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
        evidence_photos=evidence_list,
        resolution_notes=ticket.resolution_notes,
        created_at=ticket.created_at,
        resolved_at=ticket.resolved_at,
    )


def create_dispute(
    db: Session,
    user: User,
    req: DisputeCreateRequest,
) -> DisputeTicket:
    order = db.query(Order).filter(Order.id == req.order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到訂單 ID: {req.order_id}",
        )

    if user.id not in [order.renter_id, order.lender_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="僅此訂單之借用人或出借人可發起爭議申訴。",
        )

    # 檢查是否已有爭議工單
    existing = db.query(DisputeTicket).filter(DisputeTicket.order_id == req.order_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="此訂單已存在爭議工單，無法重複提交申訴。",
        )

    evidence_json = json.dumps(req.evidence_photos or [], ensure_ascii=False)

    ticket = DisputeTicket(
        order_id=order.id,
        complainant_id=user.id,
        reason=req.reason,
        status=DisputeStatus.OPEN,
        evidence_photos=evidence_json,
    )
    # 凍結訂單款項，狀態變更為 DISPUTED
    order.status = OrderStatus.DISPUTED

    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def get_dispute(
    db: Session,
    user: User,
    dispute_id: int,
) -> DisputeTicket:
    ticket = db.query(DisputeTicket).filter(DisputeTicket.id == dispute_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到爭議工單 ID: {dispute_id}",
        )

    order = ticket.order
    if user.id not in [ticket.complainant_id, order.renter_id, order.lender_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您無權限查看此爭議工單。",
        )

    return ticket


def resolve_dispute(
    db: Session,
    dispute_id: int,
    resolution_status: str,
    notes: str,
) -> DisputeTicket:
    ticket = db.query(DisputeTicket).filter(DisputeTicket.id == dispute_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到爭議工單 ID: {dispute_id}",
        )

    try:
        ticket.status = DisputeStatus(resolution_status.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"無效的爭議處理狀態: {resolution_status}",
        )

    ticket.resolution_notes = notes
    ticket.resolved_at = datetime.now(timezone.utc)

    # 爭議處理結案時，將訂單狀態解除凍結轉為 COMPLETED
    if ticket.status == DisputeStatus.RESOLVED:
        ticket.order.status = OrderStatus.COMPLETED

    db.commit()
    db.refresh(ticket)
    return ticket
