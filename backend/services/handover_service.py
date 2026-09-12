import os
import time
import hmac
import hashlib
import struct
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import Order, User, OrderStatus
from .compensation_service import contribute_to_pool, calculate_compensation

HMAC_SECRET = os.getenv("HMAC_SECRET", "linli-tool-hmac-invitation-secret-key-2026")
TOTP_WINDOW_SECONDS = 60


def _generate_totp_for_counter(order_id: int, renter_id: int, counter: int) -> str:
    message = f"handover:{order_id}:{renter_id}:{counter}".encode("utf-8")
    digest = hmac.new(HMAC_SECRET.encode("utf-8"), message, hashlib.sha256).digest()
    # Dynamic truncation (RFC 4226 style)
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{code_int % 1000000:06d}"


def generate_handover_code(order: Order) -> Tuple[str, int]:
    """為借用人產生每 60 秒輪替之動態 6 碼取件核銷碼"""
    now = int(time.time())
    counter = now // TOTP_WINDOW_SECONDS
    expires_in = TOTP_WINDOW_SECONDS - (now % TOTP_WINDOW_SECONDS)
    code = _generate_totp_for_counter(order.id, order.renter_id, counter)
    return code, expires_in


def verify_handover_code(order: Order, input_code: str) -> bool:
    """出借人驗證取件碼 (支援當前與前一窗口容錯)"""
    now = int(time.time())
    current_counter = now // TOTP_WINDOW_SECONDS
    
    current_code = _generate_totp_for_counter(order.id, order.renter_id, current_counter)
    if hmac.compare_digest(input_code.strip(), current_code):
        return True

    # 允許前一窗口 (前 60 秒內剛好換碼之寬限期)
    prev_code = _generate_totp_for_counter(order.id, order.renter_id, current_counter - 1)
    if hmac.compare_digest(input_code.strip(), prev_code):
        return True

    return False


def get_handover_code_for_user(db: Session, user: User, order_id: int) -> Tuple[str, int, str]:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"找不到訂單 #{order_id}")

    if order.renter_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="僅借用人本人可取得取件核銷碼。",
        )

    if order.status != OrderStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"訂單狀態為 {order.status.value}，非 CONFIRMED 狀態無法產生取件碼。",
        )

    code, expires_in = generate_handover_code(order)
    qr_payload = f"linli://handover?order_id={order.id}&code={code}"
    return code, expires_in, qr_payload


def verify_and_confirm_pickup(db: Session, user: User, order_id: int, input_code: str) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"找不到訂單 #{order_id}")

    if order.lender_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="僅出借人本人有權限核銷取件碼。",
        )

    if order.status != OrderStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"訂單狀態為 {order.status.value}，無法執行取件核銷。",
        )

    if not verify_handover_code(order, input_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="取件核銷碼錯誤或已過期，請借用人重新整理手機畫面再試。",
        )

    order.status = OrderStatus.PICKED_UP
    order.handover_code = input_code
    db.commit()
    db.refresh(order)
    return order


def process_checkin(
    db: Session,
    user: User,
    order_id: int,
    image_url: Optional[str] = None,
    image_base64: Optional[str] = None,
    notes: Optional[str] = None,
) -> Tuple[Order, str, Dict[str, Any]]:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"找不到訂單 #{order_id}")

    if order.renter_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="僅借用人本人可上傳 Check-in 初始存證照片。",
        )

    if order.status != OrderStatus.PICKED_UP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"訂單狀態為 {order.status.value}，必須先完成現場取件核銷 (PICKED_UP) 方可 Check-in 存證。",
        )

    effective_image = image_url or image_base64 or f"https://storage.linli-tool.app/checkin/{order_id}.jpg"

    # 執行 Check-in 取件照片 vs 原始上架照片 同物件一致性比對 (防止調包或拿錯)
    from ..ai.gateway import AIGateway
    gateway = AIGateway.get_instance()

    img_bytes = None
    if image_base64:
        import base64
        try:
            b64_clean = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
            img_bytes = base64.b64decode(b64_clean)
        except Exception:
            pass

    verify_res = gateway.verify_same_object(
        user_id=user.id,
        original_image_bytes=None,
        checkin_image_bytes=img_bytes,
        item_name=order.item.name if order.item else "工具",
        hint_text=f"{notes or ''} {image_url or ''}",
    )

    if not verify_res.get("is_same_object", True) or verify_res.get("requires_retake", False):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"MISMATCH_TOOL: {verify_res.get('difference_notes') or '取件照片與原始上架工具外觀不符（非同物件），請重新拍照！'}",
        )

    checksum = hashlib.sha256(effective_image.encode("utf-8")).hexdigest()

    order.checkin_image_url = effective_image
    order.status = OrderStatus.IN_USE
    db.commit()
    db.refresh(order)
    return order, checksum, verify_res


def finalize_checkout_order(
    db: Session,
    order: Order,
    vision_result: str,
    checkout_image_url: str,
) -> dict:
    """處理歸還 Check-out 差分比對結果與狀態機推進"""
    order.checkout_image_url = checkout_image_url
    order.vision_result = vision_result

    if vision_result.upper() == "MATCH":
        order.status = OrderStatus.COMPLETED
        # 雙方信用分各 +2
        if order.renter:
            order.renter.credit_score = min(120, order.renter.credit_score + 2)
        if order.lender:
            order.lender.credit_score = min(120, order.lender.credit_score + 2)

        # 平台服務費 15% 提撥至賠償互助池
        fee_contribution = round(order.total_rent * 0.15)
        if fee_contribution > 0:
            contribute_to_pool(
                db,
                fee_contribution,
                order_id=order.id,
                reason="PLATFORM_FEE_CONTRIBUTION",
                notes=f"訂單 #{order.id} 結案提撥 15% 服務費入互助保障池",
            )
        db.commit()
        db.refresh(order)
        return {
            "status": "COMPLETED",
            "deposit_refunded": order.actual_deposit,
            "credit_score_earned": 2,
            "message": "工具外觀完好，結案成功！押金已全數退還，雙方信用分各 +2。",
        }
    else:
        # MINOR_DIFF 或 DAMAGE_DETECTED 進入 24hr INSPECTION 覆核緩衝期
        order.status = OrderStatus.INSPECTION
        comp_res = calculate_compensation(db, order.id, vision_result)
        order.compensation_amount = comp_res.liability
        order.pool_payout = comp_res.pool_payout
        db.commit()
        db.refresh(order)
        return {
            "status": "INSPECTION",
            "compensation": comp_res,
            "message": "檢測到工具狀態有異動，訂單已進入 24 小時確認覆核期 (INSPECTION)。",
        }
