from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from ..models import Community, User, CommunityInvitation, VerificationStatus
from ..schemas import (
    CommunityCreate,
    CommunityResponse,
    InvitationCreateResponse,
    JoinCommunityRequest,
    JoinCommunityResponse,
)
from ..services.auth_service import AuthService
from .auth import get_current_user, get_validated_user

router = APIRouter(prefix="/api/v1/communities", tags=["社區與社交擔保"])


@router.post("", response_model=CommunityResponse, status_code=status.HTTP_201_CREATED, summary="冷啟動建立新社區")
def create_community(
    data: CommunityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Check if a community with exact name or address already exists
    existing = db.query(Community).filter(
        (Community.name == data.name.strip()) | (Community.address == data.address.strip())
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"該社區或地址已存在 (社區名稱：{existing.name})，請向已加入的鄰居索取邀請碼加入。",
        )

    community = Community(name=data.name.strip(), address=data.address.strip())
    db.add(community)
    db.flush()

    # Creator automatically becomes a VALIDATED founding member
    current_user.community_id = community.id
    current_user.verification_status = VerificationStatus.VALIDATED
    db.commit()
    db.refresh(community)

    response = CommunityResponse.model_validate(community)
    response.member_count = 1
    return response


@router.get("/{id}", response_model=CommunityResponse, summary="取得社區詳細資訊")
def get_community(id: int, db: Session = Depends(get_db)):
    community = db.query(Community).filter(Community.id == id).first()
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="社區不存在")

    member_count = db.query(User).filter(User.community_id == id).count()
    response = CommunityResponse.model_validate(community)
    response.member_count = member_count
    return response


@router.post("/{id}/invitations", response_model=InvitationCreateResponse, summary="已驗證居民發起社交擔保邀請碼")
def create_invitation(
    id: int,
    current_user: User = Depends(get_validated_user),
    db: Session = Depends(get_db),
):
    if current_user.community_id != id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是此社區的成員，無法發送該社區邀請碼",
        )

    community = db.query(Community).filter(Community.id == id).first()
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="社區不存在")

    token, expires_at = AuthService.generate_invitation_token(current_user.id, id)

    invitation = CommunityInvitation(
        token=token,
        inviter_user_id=current_user.id,
        community_id=id,
        expires_at=expires_at,
        is_used=False,
    )
    db.add(invitation)
    db.commit()

    return InvitationCreateResponse(
        invitation_token=token,
        share_url=f"https://linli-tool.app/join?token={token}",
        expires_at=expires_at,
    )


@router.post("/join", response_model=JoinCommunityResponse, summary="透過邀請碼加入社區")
def join_community(
    data: JoinCommunityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify HMAC token
    payload = AuthService.verify_invitation_token(data.token)
    community_id = payload.get("community_id")
    inviter_id = payload.get("inviter_id")

    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邀請之目標社區不存在")

    inviter = db.query(User).filter(User.id == inviter_id).first()
    if not inviter or inviter.verification_status != VerificationStatus.VALIDATED:
        # If inviter is no longer validated, fallback to PENDING
        current_user.community_id = community_id
        current_user.verification_status = VerificationStatus.PENDING
        db.commit()
        return JoinCommunityResponse(
            success=False,
            community_id=community_id,
            community_name=community.name,
            status=VerificationStatus.PENDING.value,
            message="邀請人身分尚未通過驗證，您的加入申請已轉入待審核 (PENDING) 狀態。",
        )

    # Validated by social endorsement
    current_user.community_id = community_id
    current_user.verification_status = VerificationStatus.VALIDATED

    # Mark invitation as used
    db_invitation = (
        db.query(CommunityInvitation)
        .filter(CommunityInvitation.token == data.token)
        .first()
    )
    if db_invitation:
        db_invitation.is_used = True

    db.commit()

    return JoinCommunityResponse(
        success=True,
        community_id=community_id,
        community_name=community.name,
        status=VerificationStatus.VALIDATED.value,
        message=f"恭喜！您已透過住戶 {inviter.name} 的社交擔保，成功加入「{community.name}」！",
    )
