from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import UserResponse, UserProfileUpdate
from .auth import get_current_user

router = APIRouter(prefix="/api/v1/users", tags=["用戶與個人資料"])


@router.get("/me", response_model=UserResponse, summary="取得當前登入者個人檔案")
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse, summary="更新個人稱呼與基本資料")
def update_profile(
    update_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if update_data.name is not None and update_data.name.strip():
        current_user.name = update_data.name.strip()
        db.commit()
        db.refresh(current_user)
    return UserResponse.model_validate(current_user)
