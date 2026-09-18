from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, VerificationStatus
from ..schemas import OTPSendRequest, OTPSendResponse, OTPVerifyRequest, TokenResponse, UserResponse
from ..services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["認證與會員"])
security = HTTPBearer(auto_error=False)


@router.post("/otp/send", response_model=OTPSendResponse, summary="發送手機 OTP 驗證碼")
def send_otp(request: OTPSendRequest):
    code, ttl = AuthService.send_otp(request.phone)
    return OTPSendResponse(
        success=True,
        message="驗證碼已發送至您的手機 (測試環境同時回傳 mock_otp)",
        expires_in=ttl,
        mock_otp=code,
    )


@router.post("/otp/verify", response_model=TokenResponse, summary="驗證 OTP 並登入／自動註冊")
def verify_otp(request: OTPVerifyRequest, db: Session = Depends(get_db)):
    AuthService.verify_otp(request.phone, request.otp)

    # Find or create user
    user = db.query(User).filter(User.phone == request.phone).first()
    if not user:
        user = User(
            phone=request.phone,
            name=f"住戶_{request.phone[-4:]}",
            verification_status=VerificationStatus.PENDING,
            community_id=1,
            credit_score=80,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # 確保已登入住戶具備社區綁定，支援正常使用
        if not user.community_id:
            user.community_id = 1
            db.commit()
            db.refresh(user)

    token = AuthService.create_access_token(user.id, user.community_id)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/demo-token", response_model=TokenResponse, summary="取得示範住戶快速登入 Token (開發與展示用途)")
def get_demo_token(role: str = "renter", db: Session = Depends(get_db)):
    """
    為展示與測試用途直接發行示範住戶 JWT Bearer Token。
    - role='renter': 借用人小琳 (User 102, 信用分 90, VALIDATED)
    - role='lender': 出借人老陳 (User 101, 信用分 96, VALIDATED)
    - role='pending': 待審住戶阿強 (User 103, 信用分 80, PENDING)
    """
    if role == "lender":
        user_id = 101
        phone = "0911000101"
        name = "出借人老陳"
        status = VerificationStatus.VALIDATED
        credit = 96
    elif role == "pending":
        user_id = 103
        phone = "0933000103"
        name = "待審住戶阿強"
        status = VerificationStatus.PENDING
        credit = 80
    else:
        user_id = 102
        phone = "0922000102"
        name = "借用人小琳"
        status = VerificationStatus.VALIDATED
        credit = 90

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(
            id=user_id,
            phone=phone,
            name=name,
            verification_status=status,
            community_id=1,
            credit_score=credit,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # 確保示範帳號狀態與身分與請求角色完全吻合
        changed = False
        if user.verification_status != status:
            user.verification_status = status
            changed = True
        if not user.community_id:
            user.community_id = 1
            changed = True
        if changed:
            db.commit()
            db.refresh(user)

    token = AuthService.create_access_token(user.id, user.community_id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: Extract current authenticated user from JWT Bearer token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="請先登入以取得認證",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = AuthService.decode_access_token(token)
    user_id = payload.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用戶不存在或已被刪除",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_validated_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency: Require that user is a VALIDATED member of a community."""
    if current_user.verification_status != VerificationStatus.VALIDATED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您尚未通過社區住戶驗證，無法執行此操作",
        )
    if not current_user.community_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="您尚未加入任何社區",
        )
    return current_user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    """Optional user dependency: allows public / guest browsing while capturing token if present."""
    if not credentials:
        return None
    try:
        token = credentials.credentials
        payload = AuthService.decode_access_token(token)
        user_id = payload.get("user_id")
        if not user_id:
            return None
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None

